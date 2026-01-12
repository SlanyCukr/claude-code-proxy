"""Custom exception hierarchy for the Claude Code proxy."""


class ProxyError(Exception):
    """Base exception for all proxy errors."""


class ConfigurationError(ProxyError):
    """Raised when configuration is missing or invalid."""


class UpstreamError(ProxyError):
    """Raised when an upstream provider returns an error.

    Attributes:
        message: Error message
        status_code: HTTP status code from upstream (optional)
        provider: Upstream provider name (e.g., 'anthropic', 'zai')
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        provider: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider = provider


class UpstreamTimeoutError(UpstreamError):
    """Raised when an upstream provider request times out."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
    ) -> None:
        super().__init__(message, status_code=None, provider=provider)


class UpstreamConnectionError(UpstreamError):
    """Raised when unable to connect to an upstream provider."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
    ) -> None:
        super().__init__(message, status_code=None, provider=provider)


class RequestTooLarge(ProxyError):
    """Request body exceeds size limit."""


class InvalidJSON(ProxyError):
    """Request body is not valid JSON."""
