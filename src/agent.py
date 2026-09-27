from src.llm import llm
from src.tools import search_web


tools = [search_web]
llm_with_tools = llm.bind_tools(tools)


def run_agent(question: str) -> str:
    """Run the backward-compatible tool-calling agent."""

    messages = [
        {
            "role": "user",
            "content": question,
        }
    ]

    while True:
        response = llm_with_tools.invoke(messages)

        messages.append(response)

        if response.tool_calls:

            for tool_call in response.tool_calls:

                if tool_call["name"] == "search_web":

                    result = search_web.invoke(
                        tool_call["args"]
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "content": result,
                            "tool_call_id": tool_call["id"],
                        }
                    )

        else:

            if isinstance(
                response.content,
                str,
            ):
                return response.content

            return "".join(
                block.get("text", "")
                for block in response.content
                if isinstance(block, dict)
            )
