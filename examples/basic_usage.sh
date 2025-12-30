#!/bin/bash
# Basic usage examples for promptctl

set -e

echo "=== promptctl Basic Usage Examples ==="
echo ""

# Clean start
rm -rf ~/.promptctl

echo "1. Save a simple prompt"
echo "You are a helpful assistant" | python ../promptctl.py save --name assistant --tags ai helper
echo ""

echo "2. Save prompt from file"
echo "Write a Python function that sorts a list" > /tmp/prompt.txt
python ../promptctl.py save --file /tmp/prompt.txt --name coding-task --tags python coding
rm /tmp/prompt.txt
echo ""

echo "3. Save with inline message"
python ../promptctl.py save -m "Explain quantum computing" --name science-task --tags physics science
echo ""

echo "4. List all prompts"
python ../promptctl.py list
echo ""

echo "5. Add tags to existing prompt"
python ../promptctl.py tag add --prompt-id assistant --tags production verified
echo ""

echo "6. List all tags"
python ../promptctl.py tag list
echo ""

echo "7. Filter prompts by tag"
python ../promptctl.py tag filter --tags coding
echo ""

echo "8. Filter with AND logic"
python ../promptctl.py tag filter --tags ai production --match-all
echo ""

echo "9. Show specific prompt"
python ../promptctl.py show assistant
echo ""

echo "10. Check repository status"
python ../promptctl.py status
echo ""

echo "=== All examples completed successfully! ==="
