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

A client for [Scrapbox (Helpfeel Cosense)](https://scrapbox.io/product)

日本語版: [README.ja.md](README.ja.md)

## Documentation

- [`scrapbox-client` Python API Documentation](https://egpl.dev/scrapbox-client/scrapbox.html)
- [Cosense HTTP API Unofficial Documentation](https://egpl.dev/scrapbox-client/api/)
- [Cosense HTTP API Unofficial OpenAPI Spec](https://egpl.dev/scrapbox-client/openapi.yaml)

## Install

```bash
pip install scrapbox-client
```

## CLI

<details>

```shellsession
$ sbc
usage: sbc [-h] [--version] [--connect-sid CONNECT_SID | --connect-sid-file CONNECT_SID_FILE] [--pat PAT | --pat-file PAT_FILE] [--service-account-key SERVICE_ACCOUNT_KEY | --service-account-key-file SERVICE_ACCOUNT_KEY_FILE] {pages,all-pages,page,text,icon,page-v2,links,search,vector-search,commits,members,projects,project,whoami,file,file-info,edit-preview,edit-submit,login} ...

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
    edit-preview        Dry-run a page edit and get a preview ID (no cookie
                        auth)
    edit-submit         Commit a previewed page edit (no cookie auth)
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
  --service-account-key SERVICE_ACCOUNT_KEY
                        Service account access key, scoped to one Business project (takes precedence over connect.sid)
  --service-account-key-file SERVICE_ACCOUNT_KEY_FILE
                        Path to file containing a service account access key (default: ~/.config/sbc/service-account-key)

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

`edit-preview` and `edit-submit` need a personal access token or a
service account access key: the API rejects `connect.sid` for them

a service account is registered on one project of a Business plan and
reaches only that one, so any other project answers 400 and `projects`,
`project` and `whoami` are out of its reach

`sbc login` saves the credential read from stdin, choosing the file by its
prefix: `s%` for ~/.config/sbc/connect.sid, `pat_` for ~/.config/sbc/pat,
`cs_` for ~/.config/sbc/service-account-key

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

priority of service account access key source:
  1. --service-account-key argument
  2. --service-account-key-file argument
  3. ~/.config/sbc/service-account-key file
  4. SBC_SERVICE_ACCOUNT_KEY environment variable

a personal access token takes precedence over a service account access
key, which takes precedence over `connect.sid`
```

</details>

### Saving a credential

`sbc login` reads one credential from stdin and saves it under `~/.config/sbc/`.

| Input prefix | Credential | Saved to |
| --- | --- | --- |
| `s%` | `connect.sid` cookie | `~/.config/sbc/connect.sid` |
| `pat_` | personal access token | `~/.config/sbc/pat` |
| `cs_` | service account access key | `~/.config/sbc/service-account-key` |

```shellsession
$ echo "pat_xxxxxxxx" | sbc login
Saved to /home/you/.config/sbc/pat

$ sbc login
Enter connect.sid, personal access token or service account access key:
Saved to /home/you/.config/sbc/connect.sid
```

### Creating and editing a page (PAT / service account access key only)

Try the change with `sbc edit-preview`, then pass the returned `previewId` to
`sbc edit-submit` to commit it.
A preview is a dry run that writes nothing, expires in a few minutes, and can be
submitted only once.

The change is given as JSON with an `ops` key, either on stdin or via `--input-file`.
Look up a `lineId` in `lines[].id` of `sbc page-v2 <project> <title> --json`.

| op | Meaning |
| --- | --- |
| `{"insertBefore": "<lineId>" \| "_end", "text": "..."}` | Insert a line. `_end` is the end of the page. Text containing newlines is split into several lines |
| `{"replace": "<lineId>", "text": "..."}` | Replace a line. Multi-line text is rejected |
| `{"delete": "<lineId>"}` | Delete a line |

#### Create

Omitting `--page-id` creates a new page. The text of the first line becomes the page title.

A `status` of `create` means a new page, `update` means an existing page is updated.

Lines marked with `>` are the ones being inserted, and the ID on the right is the
line ID generated by the client.
When creating a page, **the line ID of the first line becomes the page ID**.

If a page with the same title already exists, `_2` is appended to the title and the
text of the first line is rewritten at this point, without waiting for the submit.

```shellsession
$ echo '{"ops":[{"insertBefore":"_end","text":"シンプルな新規ページ"}]}' \
    | sbc edit-preview my-project
previewId: 6a784f6497b7c9f8474230ea
expireAt:  2026-08-09T10:04:00.687Z
status:    create
title:     シンプルな新規ページ

page (after apply):
> シンプルな新規ページ    # 1f777fb354af9527c1583d2e

$ sbc edit-submit my-project 6a784f6497b7c9f8474230ea
commitId: 6a7847a7021948351af3e9ed
pageId:   1f777fb354af9527c1583d2e
title:    シンプルな新規ページ
url:      https://scrapbox.io/my-project/シンプルな新規ページ
```

#### Edit

Pass the ID of the target page to `--page-id`. The `ops` are applied in array order.
A line ID used as an anchor must exist at the moment its op is applied.

```shellsession
$ cat edit.json
{
  "ops": [
    {"replace": "6a78194f00000000007455fe", "text": "書き換えた行"},
    {"insertBefore": "_end", "text": "末尾に足した行"}
  ]
}

$ sbc edit-preview my-project --page-id 6a78192b3a6ddc39bdf42b47 --input-file edit.json
previewId: 6a7850835d9cbe48c6602555
expireAt:  2026-08-09T10:08:47.865Z
status:    update
title:     test

page (after apply):
  test
  書き換えた行
  [https://scrapbox.io/files/6a781e51d393133856f18a12.png]


> 末尾に足した行   # 26a76acbe1093acdc2c1ca37
```

#### Delete

Deleting a page is done from the browser UI.

See: <https://helpfeel.com/help/--67e0bedcc6d6e5bea3a235b8>

## Library

### Overview

```python
from scrapbox.client import ScrapboxClient

PROJECT_NAME = "help-jp"
PAGE_TITLE = "ブラケティング"

# A public project can be accessed without authentication
with ScrapboxClient() as client:
    # Get the page list
    pages = client.get_pages(PROJECT_NAME, skip=0, limit=5)
    print(f"Project: {pages.project_name}")
    print(f"Total pages: {pages.count}")
    print()
    print("First 5 pages:")
    for page in pages.pages:
        print(f"  - {page.title} (views: {page.views})")

    print()
    print()

    # Get the details of an individual page
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

    # Get the text of the page
    print("Page text:")
    text = client.get_page_text(PROJECT_NAME, PAGE_TITLE)
    print(text[:200] + "...")

    print()
    print()

    # Get the icon URL
    print("Icon URL:")
    icon_url = client.get_page_icon_url(PROJECT_NAME, PAGE_TITLE)
    print(icon_url)

print()
print()

# A private project is accessed with authentication
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

### Page size limit

Walk a project too large for one page with `skip`, or use `sbc all-pages`.

```python
from scrapbox import ScrapboxClient
from scrapbox.client import MAX_PAGE_SIZE  # 1000

with ScrapboxClient() as client:
    client.get_pages("help-jp", limit=1001)
    # ValueError: limit must be between 1 and 1000, got 1001

    client.iter_links_1hop("help-jp", "ブラケティング", per_page=0)
    # ValueError: per_page must be between 1 and 1000, got 0

    pages = client.get_pages("help-jp", limit=MAX_PAGE_SIZE)  # OK
```

### Search and traversal

```python
from scrapbox.client import ScrapboxClient

with ScrapboxClient() as client:
    # Full-text search. Pass match_any=True to return the pages matching any
    # of the words.
    result = client.search_pages("help-jp", "リンク 検索", match_any=True)
    for page in result.pages:
        print(page.title, page.words)

    # Vector search over page titles and the link notations in page bodies.
    similar = client.search_titles_by_vector("help-jp", "ページを繋げる")
    for page in similar.pages:
        print(f"{page.score:.3f} {page.title}")

    # The 1-hop and 2-hop neighbourhoods. They can be narrowed with a query.
    for page in client.get_links_1hop("help-jp", "ブラケティング").links1hop:
        print(page.title, page.linked, page.page_rank)
    print(len(client.get_links_2hop("help-jp", "ブラケティング").links2hop))

    # One response holds at most 1000 neighbours. iter_links_* follows the
    # cursor on its own, yielding one page at a time as they are consumed.
    for page in client.iter_links_1hop("help-jp", "ブラケティング"):
        print(page.title)

    # A single project, with its settings and member list. No authentication
    # is needed for a public project.
    project = client.get_project("help-jp")
    print(project.display_name, project.theme, len(project.users))

    # The v2 page endpoint carries the normalized *_lc fields.
    page_v2 = client.get_page_v2("help-jp", "ブラケティング")
    print(page_v2.links_lc, page_v2.icons_lc)

    # The member list, for resolving an author id to a name. Departed members
    # and service accounts are listed separately.
    members = client.get_project_users("help-jp")
    print([member.name for member in members.users])
```

The vector search answers HTTP 490 while it is being updated, so it has to be
retried after a while.

```python
from scrapbox import ScrapboxClient, SearchServerUpdatingError

with ScrapboxClient() as client:
    try:
        client.search_titles_by_vector("help-jp", "リンク")
    except SearchServerUpdatingError:
        ...  # try again later
```

`get_me()` raises a `NotAuthenticatedError` when no credential was accepted.
That endpoint does not answer 401.
Without a credential it answers 200 with `{"isGuest": true}` and no user at all,
so being logged out has to be read out of the body.

### Editing a page

Editing is a two-step flow.
Preview the change first, then submit the preview id it returns.
A preview is a dry run that writes nothing, expires after a few minutes, and can
only be submitted once.
A `connect.sid` cookie is rejected.

```python
from scrapbox import ScrapboxClient, changes_from_ops

with ScrapboxClient(pat="pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") as client:
    changes = changes_from_ops([{"insertBefore": "_end", "text": "a new line"}])

    preview = client.preview_page_edit("my-project", changes, page_id="<pageId>")
    print(preview.preview_id, preview.expire_at)
    for line in preview.page_preview.lines:
        print(line.text)

    result = client.submit_page_edit("my-project", preview.preview_id)
    print(result.commit_id, result.page.id, result.page.title)
```

### Files and history

```python
from scrapbox.client import ScrapboxClient

with ScrapboxClient(pat="pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") as client:
    # Metadata of a file and the text extracted from it (OCR of an image, body of a PDF)
    info = client.get_file_info("60190edf1176d9001c13f8e8.png")
    print(info.originalname, info.content_type, info.size, info.text)

    # The scaled down version of an image
    thumb = client.get_file("60190edf1176d9001c13f8e8.png", thumbnail=True)

    # The edit history of a page. Keyed by page id, so it survives a rename.
    # Pass since= to get only what changed after a commit you already know.
    for commit in client.get_commits("my-project", "<pageId>").commits:
        print(commit.id, commit.user_id, commit.changes)

    # The authenticated user and the projects they belong to
    print(client.get_me().name)
    print([project.name for project in client.get_projects().projects])
```

### Authentication

A private project can be accessed with a
[Personal Access Token](https://scrapbox.io/settings/personal-access-tokens), a
[Service Account Access Key](https://scrapbox.io/help-jp/Service_Account) or a
[`connect.sid` cookie](https://scrapbox.io/scrapboxlab/connect.sid).

```python
from scrapbox.client import ScrapboxClient

with ScrapboxClient(pat="pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") as client:
    pages = client.get_pages("your-private-pj", limit=3)

with ScrapboxClient(service_account_key="cs_xxxxxxxxxxxxxxxxxxxx") as client:
    pages = client.get_pages("your-business-pj", limit=3)

with ScrapboxClient(connect_sid="s%3AykQ__xxxxx-.xxxxx") as client:
    pages = client.get_pages("your-private-pj", limit=3)
```

A service account comes with the following limits.

- It is registered on one project of a Business plan and can only operate on
  that project.
- It stands for no particular user, so `get_me()`, `get_projects()` and
  `get_project()` are not available to it.
- Unlike the other credentials, a project's IP address restrictions do not
  apply to it.

`connect.sid` cannot be used for `preview_page_edit()` and `submit_page_edit()`.

### Images

```python
from scrapbox.client import ScrapboxClient

with ScrapboxClient() as client:
    # Get an image by its file ID
    file_id = "1a2b3c4d5e6f7g8h9i0j.JPG"
    print(f"Fetching file: {file_id}")

    try:
        image_data = client.get_file(file_id)
        print(f"Successfully fetched: {len(image_data)} bytes")

        # Save it to a file
        output_path = "downloaded_image.jpg"
        with open(output_path, "wb") as f:
            f.write(image_data)
        print(f"Saved: {output_path}")

    except Exception as e:
        print(f"Error: {e}")

    print()

    # It can also be fetched with a full URL
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
