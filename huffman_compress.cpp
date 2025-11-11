#include <iostream>
#include <fstream>
#include <string>
#include <queue>
#include <unordered_map>
#include <vector>
#include <bitset>

using namespace std;

// Huffman tree node
struct Node {
    char ch;
    int freq;
    Node *left, *right;

    Node(char c, int f) : ch(c), freq(f), left(nullptr), right(nullptr) {}
};

// Comparison object for priority queue
struct Compare {
    bool operator()(Node* l, Node* r) {
        return l->freq > r->freq;
    }
};

// Build frequency table from input file
void buildFreqTable(const string& filename, int freqTable[256]) {
    ifstream inFile(filename, ios::binary);

    if (!inFile) {
        cerr << "Error: Cannot open input file: " << filename << endl;
        return;
    }

    // Initialize frequency table
    for (int i = 0; i < 256; i++) {
        freqTable[i] = 0;
    }

    // Count character frequencies
    char ch;
    while (inFile.get(ch)) {
        freqTable[(unsigned char)ch]++;
    }

    inFile.close();
}

// Build Huffman tree
Node* buildHuffmanTree(int freqTable[256]) {
    priority_queue<Node*, vector<Node*>, Compare> pq;

    // Create leaf node for each character with non-zero frequency
    for (int i = 0; i < 256; i++) {
        if (freqTable[i] > 0) {
            pq.push(new Node((char)i, freqTable[i]));
        }
    }

    // Build the tree
    while (pq.size() > 1) {
        Node* left = pq.top();
        pq.pop();

        Node* right = pq.top();
        pq.pop();

        Node* parent = new Node('\0', left->freq + right->freq);
        parent->left = left;
        parent->right = right;

        pq.push(parent);
    }

    return pq.empty() ? nullptr : pq.top();
}

// Generate Huffman codes
void generateCodes(Node* root, string code, unordered_map<char, string>& huffmanCodes) {
    if (!root) return;

    // Leaf node
    if (!root->left && !root->right) {
        huffmanCodes[root->ch] = code.empty() ? "0" : code;
        return;
    }

    generateCodes(root->left, code + "0", huffmanCodes);
    generateCodes(root->right, code + "1", huffmanCodes);
}

// Compress file
void compress(const string& inputFile, const string& outputFile) {
    // Build frequency table
    int freqTable[256];
    buildFreqTable(inputFile, freqTable);

    // Build Huffman tree
    Node* root = buildHuffmanTree(freqTable);

    if (!root) {
        cout << "Error: Empty file or unable to build tree" << endl;
        return;
    }

    // Generate Huffman codes
    unordered_map<char, string> huffmanCodes;
    generateCodes(root, "", huffmanCodes);

    // Write compressed file
    ifstream inFile(inputFile, ios::binary);
    ofstream outFile(outputFile, ios::binary);

    if (!inFile) {
        cerr << "Error: Cannot open input file" << endl;
        return;
    }

    if (!outFile) {
        cerr << "Error: Cannot create output file" << endl;
        return;
    }

    // Write frequency table to output file
    for (int i = 0; i < 256; i++) {
        outFile.write((char*)&freqTable[i], sizeof(int));
    }

    // Encode and write compressed data
    string encodedStr = "";
    char ch;
    while (inFile.get(ch)) {
        encodedStr += huffmanCodes[ch];
    }

    // Write the number of padding bits
    int padding = 8 - (encodedStr.length() % 8);
    if (padding == 8) padding = 0;
    outFile.write((char*)&padding, sizeof(int));

    // Convert binary string to bytes and write
    for (size_t i = 0; i < encodedStr.length(); i += 8) {
        string byteStr = encodedStr.substr(i, 8);
        // Pad last byte if necessary
        while (byteStr.length() < 8) {
            byteStr += '0';
        }
        bitset<8> byte(byteStr);
        char c = (char)byte.to_ulong();
        outFile.write(&c, 1);
    }

    inFile.close();
    outFile.close();

    cout << "Compression completed successfully!" << endl;
}

// Decompress file
void decompress(const string& inputFile, const string& outputFile) {
    ifstream inFile(inputFile, ios::binary);
    ofstream outFile(outputFile, ios::binary);

    if (!inFile) {
        cerr << "Error: Cannot open input file" << endl;
        return;
    }

    if (!outFile) {
        cerr << "Error: Cannot create output file" << endl;
        return;
    }

    // Read frequency table
    int freqTable[256];
    for (int i = 0; i < 256; i++) {
        inFile.read((char*)&freqTable[i], sizeof(int));
    }

    // Rebuild Huffman tree
    Node* root = buildHuffmanTree(freqTable);

    if (!root) {
        cerr << "Error: Cannot rebuild Huffman tree" << endl;
        return;
    }

    // Read padding info
    int padding;
    inFile.read((char*)&padding, sizeof(int));

    // Read compressed data
    string encodedStr = "";
    char byte;
    while (inFile.read(&byte, 1)) {
        bitset<8> bits((unsigned char)byte);
        encodedStr += bits.to_string();
    }

    // Remove padding
    if (padding > 0) {
        encodedStr = encodedStr.substr(0, encodedStr.length() - padding);
    }

    // Decode
    Node* current = root;
    for (char bit : encodedStr) {
        if (bit == '0') {
            current = current->left;
        } else {
            current = current->right;
        }

        // Leaf node
        if (!current->left && !current->right) {
            outFile.put(current->ch);
            current = root;
        }
    }

    inFile.close();
    outFile.close();

    cout << "Decompression completed successfully!" << endl;
}

int main(int argc, char* argv[]) {
    if (argc < 4) {
        cout << "Usage: " << argv[0] << " <mode> <input_file> <output_file>" << endl;
        cout << "mode: c (compress) or d (decompress)" << endl;
        return 1;
    }

    string mode = argv[1];
    string inputFile = argv[2];
    string outputFile = argv[3];

    if (mode == "c" || mode == "C") {
        compress(inputFile, outputFile);
    } else if (mode == "d" || mode == "D") {
        decompress(inputFile, outputFile);
    } else {
        cout << "Invalid mode. Use 'c' for compress or 'd' for decompress" << endl;
        return 1;
    }

    return 0;
}
