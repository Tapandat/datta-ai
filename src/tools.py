import json

from langchain_core.tools import tool

from src.search import web_search


@tool
def search_web(query: str) -> str:
    """Search the web for current information and return structured source metadata."""
    results = web_search(query)

    if not results:
        return json.dumps(
            {
                "query": query,
                "sources": [],
            }
        )

    return json.dumps(
        {
            "query": query,
            "sources": results,
        },
        ensure_ascii=False,
    )
