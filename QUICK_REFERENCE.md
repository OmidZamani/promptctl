# promptctl - Quick Reference Card

## 🚀 Getting Started (30 seconds)

```bash
cd ~/dev/promptctl
source venv/bin/activate
echo "Test" | python promptctl.py save --name test --tags demo
python promptctl.py list
```

## 📖 Common Commands

### Save Prompts
```bash
# From stdin
echo "Prompt text" | python promptctl.py save --name myid --tags tag1 tag2

# From file
python promptctl.py save --file prompt.txt --name myid --tags tag1

# Inline
python promptctl.py save -m "Prompt text" --name myid --tags tag1
```

### List & Show
```bash
python promptctl.py list                    # All prompts
python promptctl.py list --tags python      # Filter by tag
python promptctl.py show myid               # Show specific prompt
```

### Tags
```bash
python promptctl.py tag add --prompt-id myid --tags newtag
python promptctl.py tag remove --prompt-id myid --tags oldtag
python promptctl.py tag list                # All tags with counts
python promptctl.py tag filter --tags python javascript          # OR logic
python promptctl.py tag filter --tags python prod --match-all   # AND logic
```

### Daemon
```bash
# Basic
python promptctl.py daemon

# With options
python promptctl.py daemon --interval 30 --conflict-strategy timestamp

# With AI ✨
python promptctl.py daemon --use-llm --interval 20
```

### Status & Diff
```bash
python promptctl.py status
python promptctl.py status --verbose
python promptctl.py diff
```

## 🎯 Two-Mode Operation

### Mode 1: Default (Fast, Simple)
```bash
python promptctl.py daemon
# Commits: "Auto-commit: 2025-12-30 16:22:45"
```

### Mode 2: AI-Powered ✨
```bash
python promptctl.py daemon --use-llm
# Commits: "Refactor API structure in auth module"
```

## ⚙️ Configuration

### Default Repository
`~/.promptctl/`

### Override Repository
```bash
python promptctl.py --repo /path/to/repo [command]
```

### Conflict Strategies
- `timestamp` (default) - Keep newest
- `ours` - Keep local changes
- `theirs` - Keep daemon changes
- `manual` - User intervention

## 📦 Batch Mode

```bash
# Commit every 5 saves (5x faster)
for i in {1..20}; do
  python promptctl.py save --name "p$i" --tags test \
    --batch --batch-size 5 -m "Test $i"
done
```

## 🔧 Troubleshooting

### LLM not working?
```bash
# Check Ollama
ollama list                        # Should show phi3.5
brew services list                 # Ollama should be started

# Restart Ollama
brew services restart ollama

# Test manually
ollama run phi3.5 "Hello"
```

### Check installation
```bash
cd ~/dev/promptctl
source venv/bin/activate
python promptctl.py --help         # Should work
python -c "from core.daemon import LLMCommitGenerator; print('OK')"
```

## 📂 File Structure

```
~/.promptctl/
├── prompts/              # Your prompts
│   ├── myid.md          # Content
│   └── myid.meta.json   # Metadata
├── .tags_index.json     # Tag index
├── .git/                # Git repo
└── .conflict_log.txt    # Conflict log
```

## 💡 Pro Tips

1. **Use tags liberally** - Easy filtering later
2. **Batch mode for bulk** - 5-10x faster
3. **Daemon in background** - Set and forget
4. **LLM optional** - Works great without it
5. **Git commands work** - `cd ~/.promptctl && git log`

## 🎓 Examples

### Example 1: Save + Tag + Show
```bash
echo "Code review prompt" | python promptctl.py save \
  --name review --tags coding production

python promptctl.py show review
```

### Example 2: Batch Import
```bash
for i in {1..10}; do
  echo "Prompt $i" | python promptctl.py save \
    --name "p$i" --tags batch-test --batch --batch-size 5
done
```

### Example 3: Smart Daemon
```bash
# Terminal 1
python promptctl.py daemon --use-llm --interval 20

# Terminal 2
echo "## Note" >> ~/.promptctl/prompts/myfile.md
sleep 25
cd ~/.promptctl && git log --oneline -1
```

## 🚨 Emergency Commands

### Stop all daemons
```bash
pkill -f "python promptctl.py daemon"
```

### Check what's running
```bash
ps aux | grep "promptctl.py daemon"
```

### View git history
```bash
cd ~/.promptctl
git log --oneline
git show HEAD
```

### Reset to clean state
```bash
cd ~/.promptctl
git status
git reset --hard HEAD
```

## 📊 Quick Stats

- **Lines of code**: 1,482
- **Core features**: 5
- **Commands**: 7
- **Conflict strategies**: 4
- **Time to start**: 30 seconds
- **Dependencies**: 2 (GitPython + requests)
- **Optional**: Ollama + Phi-3.5

## 🎯 One-Liners

```bash
# Quick save
echo "Prompt" | python promptctl.py save --name test --tags demo

# Quick list
python promptctl.py list

# Quick daemon
python promptctl.py daemon &

# Quick stop
pkill -f "promptctl.py daemon"

# Quick status
cd ~/.promptctl && git log --oneline -5
```

---

**More details**: See `README.md` or `QUICKSTART.md`  
**Full docs**: `PHASE_1_AND_2_COMPLETE.md`
