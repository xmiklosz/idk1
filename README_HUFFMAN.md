# Huffman Compression Tool

A complete C++ implementation of Huffman compression and decompression algorithm.

## Features

- Huffman encoding with frequency table
- Binary file compression
- Decompression with tree reconstruction
- Support for all ASCII characters (0-255)

## Compilation

### Using Makefile:
```bash
make
```

### Manual compilation:
```bash
g++ -std=c++11 -Wall -O2 -o huffman huffman_compress.cpp
```

## Usage

### Compress a file:
```bash
./huffman c input.txt compressed.huff
```

### Decompress a file:
```bash
./huffman d compressed.huff output.txt
```

## Command Line Arguments

```
./huffman <mode> <input_file> <output_file>
```

- `mode`: 'c' or 'C' for compression, 'd' or 'D' for decompression
- `input_file`: Path to the input file
- `output_file`: Path to the output file

## How It Works

1. **Compression**:
   - Reads input file and builds frequency table
   - Creates Huffman tree based on character frequencies
   - Generates binary codes for each character
   - Writes frequency table and encoded data to output file

2. **Decompression**:
   - Reads frequency table from compressed file
   - Reconstructs Huffman tree
   - Decodes binary data using the tree
   - Writes original data to output file

## File Format

Compressed files contain:
1. Frequency table (256 integers, 4 bytes each)
2. Padding information (1 integer, 4 bytes)
3. Compressed binary data

## Error Handling

The program includes error handling for:
- File open/read/write errors
- Empty files
- Invalid command line arguments
