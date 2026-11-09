"""What a failure may write to the log (security review S31).

An exception's message can quote the analysis: a driver's name in a schema
error from the calculation, the model provider's error body, Supabase's error
text with column values. The log is not where analyses are kept, so a failure
is logged by its type, its status code and where it happened, never by its
message. The traceback's frames say where; the message line is what is left
out.
"""
from __future__ import annotations

import logging
import os
import traceback

# The innermost frames are the ones that say what failed.
_FRAMES = 6


def kind(exc: BaseException) -> str:
    """'APIStatusError 500', 'ValueError': the type and, for an HTTP or API
    error, its status code and request id. No message."""
    out = type(exc).__name__
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(exc, "code", None)   # urllib's HTTPError
    if isinstance(status, int) and not isinstance(status, bool):
        out += f" {status}"
    rid = getattr(exc, "request_id", None)
    if isinstance(rid, str) and rid.isascii() and len(rid) <= 80:
        out += f" (request id {rid})"
    return out


def describe(exc: BaseException) -> str:
    """kind() of the exception and of what caused it, each with the frames
    it passed through: 'ValueError at schema.py:383 in from_dict <-
    app.py:5025 in api_kalkyl'."""
    parts, seen, e = [], set(), exc
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        frames = traceback.extract_tb(e.__traceback__)[-_FRAMES:]
        where = " <- ".join(f"{os.path.basename(f.filename)}:{f.lineno} in {f.name}"
                            for f in reversed(frames))
        parts.append(kind(e) + (f" at {where}" if where else ""))
        e = e.__cause__ or (None if e.__suppress_context__ else e.__context__)
    return "; caused by ".join(parts)


def log_failure(logger: logging.Logger, msg: str, exc: BaseException) -> None:
    """logger.exception(msg), without the message of the exception."""
    logger.error("%s: %s", msg, describe(exc))
