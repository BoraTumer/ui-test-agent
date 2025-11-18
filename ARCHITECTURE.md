# 🏗️ Architecture Documentation

## Overview

UI Test Agent ADK is a hybrid AI-powered test automation framework combining multiple execution modes for maximum flexibility and reliability.

## Table of Contents
- [System Architecture](#system-architecture)
- [Execution Modes](#execution-modes)
- [Data Flow](#data-flow)
- [Component Diagrams](#component-diagrams)
- [Sequence Diagrams](#sequence-diagrams)

---

## System Architecture

```mermaid
graph TB
    subgraph "Entry Point"
        CLI[CLI - cli.py]
    end
    
    subgraph "Execution Modes"
        STATIC[Static NL Agent<br/>nl_agent.py]
        DYNAMIC[Dynamic NL Agent<br/>dynamic_nl_agent.py]
        FUNCTION[Function Tools<br/>adk_agent.py]
        COMPUTER[Computer Use<br/>computer_use_agent.py]
    end
    
    subgraph "Core Components"
        DOM[DOM Indexer<br/>dom_indexer.py]
        CONTEXT[Context Builder<br/>context_builder.py]
        RUNNER[Scenario Runner<br/>runner.py]
        LOCATOR[Locator Engine<br/>locators.py]
    end
    
    subgraph "External Services"
        GEMINI[Google Gemini AI]
        PLAYWRIGHT[Playwright Browser]
    end
    
    CLI -->|--dynamic| DYNAMIC
    CLI -->|--nl-file| STATIC
    CLI -->|--scenario| FUNCTION
    CLI -->|--mode computer_use| COMPUTER
    
    STATIC --> CONTEXT
    STATIC --> DOM
    STATIC --> GEMINI
    
    DYNAMIC --> DOM
    DYNAMIC --> GEMINI
    DYNAMIC --> PLAYWRIGHT
    
    FUNCTION --> RUNNER
    COMPUTER --> PLAYWRIGHT
    
    CONTEXT --> DOM
    RUNNER --> LOCATOR
    RUNNER --> PLAYWRIGHT
    LOCATOR --> PLAYWRIGHT
    
    style DYNAMIC fill:#2ecc71,color:#fff
    style STATIC fill:#3498db,color:#fff
    style DOM fill:#e74c3c,color:#fff
    style CONTEXT fill:#f39c12,color:#fff
```

---

## Execution Modes

### 1. Dynamic NL Agent (NEW) 🚀

**Step-by-step decision making with real-time DOM observation**

```mermaid
graph LR
    START([User Goal]) --> OBSERVE[Observe Current DOM]
    OBSERVE --> DECIDE[Agent Decides Next Action]
    DECIDE --> EXECUTE[Execute Action]
    EXECUTE --> CHECK{Goal Achieved?}
    CHECK -->|No| OBSERVE
    CHECK -->|Yes| END([Done])
    
    style START fill:#2ecc71,color:#fff
    style END fill:#27ae60,color:#fff
    style DECIDE fill:#3498db,color:#fff
```

**Advantages:**
- ✅ Adapts to page changes in real-time
- ✅ No need to predict entire flow upfront
- ✅ Handles dynamic UIs (modals, notifications)
- ✅ Self-correcting on element changes

**Disadvantages:**
- ⚠️ Higher API cost (1 call per step)
- ⚠️ Slower execution
- ⚠️ Requires good prompt engineering

---

### 2. Static NL Agent

**Generate full test scenario upfront, then execute**

```mermaid
graph LR
    NL[Natural Language] --> ANALYZE[Intent Analysis]
    ANALYZE --> DOM[Extract DOM]
    DOM --> CONTEXT[Build Rich Context]
    CONTEXT --> AI[Gemini AI]
    AI --> SCENARIO[Generated Scenario]
    SCENARIO --> EXECUTE[Execute All Steps]
    
    style NL fill:#3498db,color:#fff
    style AI fill:#9b59b6,color:#fff
    style SCENARIO fill:#2ecc71,color:#fff
```

**Advantages:**
- ✅ Low API cost (1-2 calls total)
- ✅ Fast execution
- ✅ Predictable flow

**Disadvantages:**
- ⚠️ Can't adapt mid-execution
- ⚠️ Needs retry logic for failures

---

### 3. Function Tools Mode

**Deterministic YAML-based execution**

```mermaid
graph LR
    YAML[YAML Scenario] --> PARSE[Parse DSL]
    PARSE --> ADK[Google ADK<br/>Optional]
    PARSE --> RUNNER[Direct Runner]
    ADK --> RUNNER
    RUNNER --> PW[Playwright Actions]
    
    style YAML fill:#e74c3c,color:#fff
    style RUNNER fill:#2ecc71,color:#fff
```

---

## Data Flow

### Dynamic NL Agent Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant DynamicAgent
    participant DOMIndexer
    participant Gemini
    participant Playwright
    
    User->>CLI: --dynamic --nl-file goal.txt
    CLI->>DynamicAgent: execute_goal(goal)
    
    loop Until goal achieved (max 20 steps)
        DynamicAgent->>Playwright: Get current page
        DynamicAgent->>DOMIndexer: build_index()
        DOMIndexer->>Playwright: Query elements
        DOMIndexer-->>DynamicAgent: Formatted element list
        
        DynamicAgent->>Gemini: What's next action?<br/>(goal + DOM + history)
        Gemini-->>DynamicAgent: ActionStep(click, #btn)
        
        DynamicAgent->>Playwright: Execute action
        Playwright-->>DynamicAgent: Success/Failure
        
        alt Goal achieved
            DynamicAgent-->>CLI: Success
        else Max steps reached
            DynamicAgent-->>CLI: Timeout
        else Action failed
            DynamicAgent-->>CLI: Failed
        end
    end
```

---

### Static NL Agent Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant NLAgent
    participant ContextBuilder
    participant DOMIndexer
    participant Gemini
    participant Runner
    
    User->>CLI: --nl-file login_test.txt
    CLI->>NLAgent: build(prompt)
    
    NLAgent->>DOMIndexer: Extract page elements
    DOMIndexer-->>NLAgent: ElementInfo[]
    
    NLAgent->>ContextBuilder: build_context()
    ContextBuilder-->>NLAgent: Rich context (intent + examples + DOM)
    
    NLAgent->>Gemini: Generate scenario
    Gemini-->>NLAgent: Full YAML scenario
    
    NLAgent-->>CLI: Scenario object
    
    CLI->>Runner: run(scenario)
    Runner-->>CLI: Report (passed/failed)
    
    alt Failed with retry
        CLI->>NLAgent: build(prompt + feedback)
        NLAgent->>Gemini: Regenerate with errors
        Gemini-->>NLAgent: Improved scenario
        CLI->>Runner: run(improved_scenario)
    end
```

---

## Component Diagrams

### DOM Indexer Architecture

```mermaid
classDiagram
    class DOMSemanticIndexer {
        +Page page
        +List~ElementInfo~ elements
        +build_index(max_elements) List~ElementInfo~
        +to_context_string() str
        +get_by_role(role) List~ElementInfo~
        -_analyze_element(el) ElementInfo
        -_get_role(el) str
        -_get_attrs(el) Dict
    }
    
    class ElementInfo {
        +str tag
        +str selector
        +int priority
        +str text
        +str role
        +Dict attributes
    }
    
    class PlaywrightPage {
        +locator(selector)
        +get_by_role()
        +query_selector_all()
    }
    
    DOMSemanticIndexer --> ElementInfo : creates
    DOMSemanticIndexer --> PlaywrightPage : uses
    
    note for ElementInfo "Priority:\n1 = #id\n2 = [data-testid]\n3 = text=\n4 = [name]\n5 = CSS"
```

### Selector Priority System

```mermaid
graph TD
    START[Element Found] --> CHECK_ID{Has ID?}
    CHECK_ID -->|Yes| ID[#id<br/>Priority 1]
    CHECK_ID -->|No| CHECK_TESTID{Has data-testid?}
    CHECK_TESTID -->|Yes| TESTID[data-testid<br/>Priority 2]
    CHECK_TESTID -->|No| CHECK_TEXT{Button/Link<br/>with text?}
    CHECK_TEXT -->|Yes| TEXT[text=<br/>Priority 3]
    CHECK_TEXT -->|No| CHECK_NAME{Has name?}
    CHECK_NAME -->|Yes| NAME[name<br/>Priority 4]
    CHECK_NAME -->|No| CSS[CSS class<br/>Priority 5]
    
    ID --> OUTPUT[Return ElementInfo]
    TESTID --> OUTPUT
    TEXT --> OUTPUT
    NAME --> OUTPUT
    CSS --> OUTPUT
    
    style ID fill:#2ecc71,color:#fff
    style TESTID fill:#3498db,color:#fff
    style TEXT fill:#f39c12,color:#fff
    style NAME fill:#e67e22,color:#fff
    style CSS fill:#e74c3c,color:#fff
```

---

## Context Builder Pipeline

```mermaid
graph TB
    START[User Instructions] --> INTENT[Intent Analysis<br/>Regex-based]
    
    INTENT --> DETECT{Detected Patterns}
    DETECT -->|Login| LOGIN_INTENT[Authentication Intent]
    DETECT -->|Search| SEARCH_INTENT[Search Intent]
    DETECT -->|Cart| ECOM_INTENT[E-commerce Intent]
    DETECT -->|Fill| FORM_INTENT[Form Filling Intent]
    
    LOGIN_INTENT --> EXAMPLES[Select Examples]
    SEARCH_INTENT --> EXAMPLES
    ECOM_INTENT --> EXAMPLES
    FORM_INTENT --> EXAMPLES
    
    START --> DOM_INDEX[DOM Element Index]
    DOM_INDEX --> FORMAT[Format Elements by Role]
    
    EXAMPLES --> COMBINE[Combine Context]
    FORMAT --> COMBINE
    
    COMBINE --> PRACTICES[Add Best Practices]
    PRACTICES --> ENV[Add Environment]
    ENV --> FINAL[Final Context for AI]
    
    style INTENT fill:#3498db,color:#fff
    style EXAMPLES fill:#2ecc71,color:#fff
    style FINAL fill:#9b59b6,color:#fff
```

---

## Action Execution Flow

### Dynamic Agent Action Types

```mermaid
graph TD
    ACTION{Action Type} --> GO[go]
    ACTION --> TYPE[type]
    ACTION --> CLICK[click]
    ACTION --> SELECT[select]
    ACTION --> SEE[see]
    ACTION --> DONE[done]
    
    GO --> NAV["page.goto(url)"]
    TYPE --> FILL["locator.fill(value)"]
    CLICK --> CLICKACT["locator.click() + wait 800ms"]
    SELECT --> SELECTACT["select_option(label) fallback to value"]
    SEE --> VERIFY["wait_for(attached) + wait_for(visible)"]
    DONE --> COMPLETE[Goal Achieved]
    
    style GO fill:#3498db,color:#fff
    style TYPE fill:#2ecc71,color:#fff
    style CLICK fill:#f39c12,color:#fff
    style SELECT fill:#9b59b6,color:#fff
    style SEE fill:#1abc9c,color:#fff
    style DONE fill:#27ae60,color:#fff
```

### Select Action (Enhanced)

```mermaid
graph LR
    START[select action] --> WAIT[Wait for visible]
    WAIT --> TRY1{Try label}
    TRY1 -->|Success| DONE[Complete]
    TRY1 -->|Fail| TRY2{Try value.lower}
    TRY2 -->|Success| DONE
    TRY2 -->|Fail| TRY3{Try value as-is}
    TRY3 -->|Success| DONE
    TRY3 -->|Fail| ERROR[Throw error]
    DONE --> PAUSE[Wait 800ms<br/>for JS handlers]
    
    style START fill:#3498db,color:#fff
    style DONE fill:#2ecc71,color:#fff
    style ERROR fill:#e74c3c,color:#fff
```

---

## Error Handling & Retry Logic

### Static NL Mode Retry

```mermaid
stateDiagram-v2
    [*] --> GenerateScenario
    GenerateScenario --> ExecuteSteps
    ExecuteSteps --> CheckResult
    
    CheckResult --> Success: All steps passed
    CheckResult --> Failed: Step failed
    
    Failed --> CheckRetry: retry < max?
    CheckRetry --> CollectFeedback: Yes
    CheckRetry --> FinalFail: No
    
    CollectFeedback --> RegenerateScenario: Add error context
    RegenerateScenario --> ExecuteSteps
    
    Success --> [*]
    FinalFail --> [*]
    
    note right of CollectFeedback
        Includes:
        - Failed step details
        - Error message
        - Available selectors
        - Page context
    end note
```

### Dynamic Agent Loop Prevention

```mermaid
graph TB
    HISTORY[Check Last 8 Steps] --> SAME{Same selector<br/>used before?}
    SAME -->|Yes, type/select| SKIP[Skip this field]
    SAME -->|No| CHECK_FILLED{All fields<br/>filled?}
    
    CHECK_FILLED -->|Yes| CHECK_SUBMIT{Form<br/>submitted?}
    CHECK_SUBMIT -->|Yes| CHECK_SUCCESS{Success<br/>message seen?}
    CHECK_SUCCESS -->|Yes| DONE[Return 'done']
    CHECK_SUCCESS -->|No| VERIFY[Add 'see' action]
    
    CHECK_FILLED -->|No| FILL[Fill next field]
    CHECK_SUBMIT -->|No| SUBMIT[Click submit]
    
    style HISTORY fill:#3498db,color:#fff
    style DONE fill:#2ecc71,color:#fff
    style SKIP fill:#e74c3c,color:#fff
```

---

## Comparison Matrix

```mermaid
graph TB
    subgraph "Feature Comparison"
        direction TB
        A[Dynamic NL]
        B[Static NL]
        C[Function Tools]
        D[Computer Use]
    end
    
    subgraph "Metrics"
        direction TB
        M1[API Calls: High/Low/None/High]
        M2[Speed: Medium/Fast/Fastest/Slow]
        M3[Adaptability: High/Low/None/High]
        M4[Reliability: Medium/High/Highest/Low]
        M5[Cost: High/Low/Free/High]
    end
    
    A -.->|Many| M1
    B -.->|1-2| M1
    C -.->|0| M1
    D -.->|Many| M1
    
    style A fill:#2ecc71,color:#fff
    style B fill:#3498db,color:#fff
    style C fill:#f39c12,color:#fff
    style D fill:#9b59b6,color:#fff
```

---

## Testing Strategy

### Test Execution Decision Tree

```mermaid
graph TD
    START{Test Type} --> SIMPLE{Simple & Stable?}
    SIMPLE -->|Yes| USE_YAML[Use Function Tools<br/>YAML Scenario]
    SIMPLE -->|No| DYNAMIC_UI{Dynamic UI?}
    
    DYNAMIC_UI -->|Yes| MULTI_PAGE{Multiple Pages?}
    MULTI_PAGE -->|Yes| USE_DYNAMIC[Use Dynamic NL<br/>Step-by-step]
    MULTI_PAGE -->|No| COMPLEX{Complex Logic?}
    
    COMPLEX -->|Yes| USE_DYNAMIC
    COMPLEX -->|No| USE_STATIC[Use Static NL<br/>Generate Once]
    
    DYNAMIC_UI -->|No| USE_STATIC
    
    style USE_YAML fill:#f39c12,color:#fff
    style USE_STATIC fill:#3498db,color:#fff
    style USE_DYNAMIC fill:#2ecc71,color:#fff
```

---

## Performance Characteristics

```mermaid
graph LR
    subgraph "Dynamic NL Agent"
        D1[13 steps] --> D2[13 API calls]
        D2 --> D3[~30 seconds]
        D3 --> D4[Cost: $$]
    end
    
    subgraph "Static NL Agent"
        S1[Same test] --> S2[1-2 API calls]
        S2 --> S3[~5 seconds]
        S3 --> S4[Cost: $]
    end
    
    subgraph "Function Tools"
        F1[Same test] --> F2[0 API calls]
        F2 --> F3[~3 seconds]
        F3 --> F4[Cost: Free]
    end
    
    style D4 fill:#e74c3c,color:#fff
    style S4 fill:#f39c12,color:#fff
    style F4 fill:#2ecc71,color:#fff
```

---

## Future Enhancements

```mermaid
mindmap
  root((UI Test Agent))
    Batch Actions
      Combine similar steps
      Reduce API calls 50%
      Form filling optimization
    Smart Context
      Modal-aware DOM extraction
      Scope filtering
      Memory optimization
    Error Recovery
      Checkpoint system
      Resume from failure
      Adaptive retry
    Parallel Execution
      Multi-tab support
      Concurrent tests
      Resource pooling
    Enhanced Assertions
      Element count checks
      CSS property validation
      URL pattern matching
      Network request spying
    Visual Testing
      Screenshot comparison
      Visual regression
      Layout validation
```

---

## Technology Stack

```mermaid
graph TB
    subgraph "AI Layer"
        GEMINI[Google Gemini 2.5-flash]
        ADK[Google ADK]
    end
    
    subgraph "Automation Layer"
        PLAYWRIGHT[Playwright]
        CHROMIUM[Chromium Browser]
    end
    
    subgraph "Application Layer"
        PYTHON[Python 3.12+]
        CLI_APP[Click CLI]
        DOM_LIB[DOM Indexer]
        CONTEXT_LIB[Context Builder]
    end
    
    subgraph "Infrastructure"
        YAML_CONFIG[YAML Config]
        JSON_SCHEMA[JSON Schema]
        ARTIFACTS[Artifacts Storage]
    end
    
    GEMINI --> PYTHON
    ADK --> PYTHON
    PLAYWRIGHT --> CHROMIUM
    PYTHON --> CLI_APP
    CLI_APP --> DOM_LIB
    CLI_APP --> CONTEXT_LIB
    CLI_APP --> PLAYWRIGHT
    
    YAML_CONFIG --> CLI_APP
    JSON_SCHEMA --> CLI_APP
    CLI_APP --> ARTIFACTS
    
    style GEMINI fill:#9b59b6,color:#fff
    style PLAYWRIGHT fill:#2ecc71,color:#fff
    style PYTHON fill:#3498db,color:#fff
```

---

## Deployment Options

```mermaid
graph TB
    subgraph "Local Development"
        LOCAL[Local Machine]
        LOCAL --> VENV[Python venv]
        VENV --> RUN[Run Tests]
    end
    
    subgraph "CI/CD"
        GH[GitHub Actions]
        GL[GitLab CI]
        JENKINS[Jenkins]
        
        GH --> DOCKER
        GL --> DOCKER
        JENKINS --> DOCKER
    end
    
    subgraph "Cloud"
        DOCKER[Docker Container]
        DOCKER --> CHROME[Headless Chrome]
        DOCKER --> RESULTS[Artifacts Upload]
    end
    
    style LOCAL fill:#3498db,color:#fff
    style DOCKER fill:#2ecc71,color:#fff
    style RESULTS fill:#f39c12,color:#fff
```

---

## Key Design Decisions

### 1. Why Multiple Modes?
- **Function Tools**: Best for stable, deterministic tests
- **Static NL**: Fast AI-powered test generation
- **Dynamic NL**: Maximum adaptability for complex UIs
- **Computer Use**: Vision-based fallback

### 2. Why DOM Indexer?
- Faster than HTML parsing
- Priority-sorted selectors
- Free (no API calls)
- Deterministic results

### 3. Why Context Builder?
- Reduces AI hallucination
- Intent-aware examples
- Best practices included
- Better than raw HTML

### 4. Why Gemini 2.5-flash?
- 15 RPM quota (vs 10 for 2.0-exp)
- Stable release
- Good cost/performance balance
- Function calling support

---

## License

MIT License - See [LICENSE](LICENSE) file
