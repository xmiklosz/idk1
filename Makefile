CXX = g++
CXXFLAGS = -std=c++11 -Wall -O2

TARGET = huffman
SOURCE = huffman_compress.cpp

all: $(TARGET)

$(TARGET): $(SOURCE)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SOURCE)

clean:
	rm -f $(TARGET)

compress: $(TARGET)
	./$(TARGET) c input.txt compressed.huff

decompress: $(TARGET)
	./$(TARGET) d compressed.huff output.txt

.PHONY: all clean compress decompress
