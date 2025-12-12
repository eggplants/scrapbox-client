"""Tests for CLI main module."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from scrapbox.main import check_output_path, get_connect_sid, main

if TYPE_CHECKING:
    from pathlib import Path

ARGPARSE_ERROR_CODE = 2


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

    def test_pages_command_json(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test pages command with JSON output."""
        exit_code = main(test_args=["pages", self.PROJECT_NAME, "--limit", "3", "--json"])
        assert exit_code == 0
        captured = capfd.readouterr()
        # JSON output should contain these fields
        assert '"projectName"' in captured.out
        assert '"pages"' in captured.out
        assert '"count"' in captured.out
        # Should not have the formatted text output
        assert "Project:" not in captured.out
        assert not captured.err

    def test_pages_command_json_short_option(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test pages command with -j short option."""
        exit_code = main(test_args=["pages", self.PROJECT_NAME, "--limit", "3", "-j"])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert '"projectName"' in captured.out
        assert '"pages"' in captured.out
        assert not captured.err

    def test_all_pages_command(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test all-pages command."""
        # Use small batch size for testing
        exit_code = main(test_args=["all-pages", self.PROJECT_NAME, "--batch-size", "10"])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert f"Project: {self.PROJECT_NAME}" in captured.out
        assert "Total pages:" in captured.out
        # Check stderr for progress messages
        assert "Fetching all pages..." in captured.err or "Fetched" in captured.err

    def test_all_pages_command_json(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test all-pages command with JSON output."""
        exit_code = main(test_args=["all-pages", self.PROJECT_NAME, "--batch-size", "10", "--json"])
        assert exit_code == 0
        captured = capfd.readouterr()
        # JSON output should contain these fields
        assert '"projectName"' in captured.out
        assert '"pages"' in captured.out
        assert '"count"' in captured.out
        # Should not have the formatted text output
        assert "Project:" not in captured.out
        # Progress messages still in stderr
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

    def test_page_command_json(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test page command with JSON output."""
        exit_code = main(test_args=["page", self.PROJECT_NAME, self.PAGE_TITLE, "--json"])
        assert exit_code == 0
        captured = capfd.readouterr()
        # JSON output should contain these fields
        assert '"title"' in captured.out
        assert '"lines"' in captured.out
        assert '"linesCount"' in captured.out
        assert '"charsCount"' in captured.out
        # Should not have the formatted text output
        assert "Title:" not in captured.out
        assert not captured.err

    def test_text_command(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test text command to stdout."""
        exit_code = main(test_args=["text", self.PROJECT_NAME, self.PAGE_TITLE])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert self.PAGE_TITLE in captured.out
        assert len(captured.out) > 0
        assert not captured.err

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
        assert "--json" in captured.out or "-j" in captured.out
        assert "Project name" in captured.out

    def test_page_help(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test page subcommand help."""
        with pytest.raises(SystemExit) as e:
            main(test_args=["page", "-h"])
        assert e.value.code == 0
        captured = capfd.readouterr()
        assert "page" in captured.out
        assert "--json" in captured.out or "-j" in captured.out
        assert "Project name" in captured.out
        assert "Page title" in captured.out

    def test_text_help(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test text subcommand help."""
        with pytest.raises(SystemExit) as e:
            main(test_args=["text", "-h"])
        assert e.value.code == 0
        captured = capfd.readouterr()
        assert "text" in captured.out
        assert "Project name" in captured.out

    def test_all_pages_help(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test all-pages subcommand help."""
        with pytest.raises(SystemExit) as e:
            main(test_args=["all-pages", "-h"])
        assert e.value.code == 0
        captured = capfd.readouterr()
        assert "all-pages" in captured.out
        assert "--batch-size" in captured.out
        assert "--json" in captured.out or "-j" in captured.out
        assert "Project name" in captured.out

    def test_icon_command(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test icon command."""
        exit_code = main(test_args=["icon", self.PROJECT_NAME, self.PAGE_TITLE])
        assert exit_code == 0
        captured = capfd.readouterr()
        # Check that a URL is returned
        assert "https://" in captured.out or "http://" in captured.out
        assert not captured.err

    def test_icon_help(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test icon subcommand help."""
        with pytest.raises(SystemExit) as e:
            main(test_args=["icon", "-h"])
        assert e.value.code == 0
        captured = capfd.readouterr()
        assert "icon" in captured.out
        assert "Project name" in captured.out
        assert "Page title" in captured.out

    def test_file_command(self, capfd: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        """Test file command."""
        output_file = tmp_path / "downloaded_file.bin"
        # Using a known file ID from Scrapbox (this may need to be updated)
        file_id = "test_file_id"
        exit_code = main(test_args=["file", file_id, "--output", str(output_file)])
        # May fail if file doesn't exist, but should handle gracefully
        assert exit_code in (0, 1)
        captured = capfd.readouterr()
        if exit_code == 0:
            assert f"Downloaded to {output_file}" in captured.err
            assert output_file.exists()

    def test_file_command_unsupported_file(self, capfd: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        """Test file command with unsupported file ID."""
        output_file = tmp_path / "downloaded_file.bin"
        unsupported_file_id = "https://gyazo.com/2b10554d1274b76f058a11b69c6a88dd"
        exit_code = main(test_args=["file", unsupported_file_id, "--output", str(output_file)])
        assert exit_code == 1
        captured = capfd.readouterr()
        assert "Error: Unsupported Gyazo oEmbed type" in captured.err

    def test_file_help(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test file subcommand help."""
        with pytest.raises(SystemExit) as e:
            main(test_args=["file", "-h"])
        assert e.value.code == 0
        captured = capfd.readouterr()
        assert "file" in captured.out
        assert "--output" in captured.out
        assert "File ID" in captured.out

    def test_file_output_to_directory_error(self, capfd: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        """Test file command with directory as output path."""
        with pytest.raises(SystemExit) as e:
            main(test_args=["file", "test_file_id", "--output", str(tmp_path)])
        assert e.value.code == ARGPARSE_ERROR_CODE
        captured = capfd.readouterr()
        assert "is a directory" in captured.err


class TestCheckOutputPath:
    """Test check_output_path function."""

    def test_valid_path(self, tmp_path: Path) -> None:
        """Test valid output path."""
        output_file = tmp_path / "output.txt"
        result = check_output_path(str(output_file))
        assert result == str(output_file)

    def test_existing_file_path(self, tmp_path: Path) -> None:
        """Test existing file path is valid."""
        output_file = tmp_path / "existing.txt"
        output_file.write_text("test")
        result = check_output_path(str(output_file))
        assert result == str(output_file)

    def test_directory_path_error(self, tmp_path: Path) -> None:
        """Test directory path raises error."""
        with pytest.raises(argparse.ArgumentTypeError, match="is a directory"):
            check_output_path(str(tmp_path))

    def test_nonexistent_parent_error(self, tmp_path: Path) -> None:
        """Test non-existent parent directory raises error."""
        invalid_path = tmp_path / "nonexistent" / "output.txt"
        with pytest.raises(argparse.ArgumentTypeError, match="does not exist"):
            check_output_path(str(invalid_path))


class TestGetConnectSid:
    """Test get_connect_sid function."""

    def test_from_argument(self) -> None:
        """Test getting connect.sid from argument."""
        args = MagicMock()
        args.connect_sid = "arg-value"
        args.connect_sid_file = None
        result = get_connect_sid(args)
        assert result == "arg-value"

    def test_from_file(self, tmp_path: Path) -> None:
        """Test getting connect.sid from specified file."""
        sid_file = tmp_path / "test.sid"
        sid_file.write_text("file-value\n")
        args = MagicMock()
        args.connect_sid = None
        args.connect_sid_file = str(sid_file)
        result = get_connect_sid(args)
        assert result == "file-value"

    def test_from_default_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting connect.sid from default file."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        config_dir = tmp_path / ".config" / "sbc"
        config_dir.mkdir(parents=True)
        default_sid_file = config_dir / "connect.sid"
        default_sid_file.write_text("default-value\n")

        args = MagicMock()
        args.connect_sid = None
        args.connect_sid_file = None
        result = get_connect_sid(args)
        assert result == "default-value"

    def test_none_when_no_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returning None when no file exists."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        args = MagicMock()
        args.connect_sid = None
        args.connect_sid_file = None
        result = get_connect_sid(args)
        assert result is None

    def test_file_not_exists(self, tmp_path: Path) -> None:
        """Test when specified file doesn't exist."""
        non_existent_file = tmp_path / "non_existent.sid"
        args = MagicMock()
        args.connect_sid = None
        args.connect_sid_file = str(non_existent_file)
        result = get_connect_sid(args)
        assert result is None


class TestConnectSidPriority:
    """Test connect.sid priority logic."""

    PROJECT_NAME = "help-jp"

    def test_connect_sid_from_argument(self, tmp_path: Path) -> None:
        """Test that --connect-sid argument takes priority."""
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

            mock_client.assert_called_once_with(connect_sid="file-sid-value")

    def test_connect_sid_from_default_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that default ~/.config/sbc/connect.sid is used when no arguments provided."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

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

            mock_client.assert_called_once_with(connect_sid="default-sid-value")

    def test_connect_sid_none_when_no_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that connect_sid is None when no file exists."""
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

            mock_client.assert_called_once_with(connect_sid=None)

    def test_connect_sid_argument_priority_over_file(self) -> None:
        """Test that --connect-sid has priority over --connect-sid-file."""
        with pytest.raises(SystemExit):
            main(
                test_args=["--connect-sid", "arg-value", "--connect-sid-file", "file-path", "pages", self.PROJECT_NAME]
            )
