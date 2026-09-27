# datta.ai — AI Research Agent

Complete project snapshot: 26 September 2026.

## Current architecture

User question
    ↓
Deterministic research planning
    ↓
Parallel web search
    ↓
Source credibility scoring
    ↓
Groq structured evidence verification
    ↓
Targeted deep research when evidence is weak
    ↓
Final evidence-grounded report
    ↓
Evidence Quality + Sources

## Main technologies

- Python
- Streamlit
- LangGraph
- LangChain
- Groq
- openai/gpt-oss-120b
- DDGS web search
- Pydantic structured output

## Important security note

The real `.env` file and API keys are intentionally NOT included.
Copy `.env.example` to `.env` and add your own GROQ_API_KEY.

The `venv/` directory is also intentionally not included because it
contains installed third-party packages and is recreated with pip.

## Current known state

The Streamlit interface is working and reaches the research report.
The previous failure where Groq evidence verification produced zero
claims was caused by manually parsing model-generated JSON.

The latest `src/graph.py` replaces that approach with Groq structured
JSON Schema output and deterministic evidence guardrails.

## Important compatibility fix

`Send` must be imported from:

    from langgraph.types import Send

while `END`, `START`, and `StateGraph` come from:

    from langgraph.graph import END, START, StateGraph

## Run

Activate the virtual environment:

    .\venv\Scripts\Activate.ps1

Install dependencies:

    python -m pip install -r requirements.txt

Start Streamlit:

    python -m streamlit run app.py

Open:

    http://localhost:8501
