"""Errors raised by the AH client."""
from __future__ import annotations


class AHError(Exception):
    """Error returned by the AH API."""


class AHAuthError(AHError):
    """Not logged in or token rejected."""


class AHOrderModeError(AHError):
    """HTTP 412 'Server in order mode': an online order is open for changes, the list is locked."""
