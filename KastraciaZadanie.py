import numpy as np
import matplotlib.pyplot as plt
import random
from collections import Counter
from scipy.spatial import KDTree
import time
import os

# ============================================
# INICIALIZAČNÉ BODY
# ============================================

initial_points = {
    'R': [[-4500, -4400], [-4100, -3000], [-1800, -2400], [-2500, -3400], [-2000, -1400]],
    'G': [[4500, -4400], [4100, -3000], [1800, -2400], [2500, -3400], [2000, -1400]],
    'B': [[-4500, 4400], [-4100, 3000], [-1800, 2400], [-2500, 3400], [-2000, 1400]],
    'P': [[4500, 4400], [4100, 3000], [1800, 2400], [2500, 3400], [2000, 1400]],
}


# ============================================
# K-NN KLASIFIKÁTOR s KD-Tree
# ============================================

def classify(X, Y, k, tree, points, labels):
    dist, idx = tree.query([X, Y], k)
    nearest_labels = labels[idx] if k > 1 else [labels[idx]]
    label_counts = Counter(nearest_labels)
    return label_counts.most_common(1)[0][0]




def generate_point_in_region(expected_label):
    if expected_label == 'R':
        return random.randint(-5000, 499), random.randint(-5000, 499)
    elif expected_label == 'G':
        return random.randint(-499, 5000), random.randint(-5000, 499)
    elif expected_label == 'B':
        return random.randint(-5000, 499), random.randint(-499, 5000)
    elif expected_label == 'P':
        return random.randint(-499, 5000), random.randint(-499, 5000)


def generate_point_out_of_region(expected_label):
    return random.randint(-5000, 5000), random.randint(-5000, 5000)


def generate_fixed_points_exact_1_percent(seed=None):
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    sequence = ['R', 'G', 'B', 'P']
    all_points, all_true_labels = [], []
    out_of_region_count = 0

    print("Generujem fixnú množinu 40,000 bodov (INT súradnice)...")
    print("Každý bod má 99% šancu byť vo svojom regióne a 1% šancu byť kdekoľvek")
    print("Body sa striedajú: R → G → B → P → R → G → ...")
    print("-" * 70)

    class_counts = {label: 0 for label in sequence}
    class_out_of_region = {label: 0 for label in sequence}

    # Generujeme 10000 iterácií, v každej vygenerujeme 1 bod z každej triedy
    # Tým zabezpečíme, že body sa striedajú: R, G, B, P, R, G, B, P, ...
    for i in range(10000):
        for class_label in sequence:
            # Každý bod má 1% šancu byť mimo svojho regiónu
            if random.random() < 0.01:  # 1% šanca
                X, Y = generate_point_out_of_region(class_label)
                out_of_region_count += 1
                class_out_of_region[class_label] += 1
            else:  # 99% šanca
                X, Y = generate_point_in_region(class_label)

            all_points.append([X, Y])
            all_true_labels.append(class_label)
            class_counts[class_label] += 1

    print()
    for class_label in sequence:
        in_region = class_counts[class_label] - class_out_of_region[class_label]
        out_region = class_out_of_region[class_label]
        print(f"  Trieda {class_label}: {class_counts[class_label]} bodov ({in_region} v regióne + {out_region} mimo)")

    print(f"\n{'=' * 70}")
    print(f"✓ Celkovo: {len(all_points):,} bodov (~{out_of_region_count} mimo regiónu = {out_of_region_count/400:.1f}%)\n")

    return np.array(all_points, dtype=np.int32), np.array(all_true_labels), out_of_region_count


# ============================================
# EXPERIMENT
# ============================================

def run_experiment_with_fixed_points(k, fixed_points, fixed_true_labels, verbose=True):
    points = np.array(
        [coord for label, coords in initial_points.items() for coord in coords],
        dtype=np.int32
    )
    labels = np.array(
        [label for label, coords in initial_points.items() for _ in coords]
    )
    tree = KDTree(points.astype(float))

    correct = 0
    total = 0
    class_stats = {c: {'correct': 0, 'total': 0} for c in ['R', 'G', 'B', 'P']}
    new_points, new_labels = [], []
    all_generated_points, all_predicted_labels = [], []

    if verbose:
        print(f"\nSpúšťam experiment pre k={k}...")
        print("-" * 70)

    start = time.time()

    for i in range(40000):
        X, Y = fixed_points[i]
        true_label = fixed_true_labels[i]
        class_stats[true_label]['total'] += 1

        pred = classify(X, Y, k, tree, points, labels)

        if pred == true_label:
            correct += 1
            class_stats[true_label]['correct'] += 1
        total += 1

        all_generated_points.append([X, Y])
        all_predicted_labels.append(pred)
        new_points.append([X, Y])
        new_labels.append(pred)

        if (i + 1) % 100 == 0:
            points = np.vstack((points, np.array(new_points, dtype=np.int32)))
            labels = np.concatenate((labels, np.array(new_labels)))
            tree = KDTree(points.astype(float))
            new_points, new_labels = [], []

    acc = correct / total
    elapsed = time.time() - start

    if verbose:
        print(f"✓ k={k} dokončené za {elapsed:.1f}s — presnosť {acc*100:.2f}%")

    return acc, points, labels, np.array(all_generated_points, dtype=np.int32), np.array(all_predicted_labels), class_stats, correct


# ============================================
# VIZUALIZÁCIA
# ============================================

def visualize_with_points(points, labels, generated_points, generated_labels, k, accuracy,
                          correct_count, class_stats, save_path=None, resolution=300):
    print(f"  Vytváram vizualizáciu pre k={k}...")

    tree = KDTree(points.astype(float))
    size = resolution
    x_vals = np.linspace(-5000, 5000, size)
    y_vals = np.linspace(-5000, 5000, size)
    color_map = {'R': [1, 0.15, 0.15], 'G': [0.15, 0.85, 0.15],
                 'B': [0.15, 0.35, 1], 'P': [0.85, 0.15, 0.85]}

    image = np.zeros((size, size, 3))
    for i, x in enumerate(x_vals):
        for j, y in enumerate(y_vals):
            label = classify(int(x), int(y), k, tree, points, labels)
            image[size - 1 - j, i] = color_map[label]

    fig, ax = plt.subplots(figsize=(13, 11))
    ax.imshow(image, extent=(-5000, 5000, -5000, 5000), alpha=0.7)

    sample = min(3000, len(generated_points))
    idx = np.random.choice(len(generated_points), sample, replace=False)
    sample_points = generated_points[idx]
    sample_labels = generated_labels[idx]

    colors = {'R': 'darkred', 'G': 'darkgreen', 'B': 'darkblue', 'P': 'purple'}
    for c in colors:
        mask = sample_labels == c
        ax.scatter(sample_points[mask, 0], sample_points[mask, 1],
                   c=colors[c], s=5, alpha=0.5, label=c)

    ax.axhline(0, color='white', lw=2)
    ax.axvline(0, color='white', lw=2)
    ax.set_xlim(-5000, 5000)
    ax.set_ylim(-5000, 5000)
    ax.set_title(f"k={k} | Accuracy: {accuracy*100:.2f}% | Correct: {correct_count}/40000", fontsize=15)
    ax.legend()
    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"  ✓ Vizualizácia uložená: {save_path}")
    plt.show()


# ============================================
# POROVNÁVACÍ GRAF
# ============================================

def create_comparison_plot(results, detailed_results, save_path=None):
    print("\nVytváram porovnávací graf...")

    k_values = sorted(results.keys())
    accs = [results[k] * 100 for k in k_values]
    correct_counts = [detailed_results[k]['correct_count'] for k in k_values]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(k_values, accs, color=['#FF4444', '#44FF44', '#4444FF', '#FF44FF'],
                  edgecolor='black', alpha=0.8)
    for i, k in enumerate(k_values):
        ax.text(k, accs[i] + 0.5, f"{accs[i]:.2f}%\n({correct_counts[i]}/40k)",
                ha='center', fontsize=10)
    ax.set_title("Presnosť k-NN pre rôzne k", fontsize=14)
    ax.set_xlabel("k")
    ax.set_ylabel("Accuracy (%)")
    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"✓ Porovnávací graf uložený: {save_path}")
    plt.show()


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    env_seed = os.environ.get("FIXED_SEED")
    if env_seed is not None:
        seed = int(env_seed)
        print(f"✓ Použitý seed (FIXED_SEED) = {seed}")
    else:
        seed = int.from_bytes(os.urandom(8), "big") % (2**32)
        print(f"✓ Vygenerovaný seed: {seed} (pre reprodukovanie nastav FIXED_SEED na túto hodnotu)")

    fixed_points, fixed_true_labels, _ = generate_fixed_points_exact_1_percent(seed=seed)

    results = {}
    detailed_results = {}
    k_values = [1, 3, 7, 15]

    for k in k_values:
        acc, points, labels, gen_pts, gen_lbls, class_stats, correct = run_experiment_with_fixed_points(
            k, fixed_points, fixed_true_labels)
        results[k] = acc
        detailed_results[k] = {
            "class_stats": class_stats,
            "correct_count": correct
        }
        visualize_with_points(points, labels, gen_pts, gen_lbls, k, acc, correct, class_stats,
                              save_path=f"visualization_k{k}.png")

    create_comparison_plot(results, detailed_results, save_path="comparison_plot.png")
