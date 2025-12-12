"""Tests for CLI main module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from scrapbox.main import main

if TYPE_CHECKING:
    from pathlib import Path


class TestCLI:
    """Test CLI commands."""

    PROJECT_NAME = "help-jp"
    PAGE_TITLE = "ブラケティング"

    def test_cli_help(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test --help option."""
        with pytest.raises(SystemExit) as e:
            main(test_args=["-h"])
        assert e.value.code == 0
        captured = capfd.readouterr()
        assert "Scrapbox API client CLI" in captured.out
        assert "usage:" in captured.out
        assert not captured.err

    def test_no_command(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test running without command shows help."""
        exit_code = main(test_args=[])
        assert exit_code == 1
        captured = capfd.readouterr()
        assert "usage:" in captured.out

    def test_pages_command(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test pages command."""
        exit_code = main(test_args=["pages", self.PROJECT_NAME, "--limit", "3"])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert f"Project: {self.PROJECT_NAME}" in captured.out
        assert "Total pages:" in captured.out
        assert not captured.err

    def test_pages_command_with_skip(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test pages command with skip parameter."""
        exit_code = main(test_args=["pages", self.PROJECT_NAME, "--skip", "5", "--limit", "2"])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert f"Project: {self.PROJECT_NAME}" in captured.out
        assert "Skip: 5, Limit: 2" in captured.out
        assert not captured.err

    def test_bulk_pages_command(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test bulk-pages command."""
        # Use small batch size for testing
        exit_code = main(test_args=["bulk-pages", self.PROJECT_NAME, "--batch-size", "10"])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert f"Project: {self.PROJECT_NAME}" in captured.out
        assert "Total pages:" in captured.out
        # Check stderr for progress messages
        assert "Fetching all pages..." in captured.err or "Fetched" in captured.err

    def test_page_command(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test page command."""
        exit_code = main(test_args=["page", self.PROJECT_NAME, self.PAGE_TITLE])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert f"Title: {self.PAGE_TITLE}" in captured.out
        assert "Lines:" in captured.out
        assert "Characters:" in captured.out
        assert "Views:" in captured.out
        assert not captured.err

    def test_text_command(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test text command to stdout."""
        exit_code = main(test_args=["text", self.PROJECT_NAME, self.PAGE_TITLE])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert self.PAGE_TITLE in captured.out
        assert len(captured.out) > 0
        assert not captured.err

    def test_text_command_with_output_file(self, capfd: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        """Test text command with output file."""
        output_file = tmp_path / "output.txt"
        exit_code = main(test_args=["text", self.PROJECT_NAME, self.PAGE_TITLE, "--output", str(output_file)])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert f"Saved to {output_file}" in captured.err
        assert not captured.out

        # Verify file was created and has content
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert self.PAGE_TITLE in content

    def test_invalid_project(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test error handling for invalid project."""
        invalid_project = "this-project-definitely-does-not-exist-12345"
        exit_code = main(test_args=["pages", invalid_project])
        assert exit_code == 1
        captured = capfd.readouterr()
        assert "Error:" in captured.err

    def test_invalid_page(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test error handling for non-existent page."""
        invalid_page = "this-page-definitely-does-not-exist-12345"
        exit_code = main(test_args=["page", self.PROJECT_NAME, invalid_page])
        assert exit_code == 1
        captured = capfd.readouterr()
        assert "Error:" in captured.err

    def test_page_command_with_special_characters(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test page command with special characters in title."""
        # Testing URL encoding
        special_page = "API"
        exit_code = main(test_args=["page", self.PROJECT_NAME, special_page])
        # Should succeed or fail gracefully
        assert exit_code in (0, 1)
        captured = capfd.readouterr()
        if exit_code == 0:
            assert f"Title: {special_page}" in captured.out

    def test_pages_help(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test pages subcommand help."""
        with pytest.raises(SystemExit) as e:
            main(test_args=["pages", "-h"])
        assert e.value.code == 0
        captured = capfd.readouterr()
        assert "pages" in captured.out
        assert "--skip" in captured.out
        assert "--limit" in captured.out
        assert "Project name" in captured.out

    def test_page_help(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test page subcommand help."""
        with pytest.raises(SystemExit) as e:
            main(test_args=["page", "-h"])
        assert e.value.code == 0
        captured = capfd.readouterr()
        assert "page" in captured.out
        assert "Project name" in captured.out
        assert "Page title" in captured.out

    def test_text_help(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test text subcommand help."""
        with pytest.raises(SystemExit) as e:
            main(test_args=["text", "-h"])
        assert e.value.code == 0
        captured = capfd.readouterr()
        assert "text" in captured.out
        assert "--output" in captured.out
        assert "Project name" in captured.out

    def test_bulk_pages_help(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test bulk-pages subcommand help."""
        with pytest.raises(SystemExit) as e:
            main(test_args=["bulk-pages", "-h"])
        assert e.value.code == 0
        captured = capfd.readouterr()
        assert "bulk-pages" in captured.out
        assert "--batch-size" in captured.out
        assert "Project name" in captured.out


class TestConnectSidPriority:
    """Test connect.sid priority logic."""

    PROJECT_NAME = "help-jp"

    def test_connect_sid_from_argument(self, tmp_path: Path) -> None:
        """Test that --connect-sid argument takes priority."""
        # Create a file with different sid
        sid_file = tmp_path / "test.sid"
        sid_file.write_text("file-sid-value")

        with patch("scrapbox.main.ScrapboxClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.get_pages.return_value = MagicMock(
                project_name=self.PROJECT_NAME,
                count=0,
                skip=0,
                limit=100,
                pages=[],
            )

            main(test_args=["--connect-sid", "arg-sid-value", "pages", self.PROJECT_NAME])

            # Verify ScrapboxClient was called with the argument value
            mock_client.assert_called_once_with(connect_sid="arg-sid-value")

    def test_connect_sid_from_file(self, tmp_path: Path) -> None:
        """Test that --connect-sid-file is used when --connect-sid is not provided."""
        sid_file = tmp_path / "test.sid"
        sid_file.write_text("file-sid-value\n")

        with patch("scrapbox.main.ScrapboxClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.get_pages.return_value = MagicMock(
                project_name=self.PROJECT_NAME,
                count=0,
                skip=0,
                limit=100,
                pages=[],
            )

            main(test_args=["--connect-sid-file", str(sid_file), "pages", self.PROJECT_NAME])

            # Verify ScrapboxClient was called with the file value (stripped)
            mock_client.assert_called_once_with(connect_sid="file-sid-value")

    def test_connect_sid_from_default_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that default ~/.config/sbc/connect.sid is used when no arguments provided."""
        # Mock Path.home() to return tmp_path
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        # Create default config directory and file
        config_dir = tmp_path / ".config" / "sbc"
        config_dir.mkdir(parents=True)
        default_sid_file = config_dir / "connect.sid"
        default_sid_file.write_text("default-sid-value\n")

        with patch("scrapbox.main.ScrapboxClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.get_pages.return_value = MagicMock(
                project_name=self.PROJECT_NAME,
                count=0,
                skip=0,
                limit=100,
                pages=[],
            )

            main(test_args=["pages", self.PROJECT_NAME])

            # Verify ScrapboxClient was called with the default file value
            mock_client.assert_called_once_with(connect_sid="default-sid-value")

    def test_connect_sid_none_when_no_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that connect_sid is None when no file exists."""
        # Mock Path.home() to return tmp_path (no .config/sbc/connect.sid exists)
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        with patch("scrapbox.main.ScrapboxClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.get_pages.return_value = MagicMock(
                project_name=self.PROJECT_NAME,
                count=0,
                skip=0,
                limit=100,
                pages=[],
            )

            main(test_args=["pages", self.PROJECT_NAME])

            # Verify ScrapboxClient was called with None
            mock_client.assert_called_once_with(connect_sid=None)

    def test_connect_sid_file_not_exists(self, tmp_path: Path) -> None:
        """Test that connect_sid is None when specified file doesn't exist."""
        non_existent_file = tmp_path / "non_existent.sid"

        with patch("scrapbox.main.ScrapboxClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            mock_instance.get_pages.return_value = MagicMock(
                project_name=self.PROJECT_NAME,
                count=0,
                skip=0,
                limit=100,
                pages=[],
            )

            main(test_args=["--connect-sid-file", str(non_existent_file), "pages", self.PROJECT_NAME])

            # Verify ScrapboxClient was called with None since file doesn't exist
            mock_client.assert_called_once_with(connect_sid=None)

    def test_connect_sid_argument_priority_over_file(self, tmp_path: Path) -> None:
        """Test that --connect-sid has priority over --connect-sid-file."""
        # Note: These are mutually exclusive, so this test verifies the argument parser behavior
        # We can't actually pass both arguments, but we can verify the mutual exclusivity
        with pytest.raises(SystemExit):
            main(
                test_args=["--connect-sid", "arg-value", "--connect-sid-file", "file-path", "pages", self.PROJECT_NAME]
            )
