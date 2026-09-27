"""Application-specific exceptions for datta.ai."""


class DattaAIError(Exception):
    """Base exception for expected datta.ai application errors."""

    def __init__(self, message: str, *, user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or message


class ConfigurationError(DattaAIError):
    """Raised when application configuration is invalid or incomplete."""


class LLMError(DattaAIError):
    """Raised when an LLM request fails."""


class SearchError(DattaAIError):
    """Raised when web search fails."""


class ResearchError(DattaAIError):
    """Raised when the research workflow cannot complete."""