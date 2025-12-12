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

## Install

```bash
pip install scrapbox-client
```

## CLI

```shellsession
$ sbc
usage: sbc [-h] [--version] [--connect-sid CONNECT_SID | --connect-sid-file CONNECT_SID_FILE] {pages,all-pages,page,text,icon,file} ...

Scrapbox API client CLI

positional arguments:
  {pages,all-pages,page,text,icon,file}
                        Available commands
    pages               Get page list from a project
    all-pages           Get all pages from a project
    page                Get detailed information about a page
    text                Get text content of a page
    icon                Get icon URL for a page
    file                Download a file from Scrapbox

options:
  -h, --help            show this help message and exit
  --version, -V         Show program's version number and exit
  --connect-sid CONNECT_SID
                        Scrapbox authentication cookie (connect.sid)
  --connect-sid-file CONNECT_SID_FILE
                        Path to file containing connect.sid (default: ~/.config/sbc/connect.sid)

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
```

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
# connect.sid is obtained from browser cookies
print("=== Example with authentication ===")
connect_sid = "s%3AykQ__xxxxx-.xxxxxxxxxxxxxxxxxxxxx%2Bxxxxxxxxx%2Bxxxxxxxxxxx"
with ScrapboxClient(connect_sid=connect_sid) as client:
    try:
        pages = client.get_pages("your-private-pj", limit=3)
        print(f"Project: {pages.project_name}")
        for page in pages.pages:
            print(f"  - {page.title}")
    except Exception as e:
        print(f"Error: {e}")
```

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
