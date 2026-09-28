
"""TypeSafe client adapter used by the JEV Codex tool gate.

This module provides the infrastructure boundary between the application
and the official TypeSafe Python SDK.

Higher application layers must not depend directly on the TypeSafe SDK.
They communicate with TypeSafe through ``JevClient``.

Responsibilities:
- Create and configure the official TypeSafe client.
- Execute System One requests.
- Apply the application's configured Jev model per request.
- Translate SDK failures into application exceptions.
- Keep TypeSafe credentials isolated from the rest of the application.
- Support dependency injection for deterministic unit testing.
- Manage the lifecycle of the underlying SDK HTTP client.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from typesafe_sdk import (
    TypeSafeAPIConnectionError,
    TypeSafeAPIResponseValidationError,
    TypeSafeAPITimeoutError,
    TypeSafeAPIError,
    TypeSafeAuthenticationError,
    TypeSafeClient,
    TypeSafeError,
)

from jev_plugin.config import Settings
from jev_plugin.core import (
    JevAuthenticationError,
    JevConnectionError,
    JevPluginError,
    JevRequestError,
    JevResponseError,
)


class JevClient:
    """Application adapter around the official TypeSafe Python SDK.

    ``JevClient`` owns the SDK client and exposes only application-level
    operations to higher layers.

    The SDK client can either be created internally or injected through
    ``sdk_client``. Dependency injection is primarily useful for unit tests
    and for application-level lifecycle management.
    """

    def __init__(
        self,
        settings: Settings,
        sdk_client: TypeSafeClient | None = None,
    ) -> None:
        """Initialize the Jev client adapter.

        Args:
            settings: Application runtime configuration.
            sdk_client: Optional pre-created TypeSafe SDK client.

        Raises:
            JevAuthenticationError: If TypeSafe authentication configuration
                is invalid.
            JevPluginError: If the SDK client cannot be initialized.
        """
        self._settings = settings
        self._closed = False

        if sdk_client is not None:
            self._client = sdk_client
            return

        try:
            self._client = TypeSafeClient(
                api_key=settings.typesafe_api_key.get_secret_value(),
            )
        except TypeSafeAuthenticationError as exc:
            raise JevAuthenticationError(
                "Unable to initialize the TypeSafe client because "
                "authentication configuration is invalid.",
                cause=exc,
            ) from exc
        except TypeSafeError as exc:
            raise JevPluginError(
                "Unable to initialize the TypeSafe client.",
                cause=exc,
            ) from exc
        except Exception as exc:
            self._raise_client_initialization_error(exc)

    @property
    def model(self) -> str:
        """Return the configured Jev model name."""
        return self._settings.typesafe_model

    @property
    def is_closed(self) -> bool:
        """Return whether the Jev client has been closed."""
        return self._closed

    def evaluate(
        self,
        *,
        state: Any,
        questions: Mapping[str, Any],
    ) -> Any:
        """Evaluate a System One request through Jev.

        Args:
            state: State supplied to TypeSafe System One.
            questions: Named Jev questions to evaluate.

        Returns:
            The raw TypeSafe System One response.

        Raises:
            JevRequestError: If the request is invalid.
            JevAuthenticationError: If TypeSafe authentication fails.
            JevConnectionError: If the TypeSafe API cannot be reached.
            JevResponseError: If TypeSafe returns an invalid response.
            JevPluginError: If an unexpected SDK failure occurs.
        """
        if not questions:
            raise JevRequestError(
                "At least one Jev question is required."
            )

        if self._closed:
            raise JevPluginError(
                "The Jev client has already been closed."
            )

        try:
            return self._client.system_one(
                state=state,
                questions=dict(questions),
                model=self._settings.typesafe_model,
            )
        except TypeSafeAuthenticationError as exc:
            raise JevAuthenticationError(
                "TypeSafe authentication failed.",
                cause=exc,
            ) from exc
        except TypeSafeAPITimeoutError as exc:
            raise JevConnectionError(
                "The TypeSafe API request timed out.",
                cause=exc,
            ) from exc
        except TypeSafeAPIConnectionError as exc:
            raise JevConnectionError(
                "Unable to communicate with the TypeSafe API.",
                cause=exc,
            ) from exc
        except TypeSafeAPIResponseValidationError as exc:
            raise JevResponseError(
                "TypeSafe returned an invalid response.",
                cause=exc,
            ) from exc
        except TypeSafeAPIError as exc:
            self._raise_api_error(exc)
        except TypeSafeError as exc:
            raise JevPluginError(
                "The TypeSafe Jev request failed.",
                cause=exc,
            ) from exc
        except Exception as exc:
            self._raise_request_error(exc)

    def close(self) -> None:
        """Release the underlying TypeSafe SDK resources.

        ``close()`` is idempotent so application shutdown code can safely
        call it more than once.
        """
        if self._closed:
            return

        try:
            self._client.close()
        finally:
            self._closed = True

    def __enter__(self) -> JevClient:
        """Enter a Jev client context."""
        if self._closed:
            raise JevPluginError(
                "Cannot enter a closed Jev client."
            )

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        """Close the Jev client when leaving a context."""
        self.close()

    @staticmethod
    def _raise_api_error(exc: TypeSafeAPIError) -> None:
        """Translate a typed TypeSafe API error."""
        if isinstance(exc, TypeSafeAuthenticationError):
            raise JevAuthenticationError(
                "TypeSafe authentication failed.",
                cause=exc,
            ) from exc

        status = getattr(exc, "status", None)

        if status in {401, 403}:
            raise JevAuthenticationError(
                "TypeSafe authentication or authorization failed.",
                cause=exc,
            ) from exc

        if status == 422:
            raise JevRequestError(
                "The TypeSafe API rejected the Jev request.",
                cause=exc,
            ) from exc

        if status == 400:
            raise JevRequestError(
                "The TypeSafe API rejected the Jev request.",
                cause=exc,
            ) from exc

        if status == 429:
            raise JevRequestError(
                "The TypeSafe API rate limit was exceeded.",
                cause=exc,
            ) from exc

        if status is not None and status >= 500:
            raise JevConnectionError(
                "The TypeSafe API returned a server error.",
                cause=exc,
            ) from exc

        raise JevRequestError(
            "The TypeSafe API rejected the Jev request.",
            cause=exc,
        ) from exc

    @staticmethod
    def _raise_client_initialization_error(exc: Exception) -> None:
        """Translate an SDK client initialization failure."""
        message = str(exc).strip()
        normalized_message = message.lower()

        if (
            "api key" in normalized_message
            or "authentication" in normalized_message
            or "credential" in normalized_message
        ):
            raise JevAuthenticationError(
                "Unable to initialize the TypeSafe client because "
                "authentication configuration is invalid.",
                cause=exc,
            ) from exc

        raise JevPluginError(
            "Unable to initialize the TypeSafe client.",
            cause=exc,
        ) from exc

    @staticmethod
    def _raise_request_error(exc: Exception) -> None:
        """Translate an unexpected SDK/request exception.

        This fallback exists for defensive compatibility. Typed exceptions
        from the official SDK are handled before this method.
        """
        message = str(exc).strip()
        normalized_message = message.lower()

        if (
            "authentication" in normalized_message
            or "api key" in normalized_message
            or "unauthorized" in normalized_message
            or "401" in normalized_message
        ):
            raise JevAuthenticationError(
                "TypeSafe authentication failed.",
                cause=exc,
            ) from exc

        if (
            "connection" in normalized_message
            or "timeout" in normalized_message
            or "timed out" in normalized_message
            or "network" in normalized_message
        ):
            raise JevConnectionError(
                "Unable to communicate with the TypeSafe API.",
                cause=exc,
            ) from exc

        if (
            "response" in normalized_message
            or "answers" in normalized_message
            or "schema" in normalized_message
        ):
            raise JevResponseError(
                "TypeSafe returned an invalid response.",
                cause=exc,
            ) from exc

        if (
            "invalid" in normalized_message
            or "validation" in normalized_message
            or "request" in normalized_message
            or "question" in normalized_message
        ):
            raise JevRequestError(
                "The TypeSafe API rejected the Jev request.",
                cause=exc,
            ) from exc

        raise JevPluginError(
            "The TypeSafe Jev request failed.",
            cause=exc,
        ) from exc
