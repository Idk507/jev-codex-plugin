
"""Unit tests for the TypeSafe Jev client adapter.

These tests verify the application boundary around the official
TypeSafe Python SDK without making real network requests.

The test suite covers:

- Client initialization with the configured API key.
- Dependency injection of an SDK client.
- Configured model propagation to ``system_one``.
- Successful Jev evaluation.
- Question validation.
- Authentication error translation.
- Connection/timeout error translation.
- Response error translation.
- Request/validation error translation.
- Generic SDK failure translation.
- Preservation of the original exception as ``cause``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import SecretStr

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
    """Create isolated test settings without reading the local .env file."""
    return Settings(
        _env_file=None,
        typesafe_api_key=SecretStr(api_key),
        typesafe_model=model,
    )


class FakeTypeSafeClient:
    """Minimal fake of the official TypeSafe SDK client."""

    def __init__(self) -> None:
        self.system_one_calls: list[dict[str, object]] = []
        self.response: object = SimpleNamespace(
            choices={
                "result": SimpleNamespace(
                    choice="yes",
                    confidence=0.9,
                    probabilities={"yes": 0.9, "no": 0.1},
                )
            }
        )
        self.error: Exception | None = None

    def system_one(
        self,
        *,
        state: object,
        questions: dict[str, object],
        model: str,
    ) -> object:
        """Record the request and return the configured fake response."""
        self.system_one_calls.append(
            {
                "state": state,
                "questions": questions,
                "model": model,
            }
        )

        if self.error is not None:
            raise self.error

        return self.response


def test_client_initializes_official_sdk_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The client should construct TypeSafeClient with only the API key."""
    fake_sdk_client = Mock()

    constructor = Mock(return_value=fake_sdk_client)

    monkeypatch.setattr(
        "jev_plugin.typesafe.client.TypeSafeClient",
        constructor,
    )

    settings = build_settings(api_key="secret-key")

    client = JevClient(settings)

    constructor.assert_called_once_with(
        api_key="secret-key",
    )

    assert client.model == "jev-test-model"


def test_client_uses_injected_sdk_client() -> None:
    """Dependency injection should bypass SDK client construction."""
    fake_sdk_client = FakeTypeSafeClient()
    settings = build_settings()

    client = JevClient(
        settings,
        sdk_client=fake_sdk_client,
    )

    assert client._client is fake_sdk_client
    assert client.model == "jev-test-model"


def test_model_property_returns_configured_model() -> None:
    """The model property should expose the application configuration."""
    settings = build_settings(model="jev-custom-model")
    fake_sdk_client = FakeTypeSafeClient()

    client = JevClient(
        settings,
        sdk_client=fake_sdk_client,
    )

    assert client.model == "jev-custom-model"


def test_evaluate_calls_system_one_with_state_questions_and_model() -> None:
    """Evaluation should forward the complete request to the SDK."""
    fake_sdk_client = FakeTypeSafeClient()
    settings = build_settings(model="jev-production-model")

    client = JevClient(
        settings,
        sdk_client=fake_sdk_client,
    )

    state = {
        "customer": {
            "age": 32,
            "country": "India",
        }
    }

    questions = {
        "result": {
            "type": "noul",
            "instructions": "Is the customer eligible?",
        }
    }

    response = client.evaluate(
        state=state,
        questions=questions,
    )

    assert response is fake_sdk_client.response

    assert len(fake_sdk_client.system_one_calls) == 1

    call = fake_sdk_client.system_one_calls[0]

    assert call["state"] == state
    assert call["questions"] == questions
    assert call["model"] == "jev-production-model"


def test_evaluate_copies_questions_before_sending_to_sdk() -> None:
    """The adapter should pass an independent dictionary to the SDK."""
    fake_sdk_client = FakeTypeSafeClient()
    settings = build_settings()

    client = JevClient(
        settings,
        sdk_client=fake_sdk_client,
    )

    questions = {
        "result": "question",
    }

    client.evaluate(
        state={"value": 1},
        questions=questions,
    )

    sent_questions = fake_sdk_client.system_one_calls[0]["questions"]

    assert sent_questions == questions
    assert sent_questions is not questions


def test_evaluate_rejects_empty_questions() -> None:
    """An evaluation without questions should fail before reaching the SDK."""
    fake_sdk_client = FakeTypeSafeClient()
    settings = build_settings()

    client = JevClient(
        settings,
        sdk_client=fake_sdk_client,
    )

    with pytest.raises(
        JevRequestError,
        match="At least one Jev question is required",
    ):
        client.evaluate(
            state={"value": 1},
            questions={},
        )

    assert fake_sdk_client.system_one_calls == []


def test_evaluate_accepts_mapping_subclasses() -> None:
    """The evaluate method should accept Mapping implementations."""
    fake_sdk_client = FakeTypeSafeClient()
    settings = build_settings()

    client = JevClient(
        settings,
        sdk_client=fake_sdk_client,
    )

    class CustomMapping(dict[str, object]):
        """Test mapping implementation."""

    questions = CustomMapping(
        {
            "result": "question",
        }
    )

    response = client.evaluate(
        state={"value": 1},
        questions=questions,
    )

    assert response is fake_sdk_client.response

    sent_questions = fake_sdk_client.system_one_calls[0]["questions"]

    assert sent_questions == questions
    assert type(sent_questions) is dict


@pytest.mark.parametrize(
    ("sdk_error", "expected_exception"),
    [
        (
            RuntimeError("authentication failed"),
            JevAuthenticationError,
        ),
        (
            RuntimeError("invalid API key"),
            JevAuthenticationError,
        ),
        (
            RuntimeError("unauthorized request"),
            JevAuthenticationError,
        ),
        (
            RuntimeError("HTTP 401 unauthorized"),
            JevAuthenticationError,
        ),
        (
            RuntimeError("connection refused"),
            JevConnectionError,
        ),
        (
            RuntimeError("network failure"),
            JevConnectionError,
        ),
        (
            RuntimeError("request timed out"),
            JevConnectionError,
        ),
        (
            RuntimeError("connection timeout"),
            JevConnectionError,
        ),
        (
            RuntimeError("invalid response received"),
            JevResponseError,
        ),
        (
            RuntimeError("invalid answers collection"),
            JevResponseError,
        ),
        (
            RuntimeError("response schema is invalid"),
            JevResponseError,
        ),
        (
            RuntimeError("invalid request"),
            JevRequestError,
        ),
        (
            RuntimeError("request validation failed"),
            JevRequestError,
        ),
        (
            RuntimeError("invalid question"),
            JevRequestError,
        ),
    ],
)
def test_evaluate_translates_sdk_errors(
    sdk_error: Exception,
    expected_exception: type[JevPluginError],
) -> None:
    """Known SDK failures should be translated into application exceptions."""
    fake_sdk_client = FakeTypeSafeClient()
    fake_sdk_client.error = sdk_error

    settings = build_settings()

    client = JevClient(
        settings,
        sdk_client=fake_sdk_client,
    )

    with pytest.raises(expected_exception) as exc_info:
        client.evaluate(
            state={"value": 1},
            questions={"result": "question"},
        )

    assert exc_info.value.cause is sdk_error


def test_evaluate_translates_unknown_sdk_error_to_plugin_error() -> None:
    """Unexpected SDK failures should become the generic plugin error."""
    sdk_error = RuntimeError("something completely unexpected happened")

    fake_sdk_client = FakeTypeSafeClient()
    fake_sdk_client.error = sdk_error

    settings = build_settings()

    client = JevClient(
        settings,
        sdk_client=fake_sdk_client,
    )

    with pytest.raises(
        JevPluginError,
        match="The TypeSafe Jev request failed",
    ) as exc_info:
        client.evaluate(
            state={"value": 1},
            questions={"result": "question"},
        )

    assert exc_info.value.cause is sdk_error


def test_authentication_error_does_not_expose_api_key() -> None:
    """Authentication failures should not leak the configured API key."""
    api_key = "super-secret-api-key"

    sdk_error = RuntimeError("authentication failed")

    fake_sdk_client = FakeTypeSafeClient()
    fake_sdk_client.error = sdk_error

    settings = build_settings(api_key=api_key)

    client = JevClient(
        settings,
        sdk_client=fake_sdk_client,
    )

    with pytest.raises(JevAuthenticationError) as exc_info:
        client.evaluate(
            state={"value": 1},
            questions={"result": "question"},
        )

    assert api_key not in str(exc_info.value)
    assert api_key not in repr(exc_info.value)


def test_client_initialization_translates_authentication_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Authentication failures during SDK initialization should be translated."""
    sdk_error = RuntimeError("invalid API key")

    constructor = Mock(side_effect=sdk_error)

    monkeypatch.setattr(
        "jev_plugin.typesafe.client.TypeSafeClient",
        constructor,
    )

    settings = build_settings(api_key="secret-key")

    with pytest.raises(
        JevAuthenticationError,
        match="authentication configuration is invalid",
    ) as exc_info:
        JevClient(settings)

    assert exc_info.value.cause is sdk_error

    constructor.assert_called_once_with(
        api_key="secret-key",
    )


def test_client_initialization_translates_unknown_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected initialization failures should become JevPluginError."""
    sdk_error = RuntimeError("unexpected SDK initialization failure")

    constructor = Mock(side_effect=sdk_error)

    monkeypatch.setattr(
        "jev_plugin.typesafe.client.TypeSafeClient",
        constructor,
    )

    settings = build_settings()

    with pytest.raises(
        JevPluginError,
        match="Unable to initialize the TypeSafe client",
    ) as exc_info:
        JevClient(settings)

    assert exc_info.value.cause is sdk_error


def test_evaluate_preserves_sdk_response_object() -> None:
    """The client adapter should not mutate or transform SDK responses."""
    fake_sdk_client = FakeTypeSafeClient()

    expected_response = {
        "raw": "sdk-response",
    }

    fake_sdk_client.response = expected_response

    settings = build_settings()

    client = JevClient(
        settings,
        sdk_client=fake_sdk_client,
    )

    response = client.evaluate(
        state={"value": 1},
        questions={"result": "question"},
    )

    assert response is expected_response


def test_evaluate_can_be_called_multiple_times() -> None:
    """A long-lived client should support multiple independent requests."""
    fake_sdk_client = FakeTypeSafeClient()

    settings = build_settings(
        model="jev-test-model",
    )

    client = JevClient(
        settings,
        sdk_client=fake_sdk_client,
    )

    first_state = {"request": 1}
    second_state = {"request": 2}

    first_questions = {
        "result": "first question",
    }

    second_questions = {
        "result": "second question",
    }

    client.evaluate(
        state=first_state,
        questions=first_questions,
    )

    client.evaluate(
        state=second_state,
        questions=second_questions,
    )

    assert len(fake_sdk_client.system_one_calls) == 2

    first_call = fake_sdk_client.system_one_calls[0]
    second_call = fake_sdk_client.system_one_calls[1]

    assert first_call["state"] == first_state
    assert first_call["questions"] == first_questions
    assert first_call["model"] == "jev-test-model"

    assert second_call["state"] == second_state
    assert second_call["questions"] == second_questions
    assert second_call["model"] == "jev-test-model"


def test_evaluate_does_not_call_sdk_when_questions_are_empty() -> None:
    """Validation failures must happen before any SDK request is attempted."""
    fake_sdk_client = FakeTypeSafeClient()

    settings = build_settings()

    client = JevClient(
        settings,
        sdk_client=fake_sdk_client,
    )

    with pytest.raises(JevRequestError):
        client.evaluate(
            state={"value": 1},
            questions={},
        )

    assert fake_sdk_client.system_one_calls == []


def test_configured_model_is_used_for_every_request() -> None:
    """The configured application model should be explicitly sent per request."""
    fake_sdk_client = FakeTypeSafeClient()

    settings = build_settings(
        model="jev-production-model",
    )

    client = JevClient(
        settings,
        sdk_client=fake_sdk_client,
    )

    client.evaluate(
        state={"id": 1},
        questions={"q1": "question 1"},
    )

    client.evaluate(
        state={"id": 2},
        questions={"q2": "question 2"},
    )

    assert [
        call["model"]
        for call in fake_sdk_client.system_one_calls
    ] == [
        "jev-production-model",
        "jev-production-model",
    ]
