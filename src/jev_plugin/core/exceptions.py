"""Application-specific exception hierarchy.

This module defines the exception boundary for the Jev plugin.

Third-party exceptions from the TypeSafe SDK, HTTP libraries, validation
libraries, or MCP framework should not leak directly into higher-level
application layers.

Infrastructure components should translate those exceptions into the
appropriate application-specific exception defined here.
"""


class JevPluginError(Exception):
    """Base exception for all Jev plugin application errors.

    Args:
        message: Human-readable description of the failure.
        cause: Optional underlying exception that caused the failure.
    """

    def __init__(
        self,
        message: str,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause


class JevConfigurationError(JevPluginError):
    """Raised when application configuration is invalid."""


class JevAuthenticationError(JevPluginError):
    """Raised when authentication with TypeSafe fails."""


class JevConnectionError(JevPluginError):
    """Raised when communication with TypeSafe cannot be established."""


class JevRequestError(JevPluginError):
    """Raised when TypeSafe rejects or cannot process a request."""


class JevResponseError(JevPluginError):
    """Raised when the TypeSafe response is missing or invalid."""


