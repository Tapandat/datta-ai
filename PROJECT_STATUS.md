# Project Status — 26 September 2026

## Completed

1. Created the AI Research Agent project.
2. Set up a Python virtual environment.
3. Added LangChain and LangGraph.
4. Added DDGS web search.
5. Added source normalization and metadata.
6. Added source-type classification.
7. Added source-level classification.
8. Added domain reputation heuristics.
9. Added recency scoring.
10. Added specificity scoring.
11. Added credibility scoring.
12. Added source IDs.
13. Added evidence verification.
14. Added deterministic quote validation.
15. Added numeric claim validation.
16. Added citation validation.
17. Added Evidence Quality output.
18. Added Sources output.
19. Added weak-claim detection.
20. Added deterministic follow-up query generation.
21. Added deep research.
22. Hit the Gemini free-tier quota while the older graph still used Gemini.
23. Migrated the LLM layer to Groq.
24. Confirmed `openai/gpt-oss-120b` works through Groq.
25. Fixed the LangGraph `Send` import.
26. Built the Streamlit interface.
27. Fixed the blank Streamlit page caused by the old CLI `input()`.
28. Added live Streamlit progress reporting.
29. Identified the zero-verified-claims issue.
30. Prepared a structured-output verification implementation.

## Current implementation

`src/graph.py` is the newest structured-output version.

`backup_versions/graph_previous.py` preserves the previous graph version
so earlier work is not lost.

## Deliberately excluded

- `.env`
- API keys
- `venv/`
- `__pycache__/`
- compiled `.pyc` files

These are environment/secrets rather than source files.

## Next test

Run:

    python -c "from src.graph import research_graph; print('GRAPH OK')"

Then:

    python -m streamlit run app.py

Use the Streamlit UI and observe the verification stage.
