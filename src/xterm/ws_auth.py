"""Log-in check shared by every WebSocket consumer.

Browsers can't send an Authorization header when they open a WebSocket, so the pages offer the
JWT access token as a subprotocol: ``token.<base64 of the token>``, next to a second subprotocol
that names the connection (``container.<id>``, ``terminal.<id>``, ``notifications``, ...). The
server has to answer with one of the offered subprotocols; it picks the name, not the token, so
the token is not echoed back in the response headers.

Subprotocols must be HTTP tokens, and ``=`` isn't allowed in those (browsers throw a
SyntaxError), so pages drop the base64 padding and it is restored here.
"""
import base64
import binascii
from dataclasses import dataclass
from typing import Iterable, Optional

from channels.db import database_sync_to_async
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

TOKEN_PREFIX = "token."


@dataclass(frozen=True)
class Subprotocols:
    """What the client offered: the decoded access token, and the subprotocol to accept with."""

    token: Optional[str]
    accept_with: Optional[str]


def decode_token(value: str) -> Optional[str]:
    """The token from the part after ``token.``, with or without base64 padding; None if garbled."""
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), validate=True).decode("ascii")
    except (binascii.Error, UnicodeDecodeError):
        return None


def read_subprotocols(offered: Optional[Iterable[str]]) -> Subprotocols:
    token = accept_with = None
    for protocol in offered or ():
        if protocol.startswith(TOKEN_PREFIX):
            token = token or decode_token(protocol[len(TOKEN_PREFIX):])
        elif accept_with is None:
            accept_with = protocol
    return Subprotocols(token, accept_with)


# The same checks DRF runs for "Authorization: Bearer ..." on the REST API: signature, expiry,
# token type, and that the user still exists and is active.
_jwt = JWTAuthentication()


@database_sync_to_async
def user_for_token(raw_token: Optional[str]):
    """The user an access token belongs to, or None when the token or the user isn't valid."""
    if not raw_token:
        return None
    try:
        return _jwt.get_user(_jwt.get_validated_token(raw_token))
    except (InvalidToken, TokenError, AuthenticationFailed):
        return None
