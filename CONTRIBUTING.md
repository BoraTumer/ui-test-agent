# Contributing to UI Test Agent ADK

Thank you for your interest in contributing! 🎉

## Getting Started

1. **Fork the repository**
2. **Clone your fork**:
   ```bash
   git clone https://github.com/your-username/ui-test-agent-adk.git
   cd ui-test-agent-adk
   ```
3. **Create a branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"
pip install -r requirements.txt

# Install Playwright browsers
python -m playwright install

# Setup environment
cp .env.example .env
# Add your GEMINI_API_KEY
```

## Project Structure

```
src/ui_test_agent/
├── nl_agent.py          # ADK-based natural language processing
├── dom_explorer.py      # HTML element extraction
├── runner.py            # Test execution engine
├── locators.py          # Selector resolution
├── semantic_eval.py     # AI-powered assertions
└── cli.py              # Command-line interface
```

## Making Changes

### Code Style

- Follow PEP 8
- Use type hints where possible
- Add docstrings for public functions
- Keep functions focused and small

### Testing

```bash
# Run existing tests
python -m ui_test_agent run --scenario scenarios/demo_login.yml --config config.yaml

# Test with natural language
python -m ui_test_agent run --nl-file scenarios/demo_login.txt --config config.yaml --headful
```

### Commit Messages

Use clear, descriptive commit messages:
```
feat: Add support for Firefox browser
fix: Resolve selector extraction from dynamic IDs
docs: Update README with new examples
refactor: Simplify DOM extraction logic
```

## Areas for Contribution

### High Priority
- 🔍 Enhanced selector fallback strategies
- 🔄 Improved feedback loop quality
- 🦊 Firefox and WebKit browser support
- 🧪 More comprehensive test scenarios

### Medium Priority
- 📊 Better error messages and debugging
- 🎨 UI for test management
- 🌍 Multi-language support
- ⚡ Performance optimizations

### Nice to Have
- 📸 Visual regression testing
- 🔌 Plugin system for custom actions
- 📱 Mobile browser support
- ☁️ Cloud execution support

## Pull Request Process

1. **Update documentation** if needed
2. **Add tests** for new features
3. **Ensure all tests pass**
4. **Update CHANGELOG.md**
5. **Create pull request** with clear description

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement

## Testing
How was this tested?

## Checklist
- [ ] Code follows project style
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] CHANGELOG updated
```

## Code Review

All submissions require review. We'll:
- Check code quality and style
- Verify tests pass
- Review documentation
- Test functionality

## Questions?

Feel free to:
- Open an issue for discussion
- Ask questions in pull requests
- Reach out to maintainers

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for making UI Test Agent ADK better! 🚀
