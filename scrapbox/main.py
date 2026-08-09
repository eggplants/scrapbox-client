"""CLI for Scrapbox client."""

import argparse
import getpass
import os
import sys
from pathlib import Path
from textwrap import dedent

from . import __version__
from .client import ScrapboxClient
from .models import PageListResponse

CONNECT_SID_FILE_NAME = "connect.sid"
"""File name of the saved connect.sid, under the config directory."""

PAT_FILE_NAME = "pat"
"""File name of the saved personal access token, under the config directory."""

CONNECT_SID_PREFIX = "s%"
"""Prefix identifying a connect.sid cookie value."""

PAT_PREFIX = "pat_"
"""Prefix identifying a personal access token."""


class ScrapboxCliArgs(argparse.Namespace):
    """Dataclass for CLI arguments."""

    command: str
    project: str | None = None
    title: str | None = None
    file_id: str | None = None
    skip: int = 0
    limit: int = 100
    batch_size: int = 1000
    json: bool = False
    output: str | None = None
    connect_sid: str | None = None
    connect_sid_file: str | None = None
    pat: str | None = None
    pat_file: str | None = None


def check_output_path(path_str: str) -> str:
    """Check if the output path is valid.

    Args:
        path_str: The output path string.

    Returns:
        The validated output path string.
    """
    path = Path(path_str)
    if path.exists() and path.is_dir():
        msg = f"Output path '{path_str}' is a directory."
        raise argparse.ArgumentTypeError(msg)
    if not path.parent.exists():
        msg = f"Parent directory of '{path_str}' does not exist."
        raise argparse.ArgumentTypeError(msg)
    return path_str


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI.

    Args:
        test_args: Optional list of test arguments for testing.

    Returns:
        The argument parser instance.
    """
    parser = argparse.ArgumentParser(
        description="Scrapbox API client CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent(
            """
            examples:
              sbc pages my-project --limit 10 --skip 10 --json
              sbc all-pages my-project --batch-size 500 --json
              sbc page my-project "Page Title" --json
              sbc text my-project "Page Title"
              sbc icon my-project "Page Title"
              sbc file 60190edf1176d9001c13f8e8.png --output image.png
              echo "pat_xxxxxxxx" | sbc login

            `sbc login` saves the credential read from stdin, choosing the file by
            its prefix: `s%` for ~/.config/sbc/connect.sid, `pat_` for ~/.config/sbc/pat

            priority of `connect.sid` source:
              1. --connect-sid argument
              2. --connect-sid-file argument
              3. ~/.config/sbc/connect.sid file
              4. SBC_CONNECT_SID environment variable

            priority of personal access token source:
              1. --pat argument
              2. --pat-file argument
              3. ~/.config/sbc/pat file
              4. SBC_PAT environment variable

            a personal access token takes precedence over `connect.sid`
            """
        ),
    )
    # version
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"sbc {__version__}",
        help="Show program's version number and exit",
    )

    auth_group = parser.add_mutually_exclusive_group()
    auth_group.add_argument(
        "--connect-sid",
        help="Scrapbox authentication cookie (connect.sid)",
        default=None,
    )
    auth_group.add_argument(
        "--connect-sid-file",
        help="Path to file containing connect.sid (default: ~/.config/sbc/connect.sid)",
        default=None,
    )

    pat_group = parser.add_mutually_exclusive_group()
    pat_group.add_argument(
        "--pat",
        help="Scrapbox personal access token (takes precedence over connect.sid)",
        default=None,
    )
    pat_group.add_argument(
        "--pat-file",
        help="Path to file containing a personal access token (default: ~/.config/sbc/pat)",
        default=None,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # pages command
    pages_parser = subparsers.add_parser("pages", help="Get page list from a project")
    pages_parser.add_argument("project", help="Project name")
    pages_parser.add_argument("--skip", type=int, default=0, help="Number of pages to skip")
    pages_parser.add_argument("--limit", type=int, default=100, help="Number of pages to retrieve")
    pages_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    pages_parser.set_defaults(handler=cmd_pages)

    # all-pages command
    all_pages_parser = subparsers.add_parser("all-pages", help="Get all pages from a project")
    all_pages_parser.add_argument("project", help="Project name")
    all_pages_parser.add_argument(
        "--batch-size", type=int, default=1000, help="Number of pages to fetch per batch (default: 1000)"
    )
    all_pages_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    all_pages_parser.set_defaults(handler=cmd_all_pages)

    # page command
    page_parser = subparsers.add_parser("page", help="Get detailed information about a page")
    page_parser.add_argument("project", help="Project name")
    page_parser.add_argument("title", help="Page title")
    page_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    page_parser.set_defaults(handler=cmd_page)

    # text command
    text_parser = subparsers.add_parser("text", help="Get text content of a page")
    text_parser.add_argument("project", help="Project name")
    text_parser.add_argument("title", help="Page title")
    text_parser.set_defaults(handler=cmd_text)

    # icon command
    icon_parser = subparsers.add_parser("icon", help="Get icon URL for a page")
    icon_parser.add_argument("project", help="Project name")
    icon_parser.add_argument("title", help="Page title")
    icon_parser.set_defaults(handler=cmd_icon)

    # file command
    file_parser = subparsers.add_parser("file", help="Download a file from Scrapbox")
    file_parser.add_argument("file_id", help="File ID or full URL")
    file_parser.add_argument("--output", "-o", required=True, type=check_output_path, help="Output file path")
    file_parser.set_defaults(handler=cmd_file)

    # login command
    login_parser = subparsers.add_parser("login", help="Save a credential read from stdin")
    login_parser.set_defaults(handler=cmd_login)

    return parser


def cmd_pages(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute pages command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    try:
        assert args.project is not None
        pages = client.get_pages(args.project, skip=args.skip, limit=args.limit)
        if args.json:
            print(pages.model_dump_json(indent=2, by_alias=True))
        else:
            output = dedent(
                f"""
                ===
                Project: {pages.project_name}
                Total pages: {pages.count}
                Skip: {pages.skip}, Limit: {pages.limit}
                ===
                """
            )
            for page in pages.pages:
                output += f"- {page.title} (views: {page.views}, updated: {page.updated})\n"
            print(output.rstrip())
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_all_pages(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute all-pages command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    try:
        assert args.project is not None
        all_pages = []
        skip = 0
        batch_size = args.batch_size

        print("Fetching all pages...", file=sys.stderr)

        while True:
            pages = client.get_pages(args.project, skip=skip, limit=batch_size)

            if not pages.pages:
                break

            all_pages.extend(pages.pages)
            skip += len(pages.pages)

            print(f"Fetched {len(all_pages)}/{pages.count} pages...", file=sys.stderr)

            if skip >= pages.count:
                break

        if args.json:
            result = PageListResponse.model_validate(
                {
                    "project_name": pages.project_name,
                    "skip": 0,
                    "limit": len(all_pages),
                    "count": len(all_pages),
                    "pages": all_pages,
                }
            )
            print(result.model_dump_json(indent=2, by_alias=True))
        else:
            output = dedent(
                f"""
                ===
                Project: {pages.project_name}
                Total pages: {len(all_pages)}
                ===
                """
            )
            for page in all_pages:
                output += f"- {page.title} (views: {page.views}, updated: {page.updated})\n"
            print(output.rstrip())
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_page(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute page command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    try:
        assert args.project is not None
        assert args.title is not None
        page = client.get_page(args.project, args.title)
        if args.json:
            print(page.model_dump_json(indent=2, by_alias=True))
        else:
            output = dedent(
                f"""
                ===
                Title: {page.title}
                ID: {page.id}
                Lines: {page.lines_count}
                Characters: {page.chars_count}
                Views: {page.views}
                Created: {page.created}
                Updated: {page.updated}
                ===

                Content:
                """
            )
            for line in page.lines:
                output += f"  {line.text}\n"
            print(output.rstrip())
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_text(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute text command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    try:
        assert args.project is not None
        assert args.title is not None
        print(client.get_page_text(args.project, args.title))
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_icon(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute icon command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    try:
        assert args.project is not None
        assert args.title is not None
        print(client.get_page_icon_url(args.project, args.title))
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_file(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute file command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    try:
        assert args.output is not None
        assert args.file_id is not None
        Path(args.output).write_bytes(client.get_file(args.file_id))
        print(f"Downloaded to {args.output}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def get_config_dir() -> Path:
    """Get the directory where credentials are stored.

    Returns:
        The ~/.config/sbc directory path.
    """
    return Path.home() / ".config" / "sbc"


def read_credential_from_stdin() -> str:
    """Read a credential from stdin, without echoing it back on a terminal.

    Returns:
        The credential string, stripped of surrounding whitespace.
    """
    if sys.stdin.isatty():
        return getpass.getpass("Enter connect.sid or personal access token: ").strip()
    return sys.stdin.read().strip()


def save_credential(credential: str) -> Path:
    """Save a credential to the file matching its type.

    The credential type is detected from its prefix: `s%` for a connect.sid
    cookie, `pat_` for a personal access token.

    Args:
        credential: The credential to save.

    Returns:
        The path the credential was written to.

    Raises:
        ValueError: If the credential is empty or of an unknown type.
    """
    if not credential:
        msg = "No credential given."
        raise ValueError(msg)
    if len(credential.split()) > 1:
        msg = "Credential must be a single line without whitespace."
        raise ValueError(msg)

    if credential.startswith(CONNECT_SID_PREFIX):
        file_name = CONNECT_SID_FILE_NAME
    elif credential.startswith(PAT_PREFIX):
        file_name = PAT_FILE_NAME
    else:
        msg = (
            f"Unknown credential type: expected a connect.sid starting with "
            f"'{CONNECT_SID_PREFIX}' or a personal access token starting with '{PAT_PREFIX}'."
        )
        raise ValueError(msg)

    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    credential_file = config_dir / file_name
    credential_file.touch(mode=0o600, exist_ok=True)
    credential_file.chmod(0o600)
    credential_file.write_text(f"{credential}\n")
    return credential_file


def cmd_login() -> int:
    """Execute login command.

    Unlike the other commands, this one takes no client: it only writes to the
    config directory.

    Returns:
        Exit code.
    """
    try:
        credential_file = save_credential(read_credential_from_stdin())
    except (ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"Saved to {credential_file}", file=sys.stderr)
    return 0


def get_credential(value: str | None, file_path: str | None, default_file_name: str, env_var: str) -> str | None:
    """Get a credential from arguments, a default file, or the environment.

    Args:
        value: Credential passed directly as an argument.
        file_path: Path to a file containing the credential.
        default_file_name: File name looked up under ~/.config/sbc/.
        env_var: Name of the environment variable to fall back to.

    Returns:
        The credential string or None if not found.
    """
    if value:
        return value

    if file_path:
        credential_file = Path(file_path)
        if credential_file.exists():
            return credential_file.read_text().strip()

    default_file = get_config_dir() / default_file_name
    if default_file.exists():
        return default_file.read_text().strip()

    if env_var in os.environ:
        return os.environ[env_var]

    return None


def get_connect_sid(args: ScrapboxCliArgs) -> str | None:
    """Get connect.sid from arguments or default location.

    Args:
        args: Parsed command-line arguments.

    Returns:
        The connect.sid string or None if not found.
    """
    return get_credential(args.connect_sid, args.connect_sid_file, CONNECT_SID_FILE_NAME, "SBC_CONNECT_SID")


def get_pat(args: ScrapboxCliArgs) -> str | None:
    """Get the personal access token from arguments or default location.

    Args:
        args: Parsed command-line arguments.

    Returns:
        The personal access token string or None if not found.
    """
    return get_credential(args.pat, args.pat_file, PAT_FILE_NAME, "SBC_PAT")


def main(*, test_args: list[str] | None = None) -> int:
    """Main entry point for CLI.

    Returns:
        Exit code.
    """
    parser = create_parser()
    args = (
        parser.parse_args(test_args, namespace=ScrapboxCliArgs())
        if test_args is not None
        else parser.parse_args(namespace=ScrapboxCliArgs())
    )

    if not hasattr(args, "handler"):
        parser.print_help()
        return 1

    if args.handler is cmd_login:
        return cmd_login()

    with ScrapboxClient(connect_sid=get_connect_sid(args), pat=get_pat(args)) as client:
        return args.handler(client, args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
