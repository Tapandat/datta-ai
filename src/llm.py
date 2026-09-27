"""LLM configuration and helper functions for datta.ai."""

from langchain_groq import ChatGroq

from src.config import settings
from src.errors import LLMError
from src.logger import get_logger


logger = get_logger("llm")


# ============================================================
# Configuration Validation
# ============================================================

def _validate_configuration() -> None:
    """Validate the minimum configuration required by the LLM."""

    if not settings.groq_api_key:
        raise LLMError(
            "GROQ_API_KEY is not configured.",
            user_message=(
                "The AI service is not configured correctly. "
                "Please check the application configuration."
            ),
        )

    if settings.groq_api_key.lower().startswith("your_"):
        raise LLMError(
            "GROQ_API_KEY contains a placeholder value.",
            user_message=(
                "The AI service is not configured correctly. "
                "Please check the application configuration."
            ),
        )


_validate_configuration()


# ============================================================
# LLM Instance
# ============================================================

llm = ChatGroq(
    model=settings.groq_model,
    temperature=settings.groq_temperature,
    api_key=settings.groq_api_key,
)


# ============================================================
# Response Helpers
# ============================================================

def get_response_text(response) -> str:
    """Convert a LangChain response into plain text."""

    content = getattr(
        response,
        "content",
        "",
    )

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []

        for block in content:
            if isinstance(block, dict):
                text_parts.append(
                    str(block.get("text", ""))
                )
            else:
                text_parts.append(
                    str(block)
                )

        return "".join(text_parts)

    return str(content)


# ============================================================
# LLM Request
# ============================================================

def ask_llm(question: str) -> str:
    """Send one request to the configured LLM.

    Args:
        question: User's question or prompt.

    Returns:
        Plain-text LLM response.

    Raises:
        LLMError: If the request cannot be completed.
    """

    if not question or not question.strip():
        raise LLMError(
            "LLM request received an empty question.",
            user_message=(
                "Please enter a research question."
            ),
        )

    cleaned_question = question.strip()

    logger.info(
        "LLM request started | model=%s | question_length=%d",
        settings.groq_model,
        len(cleaned_question),
    )

    try:
        response = llm.invoke(
            cleaned_question
        )

        response_text = get_response_text(
            response
        ).strip()

        if not response_text:
            logger.error(
                "LLM returned an empty response."
            )

            raise LLMError(
                "LLM returned an empty response.",
                user_message=(
                    "The AI service returned an empty response. "
                    "Please try again."
                ),
            )

        logger.info(
            "LLM request completed | response_length=%d",
            len(response_text),
        )

        return response_text

    except LLMError:
        logger.exception(
            "LLM request failed with application error."
        )
        raise

    except Exception as exc:
        logger.exception(
            "LLM provider request failed | error_type=%s",
            type(exc).__name__,
        )

        raise LLMError(
            "LLM provider request failed.",
            user_message=(
                "The AI service could not complete the request. "
                "Please try again in a moment."
            ),
        ) from exc


# ============================================================
# Backward Compatibility
# ============================================================

def ask_gemini(question: str) -> str:
    """Backward-compatible wrapper.

    The project previously used Gemini. Existing code can continue
    calling ask_gemini() while the active provider remains Groq.
    """

    return ask_llm(question)