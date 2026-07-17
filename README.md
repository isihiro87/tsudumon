# pdf-workbook — 印刷用問題集ジェネレーター

marutto-study の `data/content/history/{章フォルダ}/*.json`（フラッシュカード＋4択クイズ）を材料に、
市販ワーク3種（新ワーク・ワーク・必修テキスト）の「いいところどり」構成の A4 問題集 PDF を生成する。

## 1冊の構成

| セクション | 元ネタ | 内容 |
|---|---|---|
| 年表でチェック | 新ワーク「年表や資料でまとめよう」 | 章全体の穴埋め年表 |
| A 要点まとめ | 新ワークのまとめ文 | トピックごとの穴埋め要約文＋解答欄 |
| B 一問一答 | ワーク/必修テキストの確認問題 | チェックボックス＋右端解答欄、14問（basic優先） |
| C 実戦問題 | アプリの4択クイズ | ア〜エの4択8問（standard/advanced優先・正解位置は自然ランダムに再配置） |
| D 記述問題 | 市販ワークの記述問題 | 理由・目的・しくみ等を文章で説明（2問／指定語句チップ付き） |
| 巻末解答 | — | 全セクションの解答（用語はルビ付き、記述は模範解答） |

- 一問一答は flashcards（back=問題文、front=答え）から、4択は quiz.questions から自動選定。
- 年表・要点まとめ・記述問題は自動化できないので、章ごとに `books/{章フォルダ}.json` に
  執筆して置く（`[[答え]]` で囲んだ語が空欄①②…になる）。全19章分作成済み。
  執筆はSonnet 5サブエージェントに章単位で委任し、`validate_books.py` で
  形式チェック（topics網羅・空欄数・文字数・指定語句の包含）を行うフロー。

## 使い方

```powershell
cd C:\Users\user\projects\education-apps\pdf-workbook
python -X utf8 generate_history_workbook.py   # output/{章}.html を生成

# Edge ヘッドレスで PDF 化
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  --headless --disable-gpu --no-pdf-header-footer `
  --print-to-pdf="C:\Users\user\projects\education-apps\pdf-workbook\output\04-ancient-state.pdf" `
  "file:///C:/Users/user/projects/education-apps/pdf-workbook/output/04-ancient-state.html"
```

## 章データ（books/*.json）のスキーマ

```json
{
  "volume": "歴史 ⑤",
  "title": "武士の台頭と鎌倉幕府",
  "subtitle": "平安時代末期 〜 鎌倉時代",
  "topics": ["..."],          // data/content/history/{章}/ の topicId を order 順に
  "timeline": [["年", "できごと（[[答え]] が空欄になる）"]],
  "summaries": { "topicId": "穴埋めまとめ文" },
  "written": { "topicId": [ { "q": "問題文", "keywords": ["指定語句"], "a": "模範解答" } ] }
}
```

編集後は `python -X utf8 validate_books.py` → `python -X utf8 generate_history_workbook.py` → Edge で PDF 化。
記述問題の執筆基準は `written-task.md` 参照。

## QRコード → 公式LINEで解く（パイロット: 律令国家と奈良時代）

章データに `"lineQr": ["topicId", ...]` を書くと、そのトピック末尾に QR コード付きの
案内ボックスが印刷される（要 `pip install segno`）。

- QR の中身: `https://line.me/R/oaMessage/@824cebif/?ワーク {単元名}`（`@824cebif` = bot/info の basicId）
  → スキャンするとトークに「ワーク {単元名}」が送信される
- 公式LINE 側: `lineWebhook` の `handleWorkbookQuestion` がこの定型文を検知し、
  その単元の4択問題を reply で1問出題（配信枠ゼロ・約1 read・回答/解説は既存フロー）
- 単元名はビルド時生成の `QUESTION_INDEX` で学年横断に解決するため、
  生徒の設定学年と冊子の単元の学年が違っても解ける
- 実装詳細: `marutto-study/.steering/20260711-workbook-qr-line/`

## 注意

- 問題文・解答は **自作の marutto-study JSON データ由来**。市販ワーク PDF からは
  紙面構成（セクションの種類・レイアウト）だけを参考にしており、文章は転載していない。
- 問題数の調整は `N_ITTOITTO` / `N_QUIZ` 定数で。
