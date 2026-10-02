# NAC QuickMap

LROC（Lunar Reconnaissance Orbiter Camera）の製品ページ URL からメタデータを自動取得し、
ローカルの SQLite に蓄積・分類・Excel 出力するデスクトップアプリです（PyQt6 製）。

## 主な機能

- **自動取得**: LROC の製品ページ URL を入力すると、ページ内のメタデータ表を解析して登録します。
  同じ製品を再取得した場合は上書き更新されます。
- **一覧表示**: Product ID / Original / Orbit / 緯度経度 / 解像度 / 各種角度などを表で表示します。
  選択した行の詳細（raw データを含む）は右側のツリーに表示されます。
- **絞り込み**: Product ID・Original・Orbit 番号で部分一致検索ができます。
- **タブ**
  - **すべて**: 登録済みの全製品
  - **セッション**: 今回の起動以降に登録・再取得した製品（保存済みの製品を再取得した場合も含む）
  - **タグ名のタブ**: そのタグが付いた製品
- **タグ（クラス分け）**: 選択した行にタグを付け外しできます。
  左パネルのチェックボックスで複数タグの絞り込み（「すべて一致」で AND / OR を切り替え）もできます。
- **タグ色のオーバーレイ**: すべてのタブで、タグごとの色が行に半透明で重なります。
  - タグを作ると、未使用のパレット色が自動で割り当てられます。
  - 複数タグが付いた製品は、タグ名の昇順で最初のタグの色になります。全タグ名は「Tags」列に表示されます。
  - タブの文字色と、左パネルのチェックボックス横の帯にも同じ色が使われます。
  - 色の変更: メニュー「タグ」→「タグの色を変更」
- **Excel エクスポート**: メニュー「ファイル」→「Excelにエクスポート」。
  範囲は「選択した行 / フィルタ結果 / すべて」から選べます。

## 動作環境

- Python 3.10 以上
- 必要なライブラリ
  - PyQt6
  - requests
  - beautifulsoup4
  - openpyxl

```bash
pip install PyQt6 requests beautifulsoup4 openpyxl
```

## 起動方法

プロジェクトのルート（`main.py` のある場所）で実行します。

```bash
python main.py
```

初回起動時に、同じフォルダへ `lroc_data.db` が作られます。

## フォルダ構成

```
NAC QuickMap/
├─ main.py                 起動スクリプト
├─ lroc_data.db            データベース（初回起動時に自動作成）
├─ icon.ico                ショートカット用アイコン
├─ create_shortcut.bat     Windows: デスクトップにショートカットを作成
├─ create_shortcut.ps1     　　　　　（上記 bat から呼ばれる）
├─ NAC QuickMap.command    macOS: ダブルクリックで起動
└─ app/
   ├─ __init__.py
   ├─ main_window.py       メインウィンドウ（UI）
   ├─ db.py                SQLite レイヤー（Qt 非依存）
   ├─ fetcher.py           製品ページの取得・解析（Qt 非依存）
   ├─ workers.py           取得を行うバックグラウンドスレッド
   ├─ excel.py             .xlsx 出力（Qt 非依存）
   └─ export_flow.py       エクスポート時のダイアログ処理
```

`app/` の中身は `import` のためにこの構成を保ってください（`from app import ...` を使っています）。

## 使い方

1. 画面左上の入力欄に製品ページの URL を貼り付け、「自動取得」を押します。
   URL の形式は次のとおりです。
   ```
   https://data.lroc.im-ldi.com/lroc/view_lroc/<dataset>/<product>
   ```
   対応ホストは `data.lroc.im-ldi.com` と `wms.lroc.im-ldi.com` です。取得のタイムアウトは 20 秒です。
2. 取得に成功すると登録され、「セッション」タブに表示されます。
3. 行を選択して、メニュー「タグ」→「タグを追加」でタグを付けます（複数行の選択も可）。
   新しい名前を入力すればタグが新規作成されます。
4. タグを外す・名前を変える・色を変えるときも、メニュー「タグ」から操作します。
5. タグのタブの「×」を押すと、そのタグを削除します（確認ダイアログあり）。
   「すべて」「セッション」のタブは閉じられません。

## データについて

- データは `lroc_data.db`（SQLite）に保存されます。バックアップはこのファイルをコピーするだけです。
- テーブルは `lroc_products`（製品）、`tags`（タグ名と色）、`product_tags`（製品とタグの対応）の 3 つです。
- 古いバージョンの DB でも、起動時に不足している列（スロー角・ピクセルサイズ・色など）を自動で追加します。
- Excel の保存先フォルダは、前回の場所を記憶します。

## デスクトップのショートカットを作る

### Windows

1. `create_shortcut.bat`、`create_shortcut.ps1`、`icon.ico` を `main.py` と同じフォルダに置きます。
2. `create_shortcut.bat` をダブルクリックします。
3. デスクトップに「NAC QuickMap」のアイコンができます。以後はダブルクリックで起動します。

仕組み:

- `pythonw.exe` で起動するため、黒いコンソール画面は出ません。
- フォルダ内に `.venv` があればその Python を、なければ PATH 上の Python を使います。
- 作業フォルダは `main.py` のある場所に設定されます。
- アイコンを変えたいときは `icon.ico` を差し替えてから、もう一度 `create_shortcut.bat` を実行します。

### macOS

1. `NAC QuickMap.command` を `main.py` と同じフォルダに置きます。
2. 初回だけ、ターミナルで実行権限を付けます。
   ```bash
   chmod +x "NAC QuickMap.command"
   ```
3. ダブルクリックで起動します（ターミナルのウィンドウも一緒に開きます）。

### 注意

- プロジェクトのフォルダを移動・名前変更した場合は、ショートカットを作り直してください。
- ショートカットから起動しないときは、コマンドプロンプトで `python main.py` を実行してエラーを確認してください。
  PyQt6 などが入っていない Python を指していることが多いです。
- ショートカット作成スクリプトは Windows の実機では動作確認していません。

## 設定を調整する

| 内容 | 場所 |
|---|---|
| タグ色の濃さ（0〜255） | `app/main_window.py` の `TAG_OVERLAY_ALPHA` |
| タグの自動割り当て色 | `app/db.py` の `TAG_PALETTE` |
| 一覧に表示する列 | `app/main_window.py` の `LIST_COLUMNS` / `LIST_KEYS` |
| Excel の列・幅 | `app/excel.py` の `HEADERS` / `KEYS` / `WIDTHS` |
| 取得タイムアウト・User-Agent | `app/fetcher.py` |
