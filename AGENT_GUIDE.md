# Agent Mode Guide

Autonomous agent for prompt testing, improvement, and self-optimization.

## Overview

Agent mode runs fully autonomously to:
- Execute prompts against test cases
- Score results automatically
- Self-improve through iterative feedback
- Track quality metrics over multiple rounds
- Report progress and final results

## Quick Start

### Basic Agent Run

```bash
promptctl agent my-prompt --rounds 5
```

This will:
1. Load your prompt
2. Run it against test cases
3. Score the results (0-100)
4. Generate improvements
5. Repeat for 5 rounds
6. Save the best version

### With Custom Test Cases

Create `tests.json`:
```json
[
  {
    "input": "Translate 'hello' to Spanish",
    "expected": "hola"
  },
  {
    "input": "Translate 'goodbye' to Spanish",
    "expected": "adiós"
  }
]
```

Run agent:
```bash
promptctl agent my-prompt --test-file tests.json --rounds 5
```

### With Detailed Report

```bash
promptctl agent my-prompt --rounds 5 --report
```

## Command Options

```bash
promptctl agent PROMPT_ID [options]
```

**Options:**
- `--rounds N`: Number of improvement rounds (default: 5)
- `--min-score SCORE`: Stop early if this score is reached (default: 90.0)
- `--test-file FILE`: JSON file with test cases
- `--report`: Print detailed report at the end

## How It Works

### Agent Loop

```
1. Execute → 2. Score → 3. Analyze → 4. Improve → 5. Repeat
```

**Phase 1: Execute**
- Run prompt with each test input
- Capture outputs
- Time execution

**Phase 2: Score**
- Compare output vs expected
- Calculate score (0-100)
- Default: fuzzy string matching

**Phase 3: Analyze**
- Identify failing cases
- Generate feedback
- Suggest improvements

**Phase 4: Improve**
- Use LLM to create better version
- Apply feedback from analysis
- Maintain prompt structure

**Phase 5: Repeat**
- Continue for N rounds
- Track best version
- Stop early if target reached

### Scoring Algorithm

Default scoring (customizable):

```python
# Exact match: 100 points
if actual == expected:
    score = 100.0

# Substring match: 80 points
elif expected in actual:
    score = 80.0

# Word overlap: 0-60 points
else:
    overlap_ratio = words_in_common / total_expected_words
    score = overlap_ratio * 60.0
```

## Examples

### Example 1: Simple Prompt Optimization

```bash
# Create prompt
promptctl save --name greeting -m "Greet the user warmly"

# Run agent
promptctl agent greeting --rounds 3
```

**Output:**
```
Starting agent for prompt: greeting
Rounds: 3
Target score: 90.0
============================================================

=== ROUND 1/3 ===
Round 1 score: 45.00/100
Feedback: Significant improvements needed: add more context and examples

=== ROUND 2/3 ===
Round 2 score: 72.00/100
New best score: 72.00
Feedback: Good performance: refine edge cases and improve clarity

=== ROUND 3/3 ===
Round 3 score: 88.00/100
New best score: 88.00
Feedback: Excellent performance: minor optimizations only

=== AGENT RUN COMPLETE ===
Best score: 88.00/100
Best version saved as: greeting_agent_optimized

✓ Agent run complete!
Best version: greeting_agent_optimized
Final score: 88.00/100
```

### Example 2: Code Generation

```bash
# Create prompt
promptctl save --name codegen -m "Write a Python function to sort a list"

# Create tests
cat > code_tests.json <<EOF
[
  {"input": "Sort [3,1,2]", "expected": "[1, 2, 3]"},
  {"input": "Sort [5,4,3,2,1]", "expected": "[1, 2, 3, 4, 5]"},
  {"input": "Sort []", "expected": "[]"}
]
EOF

# Run agent with report
promptctl agent codegen \
  --test-file code_tests.json \
  --rounds 5 \
  --min-score 95 \
  --report
```

### Example 3: Quick Test (No Optimization)

```bash
# Just test without improving
promptctl test my-prompt --test-file tests.json
```

Output:
```
Test Results for my-prompt:
Average score: 76.50/100
  Test 1: 80.00/100
  Test 2: 75.00/100
  Test 3: 75.00/100
```

## Advanced Usage

### Custom Metrics in Python

```python
from core.agent import PromptAgent

def strict_metric(actual: str, expected: str) -> float:
    """Require exact match."""
    return 100.0 if actual.strip() == expected.strip() else 0.0

agent = PromptAgent("my-prompt")
best_id, score = agent.run(
    rounds=5,
    metric_fn=strict_metric
)
```

### Programmatic Access

```python
from core.agent import PromptAgent

# Initialize agent
agent = PromptAgent(
    prompt_id="my-prompt",
    test_cases=[
        {"input": "Test 1", "expected": "Output 1"},
        {"input": "Test 2", "expected": "Output 2"}
    ]
)

# Run optimization
best_id, score = agent.run(rounds=5, min_score=90.0)

# Get detailed report
report = agent.get_report()
print(f"Improvement: +{report['improvement']:.2f} points")
```

### Integration with CI/CD

```bash
#!/bin/bash
# test_prompts.sh

# Run agent and check if score meets threshold
promptctl agent my-prompt --test-file tests.json --rounds 3

# Exit code 0 if successful
if [ $? -eq 0 ]; then
    echo "✓ Prompt quality acceptable"
else
    echo "✗ Prompt needs improvement"
    exit 1
fi
```

## Configuration

### LLM Backend

Agent uses Ollama (Phi-3.5) by default:

```bash
# Ensure Ollama is running
ollama serve

# Pull Phi-3.5 if needed
ollama pull phi3.5

# Run agent
promptctl agent my-prompt
```

### Port Configuration

Default: `http://localhost:11434`

Customize in Python:
```python
agent = PromptAgent(
    prompt_id="my-prompt",
    llm_url="http://localhost:11434/api/generate",
    llm_model="phi3.5"
)
```

## Best Practices

1. **Start with good test cases**
   - Diverse inputs
   - Clear expected outputs
   - Representative of real use

2. **Use appropriate number of rounds**
   - 3-5 rounds usually sufficient
   - More rounds = risk of overfitting
   - Watch for diminishing returns

3. **Set realistic target scores**
   - 90+ is very high quality
   - 80-90 is good
   - <80 needs work

4. **Monitor progress**
   - Use `--report` to see details
   - Check round-by-round scores
   - Identify when to stop

5. **Version control**
   - All iterations are committed to git
   - Can always revert to previous version
   - Track improvement over time

## Comparison: Agent vs DSPy Optimize

| Feature | Agent Mode | DSPy Optimize |
|---------|-----------|---------------|
| Approach | Autonomous feedback loop | Structured optimization |
| Speed | Slower (full execution) | Faster |
| Accuracy | Higher (real LLM tests) | Lower (simulated) |
| Control | Less | More |
| Use case | Final polish | Initial improvement |

**Recommendation:**
- Use DSPy `optimize` first for quick wins
- Use `agent` for final refinement and testing

## Troubleshooting

### Agent not improving scores

- Check test cases are realistic
- Ensure LLM (Ollama) is running
- Try fewer rounds (avoid overfitting)
- Verify prompt isn't already optimal

### Slow execution

- Reduce number of test cases
- Use simpler test cases
- Check LLM response times

### Scores too low

- Review test case expectations
- Check if expected outputs are achievable
- Consider custom metric function

## Integration

### With Daemon

```bash
# Terminal 1: Start daemon
promptctl daemon

# Terminal 2: Run agent
promptctl agent my-prompt --rounds 5

# Daemon auto-commits all versions
```

### With DSPy

```bash
# First: DSPy optimization
promptctl optimize my-prompt --rounds 3

# Then: Agent refinement
promptctl agent my-prompt_optimized --rounds 5
```

## Next Steps

- Create comprehensive test suites
- Set up automated testing in CI/CD
- Build custom metrics for your domain
- Integrate with browser extension for quick captures

See also:
- [DSPY_GUIDE.md](DSPY_GUIDE.md) - DSPy optimization
- [EXTENSION_GUIDE.md](EXTENSION_GUIDE.md) - Browser extension
- [README.md](README.md) - Main documentation
