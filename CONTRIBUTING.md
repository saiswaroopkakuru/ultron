# Contributing to Ultron

Thank you for your interest in making Ultron even better! Ultron is an open-source project dedicated to cutting token usage by up to 95% while keeping operational code precision at 100%.

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/ultron.git
   cd ultron
   ```

2. **Create a virtual environment & install dependencies**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   pip install pytest flake8
   ```

3. **Run Unit Tests**:
   ```bash
   python -m pytest tests -v
   ```

4. **Run Open-Source Model Benchmarks**:
   ```bash
   # Ensure Ollama is running:
   ollama pull qwen2.5:0.5b
   python benchmarks/run_ollama_eval.py
   ```

## Pull Request Guidelines

- **Code Precision Rule**: Any compression feature must preserve 100% of code blocks, syntax, file paths, and identifiers. Never apply lossy abbreviations to code!
- **Tests**: Add unit tests in `tests/` for every new feature or bug fix.
- **Documentation**: Update docstrings and the README if adding new CLI commands or MCP tools.
