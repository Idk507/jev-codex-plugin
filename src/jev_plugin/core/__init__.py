"""Core application infrastructure.

This package contains shared infrastructure such as exceptions and
application-wide logging.
"""

from .exceptions import (
    JevAuthenticationError,
    JevConfigurationError,
    JevConnectionError,
    JevPluginError,
    JevRequestError,
    JevResponseError,
)

__all__ = [
    "JevPluginError",
    "JevConfigurationError",
    "JevAuthenticationError",
    "JevConnectionError",
    "JevRequestError",
    "JevResponseError",
]
