datta.ai

AI-powered research agent that searches the web, evaluates evidence, and turns a research question into a structured report.






🚀 Live Application

Open datta.ai →

Ask a research question, let the agent gather web evidence, and receive a structured report with sources.

🧠 What is datta.ai?

datta.ai is a research-focused AI agent built to go beyond a conventional chatbot.

A normal LLM response can rely heavily on information already present in the model. datta.ai instead follows a research workflow:

Question → Search → Evidence → Source Evaluation → Synthesis → Report

The application combines an LLM with web search and a LangGraph workflow to investigate questions and organize the resulting evidence into a readable research report.

✨ Core Capabilities

Capability

What it does

🔎 Web Research

Searches the web for information relevant to the research question

🧠 Agentic Workflow

Uses LangGraph to coordinate the research process

📚 Evidence Collection

Collects and structures information from multiple sources

🛡️ Source Evaluation

Uses source metadata and credibility signals during research

🔗 Claim–Source Matching

Connects research claims with supporting evidence

📝 Report Synthesis

Produces a structured final research report

👤 Authentication

Supports account creation, sign-in, and guest access

💾 Research History

Allows users to save and revisit previous research

🧹 History Management

Supports deleting individual or all saved research

☁️ Cloud Deployment

Deployed on Streamlit Community Cloud

🔐 Secret Management

Keeps API credentials outside the Git repository

🏗️ How It Works

                         ┌─────────────────────┐
                         │    User Question    │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Research Agent    │
                         │     LangGraph       │
                         └──────────┬──────────┘
                                    │
                     ┌──────────────┼──────────────┐
                     │              │              │
                     ▼              ▼              ▼
               ┌──────────┐  ┌────────────┐  ┌─────────────┐
               │   Groq   │  │ Web Search │  │   Evidence  │
               │   LLM    │  │   (DDGS)   │  │  Evaluation │
               └────┬─────┘  └─────┬──────┘  └──────┬──────┘
                    │              │                │
                    └──────────────┼────────────────┘
                                   ▼
                         ┌─────────────────────┐
                         │  Evidence Synthesis │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Structured Research│
                         │       Report       │
                         └─────────────────────┘

🔬 Research Pipeline

The research workflow is designed around multiple stages rather than a single LLM prompt.

1. Research Question

The user enters a question through the Streamlit interface.

2. Research Planning

The agent determines how the question should be investigated.

3. Web Search

The search layer retrieves relevant web sources.

4. Source Analysis

Retrieved sources are processed using signals including:

Domain/source type

Primary vs. secondary source

Domain reputation heuristics

Recency

Query relevance

Specificity

Source diversity

5. Evidence Analysis

The workflow evaluates the collected information and connects claims with relevant supporting sources.

6. Report Generation

The LLM synthesizes the researched evidence into a structured response.

📄 Report Format

A typical research report contains sections such as:

Executive Summary
Key Findings
Benefits / Positive Effects
Limitations / Risks
Evidence
Sources

The output is designed to be useful for:

Technical research

Academic exploration

Industry research

Current-topic investigation

Interview preparation

Project research

🛠️ Technology Stack

Application

Python 3.12

Streamlit

LangChain

LangGraph

AI

Groq

openai/gpt-oss-120b

Search

DDGS

Storage

SQLite

Configuration & Validation

python-dotenv

Pydantic

Version Control & Deployment

Git

GitHub

Streamlit Community Cloud

📁 Project Structure

datta-ai/
│
├── app.py
├── requirements.txt
├── README.md
├── PROJECT_STATUS.md
├── MANIFEST.txt
├── .env.example
├── .gitignore
│
├── .streamlit/
│   └── config.toml
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
├── data/
│   └── datta_ai.db
│
└── logs/

data/, logs/, .env, and other local/runtime files are excluded from version control where appropriate.

🔐 Security

API credentials are deliberately kept outside the Git repository.

Local development

Use a .env file:

GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
GROQ_TEMPERATURE=0.0

Streamlit Cloud

The deployed application reads the Groq credential from Streamlit Secrets.

The real API key is not stored in GitHub.

The repository contains only:

.env.example

with placeholder configuration.

⚙️ Run Locally

1. Clone

git clone https://github.com/Tapandat/datta-ai.git
cd datta-ai

2. Create virtual environment

Windows:

python -m venv venv
.env\Scripts\Activate.ps1

Linux/macOS:

python3 -m venv venv
source venv/bin/activate

3. Install dependencies

python -m pip install -r requirements.txt

4. Configure environment

Create .env:

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

5. Start the application

streamlit run app.py

Open:

http://localhost:8501

🧪 Validation

The application components can be checked with:

python -m py_compile src/config.py src/logger.py src/errors.py src/llm.py src/search.py src/graph.py app.py

The development workflow also validates:

Configuration loading

Groq connectivity

Web search

Research graph compilation

Research execution

Report generation

Streamlit UI

Authentication

Research history

Error handling

Logging

📊 Source Credibility

datta.ai does not treat every search result as equivalent.

The search layer extracts metadata and uses heuristic signals to help rank sources.

Examples of source categories include:

Government
Academic / Research
News
Technology
Commercial
General Web

Additional signals include:

Relevance
Recency
Specificity
Source type
Primary-source preference
Domain reputation
Source diversity

These are heuristics, not a guarantee that a source is objectively correct.

Users should still inspect the original sources before relying on important information.

💡 Design Principles

Evidence before synthesis

The agent first gathers information and then generates the final report.

Separation of responsibilities

The project separates:

UI
Configuration
LLM
Search
Tools
Research Graph
Logging
Error Handling

This keeps the application modular and easier to maintain.

Secure configuration

Secrets are separated from source code.

Deployment readiness

The same configuration system supports local .env usage and Streamlit Cloud secrets.

⚠️ Limitations

datta.ai is a portfolio/research project and should not be treated as an authoritative source by itself.

Search limitations

Web search availability and result quality can affect the research output.

LLM limitations

Generated text can contain errors or incomplete interpretations even when sources are provided.

Credibility heuristics

Source scoring is based on heuristic signals and should not be interpreted as a definitive measure of truthfulness.

Current storage

The current implementation uses SQLite. A larger production deployment would benefit from a managed database such as PostgreSQL.

Authentication

The current authentication implementation is designed for this project/demo environment and would require additional controls for a large-scale production service.

🚀 Future Roadmap

□ PostgreSQL / managed database
□ Production-grade authentication
□ OAuth providers
□ PDF / Markdown report export
□ Advanced citation verification
□ Semantic source clustering
□ Multi-agent research
□ Research comparison mode
□ User-configurable research depth
□ Additional LLM providers
□ Automated evaluation benchmarks
□ Docker deployment
□ Background research jobs

🎯 Project Goal

The project explores how an AI application can move from:

"Ask an LLM a question"

towards:

"Investigate the question,
collect evidence,
evaluate sources,
connect claims to evidence,
and synthesize a structured report."

The focus is on combining LLMs + web search + agentic workflows + evidence analysis + structured reporting in a deployable application.

👨‍💻 Author

Tapan Datta

B.Tech — Computer Science Engineering

GitHub:
https://github.com/Tapandat

Project:
https://github.com/Tapandat/datta-ai

Live Demo:
https://datta-ai-gkp48r6cwrmrkft7rfgxk7.streamlit.app/

⭐ Try It

🚀 Launch datta.ai

If you find the project interesting, feel free to explore the repository and ⭐ the project.
