# scrapbox-client

[![PyPI version](
  <https://badge.fury.io/py/scrapbox-client.svg>
  )](
  <https://badge.fury.io/py/scrapbox-client>
) [![CI](
  <https://github.com/eggplants/scrapbox-client/actions/workflows/ci.yml/badge.svg>
  )](
  <https://github.com/eggplants/scrapbox-client/actions/workflows/ci.yml>
)

[Scrapbox (Helpfeel Cosense)](https://scrapbox.io/product) Client

The HTTP endpoints this package talks to are documented in
[cosense-api.md](cosense-api.md).

## Install

```bash
pip install scrapbox-client
```

## CLI

```shellsession
$ sbc
usage: sbc [-h] [--version] [--connect-sid CONNECT_SID | --connect-sid-file CONNECT_SID_FILE] [--pat PAT | --pat-file PAT_FILE] {pages,all-pages,page,text,icon,page-v2,links,search,vector-search,commits,members,projects,project,whoami,file,file-info,edit-preview,edit-submit,login} ...

Scrapbox API client CLI

positional arguments:
  {pages,all-pages,page,text,icon,page-v2,links,search,vector-search,commits,members,projects,project,whoami,file,file-info,edit-preview,edit-submit,login}
                        Available commands
    pages               Get page list from a project
    all-pages           Get all pages from a project
    page                Get detailed information about a page
    text                Get text content of a page
    icon                Get icon URL for a page
    page-v2             Get page details from the v2 endpoint
    links               Get the 1-hop or 2-hop neighbourhood of a page
    search              Search the full text of a project
    vector-search       Search pages by vector similarity
    commits             Get the edit history of a page
    members             Get the members of a project
    projects            Get the projects you belong to
    project             Get a single project by name
    whoami              Get the authenticated user
    file                Download a file from Scrapbox
    file-info           Get metadata and extracted text of a file
    edit-preview        Dry-run a page edit and get a preview ID (personal
                        access token only)
    edit-submit         Commit a previewed page edit (personal access token
                        only)
    login               Save a credential read from stdin

options:
  -h, --help            show this help message and exit
  --version, -V         Show program's version number and exit
  --connect-sid CONNECT_SID
                        Scrapbox authentication cookie (connect.sid)
  --connect-sid-file CONNECT_SID_FILE
                        Path to file containing connect.sid (default: ~/.config/sbc/connect.sid)
  --pat PAT             Scrapbox personal access token (takes precedence over connect.sid)
  --pat-file PAT_FILE   Path to file containing a personal access token (default: ~/.config/sbc/pat)

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
  echo '{"ops":[{"insertBefore":"_end","text":"hello"}]}' \
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
```

### Saving a credential

`sbc login` reads one credential from stdin and stores it under `~/.config/sbc/`,
where the other commands pick it up. The destination is chosen from the prefix of
the value, so no flag is needed to say which kind it is:

| Input prefix | Credential | Saved to |
| --- | --- | --- |
| `s%` | `connect.sid` cookie | `~/.config/sbc/connect.sid` |
| `pat_` | personal access token | `~/.config/sbc/pat` |

```shellsession
$ echo "pat_xxxxxxxx" | sbc login
Saved to /home/you/.config/sbc/pat

$ sbc login
Enter connect.sid or personal access token:
Saved to /home/you/.config/sbc/connect.sid
```

Anything else is rejected with a non-zero exit code. On a terminal the value is
prompted for without echo; credential files are written with `0600` permissions.

## Library

### Overview

```python
from scrapbox.client import ScrapboxClient

PROJECT_NAME = "help-jp"
PAGE_TITLE = "ブラケティング"

# Access public project without authentication
with ScrapboxClient() as client:
    # Get page list
    pages = client.get_pages(PROJECT_NAME, skip=0, limit=5)
    print(f"Project: {pages.project_name}")
    print(f"Total pages: {pages.count}")
    print()
    print("First 5 pages:")
    for page in pages.pages:
        print(f"  - {page.title} (views: {page.views})")

    print()
    print()

    # Get individual page details
    print("Get page details:")
    page_detail = client.get_page(PROJECT_NAME, PAGE_TITLE)
    print(f"Title: {page_detail.title}")
    print(f"Lines: {page_detail.lines_count}")
    print(f"Characters: {page_detail.chars_count}")
    print(f"First 5 lines:")
    for line in page_detail.lines[:5]:
        print(f"  {line.text}")

    print()
    print()

    # Get page text
    print("Page text:")
    text = client.get_page_text(PROJECT_NAME, PAGE_TITLE)
    print(text[:200] + "...")

    print()
    print()

    # Get icon URL
    print("Icon URL:")
    icon_url = client.get_page_icon_url(PROJECT_NAME, PAGE_TITLE)
    print(icon_url)

print()
print()

# Access private project with authentication
# A personal access token is issued from the Cosense settings page
print("=== Example with authentication ===")
pat = "pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
with ScrapboxClient(pat=pat) as client:
    try:
        pages = client.get_pages("your-private-pj", limit=3)
        print(f"Project: {pages.project_name}")
        for page in pages.pages:
            print(f"  - {page.title}")
    except Exception as e:
        print(f"Error: {e}")
```

### Page size limits

`get_pages(limit=...)` and the `per_page=` of the related pages calls both map to a
page size the API caps at 1000. It does not report a request that asks for more: it
quietly serves 1000, and a size below 1 quietly becomes something else again, so the
number of entries you get back cannot tell you which happened. Anything outside 1 to
1000 is refused here instead:

```python
from scrapbox import ScrapboxClient
from scrapbox.client import MAX_PAGE_SIZE  # 1000

with ScrapboxClient() as client:
    client.get_pages("help-jp", limit=1001)
    # ValueError: limit must be between 1 and 1000, got 1001

    client.iter_links_1hop("help-jp", "ブラケティング", per_page=0)
    # ValueError: per_page must be between 1 and 1000, got 0

    pages = client.get_pages("help-jp", limit=MAX_PAGE_SIZE)  # fine
```

Walk a project larger than one page with `skip`, or use `sbc all-pages`. The CLI
refuses an out-of-range `--limit`, `--batch-size` or `--per-page` before sending
anything, exiting with status 2.

### Searching and browsing

```python
from scrapbox.client import ScrapboxClient

with ScrapboxClient() as client:
    # Full-text search. Pass match_any=True to match any of the words.
    result = client.search_pages("help-jp", "リンク 検索", match_any=True)
    for page in result.pages:
        print(page.title, page.words)

    # Vector search over page titles and the link notations in page bodies.
    similar = client.search_titles_by_vector("help-jp", "ページを繋げる")
    for page in similar.pages:
        print(f"{page.score:.3f} {page.title}")

    # 1-hop and 2-hop neighbourhoods, optionally narrowed by a query.
    for page in client.get_links_1hop("help-jp", "ブラケティング").links1hop:
        print(page.title, page.linked, page.page_rank)
    print(len(client.get_links_2hop("help-jp", "ブラケティング").links2hop))

    # One response holds at most 1000 neighbours. iter_links_* follows the
    # cursor for you and yields each page as it is consumed.
    for page in client.iter_links_1hop("help-jp", "ブラケティング"):
        print(page.title)

    # A single project, including its settings and member list. No
    # authentication is needed for a public one.
    project = client.get_project("help-jp")
    print(project.display_name, project.theme, len(project.users))

    # The v2 page endpoint adds the normalized *_lc fields.
    page_v2 = client.get_page_v2("help-jp", "ブラケティング")
    print(page_v2.links_lc, page_v2.icons_lc)

    # Members, used to resolve an author id to a name. Departed members and
    # service accounts are listed separately.
    members = client.get_project_users("help-jp")
    print([member.name for member in members.users])
```

The vector search backend is updated from time to time, and answers with a
non-standard HTTP 490 while it is. That becomes a `SearchServerUpdatingError`,
which is transient — retry it when convenient:

```python
from scrapbox import ScrapboxClient, SearchServerUpdatingError

with ScrapboxClient() as client:
    try:
        client.search_titles_by_vector("help-jp", "リンク")
    except SearchServerUpdatingError:
        ...  # try again later
```

`get_me()` raises a `NotAuthenticatedError` when no credential was accepted.
That endpoint does not answer 401: without one it answers 200 with
`{"isGuest": true}` and no user at all, so being logged out has to be read out
of the body.

### Editing a page

Editing is a two-step flow: preview the change, then submit the preview id it
returns. A preview is a dry run, expires after a few minutes, and can only be
submitted once. **These endpoints only accept a personal access token**; a
`connect.sid` cookie is rejected, so the client raises
`PersonalAccessTokenRequiredError` without sending the request.

```python
from scrapbox import ScrapboxClient, changes_from_ops

with ScrapboxClient(pat="pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") as client:
    changes = changes_from_ops([{"insertBefore": "_end", "text": "a new line"}])

    preview = client.preview_page_edit("my-project", changes, page_id="<pageId>")
    print(preview.preview_id, preview.expire_at)
    for line in preview.page_preview.lines:
        print(line.text)

    result = client.submit_page_edit("my-project", preview.preview_id)
    print(result.commit_id, result.page.title)
```

An op is one of `{"insertBefore": "<lineId>" | "_end", "text": ...}`,
`{"replace": "<lineId>", "text": ...}` or `{"delete": "<lineId>"}`. They are
applied in order, and every anchor must exist at the time it is applied. Omit
`page_id` to create a new page instead of updating one.

### Files and history

```python
from scrapbox.client import ScrapboxClient

with ScrapboxClient(pat="pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") as client:
    # Metadata and the text extracted from a file (OCR of an image, body of a PDF).
    info = client.get_file_info("60190edf1176d9001c13f8e8.png")
    print(info.originalname, info.content_type, info.size, info.text)

    # The scaled down version of an image.
    thumb = client.get_file("60190edf1176d9001c13f8e8.png", thumbnail=True)

    # The history of a page. Keyed by page id, so it survives renames; pass
    # since= to get only what changed after a commit you have already seen.
    for commit in client.get_commits("my-project", "<pageId>").commits:
        print(commit.id, commit.user_id, commit.changes)

    # The authenticated user and the projects they belong to.
    print(client.get_me().name)
    print([project.name for project in client.get_projects().projects])
```

### Authentication

A private project can be accessed with either a personal access token
or a `connect.sid` cookie:

```python
from scrapbox.client import ScrapboxClient

# Recommended: personal access token, issued from the Cosense settings page
with ScrapboxClient(pat="pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") as client:
    pages = client.get_pages("your-private-pj", limit=3)

# connect.sid cookie, obtained from browser cookies
with ScrapboxClient(connect_sid="s%3AykQ__xxxxx-.xxxxx") as client:
    pages = client.get_pages("your-private-pj", limit=3)
```

The token is sent as the `x-personal-access-token` header, and only to
`scrapbox.io`, so it is not forwarded to the image hosts that `get_file()`
follows redirects to. When both credentials are given, the token takes
precedence and the cookie is not sent.

A cookie is enough for every read endpoint, but not for `preview_page_edit()`
and `submit_page_edit()`, which the API restricts to personal access tokens.

### Image

```python
from scrapbox.client import ScrapboxClient

with ScrapboxClient() as client:
    # Get image by specifying file ID
    file_id = "1a2b3c4d5e6f7g8h9i0j.JPG"
    print(f"Fetching file: {file_id}")
    
    try:
        image_data = client.get_file(file_id)
        print(f"Successfully fetched: {len(image_data)} bytes")
        
        # Save to file
        output_path = "downloaded_image.jpg"
        with open(output_path, "wb") as f:
            f.write(image_data)
        print(f"Saved: {output_path}")
        
    except Exception as e:
        print(f"Error: {e}")

    print()

    # Can also fetch with full URL
    print("Fetch with full URL:")
    try:
        full_url = "https://gyazo.com/da78df293f9e83a74b5402411e2f2e01"
        image_data2 = client.get_file(full_url)
        print(f"Successfully fetched: {len(image_data2)} bytes")
    except Exception as e:
        print(f"Error: {e}")
```

## License

MIT
