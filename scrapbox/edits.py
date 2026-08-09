"""Helpers for building page edit changes.

The edit API takes low-level changes keyed by line id (`_insert` / `_update` /
`_delete`). This module turns the friendlier "ops" form into those changes, and
generates the line ids that an insertion needs.
"""

import secrets
from collections.abc import Mapping, Sequence
from typing import Any

from .models import ChangeLines, DeleteChange, InsertChange, PageChange, UpdateChange

LINE_ID_BYTES = 12
"""Number of random bytes in a line id, which the API expects as 24 hex digits."""

END_ANCHOR = "_end"
"""Anchor that inserts at the end of the page instead of before a line."""

OP_KEYS = ("insertBefore", "replace", "delete")
"""Keys that identify the kind of an op. Exactly one must be present."""


def new_line_id() -> str:
    """Generate a line id for a newly inserted line.

    The client, not the server, chooses the id of an inserted line.

    Returns:
        A 24 digit hexadecimal id.
    """
    return secrets.token_hex(LINE_ID_BYTES)


def _split_lines(text: str) -> list[str]:
    """Split text the way the edit API counts lines.

    Unlike `str.splitlines`, a trailing newline yields a final empty line, so that
    a deliberate blank line at the end is preserved.

    Args:
        text: The text to split.

    Returns:
        One entry per line, never empty.
    """
    return text.replace("\r\n", "\n").split("\n")


def _op_kind(op: Mapping[str, Any]) -> str:
    """Determine which kind of op a mapping describes.

    Args:
        op: The op to inspect.

    Returns:
        The name of the single op key present.

    Raises:
        ValueError: If the op does not hold exactly one op key.
    """
    kinds = [key for key in OP_KEYS if key in op]
    if len(kinds) != 1:
        msg = f"each op must have exactly one of {', '.join(OP_KEYS)}, got: {sorted(op)}"
        raise ValueError(msg)
    return kinds[0]


def _insert_changes(op: Mapping[str, Any]) -> list[PageChange]:
    """Build the changes for an `insertBefore` op.

    Text spanning several lines is inserted as one change per line, in order.

    Args:
        op: The op to convert.

    Returns:
        The changes to send.

    Raises:
        TypeError: If the anchor or the text is not a string.
    """
    anchor = op["insertBefore"]
    text = op.get("text")
    if not isinstance(anchor, str):
        msg = "insertBefore must be a line id string, or '_end'"
        raise TypeError(msg)
    if not isinstance(text, str):
        msg = "insertBefore.text must be a string"
        raise TypeError(msg)
    return [InsertChange(insert=anchor, lines=ChangeLines(id=new_line_id(), text=line)) for line in _split_lines(text)]


def _replace_change(op: Mapping[str, Any]) -> PageChange:
    """Build the change for a `replace` op.

    Args:
        op: The op to convert.

    Returns:
        The change to send.

    Raises:
        TypeError: If the line id or the text is not a string.
        ValueError: If the text spans several lines.
    """
    line_id = op["replace"]
    text = op.get("text")
    if not isinstance(line_id, str):
        msg = "replace must be a line id string"
        raise TypeError(msg)
    if not isinstance(text, str):
        msg = "replace.text must be a string"
        raise TypeError(msg)
    if len(_split_lines(text)) > 1:
        msg = (
            "replace does not support multi-line text. To split a line into several, "
            "insertBefore the new lines first, then delete the original line."
        )
        raise ValueError(msg)
    return UpdateChange(update=line_id, lines=ChangeLines(text=text))


def _delete_change(op: Mapping[str, Any]) -> PageChange:
    """Build the change for a `delete` op.

    Args:
        op: The op to convert.

    Returns:
        The change to send.

    Raises:
        TypeError: If the line id is not a string.
    """
    line_id = op["delete"]
    if not isinstance(line_id, str):
        msg = "delete must be a line id string"
        raise TypeError(msg)
    return DeleteChange(delete=line_id)


def changes_from_ops(ops: Sequence[Mapping[str, Any]]) -> list[PageChange]:
    """Convert ops into the changes the edit API expects.

    An op is one of:

    - `{"insertBefore": "<lineId>" | "_end", "text": "..."}`
    - `{"replace": "<lineId>", "text": "..."}`
    - `{"delete": "<lineId>"}`

    Ops are applied in order, and every anchor must exist at the time it is applied.

    Args:
        ops: The ops to convert.

    Returns:
        The changes to send to the edit API.

    Raises:
        TypeError: If `ops` is not a sequence of objects, or a field has the wrong type.
        ValueError: If an op is malformed.
    """
    if isinstance(ops, str) or not isinstance(ops, Sequence):
        msg = "ops must be a list"
        raise TypeError(msg)

    changes: list[PageChange] = []
    for op in ops:
        if not isinstance(op, Mapping):
            msg = f"each op must be an object, got: {op!r}"
            raise TypeError(msg)
        kind = _op_kind(op)
        if kind == "insertBefore":
            changes.extend(_insert_changes(op))
        elif kind == "replace":
            changes.append(_replace_change(op))
        else:
            changes.append(_delete_change(op))
    return changes
