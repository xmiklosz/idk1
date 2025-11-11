#include <iostream>
#include <fstream>
#include <queue>
#include <unordered_map>
#include <vector>
#include <string>
#include <cstdint>
using namespace std;

struct Node {
    unsigned char ch;
    int freq;
    Node *left, *right;

    Node(unsigned char c, int f) : ch(c), freq(f), left(nullptr), right(nullptr) {}
};

// FIXED: Deterministic comparison for priority queue
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
        // This ensures consistent ordering when frequencies are equal
        return a > b;
    }
};

void buildFreqTable(const string& filename, int freq[256]) {
    for (int i = 0; i < 256; i++) freq[i] = 0;

    ifstream file(filename, ios::binary);
    if (!file) {
        cerr << "Error: Cannot open input file!" << endl;
        return;
    }

    char c;
    while (file.get(c)) {
        freq[(unsigned char)c]++;
    }
    file.close();
}

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

void generateCodes(Node* root, string code, string codes[256]) {
    if (!root) return;

    // Leaf node
    if (!root->left && !root->right) {
        codes[root->ch] = code.empty() ? "0" : code;
        return;
    }

    generateCodes(root->left, code + "0", codes);
    generateCodes(root->right, code + "1", codes);
}

void compress(const string& infile, const string& outfile) {
    cout << "Compressing " << infile << "..." << endl;

    // Step 1: Build frequency table
    int freq[256];
    buildFreqTable(infile, freq);

    int64_t total = 0;  // FIXED: Use fixed-size type
    for (int i = 0; i < 256; i++) total += freq[i];

    if (total == 0) {
        cout << "Error: Empty file!" << endl;
        return;
    }

    // Step 2: Build Huffman tree and generate codes
    Node* root = buildTree(freq);
    if (!root) {
        cout << "Error: Failed to build tree!" << endl;
        return;
    }

    string codes[256];
    for (int i = 0; i < 256; i++) codes[i] = "";
    generateCodes(root, "", codes);

    // Step 3: Write compressed file
    ofstream out(outfile, ios::binary);
    if (!out) {
        cerr << "Error: Cannot create output file!" << endl;
        return;
    }

    // Write frequency table (1024 bytes)
    for (int i = 0; i < 256; i++) {
        int32_t f = freq[i];  // FIXED: Use fixed-size type
        out.write((char*)&f, sizeof(int32_t));
    }

    // FIXED: Write total as fixed-size int64_t
    out.write((char*)&total, sizeof(int64_t));

    // Encode and write data
    ifstream in(infile, ios::binary);
    if (!in) {
        cerr << "Error: Cannot reopen input file!" << endl;
        return;
    }

    string bits = "";
    char c;

    while (in.get(c)) {
        bits += codes[(unsigned char)c];

        // Write complete bytes
        while (bits.length() >= 8) {
            unsigned char byte = 0;
            for (int i = 0; i < 8; i++) {
                byte = (byte << 1) | (bits[i] == '1' ? 1 : 0);
            }
            out.write((char*)&byte, 1);
            bits = bits.substr(8);
        }
    }
    in.close();

    // Write remaining bits with padding
    if (bits.length() > 0) {
        while (bits.length() < 8) bits += "0";
        unsigned char byte = 0;
        for (int i = 0; i < 8; i++) {
            byte = (byte << 1) | (bits[i] == '1' ? 1 : 0);
        }
        out.write((char*)&byte, 1);
    }

    out.close();

    // Display statistics
    ifstream inStat(infile, ios::binary | ios::ate);
    ifstream outStat(outfile, ios::binary | ios::ate);

    long originalSize = inStat.tellg();
    long compressedSize = outStat.tellg();

    inStat.close();
    outStat.close();

    cout << endl;
    cout << "=== Compression Statistics ===" << endl;
    cout << "Original file:    " << infile << " - " << originalSize << " bytes (" << (originalSize / 1024.0) << " KB)" << endl;
    cout << "Compressed file:  " << outfile << " - " << compressedSize << " bytes (" << (compressedSize / 1024.0) << " KB)" << endl;

    if (originalSize > 0) {
        double ratio = 100.0 * compressedSize / originalSize;
        cout << "Compression ratio: " << ratio << "%" << endl;

        if (compressedSize > originalSize) {
            cout << endl;
            cout << "Note: Compressed file is larger than original." << endl;
            cout << "This is normal for small files due to the header overhead (~1KB)." << endl;
            cout << "Huffman compression works best on files larger than 2-3 KB." << endl;
        }
    }

    cout << endl;
    cout << "Compression complete!" << endl;
}

int main(int argc, char* argv[]) {
    if (argc == 3) {
        compress(argv[1], argv[2]);
    } else {
        string in, out;
        cout << "Input file: ";
        cin >> in;
        cout << "Output file: ";
        cin >> out;
        compress(in, out);
        cout << "\nPress Enter...";
        cin.ignore();
        cin.get();
    }
    return 0;
}
