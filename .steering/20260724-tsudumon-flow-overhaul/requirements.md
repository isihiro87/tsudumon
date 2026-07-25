# 要求内容 — つづもん 登録〜利用フロー総合改善

作成 2026-07-24。正本設計: `pdf-workbook/docs/つづもん-登録フロー設計.md`（LINEファースト・中間案）を前提に、
①ゲート基盤の穴埋め、②自動ログイン（毎回ログイン操作の撲滅）、③3日間無料お試し を一体で実装する。

## 概要

有料登録ユーザーが「リッチメニューを押すだけ・ログイン操作なし」で教材を使え、
未購入ユーザーが「LINE友だち追加＋ワンタップで3日間全単元を試せる」状態にする。

## 背景

- 現状のゲートは `localStorage['tzm-lic']`（学年配列・**期限なし**）で解錠するため、
  3日で切れる体験を導入すると期限後も端末に全開放が残る。先に基盤を直す必要がある。
- ログインは端末ごと初回のみだが、ロック画面→ログインページ→ボタンと2タップ手動。
  LINEアプリ内ブラウザなら LINE Login は無操作で完結できるのに使っていない。
- 無料体験は現状「常設1単元」のみ。時間制限つきの全開放体験（3日）が未実装。
- 転換計測（体験開始→期限切れ→購入）のイベントが未整備。

## 実装対象の機能

### 1. ゲート基盤整備（フェーズ1）
- `tzm-lic` キャッシュを `{grades, exp}` 形式に変更（期限切れ＝未ライセンス扱い、旧形式は破棄）
- 有効期限は「entitlement の expiresAt と now+30日 の小さい方」。裏で `tsudumonEntitlement` 再検証
- `activateTsudumonLicense` の users 書き込みを「tsudumon フィールド丸ごと置き換え」に変更
  （trial→本購入で `source` 等の残留を防ぐ）
- funnel イベント基盤: `trial_started` / `trial_expired` / `tsudumon_activated` を `logServerFunnelEvent` で記録

### 2. サイレント自動ログイン（フェーズ2）
- `/tsudumon/login/` に `?auto=1`: LINE内ブラウザ（UA `Line/`）ならボタンを出さず即 OAuth リダイレクト
  （自動試行は sessionStorage で1回限り、失敗時は現行のボタン表示へフォールバック）
- 両生成器（reference/workbook）のロック処理: 未ログイン＋LINE内ブラウザなら
  ロックカードを見せる前に `login/?auto=1&next=` へ自動遷移
- 登録完了メッセージ・案内メールに「教材はLINEのメニューから開く」を明記（正規入口の一本化）

### 3. 3日間無料お試し（フェーズ3）
- 新関数 `tsudumonTrialStart`（POST {idToken}）: `users/{uid}.tsudumon = {plan:'set', source:'trial', expiresAt: now+3日}` を付与
  - 1 uid 1回（`tsudumonTrialUsedAt` を恒久保持）／有効な本ライセンス保持者には付与しない
  - 既存の `evaluateTsudumonAccess` / `tsudumonEntitlement` / 教材ゲート / AI採点はそのまま動く（無変更）
- 入口: ロックオーバーレイに「3日間ぜんぶ無料で試す」ボタン、friend-add あいさつ・リッチメニュー文言
- 期限後の受け皿: 常設無料1単元＋頭出しへ自然に戻る（expired メッセージで無料単元と購入LPを案内）
- 文言統一: LP（hero/FAQ/構造化データ）・`lp/tokushoho.html`・`lp/api/chat.js`・AIチャットプロンプトを
  「3日間全単元無料＋期限後も1単元はずっと無料」に更新
- リマインド: `tsudumonTrials/{uid}` 軽量コレクションを開始時に作成し、cron はそこだけ走査
  （開始直後・期限前日・期限翌日の3通。push は配信枠を消費するため `deliveryStats` に計上）

## 受け入れ条件

### ゲート基盤整備
- [ ] 期限切れ entitlement の端末で有料単元 step≥2 がロックされる（旧 `tzm-lic` 残存時も含む）
- [ ] 本購入の有効化で `tsudumon.source` 等の旧フィールドが残らない
- [ ] 既存の有料ユーザー（管理用アカウント含む）の閲覧が途切れない

### サイレント自動ログイン
- [ ] LINEのリッチメニューから開いた場合、ログイン画面・ボタンを一度も見ずに有料単元が開く（初回同意画面を除く）
- [ ] 外部ブラウザ（Safari/Chrome）では現行どおりボタン式ログインが出る
- [ ] OAuth 失敗時に無限リダイレクトしない（1回で手動フォールバック）

### 3日間無料お試し
- [ ] 未購入ユーザーがワンタップで体験開始→全19単元が開く
- [ ] 開始から3日（72時間）で全端末ロックに戻り、無料1単元は引き続き読める
- [ ] 同じ uid で2回目の体験開始ができない
- [ ] 体験中に本ライセンスを有効化すると本ライセンスに上書きされる
- [ ] LP・特商法・LPチャットの記述が新体験内容と一致する

## 成功指標

- 有料ユーザーの「ログインできない/またログイン」の問い合わせゼロ
- funnel: trial_started → 3日内利用 → 購入転換率が計測できる状態になる

## スコープ外

- **Stripe 決済接続**（本番キー・価格確定待ち。接続時は Checkout 直付け＋体験残日数を
  `trial_period_days` に渡す方式。`createStripeCheckoutSession` の既存パターンを流用）
  ※ **2026-07-24 決定: 商品公開は月額プラン（Stripe）が整ってから**。Stripe接続は本計画とは
  別タスクだが公開のクリティカルパス。公開前の残修正は `launch-checklist.md` 参照
- 商品モデルの最終決定（月額サブスク一本化 vs コード併存）— 本フェーズの成果物はどちらでも流用可
- 教材ページの LIFF 化（自動ログインで足りなければ将来検討）
- 管理用アカウントへのライセンス付与 — **2026-07-24 実施済み**（`TZM-YMXP-EXMK`・set/3年・
  管理者2uid、`marutto-study/scripts/_grant-tsudumon-admin.ts`）

## 参照ドキュメント

- `pdf-workbook/docs/つづもん-登録フロー設計.md` — 登録フロー正本（本作業完了後に更新）
- `marutto-study/.steering/20260718-tsudumon-license/` — ライセンス基盤の設計
- `marutto-study/CLAUDE.md` — Firestore read 規律・Functions デプロイ規律（名前指定）
