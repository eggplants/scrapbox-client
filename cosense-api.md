# Cosense (Scrapbox) HTTP API リファレンス

このパッケージ (`scrapbox/`) が実際に叩く `https://scrapbox.io/api/` 以下のエンドポイントをまとめたリファレンス。

**これは Cosense API の全体像ではない。**
このクライアントが叩かないエンドポイントは扱っていない。

同じ内容を機械可読にした OpenAPI 3.1 定義が同じディレクトリの `openapi.yaml` にある。

## 目次

- [共通仕様](#共通仕様)
- [認証](#認証)
- [エンドポイント一覧](#エンドポイント一覧)
- [ページ読み取り系](#ページ読み取り系)
- [関連ページ系](#関連ページ系)
- [検索系](#検索系)
- [履歴系](#履歴系)
- [ユーザーとプロジェクト系](#ユーザーとプロジェクト系)
- [ファイル系](#ファイル系)
- [ページ編集系](#ページ編集系)
- [`/api/` 以外の参照先](#api-以外の参照先)
- [エラー](#エラー)
- [実装との差分メモ](#実装との差分メモ)

## 共通仕様

### トランスポート

| 項目 | 内容 |
| --- | --- |
| origin | `https://scrapbox.io` 固定（`SCRAPBOX_ORIGIN`）。self-hosted origin には対応していない |
| ベース URL | `https://scrapbox.io/api` (`ScrapboxClient.BASE_URL`) |
| HTTP クライアント | `httpx.Client`（プロセス内で使い回す。`close()` またはコンテキストマネージャで閉じる） |
| メソッド | 読み取りは `GET`、編集の preview と submit のみ `POST` |
| リクエスト body | POST のみ。`Content-Type: application/json` |
| レスポンス | `/api/` 配下は `/text` を除きすべて JSON。`/text` は `text/plain; charset=utf-8` |
| リダイレクト | 既定で自動追従。`get_page_icon_url()` だけ `follow_redirects=False` で 302 の `Location` を読む |

### ページタイトルのエンコード

タイトルをパスに載せる用途と、人間が読む URL を組み立てる用途で、エンコードが別になっている。

**API 呼び出し用**は `urllib.parse.quote(title, safe="")` で、`/` も空白も非 ASCII もすべて percent-encode する。
サーバーの route が `/:project/:title` で `:title` に `/` を含められないため、`/` の `%2F` 化だけは必須である。
空白は `%20` でも `_` でも同じページに解決されることを実測で確認した。

**人間可読 URL 用**は `scrapbox.client.page_url()` が担当し、`%` `/` `?` `#` だけを percent-encode して空白を `_` に置換する。
Unicode はそのまま残す。
`sbc edit-submit` が編集後のページ URL を表示するときに使う。

### 正規化タイトル (`titleLc`)

リンク関係の比較に使う `titleLc` と `linksLc` は「空白を `_` に置換して小文字化」した形である。
v2 のページ取得が返す `linksLc` が `[link.replace(" ", "_").lower() for link in links]` と一致することを `tests/test_client.py` が検証している。

### タイムスタンプ

レスポンス中の `created` / `updated` / `accessed` / `lastAccessed` / `snapshotCreated` は unix 秒の整数である。
このクライアントは変換せず整数のまま返す。
例外は編集 preview の `expireAt` で、これだけ ISO 8601 の文字列（`"2026-08-09T06:47:53.590Z"`）で返る。

### 命名の変換

API は camelCase、このパッケージは snake_case を公開する。
`ScrapboxModel` が `alias_generator=to_camel` で両者を橋渡ししているため、`model_dump_json(by_alias=True)` を通せば API と同じ camelCase に戻る。

## 認証

### 3 種類の資格情報

| 種別 | 送り方 | 発行元 |
| --- | --- | --- |
| Personal Access Token (PAT) | `x-personal-access-token: <token>` ヘッダー | `https://scrapbox.io/settings/personal-access-tokens` |
| Service Account Access Key | `x-service-account-access-key: <key>` ヘッダー | Business プロジェクトの設定画面の Service Accounts タブ |
| セッション cookie | `connect.sid=<value>` cookie | ブラウザの cookie |

送られる資格情報は常に 1 つで、優先順位は PAT > Service Account > cookie である
（`ScrapboxClient.__init__` が負けたほうを `None` に落とす）。
公開プロジェクトの読み取りは無認証で通る。

PAT の値は `pat_`、Service Account Access Key は `cs_` で始まる。
`sbc login` はこの接頭辞で保存先ファイルを振り分ける。

### ヘッダー資格情報の送信先を限定する仕組み

ヘッダーの資格情報はクライアントのデフォルトヘッダーには入れず、リクエストごとのイベントフックで付けている。

```python
def _attach_credential(self, request: httpx.Request) -> None:
    if request.url.host != SCRAPBOX_HOST:
        return
    if self.pat:
        request.headers[PAT_HEADER] = self.pat
    elif self.service_account_key:
        request.headers[SERVICE_ACCOUNT_HEADER] = self.service_account_key
```

`get_file()` は Gyazo や Google Cloud Storage の署名付き URL へリダイレクトを追う。
ホスト名で絞ることで、リダイレクト先のサードパーティに資格情報が渡らない。

### エンドポイントごとの認証要件

SA 列は Service Account Access Key を、その **キーが属するプロジェクト** に対して使った場合を指す。

| エンドポイント | 無認証 | cookie | PAT | SA |
| --- | --- | --- | --- | --- |
| 公開プロジェクトの読み取り全般 | 可 | 可 | 可 | **400** |
| 非公開プロジェクトの読み取り全般 | 401 | 可 | 可 | 可 |
| `GET /api/commits/...` | 401 | 可 | 可 | 可 |
| `GET /api/gcs/:fileId/info` | 401 | 可 | 可 | 可 |
| `GET /api/projects` | 401 | 可 | 可 | **401** |
| `GET /api/users/me` | 200 + `{"isGuest": true}` | 可 | 可 | **200 + `{"isGuest": true}`** |
| `GET /api/projects/:project` | 公開なら可 | 可 | 可 | **401** |
| `GET /api/projects/:project/users` | 公開なら可 | 可 | 可 | 可 |
| `POST .../page-edit-for-ai/*` | 401 | **403** | 可 | 可 |

編集系だけ cookie では通らない。
このクライアントは PAT も Service Account Access Key も無ければリクエストを送らずに
`PersonalAccessTokenRequiredError` を投げる（`_post_json`）。

公開プロジェクトでも `commits` と `gcs/info` は無認証だと 401 になる点に注意する。
`help-jp` に対して確認した。

### Service Account

Business プロジェクトの設定画面から登録する、プロジェクト 1 つに紐づく資格情報である。
`x-service-account-access-key` ヘッダーで送る。

公式ヘルプは「Private Project 内のデータを、サービス外のツールから読み取るためのしくみ」と説明しているが、
**実測では書き込みもできる**。
`page-edit-for-ai/preview` と `submit` はどちらも 200 を返し、作られた commit の `userId` は
Service Account 自身の id になる。
`GET /api/projects/:project/users` の `serviceAccounts` に出てくる id と一致する。

スコープはキーが属するプロジェクトだけで、**公開プロジェクトを含む他のプロジェクトはすべて 400 になる**。

```json
{"name":"BadRequestError","message":"Service account is not available for this project."}
```

ユーザーではないため、ユーザーを前提とするエンドポイントは通らない。

| エンドポイント | 結果 |
| --- | --- |
| `GET /api/users/me` | 200 だが body は `{"isGuest": true}` で、無認証と区別がつかない |
| `GET /api/projects` | 401 |
| `GET /api/projects/:project` | **401**。自分が属するプロジェクトでも通らない |

`GET /api/projects/:project` だけが 401 で、`GET /api/projects/:project/users` は通る。
しかも後者は無認証のときと違い `email` や `photo` まで含むフル情報を返す。

Service Account によるアクセスはプロジェクトの IP アドレス制限を受けない。

### 資格情報が生きているかの確認

`sbc info` は 3 種類の資格情報それぞれを、他を混ぜずに 1 つずつ送って確かめる。

| 資格情報 | 叩くエンドポイント | 判定 |
| --- | --- | --- |
| `connect.sid` | `GET /api/users/me` | `id` があれば有効。`{"isGuest": true}` は失効 |
| PAT | `GET /api/users/me` | 同上。無効なトークンは 401 `InvalidPersonalAccessTokenError` |
| Service Account Access Key | `GET /api/projects/:project/users` | 200 なら有効 |

Service Account Access Key だけは、キーが属するプロジェクトを `--project` で渡さないと判定できない。
属さないプロジェクトは 400 `Service account is not available for this project.` を返すが、
**存在しないでたらめなキーでも同じ 400 が返る**ため、この応答からはキーの生死が分からない。
`sbc info` はこの場合を `invalid` ではなく `unknown` として報告する。

## エンドポイント一覧

| メソッド | パス | クライアントメソッド | CLI |
| --- | --- | --- | --- |
| GET | `/api/pages/:project` | `get_pages` | `pages`, `all-pages` |
| GET | `/api/pages/:project/:title` | `get_page` | `page` |
| GET | `/api/pages/:project/:title/text` | `get_page_text` | `text` |
| GET | `/api/pages/:project/:title/icon` | `get_page_icon_url` | `icon` |
| GET | `/api/pages/v2/:project/:title` | `get_page_v2` | `page-v2` |
| GET | `/api/pages/v2/:project/:title/links1hop` | `get_links_1hop`, `iter_links_1hop` | `links --hop 1` |
| GET | `/api/pages/v2/:project/:title/links2hop` | `get_links_2hop`, `iter_links_2hop` | `links --hop 2` |
| GET | `/api/pages/:project/search/query` | `search_pages` | `search` |
| GET | `/api/pages/:project/search/vector/titles` | `search_titles_by_vector` | `vector-search` |
| GET | `/api/commits/:project/:pageId` | `get_commits` | `commits` |
| GET | `/api/projects/:project/users` | `get_project_users` | `members`, `info --project` |
| GET | `/api/projects/:project` | `get_project` | `project` |
| GET | `/api/projects` | `get_projects` | `projects` |
| GET | `/api/users/me` | `get_me` | `whoami`, `info` |
| GET | `/api/gcs/:fileId/info` | `get_file_info` | `file-info` |
| GET | `/api/oembed-proxy/gyazo` | `get_file`（Gyazo URL のとき） | `file` |
| POST | `/api/pages/v2/:project/page-edit-for-ai/preview` | `preview_page_edit` | `edit-preview` |
| POST | `/api/pages/v2/:project/page-edit-for-ai/submit` | `submit_page_edit` | `edit-submit` |

## ページ読み取り系

### `GET /api/pages/:projectName`

プロジェクトのページ一覧。
本文 (`lines`) は含まれない。

末尾のスラッシュは付けても付けなくても 200 が返る。
このクライアントは付けずに送る。

| クエリ | 値 | 既定 |
| --- | --- | --- |
| `skip` | オフセット | 0 |
| `limit` | 1 リクエストで返る件数 | 100 |
| `sort` | `updated` / `created` / `accessed` / `linked` / `views` / `title` | `updated` |
| `filterType` | `icon`。クライアントはこの値しか送らない | なし |
| `filterValue` | `filterType=icon` と対で送る絞り込み値 | なし |

`limit` の範囲外は **API 側ではエラーにならず、黙って別の値に置き換えられる**。
1000 を超えると 1000 に、0 以下だと既定の 100 になる。
`limit=2000` を送ってもレスポンスの `limit` は 1000 で返る。

返ってきた件数だけを見ても、丸められた結果なのか最終ページなのかを区別できない。
そのためこのクライアントは範囲外を API に渡さず、`ValueError` を投げる（`check_page_size()`）。
CLI では argparse が受け取る前に弾き、終了コード 2 で止まる。

```console
$ sbc pages my-project --limit 1001
sbc pages: error: argument --limit: page size must be between 1 and 1000, got 1001
```

1 リクエストで 1000 件を超えられないので、全ページの取得は `skip` を進めるループになる（`sbc all-pages` が `--batch-size` 既定 1000 でこれを行う）。

`sort` に未知の値を送ってもエラーにはならず、既定の並びで 200 が返る。
不正値を検出したいなら呼び出し側で弾く（CLI は `argparse` の `choices` で制限している）。

`filterValue` にはログイン名 (`name`) を渡す。
表示名 (`displayName`) ではない。
本文中に `[<name>.icon]` を持つページと、そのユーザーが編集したページが返る。

レスポンス:

| key | 型 | 説明 |
| --- | --- | --- |
| `projectName` | string | プロジェクト名 |
| `skip` | number | 送った `skip` |
| `limit` | number | 適用された `limit` |
| `count` | number | 条件に一致するページの総数 |
| `pages` | `PageListItem[]` | ページ |

`PageListItem` は `id`, `title`, `image`, `descriptions`, `user`, `lastUpdateUser`, `users`, `pin`, `views`, `linked`, `created`, `updated`, `accessed`, `linesCount`, `charsCount`, `helpfeels` を持つ。

`pin` は 0 か正の整数で、正なら固定表示されている。
値は `9007197717386014` のように巨大な数になり、大きいほど前に来る。
`sort=title` を指定しても固定ページが降順の `pin` 順で先頭に並び、その後ろに `pin: 0` のページがタイトル順で続く。

`helpfeels` は Helpfeel 記法の行から抽出された質問文の配列である。
本文中の `?` と半角スペースで始まる行が対象で、その接頭辞を除いた部分が入る。

`descriptions` は冒頭数行の抜粋である。

### `GET /api/pages/:projectName/:encodedTitle`（v1）

単一ページの本文とメタデータ。
v2 との違いは、関連ページ (`relatedPages`) を同梱する代わりに正規化 field (`linksLc` / `iconsLc` / `projectLinksLc`) を持たないことだけである。

- パスパラメータ: `projectName`、`encodedTitle`
- クエリ: なし

レスポンス（v1 と v2 で共通の field）:

| key | 型 | 説明 |
| --- | --- | --- |
| `id` | string | pageId（不変） |
| `title` | string | ページタイトル |
| `image` | string \| null | サムネイル画像の URL |
| `descriptions` | string[] | 冒頭数行の抜粋 |
| `persistent` | boolean | 実体のあるページなら true |
| `commitId` | string | 最新コミット ID。実体の無いページでは key ごと落ちる |
| `lines` | `Line[]` | 本文の行 |
| `links` | string[] | 本文中のリンク記法 `[title]` のタイトル |
| `icons` | string[] | `[name.icon]` 記法のタイトル |
| `projectLinks` | string[] | 別プロジェクトへのリンク |
| `files` | string[] | 本文から参照されているファイル ID |
| `helpfeels` | string[] | Helpfeel 記法（`?` と半角スペースで始まる行）から抽出された質問文 |
| `pageRank` | number | 被リンクから計算される重要度 |
| `linked` | number | 被リンク数 |
| `views` | number | 閲覧数 |
| `pin` | number | 固定表示の順序 |
| `linesCount` / `charsCount` | number | 行数と文字数。実体の無いページでは key ごと落ちる |
| `created` / `updated` / `accessed` / `lastAccessed` / `snapshotCreated` | number | unix 秒 |
| `user` | `User` | 作成者 |
| `lastUpdateUser` | `User \| null` | 最終更新者 |
| `users` | `User[]` | 編集したことのあるユーザー |
| `infoboxDefinition` | string[] | Infobox 定義行 |
| `infoboxDisableLinks` | string[] | Infobox でリンク化しない項目 |
| `infoboxResult` | `InfoboxResult[]` | このページ本文から抽出された Infobox |

v1 のみ:

| key | 型 | 説明 |
| --- | --- | --- |
| `relatedPages` | `RelatedPages` | 1-hop と 2-hop の関連ページ |

`Line` は `{ id, text, userId, created, updated }` である。
行の著者は `User` オブジェクトではなく `userId` 文字列で返るので、名前を出すには `/api/projects/:project/users` と突き合わせる。

`User` は `{ id, name?, displayName?, photo?, email? }` である。
`id` 以外はすべて欠けうる。

`InfoboxResult` は `{ title?, infobox?, hallucination?, truncated? }` である。
`hallucination`（抽出器が埋めた不確実な値）または `truncated`（抽出が途中で切れた）が立っている結果は信用できない。

`RelatedPages` は `links1hop`, `links2hop`, `projectLinks1hop`, `charsCount`, `hasBackLinksOrIcons`, `hiddenHeadwordsLc`, `fatHeadwordsLc`, `search`, `searchBackend` を持つ。
このうち `charsCount` は数値ではなく hop ごとの dict (`{"links1hop": 12294, "links2hop": 7618}`) で返る。
`RelatedPages.chars_count` の型が `dict[str, int] | int | None` になっているのはこのためである。

**存在しないページの扱い**が二通りある。

被リンクを持つページは、実体が無くても 200 で返る。
その場合 `persistent` は false になり、`id` と `lines[].id` にはリクエストのたびに変わる仮の値が入る。
この仮の ID を編集の anchor に使っても通らないので、編集の起点には使えない。

このとき `commitId` / `linesCount` / `charsCount` は **null ではなく key ごと落ちる**。
`PageBase` でこの 3 つが optional なのはそのためである。

被リンクも無い完全な未作成ページは 404 になる。

```json
{"name":"NotFoundError","message":"Page not found","details":{"linkTo":"https://scrapbox.io/help-jp/"}}
```

### `GET /api/pages/v2/:projectName/:encodedTitle`

v1 と同じページ情報を、正規化 field 付きで返す。

v2 のみ:

| key | 型 | 説明 |
| --- | --- | --- |
| `linksLc` | string[] | `links` の正規化形 |
| `iconsLc` | string[] | `icons` の正規化形 |
| `projectLinksLc` | string[] | `projectLinks` の正規化形 |

`relatedPages` は返らない。
関連ページが要るなら `links1hop` / `links2hop` を別に叩く。

編集 API のパスが `/api/pages/v2/...` 配下にあるので、編集の起点となる `id` と `lines[].id` を取るならこちらを使うほうが一貫する。

### `GET /api/pages/:projectName/:encodedTitle/text`

本文をプレーンテキストで返す。
JSON ではなく `text/plain; charset=utf-8` である。

1 行目はページタイトル、2 行目以降が本文になる。
存在しないページは 404 で、body は JSON の `{"name":"NotFoundError","message":"Page not found."}` になる（末尾の句点が v1 / v2 の同名エラーと違う）。

### `GET /api/pages/:projectName/:encodedTitle/icon`

ページのアイコン画像へ **302 でリダイレクトする**。
画像そのものではなくリダイレクト先の URL が欲しいので、`get_page_icon_url()` だけは `follow_redirects=False` で叩き、`Location` ヘッダーを返す。

リダイレクト先はアイコンの実体によって変わる。

| アイコンの持ち方 | `Location` の例 |
| --- | --- |
| Gyazo 画像 | `https://gyazo.com/<hash>/max_size/400` |
| プロジェクトにアップロードされたファイル | `https://scrapbox.io/files/<fileId>.png?type=thumbnail&size=small` |

存在しないページは 404 になる。
200 が返った場合（リダイレクトしない場合）は、リクエストした URL 自身を返す実装になっている。

## 関連ページ系

`links1hop` と `links2hop` はパス末尾が違うだけで、クエリは共通である。

### `GET /api/pages/v2/:projectName/:encodedTitle/links1hop`

### `GET /api/pages/v2/:projectName/:encodedTitle/links2hop`

| クエリ | 値 | 既定 |
| --- | --- | --- |
| `search` | 検索語 | 関連ページを全文検索で絞り込む。省略可 |
| `op` | `or` | 複数語を OR で扱う。省略時は AND |
| `perPage` | 1 リクエストで返る件数 | 1000 |
| `nextId` | カーソル。この ID の次から返す | なし（先頭から） |

クライアントでは `search=`, `match_any=True`, `per_page=`, `next_id=` に対応する。

共通のレスポンス field:

| key | 型 | 説明 |
| --- | --- | --- |
| `links1hop` / `links2hop` | `LinkPage[]` | 近傍のページ |
| `pagination` | `Pagination` | `{ perPage, total, hasNext, nextId }` |
| `synonyms` | array | 同義語。実測では常に空配列 |
| `searchBackend` | string \| null | 検索に使われたバックエンド名 |

1hop のみ:

| key | 型 | 説明 |
| --- | --- | --- |
| `charsCount` | number | 対象ページの文字数 |
| `hasBackLinksOrIcons` | boolean | 被リンクまたはアイコン参照があるか |
| `kcsControlTagsLc` | string[] | Helpfeel の制御タグ（正規化形） |

2hop のみ:

| key | 型 | 説明 |
| --- | --- | --- |
| `hiddenHeadwordsLc` | string[] | 表示から隠された見出し語（正規化形） |

2-hop のレスポンスに 1-hop の近傍は含まれない。

`LinkPage` の field:

`id`, `title`, `titleLc`, `image`, `descriptions`, `linksLc`, `linked`, `pageRank`, `views`, `linesCount`, `charsCount`, `created`, `updated`, `accessed`, `lastAccessed`, `user`, `lastUpdateUser`, `users`, `infoboxDefinition`, `infoboxDisableLinks`, `infoboxResult`

**どの field が入るかは要素ごとに違う。**
`infobox*` を持つ要素と持たない要素が同じレスポンスに混在する。
`LinkPage` で `id` と `title` 以外がすべて optional なのはこのためである。

`search` クエリを付けて呼ぶと、各要素に `search` field が増える。
中身は `{"words": ["リンク"], "excludes": []}` の形で、ハイライトすべき語を伝える。

### ページネーション

`perPage` と `nextId` で近傍を分割して取る。
実測で確かめた挙動は次のとおり。

- `perPage` の範囲外も API 側ではエラーにならない。1000 超は 1000 に、`0` や数値でない値は既定の 1000 に、負数は 1 になる。`limit` と同じ理由で、このクライアントは範囲外を `ValueError` で弾く
- `nextId` はそのページの **最後の要素の `id`** で返る。これをそのまま送ると、その要素の次から返る。要素の重複は起きない
- 打ち切りの判定は `hasNext` で行う。`total` は近傍全体の件数で、`search` で絞っても減らない

`search` を付けた場合、フィルタは **ページ単位で適用される**。
そのため途中のページが空になったり `perPage` より少なくなったりする一方で、カーソルはまだ先を指していることがある。
件数で打ち切らず `hasNext` だけを見る必要がある。

このクライアントでは `iter_links_1hop()` と `iter_links_2hop()` がこの walk を行い、`LinkPage` を遅延して 1 件ずつ返す。
CLI では `sbc links <project> <title> --all` にあたる。

```python
with ScrapboxClient() as client:
    for page in client.iter_links_1hop("help-jp", "ブラケティング"):
        print(page.title)
```

カーソルを自分で持ちたい場合は `get_links_1hop(..., per_page=..., next_id=...)` を直接使う。

## 検索系

### `GET /api/pages/:projectName/search/query`

本文の全文検索。

| クエリ | 値 | 既定 |
| --- | --- | --- |
| `q` | 検索クエリ（必須） | なし |
| `op` | `or` | 省略時 AND |
| `sort` | `pageRank` / `updated` | `pageRank` |

レスポンス:

| key | 型 | 説明 |
| --- | --- | --- |
| `projectName` | string | プロジェクト名 |
| `searchQuery` | string | 送ったクエリ文字列 |
| `query` | object | 解析済みクエリ。`{"words": [...], "excludes": [...]}` |
| `field` | string | 検索対象。実測では `lines` |
| `backend` | string | 検索バックエンド。実測では `elasticsearch` |
| `count` | number | ヒット件数 |
| `limit` | number | 返却上限。実測では 100 |
| `existsExactTitleMatch` | boolean | クエリと完全一致するタイトルが存在するか |
| `pages` | `SearchResultPage[]` | ヒットしたページ |

`SearchResultPage` は `id`, `title`, `image`, `user`, `lastUpdateUser`, `users`, `views`, `linked`, `created`, `updated`, `pageRank`, `linesCount`, `charsCount`, `words`, `lines` を持つ。
`words` はマッチした語、`lines` はマッチした本文行（文字列の配列）である。

`op=or` の有無で `query` の中身は変わらない。
`count` だけが変わる（実測では AND 11 件に対し OR 37 件）。
どちらで検索したかはレスポンスからは読めない。

`skip` は受け付けない。
`limit` を超えるヒットの続きを取る手段はこの API にはない。

### `GET /api/pages/:projectName/search/vector/titles`

ベクトル検索。
**検索対象はページタイトルと本文中のリンク記法だけ**で、本文の通常テキストは対象外である。

| クエリ | 値 |
| --- | --- |
| `q` | 検索クエリ（必須） |

レスポンス: `{ "pages": VectorSearchPage[] }`。
top-level には `pages` 以外の field が無い。
実測では 20 件が類似度の降順で返った。

`VectorSearchPage` は `exists` の値で持つ field が変わる。

| `exists` | 入る field |
| --- | --- |
| true | `title`, `score`, `image`, `linked`, `id`, `user`, `lastUpdateUser`, `users`, `views`, `created`, `updated`, `pageRank`, `linesCount`, `charsCount` |
| false | `title`, `score`, `image`, `linked` のみ |

`exists: false` は、どこかのページからリンクされているだけで実体の無いページである。

**検索バックエンドの更新中は非標準の HTTP 490 が返る。**

```json
{"name":"UpdatingSearchServerError","message":"Updating search server. Please try again later."}
```

一時的なもので、再試行すれば 200 になる。
このクライアントは 490 を `SearchServerUpdatingError` として他の 4xx / 5xx と区別する（`_raise_for_status`）。
待ち時間が読めないため自動再試行はせず、再試行の判断は呼び出し側に委ねている。

## 履歴系

### `GET /api/commits/:projectName/:pageId`

ページの編集履歴。
タイトルではなく pageId 起点なので、リネームをまたいで追跡できる。

**公開プロジェクトでも無認証では 401 になる。**

| クエリ | 値 |
| --- | --- |
| `head` | commitId。これより後の commit だけを返すカーソル。省略時は全履歴 |

クライアントでは `since=` に対応する。

レスポンス: `{ "commits": Commit[] }`。

`Commit` は `{ id, kind, changes, parentId, pageId, userId, created }` である。
`kind` はテストが持つ実レスポンス由来のサンプルで `"page"` だった。
`parentId` は先行 commit が無ければ null になる。

`changes` の各要素は、判別用の key を一つだけ持つ。

| 形 | 意味 | モデル |
| --- | --- | --- |
| `{"_insert": <lineId>, "lines": {"id", "text"}}` | 行の挿入 | `InsertChange` |
| `{"_update": <lineId>, "lines": {"text", "origText"}}` | 行の更新（`origText` が変更前） | `UpdateChange` |
| `{"_delete": <lineId>}` | 行の削除 | `DeleteChange` |
| `{"title": "...", "titleLc": "..."}` | ページタイトルの変更 | `TitleChange` |

これらに加えて `linesCount` / `charsCount` / `links` / `icons` / `descriptions` / `helpfeels` / `infobox*` といった派生メタデータの change も同じ配列に混ざって返る。
専用のモデルは持たせず、`PageChange` の union 末尾にある `dict[str, Any]` に落ちる。
未知の形の change が来てもバリデーションで落ちないようにするための構成である。

## ユーザーとプロジェクト系

### `GET /api/projects/:projectName/users`

プロジェクトのメンバー一覧。
ページや行の著者 ID を名前に解決するのに使う。

レスポンス:

| key | 型 | 説明 |
| --- | --- | --- |
| `users` | `ProjectMember[]` | 現メンバー |
| `memberSnapshots` | `MemberSnapshot[]` | 退去済み、削除済みメンバーの記録 |
| `serviceAccounts` | `ServiceAccount[]` | Service Account |
| `serviceAccountSnapshots` | `ServiceAccount[]` | 削除済み Service Account |

- `ProjectMember`: `User` に `provider`（`google` / `microsoft` / `saml` 等）, `created`, `updated` を加えたもの
- `MemberSnapshot`: `{ id, reason, created, updated, data }`。`reason` は `deleted` / `left`
- `ServiceAccount`: `{ id, usage }`。`usage` は用途ラベルであって人名ではない

**公開プロジェクトを無認証で叩くと `users` しか返らず、その要素も `{id, name}` だけになる。**
`help-jp` に対して確認した。
`displayName` や `email` の存在を前提にはできない。

著者 ID は現メンバー、退去者、Service Account のいずれにも該当しうる。
名前を解決するなら 4 つの配列すべてを 1 つの id → 情報マップにマージする必要がある。

### `GET /api/projects/:projectName`

単一プロジェクトの情報。
公開プロジェクトなら無認証で読める。

レスポンス:

| key | 型 | 説明 |
| --- | --- | --- |
| `id` | string | プロジェクト ID |
| `name` | string | URL に使われる名前 |
| `displayName` | string | 表示名 |
| `publicVisible` | boolean | 公開プロジェクトか |
| `loginStrategies` | string[] | 利用できるログイン方式 |
| `additionalPlans` | object | 追加プランの有効状態 |
| `theme` | string | 配色テーマ。実測では `blue` |
| `image` | string \| null | プロジェクトのアイコン URL |
| `gyazoTeamsName` | string \| null | 連携する Gyazo Teams 名 |
| `translation` | boolean | 翻訳機能の有効状態 |
| `infobox` | boolean | Infobox の有効状態 |
| `disableRealtimeCollaboration` | boolean | リアルタイム共同編集を止めているか |
| `created` / `updated` | number | unix 秒 |
| `users` | `User[]` | メンバー。公開プロジェクトでは `{id, name}` だけ |
| `isMember` | boolean | 認証ユーザーがメンバーか |

`/api/projects` の要素と重なるが、**同じ形ではない**。
こちらは設定 (`theme`, `translation`, `infobox` 等) とメンバー一覧を持ち、`/api/projects` が持つ集計値 (`usersCount`, `adminsCount`, `isOwner`, `isAdmin`) を持たない。
`ProjectDetail` が `Project` を継承しているのはそのためで、継承元の集計値は None のままになる。

存在しないプロジェクト名は 404 になる。

```json
{"name":"NotFoundError","message":"Project is not found"}
```

### `GET /api/projects`

認証ユーザーが参加しているプロジェクトの一覧。
**認証が必須**である。

レスポンス: `{ "projects": Project[] }`。

`Project` は `id`, `name`（URL に使われる名前）, `displayName`, `publicVisible`, `loginStrategies`, `plan`, `additionalPlans`, `alert`, `usersCount`, `isMember`, `billingId`, `created`, `updated`, `isOwner`, `isAdmin`, `adminsCount` を持つ。

並び順は API 任せで、このクライアントはソートし直さない。

### `GET /api/users/me`

認証ユーザー自身の情報。

レスポンス: `id`, `name`, `displayName`, `email`, `photo`, `provider`, `pageFilters`, `created`, `updated`, `isGuest`, `config`。

`pageFilters` は `{ type, value }` の配列で、ページ一覧のフィルタ設定にあたる。

**このエンドポイントは無認証でも 401 を返さない。**
200 で `{"isGuest": true}` だけが返る。
認証の有無はステータスコードではなく body から読む必要がある。
`get_me()` は `id` の無い body を `NotAuthenticatedError` にする。

`get_pages(filter_value=...)` に渡すのは `displayName` ではなく `name` なので、その確認にこのエンドポイントを使う。

## ファイル系

### `GET /api/gcs/:fileId/info`

プロジェクトにアップロードされたファイルのメタデータと、そこから抽出されたテキスト。

`fileId` は 24 桁の 16 進数である。
`bare_file_id()` が、拡張子付きの ID (`5f15....png`) や完全な URL (`https://scrapbox.io/files/5f15....png`) から素の ID を取り出す。
`.tar.gz` のように拡張子が二段でも、最初の `.` で切るので正しく落ちる。

**公開プロジェクトのファイルでも無認証では 401 になる。**

```json
{"name":"NotLoggedInError","message":"You are not logged in yet."}
```

レスポンス:

| key | 型 | 説明 |
| --- | --- | --- |
| `id` | string | ファイル ID |
| `projectName` | string | 所属プロジェクト |
| `text` | string \| null | 抽出テキスト（画像の OCR、PDF の本文など）。API 側で切り詰められる |
| `originalname` | string \| null | アップロード時のファイル名 |
| `contentType` | string \| null | MIME タイプ |
| `size` | number \| null | バイト数 |

### `GET /api/oembed-proxy/gyazo`

Gyazo の oEmbed を Cosense 側で中継するエンドポイント。
`get_file()` に Gyazo の URL を渡し、その URL に拡張子が無いときだけ叩く。
拡張子があれば oEmbed を経ずに `https://i.gyazo.com/<path>` へ直接組み替える。

| クエリ | 値 |
| --- | --- |
| `url` | `https://gyazo.com/<hash>`（hash は 32 桁 16 進数） |

レスポンスは `type` によって形が変わる。

共通: `version`（`"1.0"`）, `type`, `provider_name`, `provider_url`, `width`, `height`, `scale`, `title`。

| `type` | 追加の field |
| --- | --- |
| `photo` | `url`（`https://i.gyazo.com/<hash>.png` など） |
| `video` | `html`, `thumbnail_url`, `thumbnail_width`, `thumbnail_height`, `has_audio_track`, `video_length_ms` |

`video` の場合、oEmbed の `url` は返らない。
`get_file()` は元 URL の hash から `https://i.gyazo.com/<hash>.mp4` を組み立てて取りに行く。

数値 field は空文字で返ることがある。
`GyazoOEmbedBase` の `field_validator` が空文字を `None` に、数値文字列を数値に正規化する。

エラーの形が `/api/` の他のエンドポイントと違う。

| 状況 | ステータス | body |
| --- | --- | --- |
| 存在しない hash | 404 | `{"message":"image not found."}` |
| `url` の欠落や不正 | 422 | `{"message":"url is not valid"}` |

いずれも `name` field を持たない。

`type` が `photo` でも `video` でもなければ、`get_file()` はモデル検証の前に `ValueError` を投げる。

## ページ編集系

編集は preview と submit の 2 段階で行う。
preview は dry-run で、何も書き込まずに `previewId` を返す。

**この 2 つだけ PAT が必須**である。
cookie では通らない。

| リクエスト | 結果 |
| --- | --- |
| cookie のみ、`Origin` なし | 403 `CrossOriginWriteNotAllowedError` |
| cookie + `Origin: https://scrapbox.io` | 403 `PersonalAccessTokenRequiredError` |
| PAT（`Origin` の有無を問わない） | 200 |

`CrossOriginWriteNotAllowedError` は cookie 認証に対する CSRF ガードであり、PAT 経路では `Origin` を見ていない。
そのためこのクライアントは `Origin` を送らない。
`tests/test_client_mock.py::test_write_requests_authenticate_with_the_token` がその不在を検証している。

### `POST /api/pages/v2/:projectName/page-edit-for-ai/preview`

リクエスト body:

```json
{
  "pageId": "<pageId>",
  "changes": [
    { "_insert": "<lineId> | _end", "lines": { "id": "<新規lineId>", "text": "..." } },
    { "_update": "<lineId>", "lines": { "text": "..." } },
    { "_delete": "<lineId>" }
  ]
}
```

- `pageId` は既存ページを編集するときだけ送る。新規ページ作成では body から省く（`preview_page_edit(page_id=None)`）
- `changes` は配列順に適用される。anchor（`_insert` / `_update` / `_delete` の値）は適用時点で存在していなければならない
- `_insert` の anchor に `_end` を指定するとページ末尾に追加される
- 新規行の `lines.id` は **クライアントが生成する**。`scrapbox.edits.new_line_id()` が `secrets.token_hex(12)` で 24 桁 16 進数を作る
- `_update` は単行しか扱えない

`scrapbox.edits.changes_from_ops()` が、扱いやすい ops 形式をこの `changes` に変換する。

| op | 変換先 |
| --- | --- |
| `{"insertBefore": "<lineId>" \| "_end", "text": "..."}` | 1 行につき 1 つの `_insert`。改行を含むテキストは複数の `_insert` に分割される |
| `{"replace": "<lineId>", "text": "..."}` | `_update` 1 つ。複数行のテキストは `ValueError` で拒否する |
| `{"delete": "<lineId>"}` | `_delete` 1 つ |

レスポンス:

```json
{
  "previewId": "6a78216d0b154dadc8dcd414",
  "expireAt": "2026-08-09T06:47:53.590Z",
  "pagePreview": {
    "title": "test",
    "persistent": true,
    "lines": [{ "id": "6a78192b3a6ddc39bdf42b47", "text": "test" }]
  }
}
```

`pagePreview` は実際には v2 ページ取得と同じ形の全体が返る（上は抜粋）。

`pagePreview.persistent` が false なら、この編集はページの新規作成になる。
true なら既存ページの更新である。

`expireAt` は ISO 8601 の文字列で、preview の有効期限は数分である。

dry-run なので、この時点では確定した URL は無い。

#### 新規作成のとき

- **1 行目の `_insert` のテキストがページタイトルになる。**
  `changes` が空だと `first change must be an _insert to create a new page (its text becomes the title)` で拒否される
- `pagePreview.persistent` は false、`commitId` は key ごと不在。
  ただし `linesCount` と `charsCount` は入る（実体の無いページを取得したときとは違う）
- `pagePreview.id` には**クライアントが送った 1 行目の line id** がそのまま入る。
  まだページが無いので実 page id ではないが、後述のとおり結果的に同じ値になる
- **同名のページが既にあると、preview の時点でタイトルに `_2` が付く。**
  1 行目のテキスト自体も付与後のタイトルに書き換わる。
  submit まで待たないと分からないわけではない

### `POST /api/pages/v2/:projectName/page-edit-for-ai/submit`

リクエスト body: `{"previewId": "<previewId>"}`

レスポンス: `{"commitId": "...", "page": { ... }}`。

`page` は **v2 ページ取得と key 単位で完全に一致する**（実測でキー集合を比較して差分ゼロ）。
更新でも新規作成でも同じ形で、`persistent` / `commitId` / `linesCount` / `charsCount` がすべて揃う。
このパッケージの `SubmittedPage` は、そのうち書き込み先を特定する `id` と `title` だけを写している。

**新規作成では、ページ id は 1 行目の `_insert` に載せた line id がそのまま採用される。**
つまり id はリクエストを送る前から分かる。
レスポンスから読む必然性があるのはむしろ `title` のほうで、こちらは `_2` の付与で変わりうる。

- `previewId` は 1 回限りで、submit すると消費される
- preview を作ったのと別のプロジェクトに submit することはできない
- 新規作成時に同名ページが既にあると、サーバーがタイトルに suffix を付けることがある。確定 URL は要求したタイトルではなくレスポンスの `page.title` から組み立てる（`cmd_edit_submit` が `page_url()` でこれを行う）

### 編集系のエラー

| ステータス | 意味 |
| --- | --- |
| 400 | preview を作ったのと別のプロジェクトに submit した |
| 401 | 認証が無い |
| 403 | cookie 認証、または PAT はあるがプロジェクトの member でない |
| 404 | `pageId` が存在しない。`previewId` が見つからない、期限切れ、消費済み、他ユーザーのもの |
| 409 | `{"error":"NotFastForward"}` は preview 生成後にページが更新された。`{"error":"DuplicateTitle"}` は preview と submit の間に他人が同名ページを作った |
| 422 | changes が不正。存在しない lineId を anchor にした。`_update` に複数行のテキストを送った |

409 が返ったら、ページの最新状態を取り直して changes を作り直す。

## `/api/` 以外の参照先

### `GET https://scrapbox.io/files/:fileId`

ファイル本体のダウンロード。

| クエリ | 値 | 説明 |
| --- | --- | --- |
| `type` | `thumbnail` | 縮小版を取る。JPEG と PNG 以外は縮小版を持たず原本が返る |

`get_file(thumbnail=True)` で付く。
Gyazo URL を渡したときは、oEmbed 側で解決するのでこのパラメータを付けない。

レスポンスは 302 で Google Cloud Storage の署名付き URL にリダイレクトする。

| リクエスト | リダイレクト先のバケット |
| --- | --- |
| `?type=thumbnail` なし | `scrapbox-file-distribute` |
| `?type=thumbnail` あり | `scrapbox-file-thumbnail` |

署名の有効期限は実測で 300 秒だった。
`_attach_pat` がホスト名で送信先を絞っているため、この署名付き URL に PAT は付かない。

### `GET https://i.gyazo.com/:hash.:ext`

Gyazo の画像および動画の実体。
oEmbed が返した `url`、または hash から組み立てた `.mp4` の URL を、そのまま取りに行く。
Cosense のエンドポイントではないので資格情報は送らない。

## エラー

`/api/` 配下のエラーは、`oembed-proxy` と編集系の一部を除いて次の形で返る。

```json
{"name": "<ErrorName>", "message": "<message>", "details": {}}
```

`details` は付かないことのほうが多い。

例外が 2 つある。
`oembed-proxy` は `{"message": ...}` だけを返す。
編集の submit も `previewId` が見つからないときは `{"message":"preview not found or expired"}` で、`name` を持たない。

実測または実装から確認できるエラー:

| ステータス | `name` | 発生条件 |
| --- | --- | --- |
| 400 | `BadRequestError` | Service Account を、属していないプロジェクトに使った |
| 401 | `NotLoggedInError` | 認証が要るエンドポイントに無認証でアクセスした。Service Account で `projects` 系を叩いた場合も同じ |
| 403 | `CrossOriginWriteNotAllowedError` | cookie 認証で編集 API を `Origin` 無しに叩いた |
| 403 | `PersonalAccessTokenRequiredError` | cookie 認証で編集 API を `Origin` 付きで叩いた |
| 404 | `NotFoundError` | ページまたはプロジェクトが存在しない |
| 490 | `UpdatingSearchServerError` | ベクトル検索のバックエンドが更新中 |

このクライアントの扱い方は `ScrapboxClient._raise_for_status` にまとまっている。

- 490 は `SearchServerUpdatingError` にする（一時エラーとして区別できるようにするため）
- それ以外の 4xx / 5xx は `httpx.HTTPStatusError` を投げる。
  このとき **body の `name` と `message` を例外メッセージに追記する**。
  ステータスコードだけでは足りないことが多く、たとえば Service Account の 400 は
  `BadRequestError: Service account is not available for this project.` まで出て初めて原因が分かる
- 編集 API の 403 は、そもそもリクエストを送らずに `PersonalAccessTokenRequiredError` で先回りする

CLI (`scrapbox/main.py`) はハンドラを `try` で包み、例外のメッセージを stderr に出して終了コード 1 を返す。

## 実装との差分メモ

実測とこのパッケージのモデル定義を突き合わせて残っている点を記録する。

| 項目 | 内容 |
| --- | --- |
| `Links1hopResponse.synonyms` | 実測では常に空配列で、要素の形が確認できていない。`list[Any]` のままにしてある |
| `PageBase.snapshot_count` | `help-jp` の実測レスポンスには `snapshotCount` が現れなかった。optional なので影響は無い |
| 全文検索の `skip` | API 自体が持たないため、`limit`（100）を超えるヒットの続きは取れない |
| 範囲外のページサイズ | API は `limit` / `perPage` の範囲外を黙って別の値に置き換える。このクライアントは `check_page_size()` で 1 以上 `MAX_PAGE_SIZE`（1000）以下に制限し、範囲外は `ValueError` にする |
| `SubmittedPage` | submit のレスポンスの `page` は v2 ページ全体だが、モデル化しているのは `id` と `title` だけである。残りを写しても取得後のページと重複するうえ、新規作成時の形を全 field ぶん実測したわけではないので、必須 field を増やさない判断をした |
| Service Account の作用範囲 | キーが属さないプロジェクトは公開でも 400 になる。CLI は `~/.config/sbc/service-account-key` を自動で読むため、キーを保存すると `sbc pages help-jp` のような公開プロジェクトの操作が通らなくなる |

### `cosense-http-api.md` との違い

`cosense-http-api.md` は、別実装（TypeScript 製 CLI）が叩く範囲をまとめた文書である。
このパッケージとは対象範囲が次の点で違う。

| 項目 | `cosense-http-api.md` の対象 | このパッケージ |
| --- | --- | --- |
| origin | ユーザーが渡す URL から抽出。self-hosted も扱う | `https://scrapbox.io` 固定 |
| 認証 | PAT と Service Account。cookie は使わない | PAT、Service Account、`connect.sid` cookie の 3 種 |
| v1 ページ取得 | 未使用 | `get_page()` で使う |
| `/text`, `/icon` | 未使用 | `get_page_text()`, `get_page_icon_url()` で使う |
| 単一プロジェクト情報 | 未使用 | `get_project()` で使う |
| Gyazo oEmbed | `api.gyazo.com` を直接叩く | `/api/oembed-proxy/gyazo` を経由する |
| タイトルのエンコード | `/` だけ `%2F` 化 | 全文字を percent-encode |
| 関連ページのページネーション | 未実装（`hasNext` で打ち切り） | `iter_links_1hop()` / `iter_links_2hop()` がカーソルを辿る |
| ファイルのリダイレクト | `redirect: 'manual'` で受け、資格情報を落として再リクエスト | 自動追従。ホスト名の判定で資格情報の流出を防ぐ |
