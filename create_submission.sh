#!/bin/bash

# FIITMeteo Binary Protocol - Submission Package Creator
# This script creates the xmiklosz.zip submission package

echo "=========================================="
echo "FIITMeteo Submission Package Creator"
echo "=========================================="
echo ""

# Check if all required files exist
echo "Checking required files..."
required_files=(
    "server.py"
    "tester.py"
    "fiitmeteo.lua"
)

missing_files=0
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "  ✗ Missing: $file"
        missing_files=$((missing_files + 1))
    else
        echo "  ✓ Found: $file"
    fi
done

if [ $missing_files -gt 0 ]; then
    echo ""
    echo "Error: $missing_files required file(s) missing!"
    exit 1
fi

echo ""
echo "All required files found!"
echo ""

# Create PDF from documentation
echo "Converting documentation to PDF..."
echo "Note: You need to convert DOCUMENTATION.md to xmiklosz.pdf manually"
echo "You can use:"
echo "  - pandoc DOCUMENTATION.md -o xmiklosz.pdf"
echo "  - Online converter (e.g., https://www.markdowntopdf.com/)"
echo "  - Markdown editor with PDF export"
echo ""

read -p "Have you created xmiklosz.pdf? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Please create xmiklosz.pdf first, then run this script again."
    exit 1
fi

if [ ! -f "xmiklosz.pdf" ]; then
    echo "Error: xmiklosz.pdf not found!"
    exit 1
fi

# Create zip file
echo ""
echo "Creating xmiklosz.zip..."
zip -r xmiklosz.zip \
    server.py \
    tester.py \
    fiitmeteo.lua \
    xmiklosz.pdf

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Submission package created successfully!"
    echo "=========================================="
    echo ""
    echo "Package contents:"
    unzip -l xmiklosz.zip
    echo ""
    echo "File size:"
    ls -lh xmiklosz.zip
    echo ""
    echo "✓ The submission package 'xmiklosz.zip' is ready!"
    echo ""
    echo "Required files:"
    echo "  ✓ server.py       - Binary protocol server"
    echo "  ✓ tester.py       - Binary protocol tester"
    echo "  ✓ fiitmeteo.lua   - Wireshark dissector"
    echo "  ✓ xmiklosz.pdf    - Documentation"
else
    echo ""
    echo "Error: Failed to create zip file!"
    exit 1
fi
