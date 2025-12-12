---
applyTo: "tests/*.py"
---

# テスト方針

このプロジェクトのテストに関する方針とガイドラインです。

## テストの実行方法

### 基本的な実行

テストは必ず `mise run pytest` を使用して実行してください：

```bash
# 全テストを実行
mise run pytest

# 特定のファイルのテストを実行
mise run pytest tests/test_main.py

# 特定のテストクラスを実行
mise run pytest tests/test_main.py::TestCLI

# 特定のテストケースを実行
mise run pytest tests/test_main.py::TestCLI::test_pages_command

# 詳細な出力で実行
mise run pytest -v

# カバレッジを含めて実行
mise run pytest --cov=scrapbox --cov-report=html
```

### 注意事項

- `python -m pytest` や直接 `pytest` を実行しないでください
- `mise run pytest` により、プロジェクトの設定に従った正しい環境でテストが実行されます
- Python 環境は `.venv` を使用し、自動的に設定されます

## テストの構成

### ディレクトリ構造

```
tests/
├── __init__.py
├── test_client.py  # ScrapboxClient のテスト
└── test_main.py    # CLI のテスト
```

### テストファイルの命名規則

- テストファイル: `test_*.py`
- テストクラス: `Test*`
- テストメソッド: `test_*`

## テストクラスの分類

### `test_main.py`

#### `TestCLI`
CLI コマンドの基本的な動作をテストします：
- 各コマンド (`pages`, `all-pages`, `page`, `text`, `icon`, `file`) の実行
- ヘルプメッセージの表示
- エラーハンドリング
- 引数のバリデーション

#### `TestCheckOutputPath`
出力パスのバリデーション関数 `check_output_path` のテストです：
- 有効なパスの確認
- ディレクトリが指定された場合のエラー
- 存在しない親ディレクトリのエラー

#### `TestGetConnectSid`
認証情報の取得関数 `get_connect_sid` のテストです：
- コマンドライン引数からの取得
- 指定ファイルからの取得
- デフォルトファイル (`~/.config/sbc/connect.sid`) からの取得
- ファイルが存在しない場合の動作

#### `TestConnectSidPriority`
認証情報の優先順位の統合テストです：
1. `--connect-sid` 引数が最優先
2. `--connect-sid-file` 引数が次点
3. デフォルトファイルが最後
4. どれも存在しない場合は `None`

### `test_client.py`

`ScrapboxClient` クラスの API 呼び出しとデータモデルのテストです。

## テスト作成のガイドライン

### モックの使用

- 外部 API への実際の呼び出しを避けるため、必要に応じてモックを使用します
- `unittest.mock.patch` を使用してモックを作成します
- モックは `scrapbox.main.ScrapboxClient` のようにインポート先でパッチします

例：
```python
with patch("scrapbox.main.ScrapboxClient") as mock_client:
    mock_instance = MagicMock()
    mock_client.return_value.__enter__.return_value = mock_instance
    # テストコード
```

### 一時ファイル・ディレクトリ

- `tmp_path` フィクスチャを使用して一時的なファイルやディレクトリを作成します
- テスト終了後は自動的にクリーンアップされます

### 環境変数のモック

- `monkeypatch` フィクスチャを使用して環境変数やパスをモックします
- 例: `monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)`

### アサーション

- `assert` 文を使用します
- エラーメッセージは `captured.err` で確認します
- 標準出力は `captured.out` で確認します
- 終了コードは `exit_code` または `e.value.code` で確認します

### テストの独立性

- 各テストは独立して実行できる必要があります
- テスト間で状態を共有しないでください
- 外部リソースへの依存を最小限にしてください

## カバレッジ目標

- 全体のコードカバレッジ: 80%以上
- 新規追加コード: 90%以上
- クリティカルなロジック: 100%

## 継続的インテグレーション

- すべてのプルリクエストはテストが通過する必要があります
- コミット前に必ずローカルでテストを実行してください
- `ruff` によるリント検査も必ず通過させてください

## デバッグ

テストのデバッグには以下のオプションが便利です：

```bash
# 詳細な出力
mise run pytest -v

# 最初の失敗で停止
mise run pytest -x

# 特定のテストのみ実行
mise run pytest -k "test_name"

# 標準出力を表示
mise run pytest -s

# デバッグ情報を表示
mise run pytest --tb=long
```

## よくある問題

### Import エラー

プロジェクトのルートディレクトリから実行していることを確認してください。

### 環境の問題

Python 環境が正しく設定されていない場合は、以下を実行してください：

```bash
mise install
mise run install
```

### テストの失敗

- エラーメッセージを注意深く読んでください
- `captured.out` と `captured.err` の内容を確認してください
- 必要に応じて `-s` オプションで標準出力を表示してください
