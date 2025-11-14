#include <iostream>
#include <fstream>
#include <queue>
#include <vector>
using namespace std;


struct Node {
    unsigned char ch;
    int freq;
    Node *left, *right;

    Node(unsigned char c, int f) : ch(c), freq(f), left(nullptr), right(nullptr) {}
};


struct Compare {
    bool operator()(Node* a, Node* b) {
        if (a->freq != b->freq) return a->freq > b->freq;

        if (!a->left && !b->left) return a->ch > b->ch;
        return false;
    }
};


Node* buildTree(int freq[256]) {
    priority_queue<Node*, vector<Node*>, Compare> pq;

    for (int i = 0; i < 256; i++) {
        if (freq[i] > 0) {
            pq.push(new Node((unsigned char)i, freq[i]));
        }
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

    // Check file size to ensure it's valid
    in.seekg(0, ios::end);
    long fileSize = in.tellg();
    in.seekg(0, ios::beg);

    if (fileSize < 1024 + sizeof(long)) {
        cout << "Error: File too small to be a valid compressed file!" << endl;
        in.close();
        return;
    }

    // Read frequency table
    int freq[256];
    for (int i = 0; i < 256; i++) {
        if (!in.read((char*)&freq[i], 4)) {
            cout << "Error: Failed to read frequency table at position " << i << endl;
            in.close();
            return;
        }
    }

    // Read total characters
    long total;
    if (!in.read((char*)&total, sizeof(long))) {
        cout << "Error: Failed to read total count!" << endl;
        in.close();
        return;
    }

    cout << "Total characters to decode: " << total << endl;

    // Build tree
    Node* root = buildTree(freq);

    // Open output file
    ofstream out(outfile, ios::binary);
    if (!out) {
        cout << "Error: Cannot create output file!" << endl;
        in.close();
        return;
    }

    Node* current = root;
    long decoded = 0;
    unsigned char byte;

    // Read and decode compressed data
    while (decoded < total && in.read((char*)&byte, 1)) {
        // Process each bit in the byte
        for (int i = 7; i >= 0 && decoded < total; i--) {
            bool bit = (byte >> i) & 1;

            if (bit) {
                current = current->right;
            } else {
                current = current->left;
            }

            // Check if we reached a leaf node
            if (!current->left && !current->right) {
                out.write((char*)&current->ch, 1);
                decoded++;
                current = root;
            }
        }
    }

    in.close();
    out.close();

    cout << "Decoded " << decoded << " characters" << endl;

    // Show statistics
    ifstream inStat(infile, ios::binary | ios::ate);
    ifstream outStat(outfile, ios::binary | ios::ate);

    long compressedSize = inStat.tellg();
    long decompressedSize = outStat.tellg();

    inStat.close();
    outStat.close();

    cout << endl;
    cout << "Decompression Statistics" << endl;
    cout << "Compressed file:   " << infile << " - " << compressedSize << " bytes (" << (compressedSize / 1024.0) << " KB)" << endl;
    cout << "Decompressed file: " << outfile << " - " << decompressedSize << " bytes (" << (decompressedSize / 1024.0) << " KB)" << endl;

    cout << endl;
    cout << "Decompression complete!" << endl;
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
