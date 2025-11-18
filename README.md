# 🤖 UI Test Agent

Natural Language UI testing framework powered by **Google Gemini** and **Playwright** for intelligent browser automation.

## ✨ Features

- **🎯 Natural Language Testing**: Write tests in plain English, AI decides actions
- **🔄 Self-Healing**: Automatically adapts to DOM changes using semantic understanding
- **🤖 Dual Execution Modes**:
  - **Static NL**: Generate complete scenario upfront, then execute
  - **Dynamic NL**: Step-by-step decision making with live DOM observation
- **📊 Rich Reporting**: HTML/JSON reports with screenshots and execution details
- **🔍 Smart DOM Indexing**: Extracts interactive elements from actual HTML
- **⚡ Context-Aware**: Uses current page state for accurate selector resolution

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone <repo-url>
cd ui-test-agent-adk

# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Install Playwright browsers
python -m playwright install --with-deps chromium

# Setup API key
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### Basic Usage

**1. Static Natural Language Mode**

```bash
python -m ui_test_agent run \
  --nl-file scenarios/demo_login.txt \
  --config config.yaml \
  --headful
```

**2. Dynamic Natural Language Mode**

```bash
python -m ui_test_agent run \
  --nl "Open http://localhost:8000/demo_login.html and login with username 'admin' and password 'password'" \
  --config config.yaml \
  --dynamic \
  --headful
```

## 📝 Writing Tests

### Natural Language Format

Create a simple `.txt` file with plain instructions:

\`\`\`text
Login Test:

1. Open demo_login.html page
2. Type "admin" in the username field
3. Type "password" in the password field  
4. Click the login button
5. Verify success message appears
\`\`\`

The AI will:
- Analyze the page HTML
- Extract correct selectors from live DOM
- Generate executable test steps
- Adapt to page changes in real-time

## 🏗️ Architecture

📚 **[See detailed architecture documentation with diagrams →](ARCHITECTURE.md)**

### Core Components

```
src/ui_test_agent/
├── nl_agent.py          # Static NL: Generate scenario upfront
├── dynamic_nl_agent.py  # Dynamic NL: Step-by-step decisions
├── dom_indexer.py       # Smart DOM element extraction
├── context_builder.py   # Rich context for AI prompts
├── runner.py            # Scenario execution engine
├── semantic_eval.py     # AI-powered assertions
├── reporting.py         # HTML/JSON report generation
└── cli.py               # Command-line interface
```

### How It Works

**Static Mode:**
1. **DOM Extraction**: Captures interactive elements with selectors
2. **AI Planning**: Gemini generates complete scenario from context
3. **Execution**: Runner executes all steps sequentially
4. **Reporting**: Generates HTML/JSON reports

**Dynamic Mode:**
1. **Goal Input**: User provides high-level goal
2. **Observe**: Agent extracts current page DOM
3. **Decide**: AI determines next single action
4. **Execute**: Performs action, observes result
5. **Repeat**: Until goal achieved or max steps reached

## 🎯 Selector Strategy

The AI follows this priority:

1. **#id** - Most reliable, always preferred
2. **[data-testid]** - Good for stable test attributes
3. **text=** - Great for buttons/links with stable text
4. **[name]** - OK for form fields
5. **[placeholder]** - Avoid (can be truncated)

### Example HTML → Selector Mapping

| HTML | Generated Selector |
|------|-------------------|
| \`<input id="email">\` | \`#email\` |
| \`<button data-testid="submit">Submit</button>\` | \`[data-testid="submit"]\` or \`text=Submit\` |
| \`<a href="/cart">Cart (3)</a>\` | \`text=Cart (3)\` |

## 📊 Reports & Artifacts

After each test run, find:

\`\`\`
artifacts/
├── report.html              # Interactive HTML report
├── report.json              # Machine-readable results
├── nl_plan_*.json          # Generated test plan (NL mode)
├── nl_scenario_*.yml       # YAML version of plan
├── nl_transcript_*.md      # AI agent conversation log
├── failure_*.png           # Screenshots on failure
└── videos/
    └── test_*.mp4          # Full test execution video
\`\`\`

## ⚙️ Configuration

`config.yaml`:

```yaml
baseUrl: http://localhost:8000
headless: false
slowMo: 500
timeouts:
  default: 8000
  url: 15000
  api: 20000
retry:
  step: 1
  scenario: 0
recordVideo: false
collectHAR: false
allowedHosts:
  - localhost
  - 127.0.0.1
artifactsDir: artifacts
```

## 🧪 Demo Pages

Three demo pages included for testing:

**`demo_login.html`** - Simple login form
- Username/password inputs
- Submit button
- Success/error messages

**`demo_ecommerce.html`** - E-commerce store
- Product catalog with filters
- Shopping cart
- Search functionality

**`demo_complex_dashboard.html`** - Multi-section dashboard
- Analytics charts
- Data tables
- Form submissions

Start local server:
```bash
python -m http.server 8000
# Visit: http://localhost:8000/demo_login.html
```

## 🔧 CLI Options

```bash
python -m ui_test_agent run [OPTIONS]

Options:
  --config PATH       Config file path (default: config.yaml)
  --nl TEXT          Inline natural language instructions
  --nl-file PATH     Natural language instructions from file
  --dynamic          Use dynamic mode (step-by-step)
  --headful          Launch browser with UI
  --slowmo MS        Slow motion in milliseconds
```

### Examples

```bash
# Static mode with file
python -m ui_test_agent run --nl-file scenarios/demo_login.txt

# Dynamic mode with inline goal
python -m ui_test_agent run --dynamic --nl "Search for MacBook and add to cart"

# With debugging (slow motion + headful)
python -m ui_test_agent run --nl-file scenarios/ecommerce_test.txt --headful --slowmo 500
```

### Environment Variables

```bash
export GEMINI_API_KEY="your-api-key"
export GEMINI_MODEL="gemini-2.5-flash"  # or gemini-1.5-pro
```

## 📚 API Key Setup

1. Get API key: https://aistudio.google.com/apikey
2. Copy `.env.example` to `.env`
3. Add key: `GEMINI_API_KEY=your-key-here`

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License

## 🙏 Acknowledgments

- Google Gemini AI
- Playwright
- Python ecosystem

---

**Made with ❤️ for intelligent UI testing**
