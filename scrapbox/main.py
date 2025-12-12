"""CLI for Scrapbox client."""

import argparse
import os
import sys
from pathlib import Path
from textwrap import dedent

from . import __version__
from .client import ScrapboxClient
from .models import PageListResponse


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

            priority of `connect.sid` source:
              1. --connect-sid argument
              2. --connect-sid-file argument
              3. ~/.config/sbc/connect.sid file
              4. SBC_CONNECT_SID environment variable
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


def get_connect_sid(args: ScrapboxCliArgs) -> str | None:
    """Get connect.sid from arguments or default location.

    Args:
        args: Parsed command-line arguments.

    Returns:
        The connect.sid string or None if not found.
    """
    if args.connect_sid:
        return args.connect_sid

    if args.connect_sid_file:
        sid_file = Path(args.connect_sid_file)
        if sid_file.exists():
            return sid_file.read_text().strip()

    default_sid_file = Path.home() / ".config" / "sbc" / "connect.sid"
    if default_sid_file.exists():
        return default_sid_file.read_text().strip()

    if "SBC_CONNECT_SID" in os.environ:
        return os.environ["SBC_CONNECT_SID"]

    return None


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

    with ScrapboxClient(connect_sid=get_connect_sid(args)) as client:
        return args.handler(client, args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
