# DSPy Integration Guide

promptctl includes powerful DSPy integration for automatic prompt optimization, chaining, and evaluation.

## Features

- **Few-shot Example Generation**: Automatically create training examples
- **Prompt Chaining**: Combine multiple prompts into workflows
- **Iterative Optimization**: Improve prompts through feedback loops
- **Metric-based Evaluation**: Score prompt quality objectively

## Installation

```bash
pip install dspy-ai
```

## Quick Start

### 1. Optimize a Prompt

Automatically improve a prompt through iterative testing:

```bash
promptctl optimize my-prompt --rounds 3
```

**Options:**
- `--rounds N`: Number of optimization iterations (default: 3)
- `--use-ollama`: Use local Ollama instead of OpenAI

**Example:**
```bash
# Optimize with local Ollama (Phi-3.5)
promptctl optimize my-prompt --rounds 5 --use-ollama
```

### 2. Chain Prompts

Combine multiple prompts into a sequential workflow:

```bash
promptctl chain prompt1 prompt2 prompt3 --name "my-workflow"
```

**Example:**
```bash
# Create a multi-step analysis chain
promptctl chain extract-data analyze-data summarize --name "data-pipeline"
```

### 3. Evaluate a Prompt

Test a prompt against predefined test cases:

```bash
promptctl evaluate my-prompt --test-file tests.json
```

**Test file format** (`tests.json`):
```json
[
  {
    "input": "What is 2+2?",
    "expected": "4"
  },
  {
    "input": "What is the capital of France?",
    "expected": "Paris"
  }
]
```

## Detailed Usage

### Optimization Loop

DSPy optimization works by:

1. **Testing** the current prompt against test cases
2. **Scoring** the results using metrics
3. **Analyzing** failures and weaknesses
4. **Generating** an improved version
5. **Repeating** for N rounds

```bash
# Full optimization with details
promptctl optimize my-prompt \
  --rounds 5 \
  --use-ollama
```

### Custom Metrics

Create custom scoring functions in Python:

```python
from core.dspy_optimizer import PromptOptimizer

def custom_metric(output: str, expected: str) -> float:
    # Return score 0-100
    if expected.lower() in output.lower():
        return 100.0
    return 0.0

optimizer = PromptOptimizer()
optimized_id, score = optimizer.optimize(
    prompt_id="my-prompt",
    metric_fn=custom_metric,
    rounds=3
)
```

### Prompt Chains

Chains are useful for multi-step workflows:

```python
from core.dspy_optimizer import PromptOptimizer

optimizer = PromptOptimizer()

# Chain extraction -> analysis -> summary
chain_id = optimizer.chain_prompts(
    prompt_ids=[
        "extract-entities",
        "analyze-sentiment", 
        "generate-summary"
    ],
    chain_name="full-nlp-pipeline"
)
```

## Configuration

### Using OpenAI (default)

Requires `OPENAI_API_KEY` environment variable:

```bash
export OPENAI_API_KEY="sk-..."
promptctl optimize my-prompt
```

### Using Local Ollama

More privacy, no API costs:

```bash
# Start Ollama
ollama serve

# Pull Phi-3.5
ollama pull phi3.5

# Use with promptctl
promptctl optimize my-prompt --use-ollama
```

## Best Practices

1. **Start with 3 rounds**: More rounds don't always help
2. **Use meaningful test cases**: Quality > Quantity
3. **Chain related prompts**: Keep workflows coherent
4. **Evaluate before deploying**: Always test first
5. **Version control**: Git tracks all optimizations

## Examples

### Example 1: Code Generation Prompt

```bash
# Original prompt
promptctl save --name code-gen -m "Write a Python function that..."

# Optimize it
promptctl optimize code-gen --rounds 3 --use-ollama

# Result: code-gen_optimized with improved quality
```

### Example 2: Multi-Step Analysis

```bash
# Create individual prompts
promptctl save --name step1 -m "Extract key points from text"
promptctl save --name step2 -m "Analyze sentiment of points"
promptctl save --name step3 -m "Generate executive summary"

# Chain them
promptctl chain step1 step2 step3 --name analysis-pipeline

# Use the chain
promptctl show analysis-pipeline
```

### Example 3: Evaluation Suite

Create `tests.json`:
```json
[
  {"input": "Test case 1", "expected": "Expected 1"},
  {"input": "Test case 2", "expected": "Expected 2"},
  {"input": "Test case 3", "expected": "Expected 3"}
]
```

```bash
# Evaluate
promptctl evaluate my-prompt --test-file tests.json
```

## Troubleshooting

### DSPy not found

```bash
pip install dspy-ai
```

### OpenAI API errors

```bash
# Use local Ollama instead
promptctl optimize my-prompt --use-ollama
```

### Optimization not improving

- Add more diverse test cases
- Try different metrics
- Reduce number of rounds (overfitting)

## Integration with Daemon

DSPy features work seamlessly with the daemon:

```bash
# Start daemon
promptctl daemon --use-llm

# In another terminal, optimize
promptctl optimize my-prompt

# Daemon auto-commits optimized versions
```

## Next Steps

- Try **Agent Mode** for fully autonomous optimization
- Create **custom metrics** for domain-specific scoring
- Build **complex chains** for multi-stage workflows
- Set up **CI/CD** with automated evaluation

See also:
- [AGENT_GUIDE.md](AGENT_GUIDE.md) - Autonomous agent features
- [README.md](README.md) - Main documentation
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Command reference
