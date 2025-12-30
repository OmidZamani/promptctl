.PHONY: help install test clean demo lint

help:
	@echo "promptctl - Makefile commands"
	@echo ""
	@echo "  make install    Install dependencies"
	@echo "  make test       Run tests"
	@echo "  make demo       Run demo"
	@echo "  make clean      Clean generated files"
	@echo "  make lint       Run linters"

install:
	pip install -r requirements.txt

test:
	python -m pytest tests/ -v

demo:
	@echo "=== promptctl Demo ==="
	@echo ""
	@echo "1. Saving prompts..."
	echo "You are a helpful coding assistant" | python promptctl.py save --name assistant --tags ai coding
	@echo ""
	@echo "2. Adding tags..."
	python promptctl.py tag add --prompt-id assistant --tags production
	@echo ""
	@echo "3. Listing prompts..."
	python promptctl.py list
	@echo ""
	@echo "4. Filtering by tag..."
	python promptctl.py tag filter --tags coding
	@echo ""
	@echo "5. Showing prompt..."
	python promptctl.py show assistant
	@echo ""
	@echo "Demo complete! Repository at ~/.promptctl"

clean:
	rm -rf ~/.promptctl
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

lint:
	@echo "Running type check..."
	python -m mypy promptctl.py core/ --ignore-missing-imports || true
	@echo ""
	@echo "Running style check..."
	python -m flake8 promptctl.py core/ --max-line-length=100 || true
