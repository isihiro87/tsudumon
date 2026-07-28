# タスクリスト — つづもん「子 → 保護者」受け渡し導線

要求: `requirements.md` ／ 設計: `design.md`（2026-07-27 作成）

## 🚨 タスク完全完了の原則

**このファイルの全タスクが完了するまで作業を継続すること**

- **全てのタスクを`[x]`にすること**
- 「時間の都合により別タスクとして実施予定」は禁止
- 未完了タスク（`[ ]`）を残したまま作業を終了しない
- スキップは技術的理由のみ。`- [x] ~~タスク名~~（理由）` の形で明記する

## 作業対象リポジトリ

| 記号 | パス |
|---|---|
| **[M]** | `marutto-study/`（Cloud Functions・LINE・スクリプト） |
| **[P]** | `pdf-workbook/`（Webページ・LP・教材生成器） |

⚠️ Functions のデプロイは**必ず名前指定**（本番の一問一答LINEを巻き込まない）

## 進捗サマリ（2026-07-27）

**コードは全フェーズ完了**（型チェック・lint・テスト 1317件 全通過／教材38ページ再生成・リンク健全）。

残る `[ ]` は**すべて外部作業か本番確認**で、コード側の未完了ではない:

| 区分 | 内容 | なぜ残っているか |
|---|---|---|
| ⏸ ユーザー作業 | Stripe のきょうだい価格 Price 作成 | Stripe ダッシュボードの操作 |
| ⏸ ユーザー作業 | `functions/.env` の3つの env | 秘密情報 |
| ⏸ ユーザー作業 | 保護者用リッチメニュー画像の生成 | Codex 実行 |
| ⏸ 承認待ち | デプロイ（push を伴う） | CLAUDE.md の慣習。配信枠を消費する |
| ⏸ 本番確認 | 実機E2E（決済・連携・きょうだい割引） | デプロイ後でないと実行できない |

---

## フェーズ0: 前提の準備（外部依存）⏸ ユーザー作業

- [ ] Stripe にきょうだい価格の Price を作成（980円/月・税込・`product=tsudumon` タグ）
- [ ] **[M]** `functions/.env` に env を追加
  - [ ] `TSUDUMON_INVITE_SECRET`（ランダム32バイト以上）
  - [ ] `STRIPE_TSUDUMON_PRICE_ID_SIBLING`
- [ ] `tsudumonTrialReminder` の本番デプロイ可否をユーザーに確認（フェーズ2のA・Bが依存）

---

## フェーズ1: 保護者ペイリンク（保護者が自分の端末で決済できるようにする）

### 1-1. トークン基盤

- [x] **[M]** `functions/src/tsudumonInviteCore.ts` を新規作成（純粋関数・副作用なし）
  - [x] `createInviteId()` … `crypto.randomBytes(16)` の base64url
  - [x] `signInviteToken(inviteId, secret)` / `parseInviteToken(t)` / `verifyInviteToken(t, secret)`
  - [x] `evaluateInvite(doc, nowMs)` → `'ok' | 'expired' | 'invalid'`
  - [x] 署名比較を `timingSafeEqual` に（計画外の追加）
  - [x] `secret` 未設定時は必ず失敗（env 未設定で素通りさせない）
- [x] **[M]** `functions/src/__tests__/tsudumonInviteCore.test.ts`（35ケース・全通過）
  - [x] 署名の一致・不一致・改ざん・書式不正
  - [x] 期限切れ判定（境界値）

### 1-2. Checkout パラメータの共通化（既存と二重実装しない）

- [x] **[M]** `tsudumonStripe.ts` から純粋関数 `buildTsudumonCheckoutParams()` を切り出す
  - [x] 引数: `{uid, tsudumonRaw, nowMs, priceId, paidBy, successUrl, cancelUrl}`
  - [x] 既存 `tsudumonCreateCheckout` をこの関数経由に置き換える（**挙動は不変**）
  - [x] `trial_period_days` の丸め（MAX_TRIAL_DAYS）は `resolveTrialPeriodDays` に集約
- [x] **[M]** `__tests__/tsudumonCheckoutParams.test.ts`（13ケース・全通過）
  - [x] 通常価格 / きょうだい価格 / 体験中の残日数 / paidBy の付与

### 1-3. カード発行・閲覧・決済の3関数

- [x] **[M]** `functions/src/tsudumonParentCore.ts` を新規作成（計画外の分割）
  - [x] `ChildSummary` の組み立てを**純粋関数**に隔離し、出してよいデータの範囲を型で固定
  - [x] `appendStudyDay` / `summarizeRecentDays` / `buildChildPlan` / `lastStudiedLabel`
  - [x] `__tests__/tsudumonParentCore.test.ts`（25ケース・全通過）
  - [x] **まちがい・会話関連の識別子を実コードに含まないことをテストで固定**
- [x] **[M]** `functions/src/tsudumonParent.ts` を新規作成
- [x] `tsudumonInviteCreate`（POST {idToken}）
  - [x] 既存カードがあれば削除して再発行（`users/{child}.tsudumonInviteId`）
  - [x] `tsudumonInvites/{inviteId}` を作成（childUid/childName/childGrade/expiresAt=14日）
  - [x] 呼び名未設定なら `needsName: true` を返す
  - [x] `{ok, token, url, qrUrl, handoffUrl, childName, expiresLabel}` を返す
- [x] `tsudumonInviteView`（POST {t}）
  - [x] トークン検証 → invite 1 read → 子 1 read（**クエリ禁止**）
  - [x] `ChildSummary` を組み立てる（§6-1。**まちがい件数は含めない**）
  - [x] 初回のみ `viewedAt` を書き、子へ1通push（`notifiedAt` で二重送信を防ぐ）
- [x] `tsudumonParentCheckout`（POST {t, idToken?}）
  - [x] トークン検証 → 子uid 取得
  - [x] `idToken` があり連携済みなら、他に連携中の子がいるか判定してきょうだい価格を使う
  - [x] `client_reference_id` = 子uid、`metadata[paidBy]='parent'`
  - [x] `success_url` = `/parents/thanks/?t=<t>`
  - [x] 既に有効なサブスクがあれば `already_subscribed`
  - [x] きょうだい価格 Price が未設定なら通常価格へフォールバック（決済を止めない）
- [x] `tsudumonInviteQr`（GET `?t=`）… QRを **SVG** で返す（`qrcode` を動的 import・0 read）
- [x] **[M]** `functions/src/index.ts` に4関数を export

### 1-4. webhook 側の受け

- [x] **[M]** `tsudumonStripeWebhook` の `checkout.session.completed` で `paidBy` を保存
  - [x] `users/{child}.tsudumon.paidBy = 'parent' | 'self'`（`mergeFields` 維持）
  - [x] funnel `tsudumon_activated` の context に `paidBy` を付与
  - [x] **`invoice.paid` で `paidBy` を引き継ぐ**（丸ごと置き換えなので、書かないと
        継続課金のたびに消える。計画時に見落としていた）
- [x] **[M]** `deliveryStatsTypes.ts` に push 種別 `tsudumonParent` を追加
- [x] **[M]** `funnelEvent.ts` に保護者導線の4イベントを追加（フェーズ5から前倒し）

### 1-5. 保護者ページ

- [x] **[P]** `web/parents/index.html` を新規作成（`/parents/` を**正本**にした）
  - [x] `?t=` 有り: 文脈見出し → 実績サマリ → 結論3行＋ボタン → 見える/見えない表
  - [x] `?t=` 無し: 一般ページとして成立させる
  - [x] 既存 `lp/parents.html` の詳細（料金・解約・通知・AI・対象・問い合わせ）を下部に統合
  - [x] きょうだい料金・保護者連携の説明に差し替え（§6を書き換え）
  - [x] 「まちがいを見せない理由」を明記（子の安心＝カードを出す条件）
  - [x] `expired` / `invalid` トークンの表示（責めない文面＋一般ページへの導線）
  - [ ] **スマホ縦画面で結論とボタンがファーストビューに入る**ことを実機確認（フェーズ6）
- [x] **[P]** `lp/parents.html` を `/parents/` への転送スタブに変更（内容の二重管理を避ける）
  - [x] `lp/index.html`(5) `privacy` `terms` `tokushoho` のリンクを `/parents/` へ更新
- [x] **[P]** `web/parents/thanks/index.html` を新規作成
  - [x] 決済完了の確認 ＋ **②公式LINE連携への導線を主役**に
  - [x] 既存 `/login/` に往復させて連携まで自動で済ませる（コールバックURL追加が不要）
  - [x] 「きょうだいがいる方は、つなぐと2人目から980円」を明示
- [x] **[P]** `deploy_tsudumon.py` の静的ページ検査に保護者導線4ページを追加
      （`firebase.json` は `web/` 全体をコピーする方式なので変更不要）

### 1-6. フェーズ1の検証 ⏸ 本番確認（デプロイ後）

- [ ] 保護者端末（LINE未ログイン・別ブラウザ）から決済 → **子のuid**に `tsudumon.plan='set'` が付く
- [ ] 決済後、子のLINEに既存の御礼push＋オンボーディングが届く
- [ ] 体験中の決済で `trial_period_days` が入り、体験終了後から課金が始まる
- [ ] 期限切れ・改ざんトークンで決済に進めない
- [ ] URL から子の LINE uid が復元できないことを確認

---

## フェーズ2: 子側のカード（案内しやすくする）

### 2-1. 学習日の記録（保護者サマリに必要な唯一の新規データ）

- [x] **[M]** `tsudumonProgressCore.ts` に `days: StudyDayLog[]` を追加
      （`{d,ms,a}` 形式に変更。日数だけでなく「今週の学習時間・問題数」も要るため）
  - [x] `mergeProgress` で当日分を加算し、古いものから捨てる（最大14件）
  - [x] `recordTsudumonProgress` の**既存の書き込みに相乗り**（追加readゼロ）
  - [x] `__tests__/tsudumonProgressCore.test.ts` に日付境界・上限・冪等のテストを追加
- [x] **[M]** `buildChildSummary()` を `tsudumonParentCore.ts` に実装（フェーズ1で前倒し）
  - [x] 直近7日の学習日数 / 今週・累計の学習時間 / 進んだ単元数 / 問題数 / 正答率 / 最終学習日
  - [x] `unitsNeedingReview` / `topWrongQids` / `wrongLeft` を**呼ばない**ことをテストで固定

### 2-2. 呼び名の確認

- [x] **[M]** カード初回発行時に呼び名を一度だけ聞くフロー（`tsudumonParentCardHandler.ts`）
  - [x] Quick Reply に学年既定（「中2のこども」）を出す
  - [x] 自由入力も受ける（`tsudumonParentNameAwaiting`）。URL・長文・記号だけは弾く
  - [x] `users/{child}.tsudumonParentName` に保存。以後は聞かない

### 2-3. カードUI

- [x] **[M]** `tsudumon/webhook.ts` に postback `tzm_parent_card` / `tzm_pname` を追加（reply＝配信枠ゼロ）
  - [x] Flex: 「見える／見えない」を**CTAより前**に置く（テストで順序を固定）
  - [x] ボタン「見せる画面をひらく」＋転送用に保護者ページURLを本文へ
  - [x] 子向けカードに金額を書かない（お金の話は保護者ページで）ことをテストで固定
- [x] **[M]** `__tests__/tsudumonParentCard.test.ts`（36ケース・全通過）
  - [x] 誤検知しないことを正検知と同じ重さで固定（歴史の質問で発火しない）
- [x] **[P]** `web/handoff/index.html`（子が保護者に見せる画面）を新規作成
  - [x] QR（`tsudumonInviteQr` の SVG）を大きく表示
  - [x] 台本3種（結果から言う型 / お金から言う型 / 見せるだけ型）＋コピー
  - [x] 「見えるもの／見えないもの」を**ページ最上部**に（見せる前に子が読む）
  - [x] 「断られてもあなたのせいではない」を明記

### 2-4. 出す4か所

- [x] **[M]** `tsudumonTrialReminder.ts` の**既存2通**にカード導線を追加
      （⚠️ 計画では体験2日目に新しい push を足す想定だったが、day1 を配信枠のために
      廃止した既存判断と衝突する。**push を増やさず** lastday / expired の
      quickReply に載せる方式へ変更した）
  - [x] 期限前日: 本文を「おうちの人に見てもらうのが早い」に書き換え
  - [x] 期限切れ後: カード導線を追記
  - [x] 両方に `parentCardQuickReply()`（postback→reply なので配信枠ゼロ）
- [x] **[P]** 両生成器のロックカードに「おうちの人にお願いする」ボタンを追加
  - [x] `generate_reference_web.py` の TEMPLATE
  - [x] `generate_workbook_web.py` の TEMPLATE
  - [x] 「月額プランに登録」と**並置**（子が自分で払う道を塞がない）
  - [x] ログイン往復（`tzm-parent-pending`）→ カード発行 → 見せる画面へ遷移
  - [x] ch04 を生成して両ページの script 5/5 が構文OKであることを確認
- [x] **[M]** 「親に聞かないと」系の発言検知 → Quick Reply でカードを1回だけ出す
  - [x] 正規表現のみ（AIツール呼び出しにしない）。保護者語＋お金/許可語の**両方**を要求
  - [x] `tsudumonParentHintedAt` で生涯1回に制限（催促にしない）

### 2-5. フェーズ2の検証 ⏸ 本番確認（デプロイ後）

- [ ] LINEトークから1タップで URL・QR・台本に到達できる
- [ ] QR を別端末で読み取り、子のスマホを渡さずに保護者ページが開ける
- [ ] 4か所すべてからカードに到達できる

---

## フェーズ3: 親子連携（きょうだい対応）

### 3-1. 連携の成立

- [x] **[M]** `tsudumonParentLink`（POST {idToken, t}）を `tsudumonParent.ts` に実装
  - [x] `parentUid === childUid` を弾く
  - [x] 上限チェック（子側の保護者2人 / 親側の子4人）
  - [x] トランザクションで親子両方を更新（`mergeFields` で対象フィールドのみ）
  - [x] 親: `tsudumonRole='parent'` / `tsudumonChildren` に append（**冪等**）
  - [x] 子: `tsudumonParents` に append
  - [x] 子へ「つながりました／見えるのは学習の記録だけです」をpush
  - [x] 再連携時は表示名だけ更新して積み増さない・pushもしない
- [x] **[M]** 冪等性テスト（同じカードを2回・きょうだい2枚目・上限超過）
      … トランザクション内では書けないので、**判定を純粋関数 `resolveParentLink` に切り出して**
      テスト可能にした（計画外のリファクタ）。11ケース追加・全通過。
      解除側 `resolveParentUnlink` も同様

### 3-2. きょうだい割引

- [x] **[M]** `tsudumonParentCheckout` の価格判定を実装（連携済み＆他に子がいれば割引Price）
  - [x] 割引Price 未設定なら通常価格へフォールバック（決済を止めない）
- [x] **[P]** `/parents/`（6項）・`/parents/thanks/` に割引と適用条件を明記
- [ ] 実際に2人分の Checkout を通し、2人目が 980円 で作られることを確認（フェーズ6）

### 3-3. 保護者モードのBot挙動

- [x] **[M]** `tsudumonDailyUnit.ts`：`ensureTsudumonDaily` と配信対象から `tsudumonRole==='parent'` を除外
  - [x] 送信側でも落とす（子→保護者に変わった経路がありうるため。追加read無し）
- [x] **[M]** 保護者用リッチメニューのリンク処理（`linkParentRichMenu`）
  - [x] `tsudumonParentLink` 成功時に自動リンク
  - [x] env `LINE_TSUDUMON_RICHMENU_PARENT` 未設定なら何もしない（画像未用意でも連携は通す）
  - [x] `scripts/setup-tsudumon-richmenu.ts` に `--variant parent` を追加（6ボタン・§7-2）
        既定メニューにはせず、ID を `.env` に控える運用（`--dry-run` で確認済み）
  - [x] 画像の Codex ブリーフ（`CODEX_BRIEF_TSUDUMON_RICHMENU.md` に追記）
  - [ ] 画像の生成そのもの（Codex 実行・ユーザー作業）
  - [x] 保護者メニュー「お子さんの追加」の受け口（`handleSiblingAddGuide`）
- [x] **[M]** `aiChatPrompt.ts` に保護者モードを追加（`TSUDUMON_PARENT_KNOWLEDGE`）
  - [x] 敬語・料金/解約/使い方/安全性・記録は「ダッシュボードで」と案内
  - [x] トーク内容・記述解答・間違えた問題は「方針として断る」文面
  - [x] **保護者分岐で子の学習文脈（progress/exam）を差し込まない**ことをテストで固定
  - [x] `__tests__/tsudumonParentPrivacy.test.ts`（25ケース・全通過）

### 3-4. 連携の解除

- [x] **[M]** 子からの連携解除を実装（`handleParentUnlink`）
  - [x] 入口は**テキスト**「保護者の連携を解除」（postbackより思い出しやすい）
  - [x] 双方から削除（片方だけ残ると保護者画面に幽霊が残る）
  - [x] 「お支払いは止まりません」を明記
  - [x] 保護者へも解除を通知（黙って消えると不信になる）

### 3-5. フェーズ3の検証 ⏸ 本番確認（デプロイ後）

- [ ] 同一保護者が子A・子Bのカードを順に開くと2人とも連携される
- [ ] 連携した保護者に「今日の1単元」が届かない
- [ ] 保護者がつづ先生に話しかけると保護者向けの応対になる
- [ ] 一問一答Bot（`@824cebif`）の挙動が一切変わらない

---

## フェーズ4: 保護者ダッシュボード

- [x] **[M]** `tsudumonParentDashboard`（POST {idToken}）を実装
  - [x] `tsudumonRole==='parent'` でなければ空を返す（連携していなければ何も見えない）
  - [x] `tsudumonChildren` の uid だけを `doc().get()`（**クエリ・列挙を一切しない**）
  - [x] 会話・解答本文のモジュールを **import しない**（import 許可リストをテストで固定）
  - [x] 子ごとに Billing Portal 用の `customerId` の有無（`plan.canManage`）を返す
- [x] **[M]** 保護者用 Billing Portal（`tsudumonParentPortal`）
  - [x] 連携中の子の `customerId` に限定（連携していない子は 403）
- [x] **[P]** `web/parents/dashboard/index.html` を新規作成
  - [x] 保護者のLINEログイン（既存 `/login/` を流用）
  - [x] 子カードを縦に並べる（呼び名・学年・契約状態・学習サマリ6項目）
  - [x] 同学年きょうだい用に表示名を編集できる（`tsudumonChildren[].name` のみ更新）
  - [x] 子ごとの「お支払い・解約」ボタン
  - [x] 「見えるもの／見えないもの」の表を常設＋出さない理由も明記
- [x] **[M]** 表示名編集用の関数 `tsudumonParentRenameChild`（POST {idToken, childUid, name}）
- [x] フェーズ4の検証（静的）
  - [x] 連携していない子のデータは uid を知っていても取得できない（`readLinkedChildren` 経由のみ）
  - [x] read が「保護者1件＋子の人数」で収まる（クエリ不使用をコードで確認）
  - [x] レスポンスにトーク内容・解答本文・まちがい件数が含まれない（テストで固定）

---

## フェーズ5: 計測とドキュメント整合

- [x] **[M]** funnel イベントを追加（`funnelEvent.ts` の型定義＋記録）
  - [x] `parent_link_created` / `parent_page_viewed` / `parent_checkout_started` /
        `parent_linked` / `parent_unlinked`（5種）
  - [x] `tsudumon_activated` に `paidBy` を付与
- [x] **[P]** 保護者ページ（`/parents/`）の記述を更新
  - [x] きょうだい項を「お一人ずつのアカウント／2人目以降は月980円（要連携）」に書き換え
  - [x] 保護者ダッシュボード・連携の説明を追加（5項）
  - [x] 「見えるもの／見えないもの」の表を追加
- [x] **[P]** `lp/tokushoho.html` の価格表記にきょうだい価格・適用条件を追記
- [x] **[P]** `lp/terms.html` に第6条「保護者の方とお子さまのアカウント連携」を新設（以降を繰り下げ）
      ＋料金・解約・アカウント管理の各条をきょうだい前提に更新
- [x] **[P]** `lp/privacy.html` に第10条「保護者の方への開示範囲」を新設
- [x] **[M]** `docs/つづもん-登録フロー設計.md` に §10「保護者導線」を追記
- [x] **[P]** `docs/つづもん-機能ロードマップ.md` のフェーズI/J の状態を更新

---

## フェーズ6: 品質チェック

- [x] **[M]** `npx vitest run functions/src/__tests__`（**66ファイル 1306件 全通過**・回帰なし）
- [x] **[M]** `npx tsc --noEmit`（型エラーなし）
- [x] **[M]** `npx eslint`（新規・変更ファイルすべてクリーン）
- [x] **[P]** `python deploy_tsudumon.py`（**全19章×2生成器 = 38ページ**再生成・リンク健全性「✓ 健全」）
  - [x] 38ページすべてに `lockParent` / `tzmStartParentCard` / `tsudumonInviteCreate` があることを検査
  - [x] 新規4ページ（parents / thanks / dashboard / handoff）の script 構文チェック
  - [x] ページが呼ぶ Functions 名が `index.ts` の export と一致することを突合
- [ ] 実機確認 ⏸ 本番確認（デプロイ後）
  - [ ] 子のLINE（体験中）→ カード発行 → QR
  - [ ] 別端末（保護者）→ ページ閲覧 → 決済 → 子に反映
  - [ ] 保護者が公式LINE追加 → 連携 → ダッシュボード
  - [ ] きょうだい2人目の連携と割引

---

## フェーズ7: デプロイ（ユーザー承認が必要）⏸

- [ ] **push を伴う変更のアーム可否をユーザーに確認**（連携通知・閲覧通知・trialReminder）
- [ ] **[M]** Functions を**名前指定**でデプロイ
  ```
  firebase deploy --only functions:tsudumonInviteCreate,functions:tsudumonInviteView,\
  functions:tsudumonInviteQr,functions:tsudumonParentCheckout,functions:tsudumonParentLink,\
  functions:tsudumonParentDashboard,functions:tsudumonParentRenameChild,\
  functions:tsudumonStripeWebhook,functions:tsudumonCreateCheckout,functions:tsudumonWebhook,\
  functions:recordTsudumonProgress,functions:tsudumonDailyUnit
  ```
- [ ] **[P]** Web・LP をデプロイ（`deploy_tsudumon.py` → `tsudumon.jp`）
- [ ] **[M]** 保護者用リッチメニューを本番作成・リンク確認
- [ ] Stripe 本番の webhook で `paidBy` が入ることを1件確認

---

## 実装後の振り返り

### 実装完了日
2026-07-27（コード完了・**未デプロイ**）

### 計画と実績の差分

**計画と異なった点**

1. **体験2日目の push を足さなかった**（設計 §9 の A）。
   `tsudumonTrialReminder` は配信枠のために day1 を廃止した経緯がある。ここに新しい push を
   足すと、その判断を打ち消して1日2通の枠を食う。**既存2通（期限前日・期限切れ後）の
   quickReply にカード導線を載せる**方式へ変更した。postback → reply なので追加の配信枠はゼロ。

2. **`tsudumonProgress.days` の形を変えた**。計画は `string[]`（日付だけ）だったが、
   保護者に「この1週間の学習時間・問題数」を出すには日別の量が要る。`{d, ms, a}` にした。
   保持は14件で、既存の書き込みに相乗りするので**追加 read はゼロ**のまま。

3. **`tsudumonParentCore.ts` を分けた**（計画では `tsudumonParent.ts` に置く予定）。
   「保護者に出してよいデータ」を純粋関数の入出力で固定したかったため。結果として
   まちがい関連・会話関連の識別子を持たないことをテストで機械的に検査できるようになった。

4. **`/parents/` を正本にし、`lp/parents.html` を転送スタブにした**。
   設計は「両方を成立させる」だったが、同じ内容を2ファイルで持つと必ずドリフトする。
   リンク元5箇所（LP・規約・特商法・プライバシー）も `/parents/` に張り替えた。

5. **連携の判定を純粋関数 `resolveParentLink` に切り出した**（計画外）。
   冪等性と上限がこの機能でいちばん壊れやすいのに、トランザクションの中ではテストできない。
   切り出して11ケースを固定した。

**新たに必要になったタスク**

- **`invoice.paid` での `paidBy` 引き継ぎ**。`tsudumon` フィールドを丸ごと置き換える実装なので、
  書かないと**継続課金のたびに `paidBy` が消える**。計画時に見落としていた。
- **`tsudumonParentPortal`**。既存 `tsudumonCreatePortal` は「本人の customerId」しか開けないので、
  保護者が払った契約を保護者自身が管理できなかった。
- **保護者メニュー「お子さんの追加」の受け口**（`handleSiblingAddGuide`）。
  リッチメニューにボタンを置いた以上、押しても無反応では困る。
- **`qrcode` の依存追加**。外部CDNを使わない方針なので Functions 側で SVG を生成する。
  discovery timeout を避けるためハンドラ内で**動的 import** にした。
- **`deliveryStatsTypes.ts` に `tsudumonParent`** を追加（push 種別の計上漏れを防ぐ）。

**技術的理由でスキップしたタスク**

なし。

### 学んだこと

**技術的な学び**

- **既存の Checkout 生成を純粋関数に切り出したのが効いた**。保護者経路は「uid の取り方」と
  「price・戻り先・paidBy」しか違わないので、パラメータ生成を共有すれば体験期間の丸め
  （`MAX_TRIAL_DAYS`）のような繊細なロジックが二重化しない。
- **プライバシーは文言ではなく import 一覧で守れる**。「返さない」より「読む手段を持たない」
  ほうが、後から機能を足す人にも壊しにくい。許可リスト方式のテストにしたので、依存が増えた
  瞬間に落ちる。
- **`users/{uid}` が両Botで共有**という制約が効いた。追加フィールドは全て `tsudumon*` 接頭辞に
  そろえ、既存フィールド（`blocked` / `onboardingState`）には触れていない。
- 教材ページは生成器のテンプレート内に JS があるため、**生成物を `node --check` で構文検査**
  すると壊れを早く見つけられる（両生成器で 5/5 スクリプトを確認した）。

**プロセス上の改善点**

- 要求 → 設計 → 実装の途中で**スコープが2回広がった**（親子連携・きょうだい・ダッシュボード）。
  requirements.md を書き足してから design.md に落としたので、実装の手戻りは無かった。
- 判断3件（きょうだい料金・まちがい件数・呼び名）を**実装前にまとめて確認**したのが効いた。
  とくに「きょうだい割引を連携済み条件にする」は、決済とLINE連携を切り離した設計の帰結として
  後から見つかった論点で、先に決めていなければ作り直しになっていた。

### 次回への改善提案

- **配信枠に触る変更は、既存の push 設計の経緯を先に読む**。今回 day1 廃止の理由を読んでいた
  ので新規 push を足さずに済んだが、設計段階では「day2 に送る」と書いてしまっていた。
- **「その判定はトランザクションの中か」を設計時に確認する**。中に入るならテストが書けないので、
  最初から純粋関数に分ける前提で設計する。
- 保護者向け機能をさらに足すとき（週次レポート等）は、`tsudumonParentPrivacy.test.ts` の
  許可リストに**追加してよい依存か**を先に判断する。ここを緩めるのは方針変更なので、
  コードレビューではなくユーザー判断にする。
