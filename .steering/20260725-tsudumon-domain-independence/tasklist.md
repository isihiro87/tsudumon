# タスクリスト

## 🚨 タスク完全完了の原則

**このファイルの全タスクが完了するまで作業を継続すること**

### 必須ルール
- **全てのタスクを`[x]`にすること**
- 「時間の都合により別タスクとして実施予定」は禁止
- 「実装が複雑すぎるため後回し」は禁止
- 未完了タスク（`[ ]`）を残したまま作業を終了しない

### タスクスキップが許可される唯一のケース
以下の技術的理由に該当する場合のみスキップ可能:
- 実装方針の変更により、機能自体が不要になった
- アーキテクチャ変更により、別の実装方法に置き換わった
- 依存関係の変更により、タスクが実行不可能になった

スキップ時は必ず理由を明記:
```markdown
- [x] ~~タスク名~~（実装方針変更により不要: 具体的な技術的理由）
```

---

## 前提・厳守事項

- **デプロイは禁止**（`firebase deploy` / `git push` を実行しない）。フェーズ6以降はユーザー承認後に実施
- **`functions/.env` の値を読まない・出力しない**。キー名のみ扱う
- **`lineWebhook.ts` は `TSUDUMON_LP_URL` 定数の1行のみ変更**する
  （`20260725-tsudumon-dedicated-line-bot` が同ファイルを改修中のため）
- **chatstudy.jp の www / typing / mubista に影響を与えない**
- 配布済みPDF・印刷QRを無効化しない（301で救済する）

---

## フェーズ0: 事前検証

- [x] `https://tsudumon.web.app/dl` を直接叩き、Cloud Function に到達するか確認
  - [x] **結果: 404（Firebase の Page Not Found）**。外部URLを `destination` に書いた現行設定は
        機能しておらず、`/dl` は Vercel の rewrite だけで成立していた。
        比較: `chatstudy.jp/tsudumon/dl/` → 400「コードが正しくありません」（＝Functionに到達）、
        Function直叩きも同じ400。**Vercelを外すと `/dl` は確実に壊れる。**
  - [x] `firebase.json` の `rewrites` を `function` 形式へ直す必要があることを確定
- [x] `https://tsudumon.web.app/wb/01/` を開き、ホスト名ガードで chatstudy.jp へ飛ぶことを確認
      （HTML先頭に `location.replace('https://www.chatstudy.jp/tsudumon'+...)` を確認）
- [x] Firebase Hosting の `trailingSlash` 相当挙動を確認（Vercelの `trailingSlash: true` と差異がないか）
  - [x] **結果: 互換**。`/wb/01` → Firebase は 301 で `/wb/01/` へ、Vercel は 308 で同等。
        末尾スラッシュ付与の挙動は同じなので、この点の対応は不要。
- [x] `/api/chat` の現状確認
  - [x] **結果**: `chatstudy.jp/api/chat`（POST）→ 308（正常）、`tsudumon.web.app/api/chat` → **404**。
        Firebase側には存在せず、Cloud Function 化が必須であることを確定。
- [x] `public/tsudumon/` 配下で「手作業管理」されているファイル一覧を確定
  - [x] 各ファイルの正本が pdf-workbook 側に存在するか、marutto-study 側にしかないかを判定

### フェーズ0の結論: `public/tsudumon/` 各要素の正本所在

| 要素 | 正本 | 移設要否 |
|---|---|---|
| `index.html` / `privacy.html` / `tokushoho.html` | `pdf-workbook/lp/` | 不要（ビルド出力先変更のみ） |
| `wb/` `ref/` `map/` `_shared/` | ジェネレータ生成 | 不要 |
| `map/img/`（19枚） | `assets/quest/` `assets/characters/` → `generate_tsudumon_portal.py` が配置 | 不要 |
| `img/`（LP参照分） | `pdf-workbook/lp/img/` → `deploy-to-chatstudy.mjs` が配置 | 不要 |
| **`login/index.html`** | **marutto-study のみ** | **要移設** |
| **`activate/index.html`** | **marutto-study のみ** | **要移設** |
| **`account/index.html`** | **marutto-study のみ** | **要移設** |
| **`_healthz.txt`** | **marutto-study のみ** | **要移設** |
| `img/quest-*.webp` `img/char_manabi_sm.png`（18枚） | 旧レイアウトの残骸。どのページからも参照されていない（quest画像の実使用は `map/img/`） | 不要（移設せず破棄） |

## フェーズ1: 手作業管理ファイルの正本を pdf-workbook へ移設

- [x] 正本が marutto-study 側にしかないファイルを `pdf-workbook/web/` へ移設
  - [x] `login/index.html`
  - [x] `activate/index.html`
  - [x] `account/index.html`
  - [x] `_healthz.txt`
  - [x] ~~`img/`（LPが参照する画像を除いた、ページ共通画像）~~
        （フェーズ0の調査により不要と判明: `img/` は `lp/img/` と `assets/quest/` から
        ビルド時に配置される生成物であり、手作業管理ではなかった。
        直下 `img/quest-*.webp` 18枚は旧レイアウトの未参照な残骸のため移設せず破棄）
- [x] 移設したファイルが差分なくコピーされたことを確認（`diff -r` で0件）
- [x] `pdf-workbook/web/README.md` を作成し、正本の所在・LINE Callback URL・編集時の注意を記録
- [ ] `deploy_tsudumon.py` の docstring を更新（「手作業管理」の記述を新しい配置に合わせる）
      → フェーズ2の出力先変更とまとめて実施

### フェーズ1で判明した追加事項

- **LINE の Callback URL は2本ある**（当初 `/login/` の1本だと想定していた）:
  - `login/index.html:59` … `REDIRECT_URI = location.origin + '/tsudumon/login/'`
  - `activate/index.html:92` … `REDIRECT_URI = location.origin + '/tsudumon/activate/'`
  → ユーザー作業セクションの LINE Console 項目を2本に修正済み。
- `login/index.html:56` / `activate/index.html:87` のコメントに
  「marutto の `/welcome` は経由しない」とあり、**`/welcome` は旧経路**で
  この2ページが後継であることが確認できた。フェーズ3の `/welcome` → `/login/` 置換は方針として正しい。
- `account/index.html:110` は既に相対パス `'../login/?next='` を使っており、この行は変更不要。

## フェーズ2: ビルド出力先の変更と firebase.json 新設

- [x] `pdf-workbook/firebase.json` を新規作成
  - [x] `hosting` のみ定義（`functions` / `firestore` は書かない）
  - [x] `site: "tsudumon"` / `public: "dist-web"`
  - [x] `/dl` を `function` 形式の rewrite に修正（フェーズ0の結果を反映）
  - [x] `/api/chat` の rewrite を追加（フェーズ4で実装する関数を指す）
  - [x] キャッシュヘッダを現行 `marutto-study/firebase.json` から移植（`_shared/img/**` を追加）
  - [x] `/tsudumon/**` → `/**` の301 redirect を追加（旧パス形式で来た場合の保険）
- [x] `pdf-workbook/.firebaserc` を新規作成（`default: chatstudy-63477`）
- [x] 3ジェネレータの出力先を `dist-web/` に変更
  - [x] `generate_workbook_web.py`（`DEPLOY_DIR`＋docstring＋`--deploy` のヘルプ）
  - [x] `generate_reference_web.py`（同上）
  - [x] `generate_tsudumon_portal.py`（`DEPLOY_FILE`＋docstring＋ヘルプ）
- [x] `deploy_tsudumon.py` の `TSUDUMON` 定数を `BASE / "dist-web"` に変更
  - [x] `WB_DEPLOY` / `REF_DEPLOY` / `MAP_DEPLOY` / `SHARED_IMG` が追随することを確認
  - [x] docstring を新構成（dist-web・firebase deploy・LPは別ビルド）に書き直し
  - [x] `git_status_summary()` を `build_summary()` に置換
        （`dist-web/` は git 管理外になり git status によるドリフト検知が使えないため。
        代わりにファイル数・容量と、LP／手書きページの入り漏れ警告を出す）
  - [x] `--check` のリンク健全性検査が新パスで動作することを確認
- [x] `lp/deploy-to-chatstudy.mjs` を `lp/build-lp.mjs` にリネーム
  - [x] 出力先を `../dist-web` に変更
  - [x] `api/chat.js` を marutto-study へコピーする処理を削除
  - [x] 先頭コメントを新構成に合わせて書き直す
  - [x] 旧ファイルを削除
- [x] フェーズ1で移設した静的ファイルを `dist-web` へコピーする処理を追加
      （`deploy_tsudumon.py` の `copy_static()`。`web/README.md` は配信対象外として除外）
- [x] `pdf-workbook/.gitignore` に `dist-web/` と `.firebase/` を追加
- [x] スモークテスト（`--chapters 01`）で wb/ref/map＋static の生成と検証が通ることを確認
- [x] `node lp/build-lp.mjs` を実行し、LPが `dist-web/` に出力されることを確認（ページ3枚＋画像44枚）
- [x] 全19章のフルビルド確認（フェーズ3のテンプレート修正後に実施）
      → 670ファイル / 129.4MB、共通画像12種・重複225枚を `_shared/img/` に集約（8.2MB削減）、検証✓健全

### フェーズ2で判明した追加事項

- ジェネレータ2本（`generate_reference_web.py:41` / `generate_workbook_web.py:32`）が
  **`marutto-study/.env` から Firebase Web 設定を読んでいる**。
  配信面は独立するが、**ビルドには依然 marutto-study のチェックアウトが必要**な状態。
  → フェーズ3のタスクとして、pdf-workbook 側にフォールバックを持たせる。

## フェーズ3: ドメイン依存箇所の書き換え

- [x] ホスト名ガードの向き先を `https://tsudumon.jp` に変更（9ファイル・各1件）
  - [x] `generate_reference_web.py` / `generate_workbook_web.py` / `generate_tsudumon_portal.py`
  - [x] `lp/index.html` / `lp/privacy.html` / `lp/tokushoho.html`
  - [x] `web/login/index.html` / `web/activate/index.html` / `web/account/index.html`
        （当初の計画では6ファイルだったが、フェーズ1で移設した3ページにも同じガードがあった）
- [ ] **ホスト名ガードの対象に `www.tsudumon.jp` を追加する（2026-07-25 追記）**
      名刺・チラシに `www.tsudumon.jp` を載せる可能性があるため、お名前.com に
      `www` の CNAME → `tsudumon.web.app` を追加し、Firebase の同一サイトに紐づける方針。
      この方式は**リダイレクトではなく同じ内容を配信する**ので、`tsudumon.jp` と
      `www.tsudumon.jp` の2つのURLで同一コンテンツが見える＝検索評価が分散する。
      対策として、既存のガードの条件を次のように広げる（**9ファイルすべて同じ形で**）:
      `if(location.hostname==='tsudumon.web.app'||location.hostname==='www.tsudumon.jp')`
      → 転送先は現行どおり `https://tsudumon.jp` + pathname + search + hash。
      ※ サーバ側リダイレクトは使わないこと（Vercelプロキシ経由の経路でループする）。
      ※ 実施後は全19章の再生成＋`node lp/build-lp.mjs`＋`firebase deploy --only hosting:tsudumon` が必要。
- [x] `/welcome` 依存を `/login/` へ切り替え
  - [x] `generate_reference_web.py`（ログインボタンの href）
  - [x] `generate_reference_web.py`（`/welcome?next=` → `/login/?next=`）
  - [x] `generate_workbook_web.py`（`/welcome?next=` → `/login/?next=`）
  - [x] 上記2ファイルの説明コメント（「認証は www.chatstudy.jp の LINE Login」）も更新
  - [x] `login/index.html` の `next` 既定値を `/tsudumon/` → `/` に変更
  - [x] `login/index.html` のオープンリダイレクト許可判定を新パス構成に合わせる
        （`/tsudumon/` 前方一致 → 「`/` 始まりかつ `//` `/\` 始まりでない」。
        プロトコル相対URL `//evil.com` を弾く条件を明示的に追加）
- [x] `/tsudumon/` プレフィックス付き絶対パスを修正
  - [x] `web/activate/index.html`: `href="/tsudumon/"` → `/`、`href="/tsudumon/account/"` → `/account/`
  - [x] `web/account/index.html`: `href="/tsudumon/activate/"` → `/activate/`、
        `href="/tsudumon/map/"` → `/map/`、`href="/tsudumon/"` → `/`
  - [x] `lp/index.html` / `lp/tokushoho.html` の `href="/tsudumon/account/"` → `/account/`
  - [x] `web/account/index.html:110` は既に相対パス `'../login/?next='` のため変更不要
- [x] `www.chatstudy.jp/tsudumon` 形式の絶対URLを `tsudumon.jp` に置換（`lp/index.html` 6件）
  - [x] canonical / og:url
  - [x] OGP画像URL・twitter:image（`img/ogp.png`）
  - [x] 構造化データ（FAQ）内の解約案内URL
  - [x] チャットボットのFAQ応答文中のアカウントページURL
- [x] `marutto-study/functions/src/lineWebhook.ts` の `TSUDUMON_LP_URL` を
      `https://tsudumon.jp/` に変更（**この1行のみ**）
- [x] ジェネレータの Firebase Web 設定読み込みに pdf-workbook 側フォールバックを追加
      （`_FB_ENV` → `_FB_ENV_CANDIDATES = [pdf-workbook/.env, marutto-study/.env]`。
      pdf-workbook 単体でもビルドできるようにするため。値は同じ Firebase プロジェクト）
- [x] 再生成して置換漏れを検査
  - [x] `python -X utf8 deploy_tsudumon.py`（全19章）→ `node lp/build-lp.mjs`
  - [x] `dist-web/` 全体を `chatstudy.jp` で grep → **残存0件**
  - [x] `dist-web/` 全体を `/tsudumon/` で grep → **残存0件**
        （`login/index.html` の説明コメント1件のみ。意図的な記述）
  - [x] `dist-web/` 全体を `/welcome` で grep → **残存0件**
- [x] `python -X utf8 deploy_tsudumon.py --check` がエラーなく通ることを確認
- [x] 生成物の抜き取り確認（`ref/05` `wb/05`）
      → ホスト名ガード・`/login/` 導線・`tophome`（`../../map/index.html`）・
      `REDIRECT_URI`（`/login/` `/activate/`）すべて期待どおり

### フェーズ3-b: marutto-study 側の残存URL（2026-07-25 追加調査で判明）

フェーズ3では `lineWebhook.ts` の `TSUDUMON_LP_URL` **1行だけ**を変更したが、
`marutto-study/functions` と `scripts` に**ユーザーへ実際に届く旧ドメインURL**が残っていた。
（`liff.line.me` の QR は影響なし＝冊子・配布済みPDFの刷り直しは不要。
`line.chatstudy.jp/*` `chatstudy.jp/mubista` `chatstudy.jp/typing` は**一問一答・別サービス用なので変更しない**。）

**A. ユーザーに届く（優先度：高）**

- [x] `functions/src/aiChatPrompt.ts` 3箇所（料金案内・支払い解約案内・不明時の案内）
      — **AI が生徒に案内する URL**。※調査後に確認したところ**既に対応済み**だった
- [x] `functions/src/tsudumonTrialReminder.ts` L28-29（`MAP_URL` / `LP_URL`）
      — cron push で実送信するリンク。※**既に対応済み**
- [x] `functions/src/tsudumon/followHandlers.ts:40` `TSUDUMON_LP_URL` — ※**既に対応済み**
- [x] `scripts/manage-tsudumon.ts` — **購入者への案内文テンプレ**（2026-07-25 対応）
  - [x] L38 `DL_BASE` → `https://tsudumon.jp/dl`
  - [x] L39 `ACTIVATE_BASE` → `https://tsudumon.jp/activate/`
  - [x] L21 docstring

**B. コメントのみ（実害なし・追随更新）**

- [x] `functions/src/gradeWritten.ts` L4・L9 — ※既に対応済み
- [x] `functions/src/referenceChat.ts` L5・L11 — ※既に対応済み
- [x] `functions/src/tsudumonActivate.ts` L5・L6 — ※既に対応済み
- [x] `functions/src/tsudumonDownload.ts` L11（2026-07-25 対応）
- [x] `docs/operations/tsudumon-fulfillment.md` L46 DLリンク（2026-07-25 対応）
- [x] `functions/src/tsudumonLpChat.ts:12` — 移行の経緯を述べた記述なので**変更しない**（正しい）
- [ ] `pdf-workbook/web/README.md` / `CODEX_BRIEF_PORTAL.md` / `docs/つづもん-登録フロー設計.md`

**変更してはいけない（別サービス・確認済み）**

- `aiChatPrompt.ts:143` `www.chatstudy.jp/typing/`（タイプでスタディ）
- `line.chatstudy.jp/*`（LIFF・一問一答）/ `chatstudy.jp/mubista`（ムビスタ）

**C. 確認**

- [x] `grep -rn "chatstudy\.jp/tsudumon" marutto-study/functions/src marutto-study/scripts` → **残存0件**
- [x] `/dl` `/api/chat` は `pdf-workbook/firebase.json` に `function` 形式 rewrite として定義済み
      → `https://tsudumon.jp/dl?c={code}` は成立する（`manage-tsudumon.ts` の変更は安全）
- [ ] **実コードで `https://tsudumon.jp/dl?c={code}` の 302 を実機確認**してから購入者に案内文を送る
- [ ] `marutto-study/vercel.json` L52-58 の `/tsudumon/dl` rewrite の扱いを決める
      （フェーズ6で 301 に置換するなら、旧DLリンクは新ドメインの `/dl` へ飛ぶことを確認）
- [ ] **301 リダイレクトは恒久的に維持**する（納品案内メール等に旧DLリンクが残っているため、
      フェーズ6の「旧URL→新URL 301」は消さない）

## フェーズ4: LPチャットAPIのCloud Function化

- [x] `marutto-study/functions/src/tsudumonLpChatCore.ts` を新規作成（純ロジック）
      （既存の `*Core.ts` パターンに合わせ、HTTPに依存しない部分を分離してテスト可能にした）
  - [x] `SYSTEM_PROMPT` を移植（1文字も変えない）
  - [x] `normalizeMessages` … 履歴8件・1メッセージ300文字の切り詰めと不正入力の排除
  - [x] `DailyCounters` … JST日次リセット付きの全体／利用者別カウンタ
  - [x] `REPLY` … 応答文言を定数化（移行前と完全一致）
  - [x] `readLimit` / `parseGeminiReply` / `buildGeminiRequest`
- [x] `marutto-study/functions/src/tsudumonLpChat.ts` を新規作成（HTTPハンドラ）
  - [x] ~~`onRequest`（v2）~~ → **v1 の `functions.region('asia-northeast1').https.onRequest`**
        （実装方針変更: 同じ Hosting rewrite で呼ばれる `tsudumonDownload` が v1 で書かれており、
        リポジトリの既存パターンに合わせた。firebase.json の `function` rewrite は v1 でも動く）
  - [x] 環境変数キー名は `GEMINI_API_KEY` / `CHAT_DAILY_LIMIT` / `CHAT_USER_DAILY_LIMIT` を踏襲
  - [x] 405・上限到達・バリデーション失敗時の応答文言を現行と一致させる
  - [x] 失敗時に `console.error` を追加（Vercel版は握りつぶしていたので運用性を上げた）
- [x] `functions/src/index.ts` に `export { tsudumonLpChat }` を追加
- [x] ユニットテスト `functions/src/__tests__/tsudumonLpChatCore.test.ts` を作成（21件・全パス）
  - [x] JST日付境界（UTC日をまたいでも同一JST日ならリセットしない）
  - [x] 履歴8件への切り詰め／300文字への切り詰め／不正要素の排除
  - [x] 末尾が assistant のときは null（＝400）
  - [x] 全体上限・利用者別上限がそれぞれ独立に効く
  - [x] Gemini応答が空・不正なときのフォールバック文言
  - [x] 応答文言が移行前と完全一致していること
- [x] `lp/index.html` のチャット呼び出し先が `/api/chat` のままで動くことを確認
      （firebase.json の rewrite で Cloud Function に到達するためフロント側の変更は不要）
- [x] `lp/api/chat.js` の先頭に「正本は Cloud Function へ移行済み」の注記を追加
- [x] `npm run build`（functions）が通ることを確認
- [x] テストが通ることを確認（`npx vitest run functions/src/__tests__/tsudumonLpChatCore.test.ts`）

## フェーズ5: 品質チェック

- [x] functions のテストが通る
      → 27ファイル383件中 **382件パス / 1件失敗**。
      失敗は `workbookTopic.test.ts`（「律令国家と奈良時代」の written 数が 2 期待に対し 3）。
      **本作業と無関係の既存failure**（データ元 `generated/workbook-input-questions.generated.ts` も
      テストファイルも作業ツリーで未変更＝HEAD時点で既に失敗する）。
- [x] functions のビルドが通る（`npm run build` → tsc エラーなし）
- [x] `deploy_tsudumon.py --check` が exit 0（全19章 ✓健全）
- [x] `dist-web/` をローカルHTTPサーバで表示確認
  - [x] LP・`wb/01/`・`ref/01/`・`map/`・`login/`・`activate/`・`account/`・
        `privacy.html`・`tokushoho.html`・`_healthz.txt` が全て200
  - [x] ページ間リンクが新パス構成で正しく解決する（6ページから辿れる54リンク全て200）
- [x] `git diff marutto-study/functions/src/lineWebhook.ts` に本作業由来の変更が
      `TSUDUMON_LP_URL` の1行だけであることを確認
      （同ファイルには並行作業「20260725-tsudumon-dedicated-line-bot」の client 引数化による
      差分が多数あるが、本作業とは別。`getLineClient()`/`client:` を含む行が88行）

## フェーズ6: 反映（🔴 ユーザー承認後に実施）

**このフェーズは承認なしに実行しない。** → 2026-07-25 に承認を得て実施。

- [x] `firebase deploy --only hosting:tsudumon --project chatstudy-63477`
      （**別セッションで実施済み**。本セッションでは未実行だが、稼働中の `tsudumon.jp` が
      フェーズ3の変更（ホスト名ガード `tsudumon.jp`・`href="/login/"`）を配信していることで確認）
- [x] `firebase deploy --only functions:tsudumonLpChat --project chatstudy-63477`
      → `FUNCTIONS_DISCOVERY_TIMEOUT=600` 付きで実行し成功。
      1st Gen / asia-northeast1 で新規作成。
- [x] ~~`tsudumon.web.app` で全ページの動作確認（DNS切替前の最終検証）~~
      （手順変更により不要: DNS・SSLが先に完了し、`tsudumon.jp` で直接検証できたため。
      またホスト名ガードが `tsudumon.web.app` → `tsudumon.jp` へ飛ばす仕様上、
      web.app では検証できない）
- [x] `tsudumon.jp` で受け入れ条件を確認
  - [x] `/` `/wb/01/` `/ref/01/` `/map/` `/login/` `/account/` すべて 200
  - [x] `https://tsudumon.jp/_healthz.txt` 200（SSL有効）
  - [x] `/dl` → 400「コードが正しくありません」＝ Cloud Function に到達
        （フェーズ0で判明した `destination` 誤設定が `function` 形式で解消されたことの実証）
  - [x] `/api/chat` → POST 200 でGemini応答、GET 405、空messages 400
  - [x] `/tsudumon/wb/01/` → 301 → `https://tsudumon.jp/wb/01`（保険の301も動作）
- [x] `marutto-study/vercel.json` の `/tsudumon` 系 rewrite を 301 redirect に置換
  - [x] `/tsudumon/dl` の rewrite も削除（転送先の `tsudumon.jp/dl` が
        Firebase Hosting の rewrite で同じ Function に到達するため不要）
  - [x] `mubista` / `typing` / SPA catch-all は無変更（影響を与えない）
- [x] marutto-study を git push（Vercel再ビルド）
      → コミット `1e0ab2f8`。**`vercel.json` の1ファイルのみをステージしてコミット**
      （並行作業の未コミット47ファイルを巻き込まないため）
- [x] 旧URL `chatstudy.jp/tsudumon/wb/01/` が301で新URLへ飛ぶことを確認
      → Vercel の www フルビルド完了（push から約17分）後に反映を確認。
      `/tsudumon/` `/wb/01/` `/ref/05/` `/map/` `/account/` すべて308で対応パスへ転送し、
      最終到達 200。`/tsudumon/dl?c=TEST` は `tsudumon.jp/dl/?c=TEST` へ転送され
      「コードが正しくありません」＝Cloud Function に到達（配布済みQRの経路が生存）。
- [x] chatstudy.jp 本体（`/` `/typing/` `/mubista/`）に影響が無いことを確認（すべて200）
- [x] 新ドメインの全ページ最終確認（11ページすべて200・LPチャット POST 200）
- [x] **LPチャットの実画面での動作をユーザーが確認**（2026-07-25・問題なし）

## フェーズ7: 移行後の掃除（2026-07-26・ユーザー承認のうえ実施）

コミット `a32b9715`（766ファイル / 113,317行の削除）。push 済み。

- [x] `marutto-study/public/tsudumon/` を削除（762ファイル・141MB）
      正本は `pdf-workbook/dist-web/`（gitignore）。残しておくと、誤って
      marutto-study から `firebase deploy` したときに本番を古い内容で上書きする事故になる。
- [x] `marutto-study/api/chat.js` を削除（Vercel版チャット関数。正本は `tsudumonLpChat`）
      削除前に `src/` からの `api/chat` 参照がゼロであることを確認（つづもんLP専用だった）。
- [x] `marutto-study/firebase.json` から `hosting` 定義を削除（`tsudumon` の1件のみだったのでキーごと）
      **`public/tsudumon` の削除とセットで行うことが重要**。定義だけ残すと
      hosting デプロイが本番サイトを空にする。
- [x] `marutto-study/scripts/vercel-ignore-build.sh` を削除
      （判定対象の `public/tsudumon` が消え役目を終えた）
- [x] `marutto-study/package.json` の build 末尾 `rmSync('dist/tsudumon')` を削除
      （**当初の4項目に無かったが、作業中に死んだ設定と判明したため追加**。
      `public/tsudumon` が dist にコピーされ Vercel の静的配信が rewrite より
      優先されるのを防ぐものだったが、コピー元が消え、かつ rewrite は redirect に
      変わったため不要になった）
- [x] `npm run typecheck` 通過
- [x] 本番の無影響を確認（`tsudumon.jp` 200 / 旧URL301転送 / chatstudy.jp 本体 200）
- [x] **Vercel ダッシュボードの Ignored Build Step を空にする**（ユーザーが実施）
      スクリプト削除後もそのままだと非ゼロ終了＝毎回ビルド実行となり動作上は無害だが、
      ビルドログにエラーが出続けるため。

## フェーズ8: 付随して直したもの

- [x] `functions/src/__tests__/workbookTopic.test.ts` の失敗を修正（コミット `162e6378`）
      HEAD 時点から失敗していた既存不具合。本移行とは無関係だが、失敗テストが常態化すると
      リグレッション検知が効かなくなるため対応した。
  - [x] 原因調査: データ側が正しく、テストの固定値が古かった
        （`律令国家と奈良時代` の記述問題は律令の説明・平城京・地方統治の3問で重複なし）
  - [x] 固定値を 3 に直すのではなく、検査の中身を作り替えた。
        テスト名は「全単元に」だが実際は1単元しか見ていなかったため、
        **全111単元・1,450問を走査**し、逆引きの種別・単元名・問題番号の一致と
        ID の全単元一意性を検証する形にした。問題数への依存が無くなり、
        コンテンツ増減で壊れず、ID重複・採番ズレを検出できるようになった。
  - [x] functions のテスト全体 38ファイル / 613件すべてパス

### フェーズ6で判明した事項

- **本番で実害が出ていた**: `chatstudy.jp/tsudumon/*` が新ビルドをプロキシ配信していたため、
  ページ内の `/login/`（ルート相対）が `www.chatstudy.jp/login/` に解決され、
  chatstudy の SPA（`<title>チャットでスタディ</title>`）が **200 で返っていた**。
  配布済みPDFのQR・LINE内リンクから来た人がログインできない状態だった。
  → design.md §0 で予見していた「デプロイと301の間が空くと壊れる」が実際に起きた。
  **Hosting のデプロイと Vercel の301はセットで行うべき**という教訓。

---

## 🔴 ユーザー作業（コンソール操作・Claudeは実行不可）

上記フェーズとは別に、ユーザー側での操作が必要な項目。
**フェーズ6の前に完了している必要がある。**

### お名前.com（DNS）
- [ ] Firebase コンソール → Hosting → `tsudumon` サイト → カスタムドメイン追加で `tsudumon.jp` を登録
- [ ] 表示されたTXTレコードをお名前.comのDNS設定に追加（所有権確認）
- [ ] 所有権確認後に表示されるAレコード2本をお名前.comに追加
- [ ] `www.tsudumon.jp` を使うかを決定（使うならリダイレクト設定も）
- [ ] SSL証明書の自動発行完了を待つ（数十分〜最大24時間）

### LINE Developers Console
LINEログインチャネル `2009587166` のコールバックURLに、**2本とも**追加する。

- [ ] `https://tsudumon.jp/login/` を追加
- [ ] `https://tsudumon.jp/activate/` を追加
- [ ] 旧URL2本（`https://www.chatstudy.jp/tsudumon/login/` / `.../activate/`）は
      **当面残す**（301猶予期間中の保険）

### Firebase / Vercel 環境変数
- [ ] `GEMINI_API_KEY` を Firebase Functions 側に設定（`functions/.env` へキーを追加）
- [ ] 必要なら `CHAT_DAILY_LIMIT` / `CHAT_USER_DAILY_LIMIT` も設定

### Stripe
- [ ] Checkout の success_url / cancel_url に新ドメインが使われているか確認し、必要なら更新
- [ ] 顧客ポータルの戻り先URLを確認

---

## 実装後の振り返り

### 実装完了日
2026-07-25（フェーズ0〜6完了。**tsudumon.jp が本番稼働中**）

同日中に、ユーザーによるコンソール作業（DNS・LINE Console）と、
承認を得たうえでのデプロイ（Cloud Function・Vercel 301）まで完了した。
LPチャットの実画面動作もユーザーが確認済み。

**残っているのは「移行後の掃除」4項目のみ**（`public/tsudumon/` 削除ほか）。
これは技術的にいつでも実施できるが、**切り戻しの余地を残すため意図的に保留**している
＝ユーザー判断待ちであり、時間や難易度を理由にスキップしたタスクは無い。

### 計画と実績の差分

**計画と異なった点**:

1. **`/dl` が Firebase 単体で壊れていたことが事前検証で判明**（フェーズ0）。
   `marutto-study/firebase.json` は `{"source":"/dl","destination":"https://…cloudfunctions.net/…"}`
   と書かれていたが、Firebase Hosting の `rewrites.destination` はローカルパス専用で
   外部URLを取れない。実測で `tsudumon.web.app/dl` は 404 を返し、
   Vercel 側の rewrite だけで成立していた。
   → 新 `firebase.json` では `{"function":{"functionId":…,"region":…}}` 形式に直した。
   **設計時に「Vercelは転送しているだけ」と考えていたが、実際には Vercel が
   機能を1つ肩代わりしていた。** 事前検証を1フェーズ設けた判断が効いた。

2. **`/api/chat` も Vercel 固有機能だった**。LPのAIチャットは Vercel Serverless Function で、
   Firebase Hosting は静的配信専用のため素直に移せない。Cloud Function へ移植した。
   これは requirements 作成時点で調査済みだったので計画に織り込めた。

3. **Cloud Function は v2 ではなく v1 で実装**。設計書では `onRequest`（v2）と書いたが、
   同じ Hosting rewrite で呼ばれる `tsudumonDownload` が v1 だったため既存パターンに合わせた。

4. **ホスト名ガードの対象が6ファイルではなく9ファイルだった**。
   フェーズ1で移設した `login/` `activate/` `account/` にも同じ1行が入っていた。

5. **LINE の Callback URL が1本ではなく2本だった**（`/login/` と `/activate/`）。
   `activate/index.html` が独自の `REDIRECT_URI` を持っていた。
   ユーザー作業セクションを2本に修正した。

**新たに必要になったタスク**:

- `pdf-workbook/web/` の新設と README 作成。
  `login/` `activate/` `account/` `_healthz.txt` は正本が marutto-study 側にしか無く、
  pdf-workbook だけをチェックアウトしても復元できない状態だった。
- ジェネレータの `.env` 探索に pdf-workbook 側フォールバックを追加。
  Firebase Web 設定を `marutto-study/.env` から読んでおり、
  配信面を独立させてもビルドに marutto-study のチェックアウトが必要なままだった。
- `deploy_tsudumon.py` の `git_status_summary()` → `build_summary()` 置換。
  `dist-web/` を gitignore にしたので git status によるドリフト検知が使えなくなった。
  代替として、LP・手書きページの入り漏れを警告する形にした。

**技術的理由でスキップしたタスク**:

- `web/img/` の移設（フェーズ1）。
  スキップ理由: フェーズ0の調査で、`img/` は `lp/img/` と `assets/quest/` から
  ビルド時に配置される**生成物**であり手作業管理ではないと判明したため。
  代替実装: 移設せず、既存のビルド経路（`build-lp.mjs` と `generate_tsudumon_portal.py`）
  をそのまま使う。直下の `img/quest-*.webp` 18枚は旧レイアウトの未参照な残骸のため破棄。

### 学んだこと

**技術的な学び**:

- **「プロキシは転送しているだけ」は検証しないと言えない。** 今回は `/dl` と `/api/chat` の
  2つで、Vercel層が実際の機能を担っていた。移行の設計は
  「経路上の各層が何を提供しているか」を実測してから確定させるべき。
- Firebase Hosting の `rewrites` は `destination`（ローカルパス）と
  `function` / `run`（バックエンド）が明確に別物。外部URLを `destination` に書いても
  エラーにならず静かに404になるため、設定ファイルを読むだけでは誤りに気づけない。
- Firebase Hosting と Vercel の末尾スラッシュ挙動は互換だった
  （ディレクトリURLに対し Firebase 301 / Vercel 308）。移行時の懸念点を1つ減らせた。
- オープンリダイレクト対策を「特定プレフィックスの前方一致」で書いていると、
  パス構成の変更時に条件ごと消えるリスクがある。
  今回は「`/` 始まりかつ `//` `/\` 始まりでない」に置き換えて意図を明示した。

**プロセス上の改善点**:

- フェーズ0（事前検証）を独立して置いたのが有効だった。
  実装前に `/dl` の404を掴めたので、デプロイ後に本番で気づく事故を回避できた。
- 同一ファイル（`lineWebhook.ts`）を並行作業が改修中だったため、
  変更を1行に限定するルールをタスクリスト冒頭に明記して守った。
  結果、`git diff` に他作業の差分が266行混ざっていても、自分の変更を特定・説明できた。

### 次回への改善提案

- **配信面は独立したが、まだ chatstudy-63477（Firebase）と公式LINEは共有している。**
  Cloud Functions の正本も marutto-study 側にある。
  「つづもんだけを別環境へ」を将来やるなら、Functions の codebase 分割が次の一歩。
- ドメインやアカウントを指す文字列（`lin.ee/...`・ドメイン・LIFF ID）が
  複数ファイルに直書きされている。今回は9ファイルのホスト名ガードを機械置換で対応したが、
  共通の設定モジュールへ集約しておくと次回の切り替えが軽くなる
  （`docs/つづもん-公式LINE分離移行手順.md` 章6の「任意ステップ」と同じ問題）。
- `workbookTopic.test.ts` が HEAD 時点で失敗している。本作業とは無関係だが、
  失敗テストが常態化するとリグレッション検知が効かなくなるため、別途修正が要る。
