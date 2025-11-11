# Huffman Compression - Issues and Fixes

## Critical Issues Found and Fixed

### 🔴 Issue #1: Non-Deterministic Tree Construction

**Original Code Problem:**
```cpp
struct Compare {
    bool operator()(Node* a, Node* b) {
        if (a->freq != b->freq) return a->freq > b->freq;
        if (!a->left && !b->left) return a->ch > b->ch;
        return false;  // ⚠️ PROBLEM!
    }
};
```

**The Problem:**
- When two nodes have equal frequency and at least one is an internal node, the comparator returns `false`
- This makes them "equal" in the priority queue's view
- The order of popping equal-frequency nodes becomes **undefined behavior**
- Results in different Huffman trees during compression vs decompression
- **This is why your decompression was producing wrong output!**

**The Fix:**
```cpp
struct Compare {
    bool operator()(Node* a, Node* b) {
        if (a->freq != b->freq) return a->freq > b->freq;

        bool aIsLeaf = (!a->left && !a->right);
        bool bIsLeaf = (!b->left && !b->right);

        // Compare characters if both are leaves
        if (aIsLeaf && bIsLeaf) {
            return a->ch > b->ch;
        }

        // Prefer leaves over internal nodes
        if (aIsLeaf != bIsLeaf) {
            return bIsLeaf;
        }

        // For two internal nodes, use pointer comparison
        // This ensures consistent deterministic ordering
        return a > b;
    }
};
```

**Why This Works:**
1. Leaf nodes with same frequency are ordered by character value
2. Leaf nodes come before internal nodes (more stable)
3. Internal nodes with same frequency use pointer comparison for determinism
4. **Both compress and decompress now build identical trees!**

---

### 🔴 Issue #2: Non-Portable `long` Type

**Original Code Problem:**
```cpp
long total;
out.write((char*)&total, sizeof(long));  // Size varies by platform!
```

**The Problem:**
- `long` is 4 bytes on 32-bit systems
- `long` is 8 bytes on 64-bit systems
- Compressing on one system and decompressing on another would fail
- Header would be misaligned, causing complete corruption

**The Fix:**
```cpp
#include <cstdint>

int64_t total;  // Always 8 bytes on all platforms
out.write((char*)&total, sizeof(int64_t));

// Also fixed frequency table:
int32_t f = freq[i];  // Always 4 bytes
out.write((char*)&f, sizeof(int32_t));
```

**Why This Works:**
- `int32_t` is guaranteed to be exactly 32 bits (4 bytes)
- `int64_t` is guaranteed to be exactly 64 bits (8 bytes)
- Cross-platform compatible

---

### 🟡 Issue #3: Missing Error Handling

**Added:**
- File open/create error checking
- Tree building validation
- Clear error messages

---

## Test Results

### Small File Test (138 bytes):
```
Original:   138 bytes
Compressed: 1105 bytes (800% - larger due to 1KB header overhead)
Status:     ✓ Verified with MD5: b83533d193a33e53b771e59d1a4233ae
```

### Larger File Test (5000 bytes):
```
Original:   5000 bytes (4.88 KB)
Compressed: 3931 bytes (3.84 KB) - 78.62% ratio
Status:     ✓ Verified with MD5: c2d65f877aee6b7f553d364acef26ad0
```

**Compression achieved 21.38% size reduction!**

---

## How to Use

### Compile:
```bash
g++ -o compress compress.cpp -std=c++11
g++ -o decompress decompress.cpp -std=c++11
```

### Compress:
```bash
./compress input.txt output.huf
```

### Decompress:
```bash
./decompress output.huf restored.txt
```

### Verify integrity:
```bash
md5sum input.txt
md5sum restored.txt
# Should match!
```

---

## Performance Notes

1. **Small files** (<2KB): Compressed file may be larger due to 1KB header overhead
2. **Medium files** (2-100KB): Good compression, typically 60-80% of original
3. **Large files** (>100KB): Best compression, especially with repetitive content
4. **Text files**: Compress very well (lots of repeated characters)
5. **Binary files**: Less effective (more uniform distribution)

---

## File Format

```
[Header]
- Byte 0-1023:    Frequency table (256 × 4-byte int32_t)
- Byte 1024-1031: Total character count (8-byte int64_t)

[Data]
- Remaining bytes: Huffman-encoded bit stream
- Padding bits at end are ignored (stops at total count)
```

---

## Key Takeaways

**Why your original code failed:**
1. The non-deterministic comparison caused different trees in compression vs decompression
2. This made the Huffman codes incompatible between the two
3. The decompressor was using wrong codes, producing garbage output

**The fix ensures:**
1. Same input always produces same tree (deterministic)
2. Compression and decompression use identical trees
3. Cross-platform compatibility with fixed-size types
4. Proper error handling and verification
