# Known issues and fixes

## Gemini quota

The older implementation used Gemini and eventually hit a free-tier
429 RESOURCE_EXHAUSTED error for gemini-3.7-flash.

The project was migrated to Groq to avoid depending on that Gemini
quota.

## LangGraph Send import

Incorrect:

    from langgraph.graph import END, START, Send, StateGraph

Correct:

    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Send

## Blank Streamlit page

The old app used terminal `input()` and was therefore inappropriate
as a Streamlit application.

The current app.py is a Streamlit UI.

## Zero verified claims

The previous verifier asked the model to manually return JSON and then
parsed the response. Groq output could not always be parsed, resulting
in zero verified claims.

The current graph uses Pydantic + Groq JSON Schema structured output
instead.
