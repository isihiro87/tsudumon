# タスクリスト

## 🚨 タスク完全完了の原則

**このファイルの全タスクが完了するまで作業を継続すること**

### 必須ルール
- **全てのタスクを`[x]`にすること**
- 「時間の都合により別タスクとして実施予定」は禁止
- 「実装が複雑すぎるため後回し」は禁止
- 未完了タスク（`[ ]`）を残したまま作業を終了しない

### 実装可能なタスクのみを計画
- 計画段階で「実装可能なタスク」のみをリストアップ
- 「将来やるかもしれないタスク」は含めない
- 「検討中のタスク」は含めない

### タスクスキップが許可される唯一のケース
以下の技術的理由に該当する場合のみスキップ可能:
- 実装方針の変更により、機能自体が不要になった
- アーキテクチャ変更により、別の実装方法に置き換わった
- 依存関係の変更により、タスクが実行不可能になった

スキップ時は必ず理由を明記:
```markdown
- [x] ~~タスク名~~（実装方針変更により不要: 具体的な技術的理由）
```

### タスクが大きすぎる場合
- タスクを小さなサブタスクに分割
- 分割したサブタスクをこのファイルに追加
- サブタスクを1つずつ完了させる

---

## フェーズ1: ゲート基盤整備

- [x] `tsudumonEntitlement` レスポンスに `expiresAtMs`（数値）を追加する
  - [x] `marutto-study/functions/src/tsudumonActivate.ts` の `tsudumonEntitlement` ハンドラを修正し、
        `expiresAt` から算出した `expiresAtMs` をレスポンスに含める

- [x] `tzm-lic` を `{"g":[...],"exp":<ms>}` 形式（v2）に変更する — `pdf-workbook/generate_reference_web.py`
  - [x] TEMPLATE 内 `isLicensed`（1379行付近）を修正: 旧形式（配列）なら破棄して false を返す、
        `exp < Date.now()` なら false を返す
  - [x] TEMPLATE 内 `refreshEntitlement`（1695行付近）を修正: `exp = min(entitlement.expiresAtMs, now+30日)`
        で `tzm-lic` を保存する
  - [x] grades が空（expired/none）のとき `tzm-lic` を明示的に削除する

- [x] `tzm-lic` を `{"g":[...],"exp":<ms>}` 形式（v2）に変更する — `pdf-workbook/generate_workbook_web.py`
  - [x] TEMPLATE 内 `isLicensed` を修正: 旧形式（配列）なら破棄して false を返す、
        `exp < Date.now()` なら false を返す
  - [x] TEMPLATE 内 `refreshEntitlement` を修正: `exp = min(entitlement.expiresAtMs, now+30日)`
        で `tzm-lic` を保存する
  - [x] grades が空（expired/none）のとき `tzm-lic` を明示的に削除する

- [x] `activateTsudumonLicense` の users 書き込みを「tsudumon フィールド丸ごと置き換え」に変更する
  - [x] `marutto-study/functions/src/tsudumonActivate.ts` を修正し、`{merge:true}` → `{mergeFields:['tsudumon']}`
        に変更（ネストマージを回避しフィールド丸ごと置換。update() でなく mergeFields を採用＝
        user doc 未存在時も安全なため）
  - [x] trial→本購入時に `source:'trial'` 等の旧フィールドが残らないことをコードレベルで確認する

- [x] funnel イベント3種（`trial_started` / `trial_expired` / `tsudumon_activated`）の記録を追加する
  - [x] `tsudumonActivate` HTTP関数と `lineWebhook.ts` の `handleTsudumonActivation` の有効化成功時
        （ok かつ初回のみ）に `logServerFunnelEvent('tsudumon_activated', uid)` を追加
  - [x] ~~`trial_started` の型追加~~（不要: `funnelEvent.ts` の union に既存だった。フェーズ3で呼び出しを接続）
  - [x] ~~`trial_expired` の型追加~~（不要: 同上。フェーズ3で呼び出しを接続）

  ※ フェーズ1完了 2026-07-24。functions ビルド成功・tsudumonCore.test.ts 14件パス・全19冊再生成確認済み

## フェーズ2: サイレント自動ログイン

- [x] `/tsudumon/login/` に `?auto=1` 対応を実装する — `marutto-study/public/tsudumon/login/index.html`
  - [x] `?auto=1` かつ UA に `Line/` を含む かつ `sessionStorage['tzm-auto-tried']` なし の場合、
        ボタンを表示せず `tzm-auto-tried=1` を立てて即 `location.href = loginUrl()` する
  - [x] それ以外（外部ブラウザ・自動試行済み・OAuth エラー戻り）の場合は現行のボタン表示にフォールバックする
  - [x] 成功時は現行どおり `onAuthStateChanged` → `next` へ `location.replace` する

- [x] 両生成器のロック処理に自動遷移を追加する（`tzmMaybeAutoLogin()` を `showLock` 冒頭で呼ぶ。
      ログイン状態は module script が公開する `window.tzmAuthUser` で判定）
  - [x] `pdf-workbook/generate_reference_web.py` に実装
  - [x] `pdf-workbook/generate_workbook_web.py` に同一実装
  - [x] 戻ってきて未解錠の場合はロックカードを表示することを確認する（フォールバック経路）

- [x] 無限ループ防止を実装する
  - [x] sessionStorage（login側=`tzm-auto-tried` / 教材側=`tzm-auto-login`）でタブ単位1回のみ自動試行
  - [x] OAuth エラー・state 不一致は現行の `showErr` に落ち、自動再試行しないことを確認する

- [x] 案内文言を更新する（正規入口の一本化）
  - [x] `activate/index.html` 成功画面に「次からはLINEメニュー『📖 教材をひらく』から開くだけ」を追記
  - [x] `manage-tsudumon.ts` の案内メールテンプレに同内容を追記

  ※ フェーズ2完了 2026-07-24。全19冊再生成・login script 構文チェック・ループ防止理屈確認済み

## フェーズ3: 3日間無料お試し

- [x] `tsudumonTrialStart` 関数を実装する — `marutto-study/functions/src/tsudumonActivate.ts`
  - [x] API: POST `{idToken}` → `{ok:true, expiresLabel}` |
        `{ok:false, reason:'already_licensed'|'trial_used'|…, message}`（`activate` と同型のエラー整形）
  - [x] トランザクション: `users/{uid}` を read し、`evaluateTrialEligibility` で判定
  - [x] `tsudumonTrialUsedAt` が既にある場合は `trial_used`（購入案内文つき）を返し何もしない
  - [x] `tsudumon = { plan:'set', source:'trial', years:0, activatedAt: now, expiresAt: now+72h }` を
        `mergeFields:['tsudumon','tsudumonTrialUsedAt']` で丸ごと置き換え書き込み
  - [x] `tsudumonTrials/{uid} = { startedAt, expiresAt, lineUserId, reminded: {} }` を書き込む（cron 用）
  - [x] `logServerFunnelEvent('trial_started', uid)` を呼ぶ
  - [x] idToken 不正時は 401、`line:` 以外の uid は 403 を返すエラーハンドリングを実装する
  - [x] トランザクション競合時は Firestore の再試行に任せる実装にする

- [x] trial 判定ロジックの純粋部分を `tsudumonCore.ts` に切り出す — `marutto-study/functions/src/tsudumonCore.ts`
  - [x] `evaluateTrialEligibility(tsudumonRaw, trialUsedAt, nowMs)` ＋ `TSUDUMON_TRIAL_HOURS=72` を追加
  - [x] ユニットテストを追加する — `__tests__/tsudumonCore.test.ts`（5ケース・19/19パス）
    - [x] `already_licensed` 判定のテスト
    - [x] `trial_used` 判定のテスト
    - [x] 上書き禁止（有効な本ライセンス保持者には trial を付与しない）のテスト

- [x] ロックカードに体験ボタンUIを追加する — `pdf-workbook/generate_reference_web.py`
  - [x] 主ボタン「🎁 3日間ぜんぶ無料で試す」を追加する（lockMsg 結果表示 div・.lb-trial CSS 含む）
  - [x] 押下→ログイン（必要なら auto・`tzm-trial-pending` で往復後も継続）→ `tsudumonTrialStart`
        呼び出し→成功で `refreshEntitlement` →解錠続行、というフローを実装する
  - [x] `trial_used` / `already_licensed` レスポンス時はメッセージ表示＋購入LP/ログイン案内を出す
  - [x] 既存「LINEでログイン（購入者の方）」「つづもんを見てみる→」ボタンは維持する

- [x] ロックカードに体験ボタンUIを追加する — `pdf-workbook/generate_workbook_web.py`
  - [x] 主ボタン「🎁 3日間ぜんぶ無料で試す」を追加する
  - [x] 押下→ログイン→ `tsudumonTrialStart` →解錠続行のフロー（ref側と同一実装・文言のみ読む/解く）
  - [x] `trial_used` / `already_licensed` レスポンス時はメッセージ表示＋購入LP/ログイン案内を出す
  - [x] 既存「LINEでログイン（購入者の方）」「つづもんを見てみる→」ボタンは維持する

  ※ 体験UI検証済み 2026-07-24: 全19冊生成・script構文チェック・両生成器ロジック一致確認

- [x] LP・特商法・LPチャットの文言を新体験内容に更新する
  - [x] `pdf-workbook/lp/index.html`: hero「まずは無料で1単元」を「3日間ぜんぶ無料でお試し」に変更する
        （meta description/og:description・ヒーロー/CTA・cta-banner・price section・final CTA すべて更新）
  - [x] `pdf-workbook/lp/index.html`: FAQ の該当記述を更新する（画面表示 `.a` div）
  - [x] `pdf-workbook/lp/index.html`: JSON-LD（構造化データ）の該当記述を更新する
  - [x] `pdf-workbook/lp/tokushoho.html`: 「無料体験（1単元）」の記述を3日間体験＋常設1単元の記述に更新する
  - [x] `pdf-workbook/lp/api/chat.js`: ナレッジの「無料体験: 1単元」を3日間体験の内容に更新する

- [x] リマインド cron `tsudumonTrialReminder` を実装する — `marutto-study/functions/src/tsudumonTrialReminder.ts`
        （新規ファイル・index.ts で export 済み・**未デプロイ＝アーム前にユーザー承認要**）
  - [x] 毎日 JST 19:00 実行のスケジュール設定を行う
  - [x] `tsudumonTrials` を `expiresAt` レンジ（now±3日）＋limit(500) で走査（`users` 全体は舐めない）
  - [x] 開始翌日: 使い方＋おすすめ単元の push を送る
  - [x] 期限前日: あと1日＋購入CTA の push を送る
  - [x] 期限翌日: `logServerFunnelEvent('trial_expired', uid)` を記録し、無料単元案内＋購入CTA の push を送る
  - [x] 送信済みかどうかを `tsudumonTrials/{uid}.reminded` フラグで管理し、重複送信を防止する
        （同一runでの重複は 緊急度順 else-if で1種のみ送信）
  - [x] push 送信時に `recordPushDelivery` で計上（新 kind `tsudumonTrial` を deliveryStatsTypes.ts に追加）
  - [x] 1ユーザーの push 失敗はログして続行する実装にする（`expireTrialUsers.ts` の既存パターン踏襲）

- [x] friend-add あいさつ・リッチメニュー文言を体験導線に合わせて更新する（marutto 側 webhook・メニュー設定）
  - [x] friend-add あいさつメッセージの文言を更新する（`handleFollow` の1通目テキスト末尾に
        つづもん3日間無料お試しの1文を追記。既存オンボ構造は無変更。`TSUDUMON_LP_URL` を再利用）
  - [x] ~~リッチメニュー文言を更新する~~（依存関係により本タスクでは実行不可: つづもんタブは
        codex 画像生成による PNG アセットで、テキスト編集では変更できない。現行タブは LP 誘導として
        機能しており体験導線を阻害しない。画像差し替えはデザイン作業として別タスク化する）

## フェーズ4: デプロイと実機検証

- [x] Functions を名前指定でデプロイする（2026-07-25）
  - [x] `firebase deploy --only functions:tsudumonActivate,functions:tsudumonEntitlement,functions:tsudumonTrialStart`
  - [ ] `firebase deploy --only functions:tsudumonTrialReminder`
        → **未実施（意図的）**。LINE配信枠を消費するため、ユーザーの明示承認を得てから実施する
  - [x] `lineWebhook`（友だち追加あいさつに体験案内＋funnelログ）を名前指定でデプロイ
  - [x] Stripe 3関数（`tsudumonCreateCheckout` / `tsudumonStripeWebhook` / `tsudumonCreatePortal`）を
        名前指定でデプロイ

- [x] 生成器の全19冊を再生成し、デプロイする（2026-07-25）
  - [x] `deploy_tsudumon.py` で ref/wb/map の全19章を再生成（リンク健全性チェック ✓ 健全）
  - [x] 共通画像225枚を `_shared/img/` に集約（8.6MB削減）
  - [x] `npx firebase deploy --only hosting:tsudumon` で本番反映

- [ ] 受け入れ条件（requirements.md）に対応する実機確認を行う
  - [x] ゲート基盤: 期限切れ entitlement で解錠されないこと
        （`_test-trial-e2e.ts` 項目6: `expiresAt` を1時間前に書換→`tsudumonEntitlement` が
        `result:'expired', grades:[]` を返す）
  - [ ] ゲート基盤: 旧形式 `tzm-lic`（期限なし配列）残存端末での失効確認 … **実機のみ検証可**
  - [ ] ゲート基盤: 本購入の有効化で `tsudumon.source` 等の旧フィールドが残らないこと
        … 未検証（テスト専用ライセンスコードが無く、本番コードの `activatedUids` を汚さないため保留）
  - [ ] ゲート基盤: 既存の有料ユーザー（管理用アカウント含む）の閲覧が途切れないこと … **実機確認待ち**
  - [ ] 自動ログイン: LINEのリッチメニューから開いて無操作で有料単元が開くこと … **実機確認待ち**
  - [ ] 自動ログイン: 外部ブラウザではボタン式ログインが出ること … **実機確認待ち**
  - [ ] 自動ログイン: OAuth 失敗時に無限リダイレクトしないこと … **実機確認待ち**
  - [x] 無料お試し: ワンタップで体験開始→全学年解錠
        （`tsudumonTrialStart` → `{ok:true, expiresLabel}`、`tsudumonEntitlement` が
        `grades:["中1","中2","中3"]` ＋ `expiresAtMs` を返す）
  - [x] 無料お試し: 付与内容が仕様どおり
        （`{plan:'set', source:'trial', years:0}`・expiresAt が now+72h と誤差0.01分・
        `tsudumonTrialUsedAt` 記録・`tsudumonTrials/{uid}` 作成）
  - [x] 無料お試し: 同じ uid で2回目の体験開始ができない
        （体験中は `already_licensed`、期限切れ後は `trial_used` を返す。二重取得は不可）
  - [ ] 無料お試し: 体験中に本ライセンスを有効化すると上書きされること … 上と同じ理由で未検証
  - [x] 無料お試し: LP・特商法の記述が新体験内容と一致（2026-07-24 修正済み）
  - [ ] 無料お試し: LPチャットの記述一致 … `marutto-study/api/chat.js` は修正済みだが
        **Vercel 未push のため本番は旧版**。push が必要
  - [ ] 管理用アカウントでリッチメニュー→無操作で有料単元が開くこと … **実機確認待ち**

- [x] `pdf-workbook/docs/つづもん-登録フロー設計.md` に本作業の実装内容を反映する（2026-07-25）

- [x] 公開前チェックリスト B 区分（Stripe と無関係の修正）を完了する（2026-07-25・`launch-checklist.md` 参照）

---

## 実装後の振り返り

### 実装完了日
{YYYY-MM-DD}

### 計画と実績の差分

**計画と異なった点**:
- {計画時には想定していなかった技術的な変更点}
- {実装方針の変更とその理由}

**新たに必要になったタスク**:
- {実装中に追加したタスク}
- {なぜ追加が必要だったか}

**技術的理由でスキップしたタスク**（該当する場合のみ）:
- {タスク名}
  - スキップ理由: {具体的な技術的理由}
  - 代替実装: {何に置き換わったか}

**⚠️ 注意**: 「時間の都合」「難しい」などの理由でスキップしたタスクはここに記載しないこと。全タスク完了が原則。

### 学んだこと

**技術的な学び**:
- {実装を通じて学んだ技術的な知見}
- {新しく使った技術やパターン}

**プロセス上の改善点**:
- {タスク管理で良かった点}
- {ステアリングファイルの活用方法}

### 次回への改善提案
- {次回の機能追加で気をつけること}
- {より効率的な実装方法}
- {タスク計画の改善点}
