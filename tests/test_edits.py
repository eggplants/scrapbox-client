"""Tests for building page edit changes."""

from typing import Any, cast

import pytest

from scrapbox.edits import changes_from_ops, new_line_id
from scrapbox.models import DeleteChange, InsertChange, UpdateChange

LINE_ID_LENGTH = 24


class TestNewLineId:
    """Test new_line_id function."""

    def test_format(self) -> None:
        """Test that a generated id has the shape the API expects."""
        line_id = new_line_id()
        assert len(line_id) == LINE_ID_LENGTH
        assert all(char in "0123456789abcdef" for char in line_id)

    def test_ids_are_distinct(self) -> None:
        """Test that ids do not repeat."""
        assert len({new_line_id() for _ in range(100)}) == 100  # noqa: PLR2004


class TestChangesFromOps:
    """Test changes_from_ops function."""

    def test_insert_before_a_line(self) -> None:
        """Test converting an insertion anchored to a line."""
        (change,) = changes_from_ops([{"insertBefore": "abc", "text": "hello"}])
        assert isinstance(change, InsertChange)
        assert change.insert == "abc"
        assert change.lines.text == "hello"
        assert change.lines.id is not None

    @staticmethod
    def _inserted(ops: list[dict[str, Any]]) -> list[InsertChange]:
        """Convert ops that are all insertions and return them narrowed."""
        changes = changes_from_ops(ops)
        assert all(isinstance(change, InsertChange) for change in changes)
        return [change for change in changes if isinstance(change, InsertChange)]

    def test_insert_splits_multi_line_text(self) -> None:
        """Test that multi-line text becomes one insertion per line, in order."""
        changes = self._inserted([{"insertBefore": "_end", "text": "one\ntwo\nthree"}])
        assert [change.lines.text for change in changes] == ["one", "two", "three"]
        assert len({change.lines.id for change in changes}) == 3  # noqa: PLR2004

    def test_insert_keeps_a_trailing_blank_line(self) -> None:
        """Test that a trailing newline is kept as a deliberate blank line."""
        changes = self._inserted([{"insertBefore": "_end", "text": "one\n"}])
        assert [change.lines.text for change in changes] == ["one", ""]

    def test_insert_normalizes_crlf(self) -> None:
        """Test that Windows line endings split the same way."""
        changes = self._inserted([{"insertBefore": "_end", "text": "one\r\ntwo"}])
        assert [change.lines.text for change in changes] == ["one", "two"]

    def test_replace(self) -> None:
        """Test converting a replacement."""
        (change,) = changes_from_ops([{"replace": "abc", "text": "new text"}])
        assert isinstance(change, UpdateChange)
        assert change.update == "abc"
        assert change.lines.text == "new text"

    def test_delete(self) -> None:
        """Test converting a deletion."""
        (change,) = changes_from_ops([{"delete": "abc"}])
        assert isinstance(change, DeleteChange)
        assert change.delete == "abc"

    def test_ops_keep_their_order(self) -> None:
        """Test that the changes come out in the order the ops were given."""
        changes = changes_from_ops([{"delete": "a"}, {"insertBefore": "b", "text": "x"}, {"replace": "c", "text": "y"}])
        assert [type(change) for change in changes] == [DeleteChange, InsertChange, UpdateChange]

    def test_serializes_with_the_api_field_names(self) -> None:
        """Test that changes serialize back to the underscore-prefixed keys."""
        (change,) = changes_from_ops([{"delete": "abc"}])
        assert isinstance(change, DeleteChange)
        assert change.model_dump(by_alias=True, exclude_none=True) == {"_delete": "abc"}

    def test_empty_ops(self) -> None:
        """Test that no ops produce no changes."""
        assert changes_from_ops([]) == []

    def test_replace_rejects_multi_line_text(self) -> None:
        """Test that a replacement spanning lines is refused.

        The API only replaces within a single line, so this has to be split into an
        insertion followed by a deletion.
        """
        with pytest.raises(ValueError, match="multi-line"):
            changes_from_ops([{"replace": "abc", "text": "one\ntwo"}])

    @pytest.mark.parametrize(
        "op",
        [
            {},
            {"insertBefore": "a", "delete": "b"},
            {"unknown": "a"},
        ],
    )
    def test_rejects_ops_without_exactly_one_kind(self, op: dict[str, Any]) -> None:
        """Test that an op must say exactly one thing."""
        with pytest.raises(ValueError, match="exactly one"):
            changes_from_ops([op])

    @pytest.mark.parametrize(
        "op",
        [
            {"insertBefore": 1, "text": "x"},
            {"insertBefore": "a", "text": 1},
            {"replace": 1, "text": "x"},
            {"replace": "a", "text": None},
            {"delete": 1},
        ],
    )
    def test_rejects_non_string_fields(self, op: dict[str, Any]) -> None:
        """Test that ids and texts must be strings."""
        with pytest.raises(TypeError, match="must be a"):
            changes_from_ops([op])

    def test_rejects_ops_that_are_not_a_list(self) -> None:
        """Test that ops must be a list.

        The ops come from user-supplied JSON, so the wrong shape has to be caught at
        runtime however well the call is typed.
        """
        with pytest.raises(TypeError, match="ops must be a list"):
            changes_from_ops(cast("list[dict[str, Any]]", {"insertBefore": "a"}))

    def test_rejects_an_op_that_is_not_an_object(self) -> None:
        """Test that each op must be an object."""
        with pytest.raises(TypeError, match="must be an object"):
            changes_from_ops(cast("list[dict[str, Any]]", ["nope"]))
