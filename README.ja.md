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

[Scrapbox (Helpfeel Cosense)](https://scrapbox.io/product) のクライアント

English version: [README.md](README.md)

## ドキュメント

- [`scrapbox-client` Python API ドキュメント](https://egpl.dev/scrapbox-client/scrapbox.html)
- [Cosense HTTP API 非公式ドキュメント](https://egpl.dev/scrapbox-client/api/)
- [Cosense HTTP API 非公式 OpenAPI Spec](https://egpl.dev/scrapbox-client/openapi.yaml)

## インストール

```bash
# mise
mise use -g pipx:scrapbox-client

# pipx
pipx install scrapbox-client

# pip
pip install scrapbox-client
```

## CLI

```shellsession
$ sbc
usage: sbc [-h] [--version] [--connect-sid CONNECT_SID | --connect-sid-file CONNECT_SID_FILE] [--pat PAT | --pat-file PAT_FILE] [--service-account-key SERVICE_ACCOUNT_KEY | --service-account-key-file SERVICE_ACCOUNT_KEY_FILE] {pages,all-pages,page,text,icon,page-v2,links,search,vector-search,commits,members,projects,project,whoami,file,file-info,edit-preview,edit-submit,login,info} ...

Scrapbox API client CLI

positional arguments:
  {pages,all-pages,page,text,icon,page-v2,links,search,vector-search,commits,members,projects,project,whoami,file,file-info,edit-preview,edit-submit,login,info}
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
    info                Show the environment and the state of each credential

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
  sbc info
  sbc info --project my-business-project --json

`edit-preview` and `edit-submit` need a personal access token or a
service account access key: the API rejects `connect.sid` for them

a service account is registered on one project of a Business plan and
reaches only that one, so any other project answers 400 and `projects`,
`project` and `whoami` are out of its reach

`sbc login` saves the credential read from stdin, choosing the file by its
prefix: `s%` for ~/.config/sbc/connect.sid, `pat_` for ~/.config/sbc/pat,
`cs_` for ~/.config/sbc/service-account-key

`sbc info` reports the environment and, for each of the three credentials,
where it was read from and whether the API still accepts it; a service
account access key is only checked when `--project` names the project it
belongs to, since every other project refuses a good key and a bogus one
alike

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

<details>

### 認証情報の保存

`sbc login` は標準入力から認証情報を1つ読み取り、`~/.config/sbc/` の下に保存する。

| 入力の接頭辞 | 認証情報 | 保存先 |
| --- | --- | --- |
| `s%` | `connect.sid` クッキー | `~/.config/sbc/connect.sid` |
| `pat_` | パーソナルアクセストークン | `~/.config/sbc/pat` |
| `cs_` | サービスアカウントアクセスキー | `~/.config/sbc/service-account-key` |

```shellsession
$ echo "pat_xxxxxxxx" | sbc login
Saved to /home/you/.config/sbc/pat

$ sbc login
Enter connect.sid, personal access token or service account access key:
Saved to /home/you/.config/sbc/connect.sid
```

### 環境と認証情報の確認

`sbc info` はバージョン・インタプリタ・設定ディレクトリを出力したうえで、
3 種類の認証情報それぞれについて、どこから読まれたか、値(接頭辞と文字数だけに伏せたもの)、
そして API がまだ受け付けるかどうかを報告する。
リクエストが飛ぶのは設定済みの認証情報だけで、
他のコマンドが実際に送るものには `[in use]` が付く。

```shellsession
$ sbc info
sbc:        0.4.0
python:     3.14.7 (CPython)
executable: /usr/bin/python3
platform:   Linux-7.0.0-27-generic-x86_64-with-glibc2.43
httpx:      0.28.1
config dir: /home/you/.config/sbc

=== credentials ===
- personal access token: valid [in use]
    source: /home/you/.config/sbc/pat
    value:  pat_... (68 chars)
    detail: you (You)
- service account access key: unknown
    source: $SBC_SERVICE_ACCOUNT_KEY
    value:  cs_a... (67 chars)
    detail: pass --project <name> to check this key against the project it belongs to
- connect.sid cookie: invalid
    source: /home/you/.config/sbc/connect.sid
    value:  s%3A... (92 chars)
    detail: the API answered as a guest, so it did not accept this credential
```

| 状態 | 意味 |
| --- | --- |
| `valid` | API が受け付けた |
| `invalid` | API が拒否した、またはゲスト扱いで応答した |
| `unknown` | 確認できなかった |
| `not set` | どの取得元にも無かった |

Service Account Access Key が届くのは 1 プロジェクトだけで、
それ以外のプロジェクトは正しいキーもでたらめなキーも同じように拒否する。
そのため `--project` でキーの属するプロジェクトを指定するまでは `unknown` のままになる。

```shellsession
$ sbc info --project my-business-project
...
- service account access key: valid [in use]
    source: /home/you/.config/sbc/service-account-key
    value:  cs_a... (67 chars)
    detail: accepted by project 'my-business-project'
```

`sbc info --json` は同じ内容を JSON で出力する。

### ページの作成と編集(PAT / Service Account Access Key限定)

`sbc edit-preview` で変更を試し、返ってきた `previewId` を `sbc edit-submit` に渡して確定する。
preview は何も書き込まない試行で、数分で失効し、submit できるのは 1 回だけである。

変更内容は `ops` キーを持つ JSON で渡す。標準入力か `--input-file` のどちらでもよい。
`lineId` は `sbc page-v2 <project> <title> --json` の `lines[].id` で調べる。

| op | 意味 |
| --- | --- |
| `{"insertBefore": "<lineId>" \| "_end", "text": "..."}` | 行の挿入。`_end` はページ末尾。改行を含むテキストは複数行に分割される |
| `{"replace": "<lineId>", "text": "..."}` | 行の置換。複数行のテキストは拒否される |
| `{"delete": "<lineId>"}` | 行の削除 |

#### 作成

`--page-id` を省くと新規作成になる。1 行目のテキストがページタイトルとなる。

`status` が `create` なら新規作成、`update` なら既存ページの更新である。

`>` の付いた行が今回挿入される行で、右の ID はクライアントが生成した行 ID である。
新規作成では、**1 行目の行 ID がそのままページ ID になる**。

同名のページが既にあると、submit を待たずこの時点でタイトルに `_2` が付き、1 行目のテキストも書き換わる。

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

#### 編集

`--page-id` に対象ページの ID を渡す。`ops` は配列順に適用される。
anchor に指定した行 ID は、その op を適用する時点で存在していなければならない。

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

#### 削除

ページの削除はブラウザの UI から行う。

参照: <https://helpfeel.com/help/--67e0bedcc6d6e5bea3a235b8>

</details>

## ライブラリ

```python
from scrapbox.client import ScrapboxClient

PROJECT_NAME = "help-jp"
PAGE_TITLE = "ブラケティング"

# 公開プロジェクトには認証なしでアクセスできる
with ScrapboxClient() as client:
    # ページ一覧を取得する
    pages = client.get_pages(PROJECT_NAME, skip=0, limit=5)
    print(f"Project: {pages.project_name}")
    print(f"Total pages: {pages.count}")
    print()
    print("First 5 pages:")
    for page in pages.pages:
        print(f"  - {page.title} (views: {page.views})")

    print()
    print()

    # 個別のページの詳細を取得する
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

    # ページのテキストを取得する
    print("Page text:")
    text = client.get_page_text(PROJECT_NAME, PAGE_TITLE)
    print(text[:200] + "...")

    print()
    print()

    # アイコンの URL を取得する
    print("Icon URL:")
    icon_url = client.get_page_icon_url(PROJECT_NAME, PAGE_TITLE)
    print(icon_url)

print()
print()

# 非公開プロジェクトには認証してアクセスする
# パーソナルアクセストークンは Cosense の設定ページから発行する
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

<details>

### ページサイズの上限

1 ページに収まらない大きさのプロジェクトは `skip` でたどるか、`sbc all-pages` を使う。

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

### 検索と回遊

```python
from scrapbox.client import ScrapboxClient

with ScrapboxClient() as client:
    # 全文検索。match_any=True を渡すと、いずれかの語に一致したページを返す。
    result = client.search_pages("help-jp", "リンク 検索", match_any=True)
    for page in result.pages:
        print(page.title, page.words)

    # ページタイトルと本文中のリンク記法を対象にしたベクトル検索。
    similar = client.search_titles_by_vector("help-jp", "ページを繋げる")
    for page in similar.pages:
        print(f"{page.score:.3f} {page.title}")

    # 1 hop と 2 hop の近傍。クエリで絞り込むこともできる。
    for page in client.get_links_1hop("help-jp", "ブラケティング").links1hop:
        print(page.title, page.linked, page.page_rank)
    print(len(client.get_links_2hop("help-jp", "ブラケティング").links2hop))

    # 1 レスポンスに入る近傍は最大 1000 件。iter_links_* はカーソルを
    # 自動でたどり、消費されるたびに 1 ページずつ yield する。
    for page in client.iter_links_1hop("help-jp", "ブラケティング"):
        print(page.title)

    # 設定とメンバー一覧を含む単一プロジェクト。公開プロジェクトなら
    # 認証はいらない。
    project = client.get_project("help-jp")
    print(project.display_name, project.theme, len(project.users))

    # v2 のページエンドポイントは、正規化された *_lc フィールドを持つ。
    page_v2 = client.get_page_v2("help-jp", "ブラケティング")
    print(page_v2.links_lc, page_v2.icons_lc)

    # 著者 ID を名前に解決するためのメンバー一覧。脱退したメンバーと
    # サービスアカウントは別に列挙される。
    members = client.get_project_users("help-jp")
    print([member.name for member in members.users])
```

ベクトル検索の更新中はHTTP 490 を返すため、時間をおいて再試行する必要がある。

```python
from scrapbox import ScrapboxClient, SearchServerUpdatingError

with ScrapboxClient() as client:
    try:
        client.search_titles_by_vector("help-jp", "リンク")
    except SearchServerUpdatingError:
        ...  # あとで再試行する
```

認証情報が1つも受け付けられなかったとき、`get_me()` は `NotAuthenticatedError` を送出する。
このエンドポイントは 401 を返さない。
認証情報がなければ 200 と `{"isGuest": true}` を返してユーザーを含めないため、ログアウト状態はボディから読み取るほかない。

### ページの編集

編集は 2 段階の流れになる。
まず変更をプレビューし、返ってきたプレビュー ID を送信する。
プレビューは実際には書き込まない試行であり、数分で失効し、送信できるのは 1 回だけである。
`connect.sid` クッキーは拒否される。

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

### ファイルと履歴

```python
from scrapbox.client import ScrapboxClient

with ScrapboxClient(pat="pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") as client:
    # ファイルのメタデータと、そこから抽出されたテキスト（画像の OCR、PDF の本文）
    info = client.get_file_info("60190edf1176d9001c13f8e8.png")
    print(info.originalname, info.content_type, info.size, info.text)

    # 画像の縮小版
    thumb = client.get_file("60190edf1176d9001c13f8e8.png", thumbnail=True)

    # ページの編集履歴。ページ ID を鍵にするのでリネームしても追える。
    # since= を渡すと、既知のコミット以降の変更だけが返る。
    for commit in client.get_commits("my-project", "<pageId>").commits:
        print(commit.id, commit.user_id, commit.changes)

    # 認証されたユーザーと、そのユーザーが所属するプロジェクト
    print(client.get_me().name)
    print([project.name for project in client.get_projects().projects])
```

### 認証

非公開プロジェクトには、[Personal Access Token](https://scrapbox.io/settings/personal-access-tokens) / [Service Account Access Key](https://scrapbox.io/help-jp/Service_Account) / [`connect.sid` Cookie](https://scrapbox.io/scrapboxlab/connect.sid) のいずれかでアクセスできる。

```python
from scrapbox.client import ScrapboxClient

with ScrapboxClient(pat="pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") as client:
    pages = client.get_pages("your-private-pj", limit=3)

with ScrapboxClient(service_account_key="cs_xxxxxxxxxxxxxxxxxxxx") as client:
    pages = client.get_pages("your-business-pj", limit=3)

with ScrapboxClient(connect_sid="s%3AykQ__xxxxx-.xxxxx") as client:
    pages = client.get_pages("your-private-pj", limit=3)
```

サービスアカウントは以下の制限がある。

- Business プランの 1 プロジェクトに登録され、そのプロジェクトのみ操作可能。
- 特定のユーザーを表さないため、`get_me()`、`get_projects()`、`get_project()` は利用できない。
- 他の認証情報と違い、プロジェクトの IP アドレス制限は適用されない。

`connect.sid` は `preview_page_edit()` と `submit_page_edit()` には使えない。

### 画像

```python
from scrapbox.client import ScrapboxClient

with ScrapboxClient() as client:
    # ファイル ID を指定して画像を取得する
    file_id = "1a2b3c4d5e6f7g8h9i0j.JPG"
    print(f"Fetching file: {file_id}")

    try:
        image_data = client.get_file(file_id)
        print(f"Successfully fetched: {len(image_data)} bytes")

        # ファイルに保存する
        output_path = "downloaded_image.jpg"
        with open(output_path, "wb") as f:
            f.write(image_data)
        print(f"Saved: {output_path}")

    except Exception as e:
        print(f"Error: {e}")

    print()

    # 完全な URL を指定して取得することもできる
    print("Fetch with full URL:")
    try:
        full_url = "https://gyazo.com/da78df293f9e83a74b5402411e2f2e01"
        image_data2 = client.get_file(full_url)
        print(f"Successfully fetched: {len(image_data2)} bytes")
    except Exception as e:
        print(f"Error: {e}")
```

</details>

## ライセンス

MIT
