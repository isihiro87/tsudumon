# 設計書 — つづもん 登録〜利用フロー総合改善

## アーキテクチャ概要

既存の「LINE uid（`line:{userId}`）を共通キーに、`users/{uid}.tsudumon` スナップショット1 readで
判定する」構造は変えない。体験も自動ログインも、この上に薄く乗せる。

```
[LINEアプリ]
  リッチメニュー/トークリンク
        │ (LINE内ブラウザ)
        ▼
[教材ページ ref/wb]  ──未ログイン＋LINE UA──▶ [/tsudumon/login/?auto=1&next=…]
  tzm-lic {grades,exp} で即解錠                │ 即 access.line.me/authorize（無操作）
  裏で tsudumonEntitlement 再検証              │ createLineCustomToken → signInWithCustomToken
        │                                      ▼
        │◀──────────── location.replace(next) ──
        │
  ロックカード「3日間ぜんぶ無料で試す」──▶ [tsudumonTrialStart] → users/{uid}.tsudumon
                                              (plan:'set', source:'trial', +3日)
                                              + tsudumonTrials/{uid}（リマインド用）
```

## コンポーネント設計

### 1. `tzm-lic` v2（両生成器の通常script＋module script）

**責務**: ネットワーク・ログイン待ちなしの即時解錠と、期限切れの確実な失効。

**形式**: `localStorage['tzm-lic'] = JSON {"g":["中1","中2","中3"],"exp":<ms>}`
- `isLicensed()`: JSON が旧形式（配列）なら破棄して false。`exp < Date.now()` なら false。
- `refreshEntitlement()`: `exp = min(entitlement.expiresAtMs, now+30日)` で保存。
  `tsudumonEntitlement` レスポンスに `expiresAtMs`（数値）を追加する（現状 label のみ）。
- grades が空（expired/none）なら `tzm-lic` を削除する（現状は空配列を保存するだけで同義だが明示）。

**実装の要点**:
- 変更箇所: `pdf-workbook/generate_reference_web.py` / `generate_workbook_web.py` の
  TEMPLATE 内 `isLicensed` / `refreshEntitlement`（ref側 1379行/1695行付近）と、
  `marutto-study/functions/src/tsudumonActivate.ts` の `tsudumonEntitlement`（expiresAtMs 追加）。
- 既存ユーザーの旧形式キャッシュは初回アクセスで破棄→ログイン済みなら裏で再取得されるため無風。

### 2. サイレントログイン（`marutto-study/public/tsudumon/login/index.html`）

**責務**: LINE内ブラウザでは人間の操作なしで OAuth を往復して戻す。

**フロー**:
1. `?auto=1` かつ UA に `Line/` を含む かつ `sessionStorage['tzm-auto-tried']` なし
   → `tzm-auto-tried=1` を立てて即 `location.href = loginUrl()`。
2. それ以外（外部ブラウザ・自動試行済み・OAuth エラー戻り）→ 現行のボタン表示。
3. 成功時は現行どおり `onAuthStateChanged` → `next` へ replace。

**教材側**: ロック到達時（`showLock` 直前）に
`未ログイン && /Line\//.test(navigator.userAgent) && sessionStorage['tzm-auto-login'] なし`
→ フラグを立てて `../../login/?auto=1&next=<現在地>` へ遷移。戻ってきて未解錠ならロックカード表示。

**実装の要点**:
- 無限ループ防止は sessionStorage（タブ単位・LINE内ブラウザは都度新規タブなので安全側）。
- Callback URL は既存の `/tsudumon/login/` のままで追加登録不要。

### 3. `tsudumonTrialStart`（`marutto-study/functions/src/tsudumonActivate.ts` に追加）

**責務**: 1 uid 1回の3日間 set entitlement 付与。

**API**: POST `{idToken}` → `{ok:true, expiresLabel}` |
`{ok:false, reason:'already_licensed'|'trial_used'|…, message}`

**トランザクション**:
```
users/{uid} を read:
  evaluateTsudumonAccess(tsudumon) === 'ok'      → already_licensed（何もしない）
  tsudumonTrialUsedAt あり                        → trial_used（購入案内文を返す）
  それ以外 → set:
    tsudumon = { plan:'set', source:'trial', years:0,
                 activatedAt: now, expiresAt: now+72h }   … フィールド丸ごと置き換え
    tsudumonTrialUsedAt = now
tsudumonTrials/{uid} = { startedAt, expiresAt, lineUserId, reminded: {} }   … cron 用
logServerFunnelEvent('trial_started', uid)
```

**既存コアとの整合**:
- `readTsudumonEntitlement` は plan/expiresAt しか見ないため、trial doc はそのまま 'ok' 判定になり、
  72時間後に自然に 'expired' となる。**コア（tsudumonCore.ts）は無変更**。
- `activateTsudumonLicense` の users 書き込みを `tsudumon` マップの merge から
  「丸ごと置き換え」（`{ merge: true }` のまま `tsudumon: {...}` を完全な新オブジェクトで
  `FieldValue` を使わず set — ネストマージを避けるため update(`{'tsudumon': {...}}`) 形式）に変更。
  これで trial→本購入時に `source:'trial'` が消える。

### 4. 体験入口 UI（両生成器 TEMPLATE）

- ロックカードに主ボタン「🎁 3日間ぜんぶ無料で試す」を追加（未 trial 判定はサーバに任せ、
  押下→ログイン（必要なら auto）→ `tsudumonTrialStart` → 成功で `refreshEntitlement` → 解錠続行。
  `trial_used` / `already_licensed` はメッセージ表示＋購入LP/ログイン案内）。
- 既存「LINEでログイン（購入者の方）」「つづもんを見てみる→」は維持。

### 5. リマインド cron `tsudumonTrialReminder`（新規・フェーズ3後半）

- 毎日 JST 19:00。`tsudumonTrials` を `expiresAt` レンジで走査（体験者数ぶんの read のみ。
  users 全体は舐めない）。
- 送信3種: 開始翌日（使い方＋おすすめ単元）／期限前日（あと1日＋購入CTA）／期限翌日
  （`trial_expired` funnel 記録＋無料単元案内＋購入CTA。`tsudumonTrials` doc に既送フラグ）。
- push は配信枠を消費 → `recordPushDelivery` で `deliveryStats` に計上。
- デプロイは名前指定（`functions:tsudumonTrialReminder` 等）。LINE本番を巻き込まない。

### 6. 文言更新

- `pdf-workbook/lp/index.html`: hero「まずは無料で1単元」→「3日間ぜんぶ無料でお試し」、
  FAQ・JSON-LD・チャットのローカル回答も同修正。
- `pdf-workbook/lp/tokushoho.html`: 「無料体験（1単元）」→ 3日間体験＋常設1単元の記述へ。
- `pdf-workbook/lp/api/chat.js`: ナレッジの「無料体験: 1単元」→ 3日間体験に更新。
- friend-add あいさつ / リッチメニュー文言（marutto 側 webhook・メニュー設定）は
  体験導線リリース時に合わせて更新。

## データフロー（体験ユーザーの3日間）

```
1. LP or 友だち追加 → 教材を開く → 有料単元 step2 でロック
2. 「3日間ぜんぶ無料で試す」→（LINE内なら無操作ログイン）→ tsudumonTrialStart
3. tzm-lic {g:[中1,中2,中3], exp:+72h} 保存 → 全単元解錠
4. 翌日 push（使い方）→ 3日目 push（あと1日＋購入CTA）
5. 72h 経過: サーバ判定 'expired'・tzm-lic も exp 超過で失効 → ロック復帰＋無料1単元
6. 期限翌日 push（購入CTA）。購入 → activate で tsudumon 丸ごと置き換え → 通常有料ユーザー
```

## §7 Stripe 月額サブスク接続（2026-07-24 追加・アカウント確保済み）

方針: **コードレスの Checkout 直付け**。LINE uid を metadata に載せて Checkout Session を作り、
webhook が `users/{uid}.tsudumon` を直接書く（TZM コードは補助・ギフト用に温存）。

- **Env**（`functions/.env`・既存 Stripe 変数と同じ供給方式に合わせる）:
  `STRIPE_TSUDUMON_SECRET_KEY` / `STRIPE_TSUDUMON_PRICE_ID` / `STRIPE_TSUDUMON_WEBHOOK_SECRET`
  （テストキーで実装・検証 → 本番キーに差し替え）
- **`tsudumonCreateCheckout`**: POST {idToken} →（activate と同じ検証）→ Checkout Session
  （mode=subscription・price=env・`client_reference_id`=uid・`subscription_data.metadata.uid`=uid・
  success_url=`/tsudumon/map/?sub=thanks`・cancel_url=LP）→ {ok, url}。
  体験中（source==='trial' 且つ未失効）なら残日数を `subscription_data.trial_period_days` に
  渡す（`createStripeCheckoutSession.ts` の MAX_TRIAL_DAYS キャップのパターンを流用）＝
  体験終了後から課金開始。
- **`tsudumonStripeWebhook`**: 署名検証（raw body）。
  - `checkout.session.completed`: metadata.uid →
    `tsudumon = {plan:'set', source:'stripe', activatedAt, expiresAt = current_period_end + 3日猶予}`
    ＋ `stripeCustomerId` / `stripeSubscriptionId` をユーザーdocへ（mergeFields）
  - `invoice.paid`: subscription.metadata.uid → `expiresAt` を新しい period_end + 3日 に延長
  - `customer.subscription.deleted`: 即失効はさせない（expiresAt 経過で自然失効）。ログのみ
- **`tsudumonCreatePortal`**: POST {idToken} → Billing Portal セッション（解約・カード変更導線）
- **UI**: ロックカードと trial_used メッセージに「月額プランに登録（1,280円/月）」ボタン
  （trial ボタンと同型の `tzm-sub-pending` ログイン往復フロー→ checkout url へ遷移）。
  解約リンクは LP FAQ「解約」項＋activate ページから portal へ。
- **公開手順**: テストモードで E2E（テストカード 4242…）→ 本番キー差し替え → webhook 本番登録 →
  フェーズ4一括デプロイ → launch-checklist.md §A の整合確認。

### §7.1 商品タグによる webhook 振り分け（2026-07-25 追加・必須）

つづもんとチャットでスタディのプレミアム課金は **同一 Stripe アカウント**に相乗りしている。
Stripe は同一アカウント内の同じイベントを**登録済みの全エンドポイントへ配信する**ため、
対策なしだと「つづもん購入 → プレミアム側 `stripeWebhook` が `markPaid()` を実行してプレミアム
権限を誤付与＋お礼 push」「プレミアムの継続課金 → つづもん側が利用権を誤延長」が起きる。
そこで **`metadata.product` タグ**で振り分ける（判定は `functions/src/stripeProductTag.ts` の
純粋関数 `getStripeProductTag()` に集約。タグ値 `tsudumon`）。

- **付与**: `tsudumonCreateCheckout` が Checkout Session 作成時に
  `metadata[product]=tsudumon` と `subscription_data[metadata][product]=tsudumon` の
  両方を付ける（Session / Subscription / Invoice のどのイベントからも引けるようにするため）。
- **`tsudumonStripeWebhook` は opt-in**: 署名検証の直後、イベント種別の分岐前に
  「タグが `tsudumon` でなければ何もせず 200（`{received:true, skipped:'not_tsudumon'}`）」。
  **タグ無し（空）も処理しない**＝誤付与より不付与を選ぶ。
- **`stripeWebhook`（プレミアム・本番稼働中）は opt-out**: 同じ位置で
  「タグが `tsudumon` なら何もせず 200（`{received:true, skipped:'tsudumon'}`）」。
  **タグ無しは従来どおり全処理**＝既存プレミアムの挙動は不変。
- **タグの探索場所**（実オブジェクトを確認して決定・推測禁止）: `metadata.product`（Session /
  Subscription）→ `parent.subscription_details.metadata.product`（Invoice・2025-04-30.basil
  以降の現行 API 形）→ `subscription_details.metadata.product`（basil 以前）→
  `lines.data[].metadata.product`（明細フォールバック）。
- **検証**: 署名付き疑似イベントを POST する `marutto-study/scripts/_test-stripe-webhook-routing.ts`
  （`line:TESTGUARD*` 以外は触らない安全ガード付き）。ユニットテストは
  `functions/src/__tests__/stripeProductTag.test.ts`。

## エラーハンドリング戦略

- `tsudumonTrialStart`: idToken 不正 401 / `line:` 以外 403 / それ以外は
  `{ok:false, reason, message}`（activate と同型）。トランザクション競合は Firestore 任せ（再試行）。
- 自動ログイン: OAuth エラー・state 不一致は現行の `showErr` に落ち、自動再試行しない。
- cron: 1ユーザーの push 失敗はログして続行（expireTrialUsers の既存パターン踏襲）。

## テスト戦略

### ユニットテスト（`marutto-study/functions/src/__tests__/`）
- trial 付与ロジックの純粋部分（already_licensed / trial_used / 上書き禁止判定）を
  tsudumonCore 側に切り出してテスト（`evaluateTsudumonAccess` との整合含む）
- `tzm-lic` v2 のパース（旧形式破棄・exp 判定）は生成器側 JS のため実機確認で代替

### 実機確認（デプロイ後）
- 管理用アカウント（付与済み set/3年）でリッチメニュー→無操作で有料単元が開くこと
- テスト uid で trial 開始→解錠→（Firestore で expiresAt を過去に書き換え）→ロック復帰
- 外部ブラウザでボタン式ログインが出ること
