Absolutely. Here is a **copy-paste-ready, portfolio-quality `README.md`** for your deployed **datta.ai** project.

````markdown
# datta.ai — AI Research Agent

<p align="center">
  <strong>Evidence-based AI-powered research assistant with web search, source credibility analysis, and structured research reports.</strong>
</p>

<p align="center">
  <a href="https://datta-ai-gkp48r6cwrmrkft7rfgxk7.streamlit.app/">
    <strong>🚀 Live Demo</strong>
  </a>
</p>

---

## 📌 Overview

**datta.ai** is an AI-powered research agent designed to transform a research question into a structured, evidence-based report.

Instead of simply generating an answer from an LLM's internal knowledge, datta.ai performs web research, evaluates available sources, organizes evidence, and produces a structured research report with citations.

The application combines:

- 🤖 Large Language Models
- 🔎 Real-time web search
- 📚 Evidence collection
- 🧠 LangGraph-based research workflow
- 📊 Source credibility analysis
- 📝 Structured report generation
- 🔐 User authentication
- 💾 Research history
- ☁️ Streamlit Cloud deployment

---

## 🚀 Live Demo

**Try datta.ai:**

https://datta-ai-gkp48r6cwrmrkft7rfgxk7.streamlit.app/

---

## ✨ Key Features

### 🔎 AI-Powered Web Research

Enter a research question and datta.ai searches the web for relevant information before generating the final answer.

Example:

> How has generative AI changed software developer productivity from 2023 to 2026?

The system searches for relevant sources and uses the collected evidence during report generation.

---

### 🧠 Agentic Research Workflow

The research process is implemented using **LangGraph**.

The workflow coordinates multiple stages including:

```text
Research Question
       ↓
Research Planning
       ↓
Web Search
       ↓
Source Collection
       ↓
Source Evaluation
       ↓
Evidence Analysis
       ↓
Claim Verification
       ↓
Report Synthesis
       ↓
Final Research Report
````

This makes the application more structured than a simple single-prompt chatbot.

---

### 📚 Source Credibility Analysis

datta.ai does more than collect search results.

Sources are evaluated using signals such as:

* Domain type
* Source category
* Primary vs secondary source
* Domain reputation
* Recency
* Query relevance
* Source specificity
* Evidence quality
* Source diversity

The system uses these signals to prioritize stronger sources during research.

---

### 📝 Structured Research Reports

The final response is organized into sections such as:

* Executive Summary
* Key Findings
* Benefits / Positive Effects
* Limitations / Risks
* Evidence
* Sources

This makes the generated research easier to read and use for academic, technical, and professional research.

---

### 🔗 Citations and Sources

Research results include source information so users can inspect the evidence behind the generated report.

The application attempts to connect claims with supporting sources rather than presenting unsupported statements as facts.

---

### 👤 User Authentication

datta.ai includes a local authentication system with:

* Account creation
* Sign in
* Password hashing
* Guest access
* Session management
* User-specific research history

Passwords are not stored as plaintext.

Password hashing uses:

```text
PBKDF2-HMAC-SHA256
120,000 iterations
```

---

### 💾 Research History

Authenticated users can save and revisit previous research.

The application supports:

* Viewing previous research
* Opening saved research
* Deleting individual research
* Deleting all saved research
* User-specific history

---

### 🛡️ Error Handling and Logging

The backend includes centralized application error handling and logging.

The project defines application-specific exceptions for:

```text
DattaAIError
├── ConfigurationError
├── LLMError
├── SearchError
└── ResearchError
```

Logging includes:

* LLM request lifecycle
* Web search lifecycle
* Research workflow events
* Application errors

Sensitive API-key patterns are redacted from logs.

---

## 🏗️ Architecture

```text
                         ┌──────────────────┐
                         │      User        │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Streamlit UI   │
                         │     app.py       │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │    LangGraph     │
                         │ Research Agent   │
                         └────────┬─────────┘
                                  │
                  ┌───────────────┼────────────────┐
                  │               │                │
                  ▼               ▼                ▼
          ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
          │    Groq      │ │  Web Search  │ │   Evidence   │
          │     LLM      │ │    DDGS      │ │   Analysis   │
          └──────────────┘ └──────────────┘ └──────────────┘
                  │               │                │
                  └───────────────┼────────────────┘
                                  ▼
                         ┌──────────────────┐
                         │ Report Synthesis │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Research Report  │
                         │ + Sources        │
                         └──────────────────┘
```

---

## 🧩 Project Structure

```text
datta-ai/
│
├── app.py
│
├── src/
│   ├── __init__.py
│   ├── agent.py
│   ├── config.py
│   ├── errors.py
│   ├── graph.py
│   ├── llm.py
│   ├── logger.py
│   ├── search.py
│   └── tools.py
│
├── history/
│   ├── architecture.md
│   └── known_issues.md
│
├── .streamlit/
│   └── config.toml
│
├── data/
│   └── datta_ai.db
│
├── logs/
│
├── .env.example
├── .gitignore
├── MANIFEST.txt
├── PROJECT_STATUS.md
├── README.md
└── requirements.txt
```

---

## 🛠️ Technology Stack

| Category             | Technology                |
| -------------------- | ------------------------- |
| Frontend             | Streamlit                 |
| Programming Language | Python 3.12               |
| LLM                  | Groq                      |
| Model                | `openai/gpt-oss-120b`     |
| Agent Framework      | LangGraph                 |
| LLM Framework        | LangChain                 |
| Web Search           | DDGS                      |
| Database             | SQLite                    |
| Configuration        | python-dotenv             |
| Validation           | Pydantic                  |
| Authentication       | PBKDF2-HMAC-SHA256        |
| Deployment           | Streamlit Community Cloud |
| Version Control      | Git + GitHub              |

---

## ⚙️ Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/Tapandat/datta-ai.git
```

```bash
cd datta-ai
```

---

### 2. Create a virtual environment

Windows:

```powershell
python -m venv venv
```

Activate it:

```powershell
.\venv\Scripts\Activate.ps1
```

Linux / macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

---

### 4. Configure environment variables

Create a `.env` file in the project root.

Example:

```env
APP_ENV=development

DEBUG=false

LOG_LEVEL=INFO

GROQ_API_KEY=your_groq_api_key_here

GROQ_MODEL=openai/gpt-oss-120b

GROQ_TEMPERATURE=0.0

SEARCH_MAX_RESULTS=8

MAX_RESEARCH_ROUNDS=1

DATABASE_PATH=data/datta_ai.db

LOG_FILE=logs/datta_ai.log

LOG_MAX_BYTES=5242880

LOG_BACKUP_COUNT=3
```

Never commit your real `.env` file.

---

### 5. Run the application

```bash
streamlit run app.py
```

The application will be available locally at:

```text
http://localhost:8501
```

---

## ☁️ Deployment

datta.ai is deployed using **Streamlit Community Cloud**.

Deployment configuration:

```text
Repository: Tapandat/datta-ai
Branch: main
Entry Point: app.py
Python: 3.12
```

The Groq API key is stored using Streamlit Cloud Secrets rather than being committed to the repository.

---

## 🔐 Environment Variables

| Variable              | Purpose                     |
| --------------------- | --------------------------- |
| `GROQ_API_KEY`        | Groq API authentication     |
| `GROQ_MODEL`          | Active LLM model            |
| `GROQ_TEMPERATURE`    | LLM generation temperature  |
| `APP_ENV`             | Application environment     |
| `DEBUG`               | Debug mode                  |
| `LOG_LEVEL`           | Logging level               |
| `SEARCH_MAX_RESULTS`  | Maximum web search results  |
| `MAX_RESEARCH_ROUNDS` | Research iteration limit    |
| `DATABASE_PATH`       | SQLite database location    |
| `LOG_FILE`            | Log file location           |
| `LOG_MAX_BYTES`       | Maximum log file size       |
| `LOG_BACKUP_COUNT`    | Number of rotated log files |

---

## 🧪 Testing

The project includes validation for the major application components.

Example compilation test:

```bash
python -m py_compile src/config.py src/logger.py src/errors.py src/llm.py src/search.py src/graph.py app.py
```

The following components have been tested during development:

* Configuration loading
* Groq LLM connection
* Web search
* Research graph compilation
* Research execution
* Report generation
* Streamlit UI
* Authentication
* Research history
* Error handling
* Logging

---

## 🔄 Research Pipeline

A typical research request follows this process:

```text
1. User enters research question
              ↓
2. Research planning
              ↓
3. Search query generation
              ↓
4. Web search
              ↓
5. Source classification
              ↓
6. Credibility evaluation
              ↓
7. Evidence extraction
              ↓
8. Claim/source matching
              ↓
9. Evidence confidence analysis
              ↓
10. Final report synthesis
              ↓
11. Sources and citations
```

---

## 📊 Source Evaluation

The search component considers several characteristics when processing sources.

### Source Type

Examples include:

```text
Government
Academic
Research Organization
News
Technology
Commercial
General Website
```

### Evidence Signals

The system considers:

```text
Source relevance
Source credibility
Source specificity
Source recency
Primary-source availability
Source diversity
```

These signals help the research workflow distinguish between different types of web sources.

---

## 🔒 Security Considerations

The project follows several security practices:

* API keys are stored outside source code.
* `.env` is excluded from Git.
* Streamlit secrets are not committed.
* Virtual environments are excluded.
* Local databases are excluded from Git.
* Logs are excluded from Git.
* Common credential and certificate files are ignored.
* API-key patterns are redacted from application logs.
* Passwords are hashed rather than stored directly.

---

## ⚠️ Current Limitations

datta.ai is a portfolio/research project and has several limitations.

### Web Search Dependency

Research quality depends partly on the availability and quality of web search results.

### LLM Dependency

The quality of generated reports depends on the configured LLM and the evidence supplied to it.

### Source Evaluation

Source credibility scoring uses heuristic signals. It should not be treated as a definitive measure of source reliability.

### SQLite Persistence

The current application uses SQLite for local user and research history.

For a larger production deployment, a managed database such as PostgreSQL would be more appropriate.

### Authentication

The current authentication system is designed for this project and demonstration environment. A production-scale application would require additional identity, session, rate-limiting, and security controls.

---

## 🚧 Future Improvements

Potential future enhancements include:

* [ ] PostgreSQL-based persistent storage
* [ ] Production-grade authentication
* [ ] OAuth providers
* [ ] Background research jobs
* [ ] Research result export to PDF
* [ ] Research result export to Markdown
* [ ] More advanced citation verification
* [ ] Multi-agent research workflows
* [ ] Improved source credibility modeling
* [ ] Semantic source clustering
* [ ] Research comparison mode
* [ ] Long-term research projects
* [ ] User-configurable research depth
* [ ] More LLM provider options
* [ ] Automated evaluation benchmarks
* [ ] Unit and integration test suite
* [ ] Docker deployment
* [ ] Cloud database integration

---

## 🎯 Why I Built This

The goal of datta.ai is to explore how modern AI agent architectures can move beyond simple question-answering systems.

The project focuses on combining:

```text
LLMs
+
Web Search
+
Agentic Workflows
+
Evidence Analysis
+
Source Credibility
+
Structured Report Generation
```

into a single research workflow.

---

## 👨‍💻 Author

**Tapan Datta**

B.Tech Computer Science Engineering

GitHub:

[https://github.com/Tapandat](https://github.com/Tapandat)

---

## ⭐ Project

If you find the project useful or interesting, consider giving the repository a ⭐ on GitHub.

**Live Application:**

[https://datta-ai-gkp48r6cwrmrkft7rfgxk7.streamlit.app/](https://datta-ai-gkp48r6cwrmrkft7rfgxk7.streamlit.app/)

**GitHub Repository:**

[https://github.com/Tapandat/datta-ai](https://github.com/Tapandat/datta-ai)

````

### After replacing `README.md`

Run:

```powershell
git add README.md
git commit -m "Improve project documentation"
git push
````

That will update the **`datta-ai` GitHub repository** with the portfolio-ready README.
