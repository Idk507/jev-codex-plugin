
"""Unit tests for the TypeSafe Jev client adapter.

The tests in this module exercise the application boundary around the
official TypeSafe Python SDK without making network requests.

Coverage includes:

- SDK client initialization.
- API-key propagation.
- Dependency injection.
- Configured model propagation.
- System One request forwarding.
- Empty-question validation.
- Mapping conversion.
- Successful evaluation.
- Typed SDK exception translation.
- HTTP status-based API error translation.
- Generic fallback exception translation.
- Exception chaining through ``cause``.
- Secret non-disclosure.
- Client lifecycle management.
- Idempotent closing.
- Context-manager behavior.
- Closed-client protection.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from unittest.mock import Mock

import httpx2
import pytest
from pydantic import SecretStr
from typesafe_sdk import (
    TypeSafeAPIConnectionError,
    TypeSafeAPIError,
    TypeSafeAPIResponseValidationError,
    TypeSafeAPITimeoutError,
    TypeSafeAuthenticationError,
)

from jev_plugin.config import Settings
from jev_plugin.core import (
    JevAuthenticationError,
    JevConnectionError,
    JevPluginError,
    JevRequestError,
    JevResponseError,
)
from jev_plugin.typesafe.client import JevClient


def build_settings(
    *,
    api_key: str = "test-api-key",
    model: str = "jev-test-model",
) -> Settings:
    """Create isolated settings without loading the local .env file."""
    return Settings(
        _env_file=None,
        typesafe_api_key=SecretStr(api_key),
        typesafe_model=model,
    )


class FakeTypeSafeClient:
    """Test double matching the relevant TypeSafeClient interface."""

    def __init__(
        self,
        *,
        response: Any = None,
        error: Exception | None = None,
    ) -> None:
        self.response = (
            {"result": "test"}
            if response is None
            else response
        )
        self.error = error
        self.system_one_calls: list[dict[str, Any]] = []
        self.close_calls = 0

    def system_one(
        self,
        *,
        state: Any,
        questions: Mapping[str, Any],
        model: str | None = None,
    ) -> Any:
        """Record the request and return a fake response."""
        self.system_one_calls.append(
            {
                "state": state,
                "questions": dict(questions),
                "model": model,
            }
        )

        if self.error is not None:
            raise self.error

        return self.response

    def close(self) -> None:
        """Record SDK-client closure."""
        self.close_calls += 1


def test_client_initializes_official_sdk_with_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JevClient should initialize the official SDK with the API key."""
    fake_sdk_client = Mock()
    sdk_constructor = Mock(return_value=fake_sdk_client)

    monkeypatch.setattr(
        "jev_plugin.typesafe.client.TypeSafeClient",
        sdk_constructor,
    )

    settings = build_settings(
        api_key="secret-api-key",
        model="jev-custom-model",
    )

    client = JevClient(settings)

    sdk_constructor.assert_called_once_with(
        api_key="secret-api-key",
    )

    assert client.model == "jev-custom-model"
    assert client.is_closed is False


def test_client_uses_injected_sdk_client() -> None:
    """Dependency injection should use the supplied SDK client."""
    fake_client = FakeTypeSafeClient(
        response={"result": "injected"},
    )

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    response = client.evaluate(
        state="Test state",
        questions={"test": object()},
    )

    assert response == {"result": "injected"}
    assert client._client is fake_client
    assert len(fake_client.system_one_calls) == 1


def test_client_exposes_configured_model() -> None:
    """The configured application model should be exposed."""
    client = JevClient(
        settings=build_settings(
            model="jev-production-model",
        ),
        sdk_client=FakeTypeSafeClient(),
    )

    assert client.model == "jev-production-model"


def test_evaluate_forwards_state_questions_and_model() -> None:
    """Evaluation should forward all request components to System One."""
    fake_client = FakeTypeSafeClient(
        response={"result": "success"},
    )

    client = JevClient(
        settings=build_settings(
            model="jev-production-model",
        ),
        sdk_client=fake_client,
    )

    state = {
        "customer": {
            "age": 31,
            "country": "India",
        }
    }

    questions = {
        "eligibility": object(),
    }

    response = client.evaluate(
        state=state,
        questions=questions,
    )

    assert response == {"result": "success"}

    assert len(fake_client.system_one_calls) == 1

    call = fake_client.system_one_calls[0]

    assert call["state"] == state
    assert call["questions"] == questions
    assert call["model"] == "jev-production-model"


def test_evaluate_copies_questions_before_forwarding() -> None:
    """Evaluation should pass a dictionary copy rather than the original mapping."""
    fake_client = FakeTypeSafeClient()

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    questions = {
        "question": object(),
    }

    client.evaluate(
        state={"value": 1},
        questions=questions,
    )

    forwarded_questions = fake_client.system_one_calls[0]["questions"]

    assert forwarded_questions == questions
    assert forwarded_questions is not questions


def test_evaluate_accepts_mapping_subclasses() -> None:
    """Mapping implementations should be accepted by evaluate()."""

    class CustomMapping(dict[str, Any]):
        """Custom mapping used to verify Mapping compatibility."""

    fake_client = FakeTypeSafeClient()

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    questions = CustomMapping(
        {
            "result": object(),
        }
    )

    client.evaluate(
        state={"value": 1},
        questions=questions,
    )

    forwarded_questions = fake_client.system_one_calls[0]["questions"]

    assert forwarded_questions == questions
    assert type(forwarded_questions) is dict


def test_client_rejects_empty_questions() -> None:
    """Empty question mappings should be rejected before an SDK call."""
    fake_client = FakeTypeSafeClient()

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    with pytest.raises(
        JevRequestError,
        match="At least one Jev question is required",
    ):
        client.evaluate(
            state="Test state",
            questions={},
        )

    assert fake_client.system_one_calls == []


def test_client_rejects_evaluation_after_close() -> None:
    """A closed client must not issue new SDK requests."""
    fake_client = FakeTypeSafeClient()

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    client.close()

    with pytest.raises(
        JevPluginError,
        match="already been closed",
    ):
        client.evaluate(
            state="Test state",
            questions={"test": object()},
        )

    assert fake_client.system_one_calls == []


def test_client_translates_authentication_error() -> None:
    """SDK authentication failures should become JevAuthenticationError."""
    sdk_error = TypeSafeAuthenticationError(
        401,
        {"error": "unauthorized"},
        httpx2.Headers(),
    )

    fake_client = FakeTypeSafeClient(
        error=sdk_error,
    )

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    with pytest.raises(JevAuthenticationError) as exc_info:
        client.evaluate(
            state="Test state",
            questions={"test": object()},
        )

    assert exc_info.value.cause is sdk_error


def test_client_translates_connection_error() -> None:
    """SDK connection failures should become JevConnectionError."""
    sdk_error = TypeSafeAPIConnectionError(
        "connection failed",
    )

    fake_client = FakeTypeSafeClient(
        error=sdk_error,
    )

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    with pytest.raises(JevConnectionError) as exc_info:
        client.evaluate(
            state="Test state",
            questions={"test": object()},
        )

    assert exc_info.value.cause is sdk_error


def test_client_translates_timeout_error() -> None:
    """SDK timeout failures should become JevConnectionError."""
    sdk_error = TypeSafeAPITimeoutError(
        10.0,
    )

    fake_client = FakeTypeSafeClient(
        error=sdk_error,
    )

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    with pytest.raises(JevConnectionError) as exc_info:
        client.evaluate(
            state="Test state",
            questions={"test": object()},
        )

    assert exc_info.value.cause is sdk_error


def test_client_translates_response_validation_error() -> None:
    """Invalid successful responses should become JevResponseError."""
    sdk_error = TypeSafeAPIResponseValidationError(
        200,
        {"answers": None},
        httpx2.Headers(),
        "answers",
    )

    fake_client = FakeTypeSafeClient(
        error=sdk_error,
    )

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    with pytest.raises(JevResponseError) as exc_info:
        client.evaluate(
            state="Test state",
            questions={"test": object()},
        )

    assert exc_info.value.cause is sdk_error


@pytest.mark.parametrize(
    ("status", "expected_exception"),
    [
        (400, JevRequestError),
        (401, JevAuthenticationError),
        (403, JevAuthenticationError),
        (422, JevRequestError),
        (429, JevRequestError),
        (500, JevConnectionError),
        (502, JevConnectionError),
        (503, JevConnectionError),
    ],
)
def test_client_translates_api_status_errors(
    status: int,
    expected_exception: type[JevPluginError],
) -> None:
    """HTTP API failures should map to the corresponding app exception."""
    sdk_error = TypeSafeAPIError(
        status,
        {"error": f"http error {status}"},
        httpx2.Headers(),
    )

    fake_client = FakeTypeSafeClient(
        error=sdk_error,
    )

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    with pytest.raises(expected_exception) as exc_info:
        client.evaluate(
            state="Test state",
            questions={"test": object()},
        )

    assert exc_info.value.cause is sdk_error


def test_client_translates_generic_typesafe_error() -> None:
    """Unexpected TypeSafe SDK errors should become JevPluginError."""
    sdk_error = RuntimeError("unexpected SDK failure")

    fake_client = FakeTypeSafeClient(
        error=sdk_error,
    )

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    with pytest.raises(
        JevPluginError,
        match="The TypeSafe Jev request failed",
    ) as exc_info:
        client.evaluate(
            state="Test state",
            questions={"test": object()},
        )

    assert exc_info.value.cause is sdk_error


def test_client_translates_string_based_authentication_fallback() -> None:
    """Legacy/unexpected authentication messages should still be classified."""
    sdk_error = RuntimeError(
        "authentication failed",
    )

    fake_client = FakeTypeSafeClient(
        error=sdk_error,
    )

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    with pytest.raises(JevAuthenticationError) as exc_info:
        client.evaluate(
            state="Test state",
            questions={"test": object()},
        )

    assert exc_info.value.cause is sdk_error


def test_client_translates_string_based_connection_fallback() -> None:
    """Unexpected connection messages should map to JevConnectionError."""
    sdk_error = RuntimeError(
        "network connection failed",
    )

    fake_client = FakeTypeSafeClient(
        error=sdk_error,
    )

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    with pytest.raises(JevConnectionError) as exc_info:
        client.evaluate(
            state="Test state",
            questions={"test": object()},
        )

    assert exc_info.value.cause is sdk_error


def test_client_translates_string_based_response_fallback() -> None:
    """Unexpected response messages should map to JevResponseError."""
    sdk_error = RuntimeError(
        "response schema validation failed",
    )

    fake_client = FakeTypeSafeClient(
        error=sdk_error,
    )

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    with pytest.raises(JevResponseError) as exc_info:
        client.evaluate(
            state="Test state",
            questions={"test": object()},
        )

    assert exc_info.value.cause is sdk_error


def test_client_translates_string_based_request_fallback() -> None:
    """Unexpected request messages should map to JevRequestError."""
    sdk_error = ValueError(
        "invalid request",
    )

    fake_client = FakeTypeSafeClient(
        error=sdk_error,
    )

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    with pytest.raises(JevRequestError) as exc_info:
        client.evaluate(
            state="Test state",
            questions={"test": object()},
        )

    assert exc_info.value.cause is sdk_error


def test_client_does_not_expose_api_key_in_authentication_error() -> None:
    """Application authentication errors must not expose the API key."""
    api_key = "super-secret-api-key"

    sdk_error = TypeSafeAuthenticationError(
        401,
        {"error": "unauthorized"},
        httpx2.Headers(),
    )

    fake_client = FakeTypeSafeClient(
        error=sdk_error,
    )

    client = JevClient(
        settings=build_settings(
            api_key=api_key,
        ),
        sdk_client=fake_client,
    )

    with pytest.raises(JevAuthenticationError) as exc_info:
        client.evaluate(
            state="Test state",
            questions={"test": object()},
        )

    assert api_key not in str(exc_info.value)
    assert api_key not in repr(exc_info.value)


def test_client_can_be_closed() -> None:
    """Closing the client should close the underlying SDK client."""
    fake_client = FakeTypeSafeClient()

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    assert client.is_closed is False

    client.close()

    assert client.is_closed is True
    assert fake_client.close_calls == 1


def test_client_close_is_idempotent() -> None:
    """Calling close() multiple times should close the SDK only once."""
    fake_client = FakeTypeSafeClient()

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    client.close()
    client.close()
    client.close()

    assert client.is_closed is True
    assert fake_client.close_calls == 1


def test_client_context_manager_closes_client() -> None:
    """Using JevClient as a context manager should close it automatically."""
    fake_client = FakeTypeSafeClient()

    with JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    ) as client:
        assert client.is_closed is False

    assert client.is_closed is True
    assert fake_client.close_calls == 1


def test_client_cannot_enter_after_close() -> None:
    """A closed client should not be re-entered as a context manager."""
    fake_client = FakeTypeSafeClient()

    client = JevClient(
        settings=build_settings(),
        sdk_client=fake_client,
    )

    client.close()

    with pytest.raises(
        JevPluginError,
        match="Cannot enter a closed Jev client",
    ):
        client.__enter__()


def test_client_can_evaluate_multiple_requests() -> None:
    """A live client should support multiple independent evaluations."""
    fake_client = FakeTypeSafeClient()

    client = JevClient(
        settings=build_settings(
            model="jev-test-model",
        ),
        sdk_client=fake_client,
    )

    first_state = {"request_id": 1}
    first_questions = {"question": object()}

    second_state = {"request_id": 2}
    second_questions = {"question": object()}

    first_response = client.evaluate(
        state=first_state,
        questions=first_questions,
    )

    second_response = client.evaluate(
        state=second_state,
        questions=second_questions,
    )

    assert first_response == {"result": "test"}
    assert second_response == {"result": "test"}

    assert len(fake_client.system_one_calls) == 2

    first_call = fake_client.system_one_calls[0]
    second_call = fake_client.system_one_calls[1]

    assert first_call["state"] == first_state
    assert first_call["questions"] == first_questions
    assert first_call["model"] == "jev-test-model"

    assert second_call["state"] == second_state
    assert second_call["questions"] == second_questions
    assert second_call["model"] == "jev-test-model"
