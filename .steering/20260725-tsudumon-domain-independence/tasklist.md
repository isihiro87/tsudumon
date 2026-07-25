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

## フェーズ4: LPチャットAPIのCloud Function化

- [ ] `marutto-study/functions/src/tsudumonLpChat.ts` を新規作成
  - [ ] `lp/api/chat.js` のロジック（SYSTEM_PROMPT・レート制限・Gemini呼び出し）を移植
  - [ ] `onRequest`（v2 / region `asia-northeast1`）でエクスポート
  - [ ] 環境変数キー名は `GEMINI_API_KEY` / `CHAT_DAILY_LIMIT` / `CHAT_USER_DAILY_LIMIT` を踏襲
  - [ ] 405・上限到達・バリデーション失敗時の応答文言を現行と一致させる
- [ ] `functions/src/index.ts` に `export { tsudumonLpChat }` を追加
- [ ] ユニットテスト `functions/src/__tests__/tsudumonLpChat.test.ts` を作成
  - [ ] GET リクエストで405を返す
  - [ ] `GEMINI_API_KEY` 未設定時にフォールバック文言を返す
  - [ ] 300文字超のメッセージを弾く
  - [ ] 全体上限到達時にFAQ/LINE誘導の文言を返す
- [ ] `lp/index.html` のチャット呼び出し先が `/api/chat` のままで動くことを確認
- [ ] `lp/api/chat.js` の先頭に「正本は functions/src/tsudumonLpChat.ts へ移行済み」の注記を追加
- [ ] `npm run build`（functions）が通ることを確認
- [ ] `npm test`（functions）が通ることを確認

## フェーズ5: 品質チェック

- [ ] functions のテストが通る（`npm test`）
- [ ] functions のビルドが通る（`npm run build`）
- [ ] `deploy_tsudumon.py --check` が exit 0
- [ ] `dist-web/` を `firebase serve` 相当（またはローカルHTTPサーバ）で表示確認
  - [ ] LP・`wb/01/`・`ref/01/`・`map/` が表示される
  - [ ] ページ間リンクが新パス構成で正しく遷移する
- [ ] `git diff marutto-study/functions/src/lineWebhook.ts` が `TSUDUMON_LP_URL` の1行のみであることを確認

## フェーズ6: 反映（🔴 ユーザー承認後に実施）

**このフェーズは承認なしに実行しない。**

- [ ] `firebase deploy --only hosting:tsudumon --project chatstudy-63477`（pdf-workbook から）
- [ ] `firebase deploy --only functions:tsudumonLpChat --project chatstudy-63477`
- [ ] `tsudumon.web.app` で全ページの動作確認（DNS切替前の最終検証）
- [ ] DNS反映後、`tsudumon.jp` で受け入れ条件を全項目確認
- [ ] `marutto-study/vercel.json` の `/tsudumon` 系 rewrite を 301 redirect に置換
- [ ] `marutto-study/public/tsudumon/` を削除
- [ ] `marutto-study/api/chat.js` を削除
- [ ] `marutto-study/firebase.json` から `hosting.tsudumon` 定義を削除
- [ ] `marutto-study/scripts/vercel-ignore-build.sh` を削除（`public/tsudumon` が消えるため役目を終える）
- [ ] marutto-study を git push（Vercel再ビルド）
- [ ] 旧URL `chatstudy.jp/tsudumon/wb/01/` が301で新URLへ飛ぶことを確認

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
（未実施）

### 計画と実績の差分

**計画と異なった点**:
- （実装後に記入）

**新たに必要になったタスク**:
- （実装後に記入）

### 学んだこと
- （実装後に記入）

### 次回への改善提案
- （実装後に記入）
