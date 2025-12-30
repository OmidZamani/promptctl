#!/bin/bash
# Batch mode example - demonstrates efficiency for bulk operations

set -e

echo "=== Batch Mode Example ==="
echo ""

# Clean start
rm -rf ~/.promptctl

echo "Scenario: Import 12 prompts"
echo "Without batch: 12 individual commits (~600ms)"
echo "With batch (size=5): 3 commits (~150ms)"
echo ""

echo "Importing prompts with batch mode (batch-size=5)..."
for i in {1..12}; do
  python ../promptctl.py save \
    --name "prompt-$i" \
    --tags test batch \
    --batch \
    --batch-size 5 \
    -m "This is test prompt number $i"
done

echo ""
echo "Checking git log..."
python ../promptctl.py --repo ~/.promptctl diff --staged || echo "No staged changes"

echo ""
echo "View commits:"
cd ~/.promptctl && git --no-pager log --oneline

echo ""
echo "Notice: Batch commits group multiple saves together!"
