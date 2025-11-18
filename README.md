# 🤖 UI Test Agent ADK

AI-powered UI testing framework combining **Google ADK (Agent Development Kit)** with **Playwright** for intelligent, self-healing browser automation.

## ✨ Features

- **🎯 Natural Language Testing**: Write tests in plain English, AI generates selectors
- **🔄 Self-Healing Selectors**: Automatically adapts to DOM changes using HTML context
- **🤖 Multi-Mode Execution**:
  - **Function Tools**: Deterministic YAML-based scenarios
  - **Natural Language**: AI-generated test plans from plain text
  - **Computer Use**: Vision-based UI automation (experimental)
- **📊 Rich Reporting**: HTML/JSON reports with screenshots and videos
- **🔍 Smart DOM Analysis**: Extracts selectors from actual HTML structure
- **⚡ Adaptive Timeouts**: Dynamic wait times based on execution history

## 🚀 Quick Start

### Installation

\`\`\`bash
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
\`\`\`

### Basic Usage

**1. Function Tools Mode (Deterministic YAML)**

\`\`\`bash
python -m ui_test_agent run \
  --scenario scenarios/demo_login.yml \
  --config config.yaml \
  --headful
\`\`\`

**2. Natural Language Mode (AI-Generated)**

\`\`\`bash
python -m ui_test_agent run \
  --config config.yaml \
  --nl-file scenarios/demo_login.txt \
  --headful \
  --slowmo 500
\`\`\`

**3. Computer Use Mode (Vision-Based)**

\`\`\`bash
python -m ui_test_agent run \
  --scenario scenarios/demo_login.yml \
  --config config.yaml \
  --mode computer_use \
  --headful
\`\`\`

## 📝 Writing Tests

### Natural Language Format

Create a simple \`.txt\` file with plain instructions:

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
- Extract correct selectors (#id, data-testid, text=)
- Generate executable test steps
- Adapt if selectors change

### YAML Format (Deterministic)

\`\`\`yaml
meta:
  name: Login Test
  description: Tests user login flow
env:
  baseUrl: http://localhost:8000
flow:
  - action: go
    url: /demo_login.html
  - action: type
    selector: "#username"
    value: admin
  - action: type
    selector: "#password"
    value: password
  - action: click
    selector: text=Login
  - action: see
    text: Success
\`\`\`

## 🏗️ Architecture

📚 **[See detailed architecture documentation with diagrams →](ARCHITECTURE.md)**

### Core Components

```
src/ui_test_agent/
├── nl_agent.py          # Natural language → test scenario (hybrid approach)
├── dom_indexer.py       # Smart DOM element extraction (Stage 1)
├── context_builder.py   # Rich context builder (Stage 2)
├── adk_agent.py         # ADK function-calling orchestration
├── computer_use_agent.py # Vision-based automation
├── runner.py            # Test execution engine
├── locators.py          # Self-healing selector resolution
├── semantic_eval.py     # AI-powered assertions
├── reporting.py         # HTML/JSON report generation
└── cli.py              # Command-line interface
```

### How It Works

1. **HTML Extraction**: Captures interactive elements as HTML snippets
   \`\`\`html
   <input id="search-input" placeholder="Search..." />
   <button id="search-btn">Search</button>
   \`\`\`

2. **AI Planning**: Google Gemini analyzes HTML and generates selectors
   \`\`\`json
   {
     "action": "type",
     "selector": "#search-input",
     "value": "MacBook"
   }
   \`\`\`

3. **Smart Execution**: Playwright executes with fallback strategies
   - Try exact selector
   - Try alternative selectors (name, placeholder, text)
   - Use semantic matching as last resort

4. **Feedback Loop**: If step fails, AI regenerates plan with error context

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

\`config.yaml\`:

\`\`\`yaml
settings:
  base_url: http://localhost:8000
  headless: false
  slowmo_ms: 500
  timeout_ms: 8000
  viewport_width: 1280
  viewport_height: 720
  video: true
  screenshots_on_failure: true

gemini:
  model: gemini-2.5-flash
  temperature: 0.7
\`\`\`

## 🧪 Demo Pages

Two demo pages included for testing:

**\`demo_login.html\`** - Simple login form
- Username/password inputs
- Submit button
- Success message

**\`demo_ecommerce.html\`** - E-commerce store (TechStore)
- Search functionality
- Product catalog (9 items)
- Shopping cart
- Filters (category, price, sort)
- Checkout flow

Start local server:
\`\`\`bash
python -m http.server 8000
# Visit: http://localhost:8000/demo_login.html
\`\`\`

## 🔧 Advanced Usage

### Custom Scenarios

\`\`\`bash
# With specific timeout
python -m ui_test_agent run \
  --scenario scenarios/custom.yml \
  --timeout 15000

# Headless with video
python -m ui_test_agent run \
  --scenario scenarios/custom.yml \
  --video \
  --no-headful
\`\`\`

### Environment Variables

\`\`\`bash
export GEMINI_API_KEY="your-api-key"
export GEMINI_MODEL="gemini-2.5-flash"  # or gemini-1.5-pro
export DEBUG=1  # Enable debug logging
\`\`\`

## 📚 API Key Setup

1. Get API key: https://aistudio.google.com/apikey
2. Copy \`.env.example\` to \`.env\`
3. Add key: \`GEMINI_API_KEY=your-key-here\`

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Add more selector fallback strategies
- Improve feedback loop quality
- Support additional browsers (Firefox, WebKit)
- Enhanced semantic assertions
- Multi-language support

## 📄 License

MIT License

## 🙏 Acknowledgments

- Google ADK (Agent Development Kit)
- Playwright
- Google Gemini AI

---

**Made with ❤️ for smarter UI testing**
