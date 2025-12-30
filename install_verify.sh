#!/bin/bash
# promptctl Installation Verification Script
# Verifies all dependencies and system requirements

set -e

echo "============================================================"
echo "🔍 promptctl Installation Verification"
echo "============================================================"
echo ""

PASS="✅"
FAIL="❌"
WARN="⚠️"
total_checks=0
passed_checks=0

check() {
    total_checks=$((total_checks + 1))
    if [ $1 -eq 0 ]; then
        echo "$PASS $2"
        passed_checks=$((passed_checks + 1))
        return 0
    else
        echo "$FAIL $2"
        [ -n "$3" ] && echo "   → Fix: $3"
        return 1
    fi
}

echo "📋 System Requirements"
echo "-----------------------------------------------------------"

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
python_major=$(echo $python_version | cut -d. -f1)
python_minor=$(echo $python_version | cut -d. -f2)

if [ "$python_major" -ge 3 ] && [ "$python_minor" -ge 10 ]; then
    check 0 "Python ${python_version} (≥3.10 required)"
else
    check 1 "Python ${python_version} (need ≥3.10)" "brew install python@3.10"
fi

# Check virtual environment
if [ -n "$VIRTUAL_ENV" ]; then
    check 0 "Virtual environment active: $(basename $VIRTUAL_ENV)"
else
    check 1 "Virtual environment NOT active" "source venv/bin/activate"
fi

# Check working directory
if [ -f "promptctl.py" ]; then
    check 0 "In promptctl directory: $(pwd)"
else
    check 1 "Not in promptctl directory" "cd ~/dev/promptctl"
fi

echo ""
echo "📦 Python Dependencies"
echo "-----------------------------------------------------------"

# Check GitPython
if python -c "import git" 2>/dev/null; then
    version=$(python -c "import git; print(git.__version__)" 2>/dev/null)
    check 0 "GitPython ${version} installed"
else
    check 1 "GitPython NOT installed" "pip install GitPython"
fi

# Check requests
if python -c "import requests" 2>/dev/null; then
    version=$(python -c "import requests; print(requests.__version__)" 2>/dev/null)
    check 0 "requests ${version} installed"
else
    check 1 "requests NOT installed" "pip install requests"
fi

# Check all imports work
if python -c "from core.daemon import PromptDaemon, LLMCommitGenerator; from core.git_manager import GitManager" 2>/dev/null; then
    check 0 "All core modules import successfully"
else
    check 1 "Core module imports failed" "Check Python path and dependencies"
fi

echo ""
echo "🤖 LLM Components (Optional)"
echo "-----------------------------------------------------------"

# Check Ollama installation
if command -v ollama &> /dev/null; then
    ollama_version=$(ollama --version 2>&1 | head -1)
    check 0 "Ollama installed: $ollama_version"
else
    check 1 "Ollama NOT installed (optional)" "brew install ollama"
fi

# Check Ollama service
if pgrep -x "ollama" > /dev/null 2>&1; then
    check 0 "Ollama service running"
else
    check 1 "Ollama service NOT running" "brew services start ollama"
fi

# Check Phi-3.5 model
if command -v ollama &> /dev/null; then
    if ollama list 2>/dev/null | grep -q "phi3.5"; then
        model_size=$(ollama list 2>/dev/null | grep "phi3.5" | awk '{print $3}')
        check 0 "Phi-3.5 model available ($model_size)"
    else
        check 1 "Phi-3.5 model NOT available" "ollama pull phi3.5"
    fi
fi

echo ""
echo "💾 Storage & Repository"
echo "-----------------------------------------------------------"

# Check disk space
if [ "$(uname)" = "Darwin" ]; then
    free_space=$(df -h . | awk 'NR==2 {print $4}')
    free_space_gb=$(df -g . | awk 'NR==2 {print $4}')
else
    free_space=$(df -h . | awk 'NR==2 {print $4}')
    free_space_gb=$(echo $free_space | sed 's/G//')
fi

if [ "${free_space_gb}" -ge 5 ] 2>/dev/null; then
    check 0 "Disk space available: ${free_space}"
else
    check 1 "Low disk space: ${free_space} (need 5GB+)" "Free up disk space"
fi

# Check promptctl repo
if [ -d "$HOME/.promptctl/.git" ]; then
    check 0 "promptctl repository initialized at ~/.promptctl"
else
    check 0 "promptctl repository not yet initialized (will auto-create)"
fi

# Check code files exist
core_files=("promptctl.py" "core/daemon.py" "core/git_manager.py" "core/tag_manager.py")
missing_files=0
for file in "${core_files[@]}"; do
    if [ ! -f "$file" ]; then
        missing_files=$((missing_files + 1))
    fi
done

if [ $missing_files -eq 0 ]; then
    check 0 "All core files present (${#core_files[@]} files)"
else
    check 1 "$missing_files core files missing" "Check installation directory"
fi

echo ""
echo "🧪 Basic Functionality Test"
echo "-----------------------------------------------------------"

# Test CLI help
if python promptctl.py --help > /dev/null 2>&1; then
    check 0 "CLI runs successfully"
else
    check 1 "CLI fails to run" "Check Python and dependencies"
fi

# Test LLM integration
if python -c "from core.daemon import LLMCommitGenerator; gen = LLMCommitGenerator(enabled=False); print('OK')" 2>/dev/null | grep -q "OK"; then
    check 0 "LLMCommitGenerator class accessible"
else
    check 1 "LLMCommitGenerator not accessible" "Check core/daemon.py"
fi

echo ""
echo "============================================================"
echo "📊 Verification Summary"
echo "============================================================"
echo ""
echo "Checks passed: $passed_checks / $total_checks"

if [ $passed_checks -eq $total_checks ]; then
    echo ""
    echo "🎉 ALL CHECKS PASSED! Installation is complete."
    echo ""
    echo "🚀 Ready to use promptctl:"
    echo "   cd ~/dev/promptctl"
    echo "   source venv/bin/activate"
    echo "   python promptctl.py --help"
    echo ""
    echo "   # Without LLM (default)"
    echo "   python promptctl.py daemon"
    echo ""
    echo "   # With LLM (smart commits)"
    echo "   python promptctl.py daemon --use-llm"
    echo ""
    exit 0
else
    failed=$((total_checks - passed_checks))
    echo ""
    echo "⚠️  $failed checks failed. Review errors above."
    echo ""
    echo "Common fixes:"
    echo "  1. Activate venv: source venv/bin/activate"
    echo "  2. Install deps: pip install -r requirements.txt"
    echo "  3. Start Ollama: brew services start ollama"
    echo "  4. Pull model: ollama pull phi3.5"
    echo ""
    exit 1
fi
