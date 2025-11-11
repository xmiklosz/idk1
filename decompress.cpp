#include <iostream>
#include <fstream>
#include <queue>
#include <vector>
#include <cstdint>
using namespace std;

struct Node {
    unsigned char ch;
    int freq;
    Node *left, *right;

    Node(unsigned char c, int f) : ch(c), freq(f), left(nullptr), right(nullptr) {}
};

// FIXED: Same deterministic comparison as compress.cpp
struct Compare {
    bool operator()(Node* a, Node* b) {
        if (a->freq != b->freq) return a->freq > b->freq;

        // Tie-breaker: Compare by character if both are leaves
        bool aIsLeaf = (!a->left && !a->right);
        bool bIsLeaf = (!b->left && !b->right);

        if (aIsLeaf && bIsLeaf) {
            return a->ch > b->ch;
        }

        // FIXED: If only one is a leaf, prefer the leaf (smaller)
        if (aIsLeaf != bIsLeaf) {
            return bIsLeaf; // b is leaf, so a should come after
        }

        // FIXED: For two internal nodes, use pointer comparison for determinism
        return a > b;
    }
};

Node* buildTree(int freq[256]) {
    priority_queue<Node*, vector<Node*>, Compare> pq;

    for (int i = 0; i < 256; i++) {
        if (freq[i] > 0) {
            pq.push(new Node((unsigned char)i, freq[i]));
        }
    }

    // Handle edge case: empty file
    if (pq.empty()) {
        return nullptr;
    }

    // Handle edge case: single unique character
    if (pq.size() == 1) {
        return pq.top();
    }

    while (pq.size() > 1) {
        Node* left = pq.top(); pq.pop();
        Node* right = pq.top(); pq.pop();

        Node* parent = new Node(0, left->freq + right->freq);
        parent->left = left;
        parent->right = right;
        pq.push(parent);
    }

    return pq.top();
}

void decompress(const string& infile, const string& outfile) {
    cout << "Decompressing " << infile << "..." << endl;

    ifstream in(infile, ios::binary);
    if (!in) {
        cout << "Error: Cannot open file!" << endl;
        return;
    }

    // Read frequency table
    int freq[256];
    for (int i = 0; i < 256; i++) {
        int32_t f;  // FIXED: Use fixed-size type
        in.read((char*)&f, sizeof(int32_t));
        freq[i] = f;
    }

    // FIXED: Read total as fixed-size int64_t
    int64_t total;
    in.read((char*)&total, sizeof(int64_t));

    cout << "Total characters to decode: " << total << endl;

    if (total == 0) {
        cout << "Error: File has no data!" << endl;
        in.close();
        return;
    }

    // Build Huffman tree
    Node* root = buildTree(freq);
    if (!root) {
        cout << "Error: Failed to build tree!" << endl;
        in.close();
        return;
    }

    // Decompress data
    ofstream out(outfile, ios::binary);
    if (!out) {
        cerr << "Error: Cannot create output file!" << endl;
        in.close();
        return;
    }

    Node* current = root;
    int64_t decoded = 0;
    unsigned char byte;

    while (in.read((char*)&byte, 1) && decoded < total) {
        // Process each bit in the byte (MSB first)
        for (int i = 7; i >= 0 && decoded < total; i--) {
            bool bit = (byte >> i) & 1;

            // Handle single character case
            if (!root->left && !root->right) {
                out.write((char*)&root->ch, 1);
                decoded++;
                continue;
            }

            if (bit) {
                current = current->right;
            } else {
                current = current->left;
            }

            // Reached a leaf node
            if (!current->left && !current->right) {
                out.write((char*)&current->ch, 1);
                decoded++;
                current = root; // Reset to root
            }
        }
    }

    in.close();
    out.close();

    cout << "Decoded " << decoded << " characters" << endl;

    // Display statistics
    ifstream inStat(infile, ios::binary | ios::ate);
    ifstream outStat(outfile, ios::binary | ios::ate);

    long compressedSize = inStat.tellg();
    long decompressedSize = outStat.tellg();

    inStat.close();
    outStat.close();

    cout << endl;
    cout << "=== Decompression Statistics ===" << endl;
    cout << "Compressed file:   " << infile << " - " << compressedSize << " bytes (" << (compressedSize / 1024.0) << " KB)" << endl;
    cout << "Decompressed file: " << outfile << " - " << decompressedSize << " bytes (" << (decompressedSize / 1024.0) << " KB)" << endl;

    if (decoded == total) {
        cout << endl;
        cout << "✓ Decompression complete and verified!" << endl;
    } else {
        cout << endl;
        cout << "⚠ Warning: Decoded " << decoded << " chars but expected " << total << endl;
    }

    cout << "Verify integrity with: md5sum " << outfile << endl;
}

int main(int argc, char* argv[]) {
    if (argc == 3) {
        decompress(argv[1], argv[2]);
    } else {
        string in, out;
        cout << "Compressed file: ";
        cin >> in;
        cout << "Output file: ";
        cin >> out;
        decompress(in, out);
        cout << "\nPress Enter...";
        cin.ignore();
        cin.get();
    }
    return 0;
}
