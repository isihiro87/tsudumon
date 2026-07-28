# つづもん 公式LINE分離 デプロイ手順

作成 2026-07-25。`.steering/20260725-tsudumon-dedicated-line-bot/` の実装完了を受けて新規作成。

> 関連: `つづもん-公式LINE分離移行手順.md`（アカウント作成・Webhook設定・コード差し替えの記録。正本）、
> `marutto-study/docs/operations/line-webhook-deploy.md`（既存 `lineWebhook` の一般的なデプロイ手順）、
> `marutto-study/CLAUDE.md`「⚠️ 公式LINE Bot は2つある」節。
>
> **本書自体はデプロイを実行しない。** デプロイはユーザー承認後に、本書の手順に従って人間（または
> 承認を得たエージェント）が実施する。

---

## 0. 前提: デプロイ前に必ず確認すること

marutto-study リポジトリの作業ツリーには、**このタスク（つづもん専用Bot分離）と無関係な未コミット変更が
大量に混在している**（2026-07-25 時点で `git status` 約49ファイル）。`firebase deploy` はコミット単位ではなく
`functions/lib`（ビルド成果物）をそのままデプロイするため、対象関数を絞っても中身には現在の作業ツリーの
全変更が含まれる。**この節の内容を必ず確認してから次に進むこと。**

確認できた無関係な変更（例）:

- `functions/src/aiCostCore.ts` / `aiTier.ts` / `llmModelResolver.ts` / `llmProvider.ts` / `llmGemini.ts` /
  `llmOpenai.ts` / `llmPrices.ts`（新規）・`functions/src/tsudumonLpChat.ts` / `tsudumonLpChatCore.ts`（新規）
  — 別ステアリング（AIコスト管理基盤・つづもんLPチャット）の実装中と見られる
- `functions/src/tsudumonStripe.ts`・`functions/src/index.ts` の `tsudumonCreateCheckout` /
  `tsudumonStripeWebhook` / `tsudumonCreatePortal` / `tsudumonTrialStart` export — Stripe決済まわりの
  並行作業
- `scripts/generate-geometry-figures.ts` / `src/data/generated/topic-registry.generated.ts` —
  数学の図形機能。本タスクと完全に無関係
- pdf-workbook 側は別ステアリング `.steering/20260725-tsudumon-domain-independence/` の変更
  （`generate_reference_web.py` / `generate_workbook_web.py` / `lp/index.html` / `web/account/index.html`）
  が未コミットのまま混在

> 本書の執筆時点で `public/tsudumon/ref/*/img/` 配下のPNG削除は確認できなかった（該当パスは現状クリーン）。
> ただし作業ツリーは流動的なので、**デプロイ直前に必ず `git status` を再確認し、上記以外にも意図しない
> 変更が無いか、これらの並行作業が「今デプロイして問題ないか（各自コミット済み・動作確認済みか）」を
> 確認してから進めること。** 迷ったら並行作業の担当エージェント／ユーザーに確認する。

---

## 1. デプロイ対象（Cloud Functions）

design.md・tasklist.md・実装コード・`git diff --stat` を突き合わせて確定した対象。

### 1-1. 必須（この機能のために変更・新設された関数）

| 関数名 | 種別 | 変更内容 |
|---|---|---|
| `tsudumonWebhook` | HTTPS（新設） | つづもん専用webhook本体 |
| `lineWebhook` | HTTPS | つづもん系ハンドラのclient引数化・`replyTextWith`新設・オンボ文言のLP誘導文削除 |
| `onAnswerCreated` | Firestore trigger | `source==='workbook'` のBot振り分け・累計10問マイルストーン案内 |
| `workbookLaunch` | HTTPS | `pushWorkbookStart` へつづもんクライアントを渡すよう変更（QR起動→つづもんのトークへ） |
| `referenceLaunch` | HTTPS | `pushReferenceStart` へつづもんクライアントを渡すよう変更 |

### 1-2. 必須（共有関数のシグネチャ変更に伴う・CLAUDE.mdの既知の注意点）

`selectAndSendQuestion` に `client` 引数が追加された。CLAUDE.md「Firebase Functions デプロイ時の重要メモ」の
とおり、**関数単位デプロイでは呼び出し元ファイルが変わっても再デプロイしないと古いコードのまま動く**ため、
この関数を呼ぶ以下も対象に含める。

| 関数名 | 種別 | 理由 |
|---|---|---|
| `dailyQuiz06` / `dailyQuiz07` / `dailyQuiz16` / `dailyQuiz18` / `dailyQuiz20` | cron | `dailyQuiz.ts` が `selectAndSendQuestion(client, ...)` 呼び出しに変更 |
| `onTestScopeFirstSet` | Firestore trigger | 同上 |

> `_manualSend.ts` も同じ変更を受けているが、これは Cloud Function ではなく手動実行スクリプト
> （`npx tsx functions/src/_manualSend.ts`）なのでデプロイ対象外。ビルドが通ればそれで良い。

### 1-3. 任意（コメント/docstringのみの変更・実行時挙動は不変）

`gradeWritten` / `referenceChat` / `tsudumonActivate` / `tsudumonEntitlement` は `tsudumon.jp` ドメイン統一で
docstring 内のURL表記だけが変わっており、実処理の分岐・送信URLは変わっていない。**今回のデプロイに含めなくても
機能上の問題はない**が、他の対象と合わせて `--only functions` に混ぜてしまっても実害はない。判断に迷ったら含めてよい。

### 1-4. デプロイしないほうがよい・要確認のもの

| 関数名 | 注意点 |
|---|---|
| `tsudumonTrialReminder` | **cron。デプロイすると即座に arm される**（JST 19:00 に自動実行開始）。次節「デプロイ順序」を参照 |
| `tsudumonLpChat` / `tsudumonCreateCheckout` / `tsudumonStripeWebhook` / `tsudumonCreatePortal` / `tsudumonTrialStart` | このステアリングの対象外（別の並行作業）。0節の確認が済むまでデプロイしない |

---

## 2. デプロイコマンド

CLAUDE.md の既知の問題（全体デプロイは Instagram シークレット未設定で失敗する）を踏まえ、**対象を絞って**
`FUNCTIONS_DISCOVERY_TIMEOUT=600` を付けて実行する。

### 2-1. ビルド確認（デプロイ前に必ず実行）

```bash
cd marutto-study/functions
npm run build
cd ..
npm test
cd functions
npm test
```

### 2-2. 本体デプロイ（`tsudumonTrialReminder` を除く）

まずは cron を含まない対象から進め、実機確認が済んでから `tsudumonTrialReminder` を足す（§3参照）。

```bash
cd marutto-study
FUNCTIONS_DISCOVERY_TIMEOUT=600 firebase deploy --only \
functions:tsudumonWebhook,\
functions:lineWebhook,\
functions:onAnswerCreated,\
functions:workbookLaunch,\
functions:referenceLaunch,\
functions:dailyQuiz06,\
functions:dailyQuiz07,\
functions:dailyQuiz16,\
functions:dailyQuiz18,\
functions:dailyQuiz20,\
functions:onTestScopeFirstSet
```

初回デプロイなので `tsudumonWebhook` は新規関数として作成される。完了後の出力に表示される Function URL
（`https://asia-northeast1-chatstudy-63477.cloudfunctions.net/tsudumonWebhook`）を控える。

### 2-3. `tsudumonTrialReminder` の個別デプロイ（arm される。実施タイミングは§3）

```bash
cd marutto-study
FUNCTIONS_DISCOVERY_TIMEOUT=600 firebase deploy --only functions:tsudumonTrialReminder
```

### 2-4. フロントエンド（LIFF launchページ）

`LiffWorkbookLaunchPage.tsx` / `LiffReferenceLaunchPage.tsx` は Firebase Hosting ではなく **Vercel**
（`git push` で自動デプロイ。marutto-study の www/line 系サイトの配信構成。詳細はメモリ
`chatstudy配信構成`）。firebase deploy には含まれない。

- `VITE_TSUDUMON_FRIEND_URL` / `VITE_TSUDUMON_OA_TALK_URL` はコードにフォールバック値
  （`https://lin.ee/XGIhuYi` / `https://line.me/R/oaMessage/%40215uijik/?`）が直書きされているため、
  **Vercel 側の環境変数設定は必須ではない**（未設定でも正しい値で動く）。設定する場合は Vercel の
  Project Settings > Environment Variables に追加してから再デプロイする。

---

## 3. デプロイ順序の制約（重要）

1. **§2-2（`tsudumonTrialReminder` を除く一式）を先にデプロイし、実機確認（§4）の
   「友だち追加→あいさつ」「QR→出題→回答」までを済ませる。**
2. `tsudumonTrialReminder` は **JST 19:00 の cron**。デプロイした瞬間に Cloud Scheduler ジョブが
   作成され、次の JST 19:00 から実際に対象ユーザーへ push を送り始める（＝arm される）。
   デプロイ前に必ず次を確認する:
   - [ ] `functions/src/tsudumonTrialReminder.ts` が `getTsudumonLineClient()`（つづもんBot）を
     使う実装に変更済みであること（旧 `getLineClient()` のままデプロイすると、
     一問一答Bot＝3,000フォロワーへ意図しないトライアルリマインドが飛ぶ）
   - [ ] 配信除外判定が `tsudumonBlockedAt` を見ていること（`blocked` のままだと一問一答をブロックした
     人にまで送ってしまう可能性がある）
   - [ ] 対象ユーザー数（`tsudumonLicenses` の trial 中ユーザー数）を事前に把握し、想定外の大量送信でないこと
   - [ ] ユーザー（人間）の承認を得てからデプロイする
3. §1-4 に挙げた無関係な関数（`tsudumonLpChat` 等）は、このステアリングのデプロイには含めない。

---

## 4. ユーザー（人間）が行う作業

エージェント/CLIでは完結しない、LINE Developers Console 上の手動操作。

### 4-1. Webhook URL の登録（つづもんの Messaging API チャネル側）

1. https://developers.line.biz/console/ → つづもんのプロバイダー → つづもんの **Messaging API チャネル**
   （一問一答チャネルと混同しないこと。Basic ID `@215uijik` / channelId `2010838149` のほう）
2. 「Messaging API」タブ → Webhook settings → Webhook URL に **デプロイ後に確定する** 下記の形式のURLを貼り付け:
   ```
   https://asia-northeast1-chatstudy-63477.cloudfunctions.net/tsudumonWebhook
   ```
   （§2-2 のデプロイ完了時にターミナル出力される実際のURLをコピーするのが確実）
3. 「Use webhook」トグルを **ON**
4. 「Verify」ボタン → **Success** を確認（Failed の場合は `line-webhook-deploy.md` §10 のトラブルシュートを
   つづもんチャネル向けに読み替えて確認）

### 4-2. 応答設定の確認

同じ「Messaging API」タブ内で:

| 項目 | 設定値 |
|---|---|
| 応答モード | **Bot**（LINE Official Account Manager の「応答設定」） |
| 応答メッセージ（Auto-reply messages） | **オフ（Disabled）** |
| あいさつメッセージ（Greeting messages） | **オフ（Disabled）** |
| Webhook | **オン（Enabled）** |

これを怠ると、コード側の `handleTsudumonFollow` のあいさつ文と LINE 既定のあいさつ・応答メッセージが
二重に届く（既存 `lineWebhook` と同じ注意点）。

### 4-3. `tsudumonTrialReminder` デプロイの承認

§3の確認事項を満たしたことを確認したうえで、デプロイの実施可否を判断する。

---

## 5. 実機確認チェックリスト

- [ ] つづもんBot（`@215uijik` / QR）を友だち追加 → あいさつメッセージが届く
- [ ] 参考書・問題集のQRを読む → **つづもんのトーク**に問題（ワーク開始カード）が届く →
      回答する → 解説が返る（旧Bot＝チャットでスタディのトークには届かないことも確認）
- [ ] つづもんBotに自由文（例:「これって無料ですか？」）を送る → AIが
      「このLINEは無料」と誤答しないこと（月額1,280円のサブスクであることを正しく案内する）
- [ ] つづもんBotをブロックする → **翌日、一問一答の毎日配信が届くこと**
      （`tsudumonBlockedAt` と `blocked` の分離確認。一問一答アカウントを別途友だち追加済みの
      テストユーザーで確認する）
- [ ] 一問一答（チャットでスタディ）の毎日配信・出題範囲設定・Win-back が従来どおり動くこと
      （`lineWebhook` の無改修部分の回帰確認）
- [ ] （`tsudumonTrialReminder` デプロイ後）3日間無料お試し中のテストユーザーに、つづもんBotから
      リマインドが届くこと。一問一答Botからは届かないこと

---

## 6. ロールバック手順

問題が起きたときに**被害を最短で止める**ことを優先する順序。

### 6-1. 最優先: LINEプラットフォーム側で受信を止める

つづもんBot経由で誤動作（誤送信・誤課金案内・意図しないpush等）が起きた場合、**まず LINE Developers
Console でつづもんチャネルの Webhook URL を空にする、または「Use webhook」トグルを OFF にする**。
これでつづもんBotへのイベントはコード側に一切届かなくなる（一問一答チャネルには影響しない・
`lineWebhook` 側の設定は完全に独立している）。

### 6-2. `tsudumonTrialReminder` を止めたい場合

Cloud Scheduler の該当ジョブ（`firebase-schedule-tsudumonTrialReminder-asia-northeast1` 等。
実際のジョブ名は `gcloud scheduler jobs list` で確認）を一時停止（Pause）する、または
`firebase functions:delete tsudumonTrialReminder` で関数自体を削除する。

### 6-3. コードを元に戻す

このタスクの変更はすべて未コミットの作業ツリー上の変更（2026-07-25 時点でコミットされていない）。
コミット前であれば `git checkout -- <ファイル>` で個別に戻せる。コミット後に戻す場合は、
このステアリングのコミットを `git revert` する（`lineWebhook.ts` は一問一答固有ロジックを
変更していないため、revert しても一問一答側の回帰は起きない設計）。

### 6-4. 一問一答（3,000フォロワー）側は触らない

上記のいずれの対応も、**既存 `lineWebhook` の Webhook URL・応答設定・デプロイ済みコードには
触れない**。つづもん側の問題切り分け中に一問一答の配信を止める必要は基本的に無い
（Bot振り分け・ブロックフィールド分離が設計どおりなら独立して動く）。

---

## 7. デプロイ後にやること

- [ ] `deliveryStats/{YYYY-MM}` に `tsudumonIntroNudge` カウントが記録され始めることを確認
      （`onAnswerCreated` の累計10問マイルストーン案内。§5の実機確認とは別に、日次の送信数として監視）
- [ ] `docs/operations/line-webhook-deploy.md` の要領で `firebase functions:log --only tsudumonWebhook`
      を数回確認し、`[tsudumonWebhook] invalid signature` 等のエラーが出ていないことを確認
- [ ] pdf-workbook 側のLP・chat.js・PDF生成の友だち追加リンク置換（移行手順書 章6-4）が
      正しく本番反映されているか、実URLで確認
