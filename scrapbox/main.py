"""CLI for Scrapbox client."""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, cast

from . import __version__
from .client import ScrapboxClient, check_page_size, page_url
from .edits import changes_from_ops
from .models import InsertChange, Links1hopResponse, Links2hopResponse, PageBase, PageListResponse

if TYPE_CHECKING:
    from .client import PageSort, SearchSort

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
    page_id: str | None = None
    preview_id: str | None = None
    query: str | None = None
    search: str | None = None
    since: str | None = None
    sort: str | None = None
    filter: str | None = None
    hop: int = 1
    match_any: bool = False
    fetch_all: bool = False
    per_page: int | None = None
    thumbnail: bool = False
    input_file: str | None = None
    skip: int = 0
    limit: int = 100
    batch_size: int = 1000
    json: bool = False
    output: str | None = None
    connect_sid: str | None = None
    connect_sid_file: str | None = None
    pat: str | None = None
    pat_file: str | None = None


def check_page_size_arg(value: str) -> int:
    """Parse a page size argument, refusing what the API would silently replace.

    Args:
        value: The raw argument.

    Returns:
        The page size.

    Raises:
        ArgumentTypeError: If the value is not an integer in the accepted range.
    """
    try:
        size = int(value)
    except ValueError as e:
        msg = f"must be an integer, got {value!r}"
        raise argparse.ArgumentTypeError(msg) from e
    try:
        # argparse names the argument itself, so the message needs no name of its own.
        return check_page_size(size)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from e


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


def _add_page_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register the commands that read a single page or list pages.

    Args:
        subparsers: The subparser action to register on.
    """
    # pages command
    pages_parser = subparsers.add_parser("pages", help="Get page list from a project")
    pages_parser.add_argument("project", help="Project name")
    pages_parser.add_argument("--skip", type=int, default=0, help="Number of pages to skip")
    pages_parser.add_argument(
        "--limit", type=check_page_size_arg, default=100, help="Number of pages to retrieve (1-1000)"
    )
    pages_parser.add_argument(
        "--sort",
        choices=("updated", "created", "accessed", "linked", "views", "title"),
        default=None,
        help="Sort order (default: updated)",
    )
    pages_parser.add_argument(
        "--filter",
        default=None,
        help="Keep pages carrying [<name>.icon] and pages that user has edited (login name, see `whoami`)",
    )
    pages_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    pages_parser.set_defaults(handler=cmd_pages)

    # all-pages command
    all_pages_parser = subparsers.add_parser("all-pages", help="Get all pages from a project")
    all_pages_parser.add_argument("project", help="Project name")
    all_pages_parser.add_argument(
        "--batch-size",
        type=check_page_size_arg,
        default=1000,
        help="Number of pages to fetch per batch (1-1000, default: 1000)",
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

    # page-v2 command
    page_v2_parser = subparsers.add_parser("page-v2", help="Get page details from the v2 endpoint")
    page_v2_parser.add_argument("project", help="Project name")
    page_v2_parser.add_argument("title", help="Page title")
    page_v2_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    page_v2_parser.set_defaults(handler=cmd_page_v2)

    # links command
    links_parser = subparsers.add_parser("links", help="Get the 1-hop or 2-hop neighbourhood of a page")
    links_parser.add_argument("project", help="Project name")
    links_parser.add_argument("title", help="Page title")
    links_parser.add_argument("--hop", type=int, choices=(1, 2), default=1, help="Number of hops (default: 1)")
    links_parser.add_argument("--search", default=None, help="Keep only neighbours whose body matches this query")
    links_parser.add_argument(
        "--or", dest="match_any", action="store_true", help="Match any of the words instead of all"
    )
    links_parser.add_argument(
        "--all",
        dest="fetch_all",
        action="store_true",
        help="Follow the pagination cursor and retrieve every neighbour",
    )
    links_parser.add_argument(
        "--per-page", type=check_page_size_arg, default=None, help="Neighbours per request (1-1000, default: 1000)"
    )
    links_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    links_parser.set_defaults(handler=cmd_links)


def _add_search_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register the search and history commands.

    Args:
        subparsers: The subparser action to register on.
    """
    # search command
    search_parser = subparsers.add_parser("search", help="Search the full text of a project")
    search_parser.add_argument("project", help="Project name")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--or", dest="match_any", action="store_true", help="Match any of the words instead of all"
    )
    search_parser.add_argument(
        "--sort", choices=("pageRank", "updated"), default=None, help="Sort order (default: pageRank)"
    )
    search_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    search_parser.set_defaults(handler=cmd_search)

    # vector-search command
    vector_parser = subparsers.add_parser("vector-search", help="Search pages by vector similarity")
    vector_parser.add_argument("project", help="Project name")
    vector_parser.add_argument("query", help="Search query")
    vector_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    vector_parser.set_defaults(handler=cmd_vector_search)

    # commits command
    commits_parser = subparsers.add_parser("commits", help="Get the edit history of a page")
    commits_parser.add_argument("project", help="Project name")
    commits_parser.add_argument("page_id", help="Page ID (immutable, survives renames)")
    commits_parser.add_argument("--since", default=None, help="Only commits after this commit ID")
    commits_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    commits_parser.set_defaults(handler=cmd_commits)


def _add_account_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register the project and user commands.

    Args:
        subparsers: The subparser action to register on.
    """
    # members command
    members_parser = subparsers.add_parser("members", help="Get the members of a project")
    members_parser.add_argument("project", help="Project name")
    members_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    members_parser.set_defaults(handler=cmd_members)

    # projects command
    projects_parser = subparsers.add_parser("projects", help="Get the projects you belong to")
    projects_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    projects_parser.set_defaults(handler=cmd_projects)

    # project command
    project_parser = subparsers.add_parser("project", help="Get a single project by name")
    project_parser.add_argument("project", help="Project name")
    project_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    project_parser.set_defaults(handler=cmd_project)

    # whoami command
    whoami_parser = subparsers.add_parser("whoami", help="Get the authenticated user")
    whoami_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    whoami_parser.set_defaults(handler=cmd_whoami)


def _add_file_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register the file commands.

    Args:
        subparsers: The subparser action to register on.
    """
    # file command
    file_parser = subparsers.add_parser("file", help="Download a file from Scrapbox")
    file_parser.add_argument("file_id", help="File ID or full URL")
    file_parser.add_argument("--output", "-o", required=True, type=check_output_path, help="Output file path")
    file_parser.add_argument("--thumbnail", action="store_true", help="Download the scaled down version")
    file_parser.set_defaults(handler=cmd_file)

    # file-info command
    file_info_parser = subparsers.add_parser("file-info", help="Get metadata and extracted text of a file")
    file_info_parser.add_argument("file_id", help="File ID or full URL")
    file_info_parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    file_info_parser.set_defaults(handler=cmd_file_info)


def _add_edit_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register the page edit commands.

    Args:
        subparsers: The subparser action to register on.
    """
    # edit-preview command
    edit_preview_parser = subparsers.add_parser(
        "edit-preview",
        help="Dry-run a page edit and get a preview ID (personal access token only)",
    )
    edit_preview_parser.add_argument("project", help="Project name")
    edit_preview_parser.add_argument("--page-id", default=None, help="Page ID to edit. Omit to create a new page")
    edit_preview_parser.add_argument("--input-file", default=None, help="Read ops JSON from a file instead of stdin")
    edit_preview_parser.set_defaults(handler=cmd_edit_preview)

    # edit-submit command
    edit_submit_parser = subparsers.add_parser(
        "edit-submit",
        help="Commit a previewed page edit (personal access token only)",
    )
    edit_submit_parser.add_argument("project", help="Project name")
    edit_submit_parser.add_argument("preview_id", help="Preview ID returned by edit-preview")
    edit_submit_parser.set_defaults(handler=cmd_edit_submit)


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
              sbc pages my-project --sort linked --filter my-name
              sbc all-pages my-project --batch-size 500 --json
              sbc page my-project "Page Title" --json
              sbc page-v2 my-project "Page Title" --json
              sbc links my-project "Page Title" --hop 2
              sbc links my-project "Page Title" --all --json
              sbc search my-project "word1 word2" --or --sort updated
              sbc vector-search my-project "some idea"
              sbc commits my-project 6a78192b3a6ddc39bdf42b47 --since <commitId>
              sbc members my-project
              sbc projects
              sbc project my-project
              sbc whoami
              sbc text my-project "Page Title"
              sbc icon my-project "Page Title"
              sbc file 60190edf1176d9001c13f8e8.png --output image.png
              sbc file-info 60190edf1176d9001c13f8e8.png
              echo '{"ops":[{"insertBefore":"_end","text":"hello"}]}' \\
                | sbc edit-preview my-project --page-id <pageId>
              sbc edit-submit my-project <previewId>
              echo "pat_xxxxxxxx" | sbc login

            `edit-preview` and `edit-submit` are only available with a personal access
            token: the API rejects `connect.sid` for them.

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

    _add_page_commands(subparsers)
    _add_search_commands(subparsers)
    _add_account_commands(subparsers)
    _add_file_commands(subparsers)
    _add_edit_commands(subparsers)

    # login command
    login_parser = subparsers.add_parser("login", help="Save a credential read from stdin")
    login_parser.set_defaults(handler=cmd_login)

    return parser


def print_page_detail(page: PageBase, *, json_output: bool) -> None:
    """Print a page detail response, as JSON or as readable text.

    Args:
        page: The page to print. Both the v1 and v2 responses are accepted.
        json_output: Whether to print JSON instead of text.
    """
    if json_output:
        print(page.model_dump_json(indent=2, by_alias=True))
        return

    # A page that is only linked to comes back without any counts.
    lines_count = "-" if page.lines_count is None else page.lines_count
    chars_count = "-" if page.chars_count is None else page.chars_count
    output = dedent(
        f"""
        ===
        Title: {page.title}
        ID: {page.id}
        Lines: {lines_count}
        Characters: {chars_count}
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


def cmd_pages(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute pages command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.project is not None
    pages = client.get_pages(
        args.project,
        skip=args.skip,
        limit=args.limit,
        # argparse already restricted this to the accepted orders.
        sort=cast("PageSort | None", args.sort),
        filter_value=args.filter,
    )
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
    return 0


def cmd_all_pages(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute all-pages command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
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
    return 0


def cmd_page(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute page command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.project is not None
    assert args.title is not None
    page = client.get_page(args.project, args.title)
    print_page_detail(page, json_output=args.json)
    return 0


def cmd_text(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute text command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.project is not None
    assert args.title is not None
    print(client.get_page_text(args.project, args.title))
    return 0


def cmd_icon(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute icon command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.project is not None
    assert args.title is not None
    print(client.get_page_icon_url(args.project, args.title))
    return 0


def cmd_file(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute file command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.output is not None
    assert args.file_id is not None
    Path(args.output).write_bytes(client.get_file(args.file_id, thumbnail=args.thumbnail))
    print(f"Downloaded to {args.output}", file=sys.stderr)
    return 0


def cmd_page_v2(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute page-v2 command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.project is not None
    assert args.title is not None
    print_page_detail(client.get_page_v2(args.project, args.title), json_output=args.json)
    return 0


def cmd_links(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute links command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.project is not None
    assert args.title is not None
    result: Links1hopResponse | Links2hopResponse | None
    if args.fetch_all:
        # Walking the cursor spans several responses, so only the entries survive.
        iterate = client.iter_links_1hop if args.hop == 1 else client.iter_links_2hop
        result = None
        pages = list(iterate(args.project, args.title, args.search, match_any=args.match_any, per_page=args.per_page))
    elif args.hop == 1:
        one_hop = client.get_links_1hop(
            args.project, args.title, args.search, match_any=args.match_any, per_page=args.per_page
        )
        result, pages = one_hop, one_hop.links1hop
    else:
        two_hop = client.get_links_2hop(
            args.project, args.title, args.search, match_any=args.match_any, per_page=args.per_page
        )
        result, pages = two_hop, two_hop.links2hop

    if args.json:
        if result is not None:
            print(result.model_dump_json(indent=2, by_alias=True))
        else:
            entries = [page.model_dump(mode="json", by_alias=True) for page in pages]
            print(json.dumps({f"links{args.hop}hop": entries}, ensure_ascii=False, indent=2))
        return 0

    print(f"=== {args.hop} hop links: {len(pages)} ===")
    for page in pages:
        print(f"- {page.title} (linked: {page.linked}, pageRank: {page.page_rank})")
    return 0


def cmd_search(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute search command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.project is not None
    assert args.query is not None
    sort = cast("SearchSort | None", args.sort)  # argparse already restricted this
    result = client.search_pages(args.project, args.query, match_any=args.match_any, sort=sort)
    if args.json:
        print(result.model_dump_json(indent=2, by_alias=True))
        return 0

    print(f"=== {result.count} hits for {result.search_query!r} ===")
    for page in result.pages:
        print(f"- {page.title}")
        for line in page.lines:
            print(f"    {line}")
    return 0


def cmd_vector_search(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute vector-search command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.project is not None
    assert args.query is not None
    result = client.search_titles_by_vector(args.project, args.query)
    if args.json:
        print(result.model_dump_json(indent=2, by_alias=True))
        return 0

    for page in result.pages:
        exists = "" if page.exists else " (empty page)"
        print(f"- {page.title} (score: {page.score:.3f}){exists}")
    return 0


def cmd_commits(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute commits command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.project is not None
    assert args.page_id is not None
    result = client.get_commits(args.project, args.page_id, since=args.since)
    if args.json:
        print(result.model_dump_json(indent=2, by_alias=True))
        return 0

    print(f"=== {len(result.commits)} commits ===")
    for commit in result.commits:
        print(f"- {commit.id} by {commit.user_id} at {commit.created} ({len(commit.changes)} changes)")
    return 0


def cmd_members(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute members command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.project is not None
    result = client.get_project_users(args.project)
    if args.json:
        print(result.model_dump_json(indent=2, by_alias=True))
        return 0

    for member in result.users:
        print(f"- {member.display_name or member.name or member.id} ({member.name})")
    for account in result.service_accounts:
        print(f"- {account.usage} (service account)")
    return 0


def cmd_projects(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute projects command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    result = client.get_projects()
    if args.json:
        print(result.model_dump_json(indent=2, by_alias=True))
        return 0

    for project in result.projects:
        visibility = "public" if project.public_visible else "private"
        print(f"- {project.name} ({project.display_name}, {visibility}, users: {project.users_count})")
    return 0


def cmd_project(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute project command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.project is not None
    project = client.get_project(args.project)
    if args.json:
        print(project.model_dump_json(indent=2, by_alias=True))
        return 0

    print(f"name:        {project.name}")
    print(f"displayName: {project.display_name}")
    print(f"id:          {project.id}")
    print(f"visibility:  {'public' if project.public_visible else 'private'}")
    print(f"theme:       {project.theme}")
    print(f"members:     {len(project.users)}")
    return 0


def cmd_whoami(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute whoami command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    me = client.get_me()
    if args.json:
        print(me.model_dump_json(indent=2, by_alias=True))
        return 0

    print(f"name:        {me.name}")
    print(f"displayName: {me.display_name}")
    print(f"email:       {me.email}")
    print(f"id:          {me.id}")
    return 0


def cmd_file_info(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute file-info command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.file_id is not None
    info = client.get_file_info(args.file_id)
    if args.json:
        print(info.model_dump_json(indent=2, by_alias=True))
        return 0

    print(f"id:          {info.id}")
    print(f"project:     {info.project_name}")
    print(f"name:        {info.originalname}")
    print(f"contentType: {info.content_type}")
    print(f"size:        {info.size}")
    if info.text:
        print()
        print(info.text)
    return 0


def read_ops(input_file: str | None) -> list[dict[str, object]]:
    """Read the ops JSON for an edit from a file or stdin.

    Args:
        input_file: Path to read from, or None to read stdin.

    Returns:
        The ops to apply.

    Raises:
        ValueError: If the input is empty or does not hold an `ops` list.
    """
    raw = Path(input_file).read_text(encoding="utf-8") if input_file else sys.stdin.read()
    if not raw.strip():
        source = f"input file '{input_file}'" if input_file else "stdin"
        example = '{"ops":[{"insertBefore":"_end","text":"..."}]}'
        msg = f"{source} is empty. Provide ops JSON, e.g. {example}"
        raise ValueError(msg)
    ops = json.loads(raw).get("ops")
    if ops is None:
        msg = "ops JSON must have an 'ops' key"
        raise ValueError(msg)
    return ops


def cmd_edit_preview(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute edit-preview command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.project is not None
    changes = changes_from_ops(read_ops(args.input_file))
    preview = client.preview_page_edit(args.project, changes, page_id=args.page_id)
    page_preview = preview.page_preview

    # The ids of the inserted lines are chosen here, not by the server, so they can be
    # shown right away: a follow-up edit needs them as anchors.
    new_ids = {change.lines.id for change in changes if isinstance(change, InsertChange) and change.lines.id}

    status = "create" if page_preview is not None and page_preview.persistent is False else "update"
    print(f"previewId: {preview.preview_id}")
    print(f"expireAt:  {preview.expire_at}")
    print(f"status:    {status}")
    print(f"title:     {page_preview.title if page_preview else ''}")
    print()
    print("page (after apply):")
    for line in page_preview.lines if page_preview else []:
        marker = f"> {line.text}\t# {line.id}" if line.id in new_ids else f"  {line.text}"
        print(marker)
    return 0


def cmd_edit_submit(client: ScrapboxClient, args: ScrapboxCliArgs) -> int:
    """Execute edit-submit command.

    Args:
        client: ScrapboxClient instance.
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    assert args.project is not None
    assert args.preview_id is not None
    result = client.submit_page_edit(args.project, args.preview_id)
    title = result.page.title if result.page else None
    print(f"commitId: {result.commit_id}")
    print(f"title:    {title}")
    if title is not None:
        print(f"url:      {page_url(args.project, title)}")
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
        try:
            return args.handler(client, args)
        except Exception as e:  # noqa: BLE001
            print(f"Error: {e}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(main())
