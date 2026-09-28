"""Tests for the Jev plugin exception hierarchy."""

import pytest

from jev_plugin.core import (
    JevAuthenticationError,
    JevConfigurationError,
    JevConnectionError,
    JevPluginError,
    JevRequestError,
    JevResponseError,
)


@pytest.mark.parametrize(
    "exception_type",
    [
        JevConfigurationError,
        JevAuthenticationError,
        JevConnectionError,
        JevRequestError,
        JevResponseError,
    ],
)
def test_application_exceptions_inherit_from_base_exception(
    exception_type: type[JevPluginError],
) -> None:
    """Every application exception must inherit from JevPluginError."""
    error = exception_type("test error")

    assert isinstance(error, JevPluginError)
    assert str(error) == "test error"
    assert error.message == "test error"
    assert error.cause is None


def test_exception_preserves_original_cause() -> None:
    """The application exception should preserve its underlying cause."""
    original_error = ValueError("underlying failure")

    error = JevConnectionError(
        "Unable to connect to TypeSafe.",
        cause=original_error,
    )

    assert isinstance(error, JevPluginError)
    assert error.message == "Unable to connect to TypeSafe."
    assert error.cause is original_error


def test_base_exception_can_be_caught_consistently() -> None:
    """All plugin-specific errors should be catchable through the base type."""
    with pytest.raises(JevPluginError):
        raise JevRequestError("TypeSafe rejected the request.")
