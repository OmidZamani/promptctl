# promptctl Quickstart Guide

## Installation

### Step 1: Create virtual environment

```bash
cd ~/dev/promptctl
python3 -m venv venv
source venv/bin/activate
```

### Step 2: Install dependencies

```bash
pip install GitPython
```

Or use requirements.txt:
```bash
pip install -r requirements.txt
```

### Step 3 (Optional): Setup AI-Powered Commits

For intelligent commit message generation:

```bash
# Install Ollama
brew install ollama

# Start service
brew services start ollama

# Download Phi-3.5 (2.2GB)
ollama pull phi3.5

# Test
ollama run phi3.5 "Write a commit message for bug fix"
# Ctrl+D to exit
```

## Quick Test

### 1. Save a prompt

```bash
echo "You are a helpful AI assistant" | python promptctl.py save \
  --name my-assistant \
  --tags ai helper
```

Output:
```
Initialized repository at /Users/omid/.promptctl
Saved prompt: my-assistant
Tags: ai, helper
```

### 2. List prompts

```bash
python promptctl.py list
```

Output:
```
Found 1 prompts:
  my-assistant                             [ai, helper]
```

### 3. Add more tags

```bash
python promptctl.py tag add --prompt-id my-assistant --tags production
```

### 4. Filter by tags

```bash
python promptctl.py tag filter --tags ai production --match-all
```

Output:
```
Prompts matching ALL of tags ['ai', 'production']:
  my-assistant                             [ai, helper, production]

Total: 1 prompts
```

### 5. Show prompt content

```bash
python promptctl.py show my-assistant
```

Output:
```
Prompt: my-assistant
Tags: ai, helper, production
Metadata: {'id': 'my-assistant', 'created_at': '2025-12-30...', 'tags': [...]}

============================================================
You are a helpful AI assistant
============================================================
```

## Batch Mode Example

```bash
# Save 10 prompts, commit every 5
for i in {1..10}; do
  python promptctl.py save \
    --name "prompt-$i" \
    --tags test \
    --batch \
    --batch-size 5 \
    -m "Test prompt $i"
done
```

You'll see:
```
Saved prompt: prompt-1
Pending saves: 1/5

Saved prompt: prompt-2
Pending saves: 2/5

...

Saved prompt: prompt-5
✓ Batch commit triggered (5 saves)
```

## Tag Commands

```bash
# List all tags with counts
python promptctl.py tag list

# Add tags
python promptctl.py tag add --prompt-id my-prompt --tags production important

# Remove tags
python promptctl.py tag remove --prompt-id my-prompt --tags draft

# Filter (OR logic - any tag matches)
python promptctl.py tag filter --tags python javascript

# Filter (AND logic - all tags must match)
python promptctl.py tag filter --tags python production --match-all
```

## Running the Daemon

Terminal 1:
```bash
python promptctl.py daemon --interval 30 --conflict-strategy timestamp
```

Terminal 2 (make changes):
```bash
echo "New prompt" | python promptctl.py save --name test --tags demo
# Daemon will auto-commit within 30 seconds
```

### With AI-Powered Commits

```bash
# Start daemon with LLM (requires Ollama setup)
python promptctl.py daemon --use-llm --interval 20

# Make changes in another terminal
echo "## Updated" >> ~/.promptctl/prompts/myfile.md

# Check commit message (AI-generated!)
cd ~/.promptctl && git log --oneline -1
# Example: "Refactor API structure in auth module"
```

## Conflict Strategies

- **timestamp** (default): Keep most recent version
- **ours**: Always keep local changes
- **theirs**: Always keep daemon changes
- **manual**: Require user intervention

## Repository Status

```bash
# Check status
python promptctl.py status

# View changes
python promptctl.py diff

# View staged changes
python promptctl.py diff --staged
```

## File Location

All prompts stored in: `~/.promptctl/`

To use a different location:
```bash
python promptctl.py --repo /path/to/repo save --name test -m "Test"
```

## Common Workflows

### Building a prompt library

```bash
# Code review prompts
python promptctl.py save --name code-review \
  --tags coding review \
  -m "Review this code for bugs, performance, and best practices"

# Documentation prompts
python promptctl.py save --name write-docs \
  --tags coding docs \
  -m "Write comprehensive documentation for this code"

# Debugging prompts
python promptctl.py save --name debug-help \
  --tags coding debug \
  -m "Help me debug this error"

# List all coding prompts
python promptctl.py list --tags coding
```

### Organizing with tags

```bash
# Production-ready prompts
python promptctl.py tag add --prompt-id code-review --tags production verified

# Find all production coding prompts
python promptctl.py tag filter --tags coding production --match-all

# List all tags
python promptctl.py tag list
```

## Next Steps

1. Read [README.md](README.md) for full documentation
2. Read [DESIGN.md](DESIGN.md) for architecture details
3. Run example scripts in `examples/`
4. Check test suite in `tests/`

## Troubleshooting

**"No module named 'git'"**:
- Make sure you activated the virtual environment: `source venv/bin/activate`
- Install GitPython: `pip install GitPython`

**"Repository not initialized"**:
- Run any command to auto-initialize: `python promptctl.py status`

**"Prompt not found"**:
- Check prompt ID: `python promptctl.py list`
- Use exact ID (case-sensitive)

## Deactivate Virtual Environment

When done:
```bash
deactivate
```

## Uninstall

```bash
# Remove repository
rm -rf ~/.promptctl

# Remove project
rm -rf ~/dev/promptctl
```
