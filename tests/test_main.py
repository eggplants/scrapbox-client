"""Tests for CLI main module."""

from __future__ import annotations

import argparse
import io
import json
import stat
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from scrapbox.client import MAX_PAGE_SIZE
from scrapbox.exceptions import PersonalAccessTokenRequiredError
from scrapbox.main import check_output_path, get_connect_sid, get_pat, main, save_credential
from scrapbox.models import (
    Commit,
    CommitsResponse,
    EditPreviewResponse,
    EditSubmitResponse,
    FileInfo,
    Me,
    PagePreview,
    PreviewLine,
    Project,
    ProjectsResponse,
    SubmittedPage,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
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

    def test_file_command_video_file(self, tmp_path: Path) -> None:
        """Test file command with video file ID."""
        output_file = tmp_path / "downloaded_file.mp4"
        video_file_id = "https://gyazo.com/2b10554d1274b76f058a11b69c6a88dd"
        exit_code = main(test_args=["file", video_file_id, "--output", str(output_file)])
        assert exit_code == 0
        assert output_file.exists()

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

    def test_file_not_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when specified file doesn't exist."""
        # Isolate the home directory and the environment: without this the lookup falls
        # back to the real ~/.config/sbc/connect.sid and the test fails on a machine
        # where a credential has actually been saved.
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        monkeypatch.delenv("SBC_CONNECT_SID", raising=False)
        non_existent_file = tmp_path / "non_existent.sid"
        args = MagicMock()
        args.connect_sid = None
        args.connect_sid_file = str(non_existent_file)
        result = get_connect_sid(args)
        assert result is None


class TestGetPat:
    """Test get_pat function."""

    def test_from_argument(self) -> None:
        """Test getting the personal access token from argument."""
        args = MagicMock()
        args.pat = "arg-value"
        args.pat_file = None
        result = get_pat(args)
        assert result == "arg-value"

    def test_from_file(self, tmp_path: Path) -> None:
        """Test getting the personal access token from specified file."""
        pat_file = tmp_path / "test.pat"
        pat_file.write_text("file-value\n")
        args = MagicMock()
        args.pat = None
        args.pat_file = str(pat_file)
        result = get_pat(args)
        assert result == "file-value"

    def test_from_default_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting the personal access token from default file."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        config_dir = tmp_path / ".config" / "sbc"
        config_dir.mkdir(parents=True)
        (config_dir / "pat").write_text("default-value\n")

        args = MagicMock()
        args.pat = None
        args.pat_file = None
        result = get_pat(args)
        assert result == "default-value"

    def test_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting the personal access token from the environment."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        monkeypatch.setenv("SBC_PAT", "env-value")
        args = MagicMock()
        args.pat = None
        args.pat_file = None
        result = get_pat(args)
        assert result == "env-value"

    def test_none_when_no_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returning None when no file exists."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        monkeypatch.delenv("SBC_PAT", raising=False)
        args = MagicMock()
        args.pat = None
        args.pat_file = None
        result = get_pat(args)
        assert result is None


class TestConnectSidPriority:
    """Test connect.sid priority logic."""

    PROJECT_NAME = "help-jp"

    @pytest.fixture(autouse=True)
    def _isolate_credentials(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Keep ambient credential files and environment variables out of these tests."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        monkeypatch.delenv("SBC_CONNECT_SID", raising=False)
        monkeypatch.delenv("SBC_PAT", raising=False)

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

            mock_client.assert_called_once_with(connect_sid="arg-sid-value", pat=None)

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

            mock_client.assert_called_once_with(connect_sid="file-sid-value", pat=None)

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

            mock_client.assert_called_once_with(connect_sid="default-sid-value", pat=None)

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

            mock_client.assert_called_once_with(connect_sid=None, pat=None)

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

            mock_client.assert_called_once_with(connect_sid=None, pat=None)

    def test_connect_sid_argument_priority_over_file(self) -> None:
        """Test that --connect-sid has priority over --connect-sid-file."""
        with pytest.raises(SystemExit):
            main(
                test_args=["--connect-sid", "arg-value", "--connect-sid-file", "file-path", "pages", self.PROJECT_NAME]
            )


class TestPatPriority:
    """Test personal access token priority logic."""

    PROJECT_NAME = "help-jp"

    @pytest.fixture(autouse=True)
    def _isolate_credentials(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Keep ambient credential files and environment variables out of these tests."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        monkeypatch.delenv("SBC_CONNECT_SID", raising=False)
        monkeypatch.delenv("SBC_PAT", raising=False)

    def _mock_client(self) -> MagicMock:
        """Build a patched ScrapboxClient returning an empty page list."""
        mock_client = MagicMock()
        mock_instance = MagicMock()
        mock_client.return_value.__enter__.return_value = mock_instance
        mock_instance.get_pages.return_value = MagicMock(
            project_name=self.PROJECT_NAME,
            count=0,
            skip=0,
            limit=100,
            pages=[],
        )
        return mock_client

    def test_pat_from_argument(self) -> None:
        """Test that --pat is passed to the client."""
        mock_client = self._mock_client()
        with patch("scrapbox.main.ScrapboxClient", mock_client):
            main(test_args=["--pat", "arg-pat-value", "pages", self.PROJECT_NAME])

            mock_client.assert_called_once_with(connect_sid=None, pat="arg-pat-value")

    def test_pat_from_file(self, tmp_path: Path) -> None:
        """Test that --pat-file is used when --pat is not provided."""
        pat_file = tmp_path / "test.pat"
        pat_file.write_text("file-pat-value\n")

        mock_client = self._mock_client()
        with patch("scrapbox.main.ScrapboxClient", mock_client):
            main(test_args=["--pat-file", str(pat_file), "pages", self.PROJECT_NAME])

            mock_client.assert_called_once_with(connect_sid=None, pat="file-pat-value")

    def test_pat_from_default_file(self, tmp_path: Path) -> None:
        """Test that default ~/.config/sbc/pat is used when no arguments provided."""
        config_dir = tmp_path / ".config" / "sbc"
        config_dir.mkdir(parents=True)
        (config_dir / "pat").write_text("default-pat-value\n")

        mock_client = self._mock_client()
        with patch("scrapbox.main.ScrapboxClient", mock_client):
            main(test_args=["pages", self.PROJECT_NAME])

            mock_client.assert_called_once_with(connect_sid=None, pat="default-pat-value")

    def test_pat_and_connect_sid_are_both_passed(self) -> None:
        """Test that both credentials reach the client, which resolves the precedence."""
        mock_client = self._mock_client()
        with patch("scrapbox.main.ScrapboxClient", mock_client):
            main(test_args=["--connect-sid", "sid-value", "--pat", "pat-value", "pages", self.PROJECT_NAME])

            mock_client.assert_called_once_with(connect_sid="sid-value", pat="pat-value")

    def test_pat_argument_priority_over_file(self) -> None:
        """Test that --pat and --pat-file are mutually exclusive."""
        with pytest.raises(SystemExit):
            main(test_args=["--pat", "arg-value", "--pat-file", "file-path", "pages", self.PROJECT_NAME])


class TestLogin:
    """Test the login command."""

    OWNER_ONLY_MODE = 0o600

    @pytest.fixture(autouse=True)
    def _fake_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Redirect the config directory into a temporary home."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    @staticmethod
    def _set_stdin(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
        """Feed text to stdin as a non-interactive stream."""
        monkeypatch.setattr("sys.stdin", io.StringIO(text))

    def test_save_pat(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a pat_ credential is saved to the pat file."""
        self._set_stdin(monkeypatch, "pat_abc123\n")
        assert main(test_args=["login"]) == 0
        assert (tmp_path / ".config" / "sbc" / "pat").read_text() == "pat_abc123\n"
        assert not (tmp_path / ".config" / "sbc" / "connect.sid").exists()

    def test_save_connect_sid(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that an s% credential is saved to the connect.sid file."""
        self._set_stdin(monkeypatch, "s%3Aabc123\n")
        assert main(test_args=["login"]) == 0
        assert (tmp_path / ".config" / "sbc" / "connect.sid").read_text() == "s%3Aabc123\n"
        assert not (tmp_path / ".config" / "sbc" / "pat").exists()

    def test_saved_credential_is_read_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a saved credential is picked up by the credential lookup."""
        self._set_stdin(monkeypatch, "pat_abc123\n")
        assert main(test_args=["login"]) == 0

        monkeypatch.delenv("SBC_PAT", raising=False)
        args = MagicMock()
        args.pat = None
        args.pat_file = None
        assert get_pat(args) == "pat_abc123"

    def test_credential_file_is_not_world_readable(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that the saved credential is only readable by its owner."""
        self._set_stdin(monkeypatch, "pat_abc123\n")
        assert main(test_args=["login"]) == 0

        mode = (tmp_path / ".config" / "sbc" / "pat").stat().st_mode
        assert stat.S_IMODE(mode) == self.OWNER_ONLY_MODE

    def test_existing_credential_is_overwritten(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that logging in again replaces the stored credential."""
        config_dir = tmp_path / ".config" / "sbc"
        config_dir.mkdir(parents=True)
        (config_dir / "pat").write_text("pat_old\n")

        self._set_stdin(monkeypatch, "pat_new\n")
        assert main(test_args=["login"]) == 0
        assert (config_dir / "pat").read_text() == "pat_new\n"

    def test_unknown_prefix_is_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a credential with an unknown prefix is rejected."""
        self._set_stdin(monkeypatch, "bogus-value\n")
        assert main(test_args=["login"]) == 1
        assert not (tmp_path / ".config" / "sbc").exists()

    def test_empty_input_is_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that empty input is rejected."""
        self._set_stdin(monkeypatch, "   \n")
        assert main(test_args=["login"]) == 1
        assert not (tmp_path / ".config" / "sbc").exists()

    def test_multiline_input_is_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that input holding more than one value is rejected."""
        self._set_stdin(monkeypatch, "pat_abc123\npat_def456\n")
        assert main(test_args=["login"]) == 1
        assert not (tmp_path / ".config" / "sbc").exists()

    def test_prompts_without_echo_on_a_terminal(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that an interactive terminal is prompted via getpass."""
        stdin = MagicMock()
        stdin.isatty.return_value = True
        monkeypatch.setattr("sys.stdin", stdin)
        with patch("scrapbox.main.getpass.getpass", return_value="pat_abc123\n") as mock_getpass:
            assert main(test_args=["login"]) == 0

        mock_getpass.assert_called_once()
        stdin.read.assert_not_called()
        assert (tmp_path / ".config" / "sbc" / "pat").read_text() == "pat_abc123\n"

    def test_login_does_not_build_a_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that login does not construct a ScrapboxClient."""
        self._set_stdin(monkeypatch, "pat_abc123\n")
        with patch("scrapbox.main.ScrapboxClient") as mock_client:
            assert main(test_args=["login"]) == 0

        mock_client.assert_not_called()

    @pytest.mark.parametrize("credential", ["pat_abc123", "s%3Aabc123"])
    def test_save_credential_returns_path(self, tmp_path: Path, credential: str) -> None:
        """Test that save_credential returns the file it wrote to."""
        path = save_credential(credential)
        assert path.parent == tmp_path / ".config" / "sbc"
        assert path.read_text() == f"{credential}\n"


class TestReadCommands:
    """Test the commands that read from a public project."""

    PROJECT_NAME = "help-jp"
    PAGE_TITLE = "ブラケティング"

    def test_page_v2_command(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test page-v2 command."""
        exit_code = main(test_args=["page-v2", self.PROJECT_NAME, self.PAGE_TITLE])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert f"Title: {self.PAGE_TITLE}" in captured.out
        assert not captured.err

    def test_page_v2_command_json(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test page-v2 command with JSON output."""
        exit_code = main(test_args=["page-v2", self.PROJECT_NAME, self.PAGE_TITLE, "--json"])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert '"linksLc"' in captured.out
        assert not captured.err

    def test_links_command(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test links command."""
        exit_code = main(test_args=["links", self.PROJECT_NAME, self.PAGE_TITLE])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert "1 hop links:" in captured.out
        assert not captured.err

    def test_links_command_two_hops(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test links command for the 2-hop neighbourhood."""
        exit_code = main(test_args=["links", self.PROJECT_NAME, self.PAGE_TITLE, "--hop", "2", "--json"])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert '"links2hop"' in captured.out

    def test_links_command_all(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test that --all walks the cursor and finds the whole neighbourhood."""
        one_page = main(test_args=["links", self.PROJECT_NAME, self.PAGE_TITLE])
        assert one_page == 0
        expected = capfd.readouterr().out

        exit_code = main(test_args=["links", self.PROJECT_NAME, self.PAGE_TITLE, "--all", "--per-page", "2"])

        assert exit_code == 0
        assert capfd.readouterr().out == expected

    def test_links_command_all_json(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test that --all keeps the JSON output keyed by hop."""
        exit_code = main(test_args=["links", self.PROJECT_NAME, self.PAGE_TITLE, "--all", "--per-page", "2", "--json"])

        assert exit_code == 0
        payload = json.loads(capfd.readouterr().out)
        assert list(payload) == ["links1hop"]
        assert all(entry["title"] for entry in payload["links1hop"])

    def test_links_command_all_two_hops_json(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test that --all keys the 2-hop output by its own hop."""
        exit_code = main(
            test_args=["links", self.PROJECT_NAME, self.PAGE_TITLE, "--hop", "2", "--all", "--per-page", "2", "--json"]
        )

        assert exit_code == 0
        assert list(json.loads(capfd.readouterr().out)) == ["links2hop"]

    def test_project_command(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test project command."""
        exit_code = main(test_args=["project", self.PROJECT_NAME])

        assert exit_code == 0
        captured = capfd.readouterr()
        assert f"name:        {self.PROJECT_NAME}" in captured.out
        assert "visibility:  public" in captured.out
        assert not captured.err

    def test_project_command_json(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test project command with JSON output."""
        exit_code = main(test_args=["project", self.PROJECT_NAME, "--json"])

        assert exit_code == 0
        payload = json.loads(capfd.readouterr().out)
        assert payload["name"] == self.PROJECT_NAME
        assert payload["users"]

    def test_project_command_unknown_project(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test that an unknown project name exits non-zero."""
        exit_code = main(test_args=["project", "this-project-definitely-does-not-exist-12345"])

        assert exit_code == 1
        assert "Error:" in capfd.readouterr().err

    def test_search_command(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test search command."""
        exit_code = main(test_args=["search", self.PROJECT_NAME, "リンク"])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert "hits for" in captured.out
        assert not captured.err

    def test_search_command_json(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test search command with JSON output."""
        exit_code = main(test_args=["search", self.PROJECT_NAME, "リンク", "--or", "--sort", "updated", "--json"])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert '"searchQuery"' in captured.out

    def test_members_command(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test members command."""
        exit_code = main(test_args=["members", self.PROJECT_NAME])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert captured.out.startswith("- ")
        assert not captured.err

    def test_pages_command_with_sort(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test pages command with an explicit sort order."""
        exit_code = main(test_args=["pages", self.PROJECT_NAME, "--sort", "title", "--limit", "3"])
        assert exit_code == 0
        captured = capfd.readouterr()
        assert "Project:" in captured.out

    def test_pages_command_rejects_unknown_sort(self) -> None:
        """Test that an unknown sort order is refused by the parser."""
        with pytest.raises(SystemExit) as e:
            main(test_args=["pages", self.PROJECT_NAME, "--sort", "nonsense"])
        assert e.value.code == ARGPARSE_ERROR_CODE

    @pytest.mark.parametrize(
        "args",
        [
            ["pages", PROJECT_NAME, "--limit", "1001"],
            ["pages", PROJECT_NAME, "--limit", "0"],
            ["pages", PROJECT_NAME, "--limit", "-1"],
            ["pages", PROJECT_NAME, "--limit", "abc"],
            ["all-pages", PROJECT_NAME, "--batch-size", "1001"],
            ["links", PROJECT_NAME, PAGE_TITLE, "--per-page", "1001"],
        ],
    )
    def test_page_size_out_of_range_is_refused(self, args: list[str], capfd: pytest.CaptureFixture[str]) -> None:
        """Test that a page size the API would silently replace is refused."""
        with pytest.raises(SystemExit) as e:
            main(test_args=args)

        assert e.value.code == ARGPARSE_ERROR_CODE
        assert "must be" in capfd.readouterr().err

    def test_pages_command_accepts_the_largest_page_size(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Test that the largest accepted page size still goes through."""
        exit_code = main(test_args=["pages", self.PROJECT_NAME, "--limit", str(MAX_PAGE_SIZE)])

        assert exit_code == 0
        assert "Project:" in capfd.readouterr().out


class TestAuthenticatedCommands:
    """Test the commands that need a credential, against a mocked client."""

    @pytest.fixture
    def client(self) -> Iterator[MagicMock]:
        """Replace the client the CLI builds with a mock.

        These commands need a credential, so the real API is never called here.
        """
        with patch("scrapbox.main.ScrapboxClient") as mock_class:
            instance = MagicMock()
            mock_class.return_value.__enter__.return_value = instance
            yield instance

    def test_whoami_command(self, client: MagicMock, capfd: pytest.CaptureFixture[str]) -> None:
        """Test whoami command."""
        client.get_me.return_value = Me(id="abc", name="shokai", display_name="Sho", email="s@example.com")

        exit_code = main(test_args=["whoami"])

        assert exit_code == 0
        captured = capfd.readouterr()
        assert "name:        shokai" in captured.out
        assert "s@example.com" in captured.out

    def test_projects_command(self, client: MagicMock, capfd: pytest.CaptureFixture[str]) -> None:
        """Test projects command."""
        client.get_projects.return_value = ProjectsResponse(
            projects=[Project(id="1", name="my-project", display_name="Mine", public_visible=False, users_count=3)]
        )

        exit_code = main(test_args=["projects"])

        assert exit_code == 0
        assert "- my-project (Mine, private, users: 3)" in capfd.readouterr().out

    def test_commits_command(self, client: MagicMock, capfd: pytest.CaptureFixture[str]) -> None:
        """Test commits command."""
        client.get_commits.return_value = CommitsResponse(
            commits=[Commit(id="c1", user_id="u1", created=1, changes=[{"linesCount": 1}])]
        )

        exit_code = main(test_args=["commits", "my-project", "page-id", "--since", "c0"])

        assert exit_code == 0
        assert "1 commits" in capfd.readouterr().out
        client.get_commits.assert_called_once_with("my-project", "page-id", since="c0")

    def test_file_info_command(self, client: MagicMock, capfd: pytest.CaptureFixture[str]) -> None:
        """Test file-info command."""
        client.get_file_info.return_value = FileInfo(
            id="f1",
            project_name="my-project",
            originalname="a.png",
            content_type="image/png",
            size=10,
            text="ocr",
        )

        exit_code = main(test_args=["file-info", "f1.png"])

        assert exit_code == 0
        captured = capfd.readouterr()
        assert "contentType: image/png" in captured.out
        assert "ocr" in captured.out

    def test_edit_preview_command(
        self,
        client: MagicMock,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test edit-preview command reading ops from stdin."""
        monkeypatch.setattr("sys.stdin", io.StringIO('{"ops":[{"insertBefore":"_end","text":"hello"}]}'))
        client.preview_page_edit.return_value = EditPreviewResponse(
            preview_id="p1",
            expire_at="2026-08-09T06:47:53.590Z",
            page_preview=PagePreview(title="test", persistent=True, lines=[PreviewLine(id="l1", text="hello")]),
        )

        exit_code = main(test_args=["edit-preview", "my-project", "--page-id", "pid"])

        assert exit_code == 0
        captured = capfd.readouterr()
        assert "previewId: p1" in captured.out
        assert "status:    update" in captured.out
        # The ops were turned into changes and the page id passed through.
        _, kwargs = client.preview_page_edit.call_args
        assert kwargs["page_id"] == "pid"

    def test_edit_preview_rejects_empty_input(
        self,
        client: MagicMock,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that edit-preview fails when nothing is piped in."""
        monkeypatch.setattr("sys.stdin", io.StringIO(""))

        exit_code = main(test_args=["edit-preview", "my-project"])

        assert exit_code == 1
        assert "is empty" in capfd.readouterr().err
        client.preview_page_edit.assert_not_called()

    def test_edit_submit_command(self, client: MagicMock, capfd: pytest.CaptureFixture[str]) -> None:
        """Test edit-submit command."""
        client.submit_page_edit.return_value = EditSubmitResponse(commit_id="c1", page=SubmittedPage(title="a b"))

        exit_code = main(test_args=["edit-submit", "my-project", "p1"])

        assert exit_code == 0
        captured = capfd.readouterr()
        assert "commitId: c1" in captured.out
        # The title is percent-encoded back into a URL.
        assert "url:      https://scrapbox.io/my-project/a_b" in captured.out

    def test_edit_without_pat_is_reported(
        self,
        client: MagicMock,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that the personal-access-token-only error reaches the user."""
        monkeypatch.setattr("sys.stdin", io.StringIO('{"ops":[]}'))
        client.preview_page_edit.side_effect = PersonalAccessTokenRequiredError("/preview")

        exit_code = main(test_args=["edit-preview", "my-project"])

        assert exit_code == 1
        assert "personal access token" in capfd.readouterr().err
