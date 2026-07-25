# つづもん webhook 棚卸し

作成 2026-07-25。調査専任（コード変更・デプロイなし）。対象リポジトリ:
`marutto-study`（`functions/` 配下が中心）、参照のみ `pdf-workbook`。

> 前提ドキュメント: `pdf-workbook/docs/つづもん-公式LINE分離移行手順.md`（分離の方針・手順書。本書はその
> 「作業量を決めるための棚卸し」として参照されている）。LIFF `2009587166-LjyCza2c` は付け替えない、
> 同一プロバイダー内なら userId は共通、という同文書の前提はコードからも確認できた（§3, §6 参照）。

`.env` のキー名のみ扱い、値は一切読んでいない。既存キーを確認したところ、ユーザーから聞いていた
`LINE_TSUDUMON_MESSAGING_CHANNEL_SECRET` / `_ACCESS_TOKEN` 以外に、次の3つも**既に用意済み・未使用**
だった（`functions/.env` キー名のみ確認、値未読）:

- `LINE_TSUDUMON_BOT_BASIC_ID`
- `LINE_TSUDUMON_CHANNEL_ID`
- `LINE_TSUDUMON_FRIEND_URL`

いずれも `functions/src/**/*.ts` / `marutto-study` 側 / `pdf-workbook` 側のどこからも参照されていない
（`grep` で0件）。**新Bot用の環境変数は用意されているが、コードは1行も繋がっていない状態**というのが
全体の結論。

---

## 1. `functions/src/index.ts` の export 一覧

全 export（`functions/src/index.ts:1-451`）を分類した。「共通」は「両方のBotで最終的に必要になる」という
意味で、現状は**すべて旧Bot（一問一答用チャネル）の設定だけで動いている**（分離後も動き続けるのは旧Bot側で、
新Bot側は棚卸しのとおり未接続）。

| export | 種別 | 分類 | 根拠 |
|---|---|---|---|
| `lineWebhook`（`lineWebhook.ts:805`） | HTTP (onRequest) | **[共通]** | 1本のwebhookが一問一答とつづもんの両方のイベントを内部分岐で処理している（§2参照） |
| `instagramWebhook`（`instagramWebhook.ts:29`） | HTTP | [一問一答] | IGコメント→DM→友だち追加は一問一答アカウントへの誘導施策（`igCampaignMatcher.ts`）。つづもんとの接続なし |
| `dailyQuiz06/07/16/18/20`（`dailyQuiz.ts:278-324`） | cron (`pubsub.schedule '0 {6,7,16,18,20} * * *'`) | [一問一答] | 毎日配信（無料/プレミアム共通の1問プッシュ）。つづもん教材とは無関係のプールから出題 |
| `onAnswerCreated`（`onAnswerCreated.ts:495`） | Firestore trigger `answers/{answerId}` | **[共通]（要注意）** | `answers`コレクションは一問一答の回答**だけでなく** workbook（つづもん）回答も `source:'workbook'` 付きで書き込む（`lineWebhook.ts:2758-2771,3020-3029,3916-3925`）。しかし `onAnswerCreated.ts` は `source` フィールドを一切見ておらず（grep 0件）、ストリーク通知・範囲設定ナッジ・プレミアムナッジを**つづもん回答にも無差別に適用している**（§6のリスク参照） |
| `onPremiumApplicationCreated`（`onPremiumApplicationCreated.ts:56`） | Firestore trigger `premiumApplications/{id}` | [一問一答] | 一問一答のプレミアム申込（現在休止中）専用 |
| `syncRichMenuToPlan`（`syncRichMenuToPlan.ts:26`） | Callable (onCall) | [一問一答]（要注意） | `RichMenuPlan = 'free'\|'trial'\|'premium'\|'workbook'`（`lineRichMenu.ts:17`）。`'workbook'` は旧Botの中でつづもん利用者に切り替える専用リッチメニュー（§6参照）。分離後は旧Bot側のこの分岐が丸ごと不要になる |
| `remindIncompleteOnboarding`（`remindIncompleteOnboarding.ts:79`） | cron (`'0 * * * *'` 毎時) | [一問一答] | 一問一答オンボーディング未完了リマインド |
| `onTestScopeFirstSet` / `onTestScopeSaved`（各ファイル:34/15） | Firestore trigger `users/{uid}` | [一問一答] | `testScope`（出題範囲設定）は一問一答固有の概念 |
| `stripeWebhook`（`stripeWebhook.ts:276`） | HTTP | [一問一答] | 一問一答プレミアムのStripe決済（`STRIPE_SECRET_KEY`系）。つづもん決済は別関数 |
| `createStripeCheckoutSession` / `cancelStripeSubscription`（各:72/51） | HTTP | [一問一答] | 同上（プレミアム、現在 `PREMIUM_FLOW_ENABLED=false` で休止中だが関数自体は生存） |
| `submitContactForm`（`submitContactForm.ts`） | HTTP | [一問一答] | `LIFF_CONTACT_URL`（chatstudy本体の/liff/contact）専用。つづもんLPは別のVercel `chat.js` を持つ |
| `tsudumonDownload`（`tsudumonDownload.ts:38`） | HTTP | [つづもん] | 納品zipダウンロード窓口 |
| `tsudumonActivate` / `tsudumonEntitlement` / `tsudumonTrialStart`（`tsudumonActivate.ts:124/226/368`） | HTTP ×3 | [つづもん] | ライセンス登録・権利確認・無料お試し開始 |
| `tsudumonTrialReminder`（`tsudumonTrialReminder.ts:75`） | cron (`'0 19 * * *'`) | [つづもん]（**ただしLINE送信は旧Botのクライアントを使用**） | 3日間無料お試しのリマインドpush。`getLineClient`（`lineWebhook.ts`由来）を使っており新Bot未接続（§3参照） |
| `tsudumonCreateCheckout` / `tsudumonStripeWebhook` / `tsudumonCreatePortal`（`tsudumonStripe.ts:126/332/493`） | HTTP ×3 | [つづもん] | つづもん月額サブスクのStripe決済（`STRIPE_TSUDUMON_*`） |
| `referenceChat`（`referenceChat.ts:31`） | HTTP | [つづもん]（AI枠はLINE側と共有） | つづもん参考書Web版のチャット。知識・履歴・1日40回枠を**LINEの`ref_ask`と共有**（`referenceChat.ts:1-16`のコメント） |
| `gradeWritten`（`gradeWritten.ts:114`） | HTTP | [つづもん] | 問題集Web版の記述問題AI採点。購入者ゲート・AI枠を共有 |
| `recordMubistaProgress` / `redeemMubistaSession`（各:126/25） | HTTP | 対象外（別プロダクト） | 授業動画アプリ「ムビスタ」用。つづもん・一問一答どちらとも独立した第3のプロダクト |
| `recalculateUserStatuses`（`recalculateUserStatuses.ts:35`） | cron (`'0 2 * * *'`) | [一問一答] | `status`（active/at-risk/dormant/churned）は一問一答の休眠判定 |
| `sendWinbackMessages`（`sendWinbackMessages.ts:73`） | cron (`'0 19 * * *'`) | [一問一答] | Win-back配信。つづもんユーザーへの影響は未確認（`status`はBot非依存でuser docに乗るため、つづもんだけ使うユーザーにも一問一答文言のWin-backが飛ぶ可能性がある。§6） |
| `monthlyDeliveryReport`（`monthlyDeliveryReport.ts:31`） | cron (`'0 9 1 * *'`) | [一問一答]（集計は共通コレクション） | `deliveryStats`集計だが、現状は同一Bot・同一プラン枠を前提にしたレポート。つづもんのpush種別（`tsudumonTrial`）も同じ`deliveryStats`に記録されており（`tsudumonTrialReminder.ts:176`）、分離後は枠がBotごとに別管理になるためレポートの前提が崩れる |
| `sendMonthlyReportInvite`（`sendMonthlyReportInvite.ts:36`） | cron（**未デプロイ・dormant**） | [一問一答] | 月末ふり返りレポート招待。CLAUDE.mdに「2026-06-19時点で未デプロイ」と明記 |
| `createLineCustomToken` / `createLiffFirebaseToken`（`index.ts:101,217`） | HTTP | [共通]（メッセージング分離とは無関係） | LINEログイン（`2009587166`）のFirebase Auth連携。移行手順書の結論どおりLIFF/ログインチャネルは付け替えないため、この2関数は分離の影響を受けない |
| `workbookLaunch`（`index.ts:316`） | HTTP | [つづもん] | ワークQR即出題の受け口。`pushWorkbookStart`を呼ぶ（`index.ts:363-364`） |
| `referenceLaunch`（`index.ts:388`） | HTTP | [つづもん] | 参考書QR即開始の受け口。`pushReferenceStart`を呼ぶ（`index.ts:435-436`） |

---

## 2. `functions/src/lineWebhook.ts` ハンドラ棚卸し

10,952行の単一ファイル。イベント振り分けは `dispatchEvent`（`lineWebhook.ts:893-922`）で
`follow` / `unfollow` / `postback` / `message` の4種のみ処理する。

### 2-1. message イベント（`handleMessage`, `lineWebhook.ts:924-1146`）

テキスト受信時の分岐順（上から評価、最初にマッチしたものが処理して return）:

| 順 | 条件 | 処理関数 | 分類 |
|---|---|---|---|
| 1 | 画像・音声 | `handleMediaMessage`（`4419`） | [共通] AIチャット基盤（aiChat.ts）を画像/音声で使う。教科knowledge文脈は一問一答想定だが仕組み自体は両方に転用可 |
| 2 | スタンプ | `handleStickerMessage`（`4536`） | [一問一答寄りだが実質共通] AIが応答するだけの汎用処理 |
| 3 | 動画 | 定型文reply | [共通] |
| 4 | `/^(設定\|せってい)\s*(変更\|へんこう)/` | `handleSettingsChange`（`4697`） | [一問一答] 配信設定（学年・教科・時刻）変更 |
| 5 | ムビスタ意図（`isMubistaIntent`） | `handleOpenMubista`（`758`） | 対象外（別プロダクト） |
| 6 | つづもんライセンスコード（`TZM-XXXX-XXXX`, `extractTsudumonCode`） | `handleTsudumonActivation`（`1229`） | **[つづもん]** ライセンス登録専用キーワード。これが「つづもん登録」に相当する現状唯一の入口（Botに直接コードを送る／`つづもん登録 {code}`という定型文、`scripts/manage-tsudumon.ts:139`参照） |
| 7 | `text === '継続希望'` | `handleTsudumonContinueRequest`（`1308`） | **[つづもん]** 期限切れ後の継続希望を管理者へ通知 |
| 8 | `/^(これで)?決定[！!。]?$/`（範囲設定「これで決定」誤爆対策） | `replyWithScopeStartChip`（`6055`） | [一問一答] |
| 9 | `WORKBOOK_PREFIX_RE`（「ワーク {単元名}」） | `handleWorkbookQuestion`（`1366`） | **[つづもん]** QR経由の出題フォールバック兼、手入力での出題起点。ここで`checkTsudumonAccess`ゲートを通す（`1386`） |
| 10 | 復帰キーワード（`detectRestartIntent`） | `handleRestartIntent`（`4611`） | [一問一答] Win-back復帰 |
| 11 | 「問題出して」系（`detectQuestionRequest`） | `selectAndSendQuestion`（`10194`） | [一問一答] 追加で解く |
| 12（フォールスルー） | 上記いずれにも非該当 | `aiChat.handleAiChat`（`aiChat.ts`, `handleMessage:1134`でdynamic import） | **[共通]** サービス知識（`aiChatPrompt.ts`）を内蔵したGeminiが応答。つづもんの質問にも答えている想定（1日40回枠は`users/{uid}.aiChat.count`で一問一答と共用） |

### 2-2. postback イベント（`handlePostback`, `lineWebhook.ts:5050-5308`）

全 `type=` 分岐を列挙（順は原文どおり）。

| type | ハンドラ | 分類 |
|---|---|---|
| `select_grade` / `select_subject` / `select_time` | `handleSelectGradePostback`等（`9270/9354/9469`） | [一問一答] オンボーディング |
| `answer` | `handleAnswerPostback`（`9637`） | [一問一答] 毎日配信/追加/苦手復習の4択回答。`type=answer`は`buildQuestionMessage`/`buildMathHybridMessage`（`10641,10916`）だけが発行し、workbook側は使わない（要確認: grep で確認済み） |
| `wb_start` / `wb_next` / `wb_end` / `wb_idk` / `wb_kind` / `wb_iskip` / `wb_regrade` / `wb_stats` / `wb_recent` / `wb_weak` / `wb_help` | `handleWorkbook*`（`3527〜4371`帯） | **[つづもん]** ワーク問題集の出題継続・記録・成績確認。ゲート再チェックはせず（設計コメント`1164-1168`により入口のみゲート） |
| `ref_ask` / `ref_talk` / `ref_check` / `ref_level` | `handleReference*`（`2296〜2497`帯） | **[つづもん]** 参考書AI対話・理解度チェック |
| `rm_switch` | 無処理（クライアント側で完結） | [共通] |
| `extra_question` | `handleExtraQuestionPostback`（`9051`） | [一問一答] |
| `restart` | `handleRestartPostback`（`4589`） | [一問一答] |
| `open_mubista` | `handleOpenMubista`（`758`） | 対象外 |
| `weak_review` | `handleWeakReviewPostback`（`9100`） | [一問一答] |
| `help` / `streak` / `settings_menu` / `settings_guide` / `pause_delivery` / `resume_delivery` | 各ハンドラ | [一問一答] 毎日配信の設定・記録系 |
| `change_learning` / `change_learning_grade` / `change_learning_subject` | `handleChangeLearning*`（`6554〜6712`） | [一問一答] |
| `report_summary` / `monthly_report` | `handleReportSummaryPostback`/`monthlyReport.handleMonthlyReportPostback` | [一問一答] |
| `test_range_menu` / `scope_start` / `scope_pick` / `scope_commit` / `scope_finish` | `handleScope*` | [一問一答] 出題範囲設定 |
| `sample_answer` | `handleSampleAnswerPostback`（`4883`） | [一問一答] follow直後のお試し1問（学年不問の静的問題） |
| `not_learned` / `not_learned_apply` | `handleNotLearnedPostback`等（`6093/6238`） | [一問一答] |
| `premium_info` | 分岐内で直接処理（`5286-5305`） | [一問一答]（休止中） |

### 2-3. follow / unfollow

- `handleFollow`（`4955-5014`）: **[共通だが要修正]**。`users/{uid}`に`onboardingState:'started'`, `blocked:false`を無条件で書き込み、お試し1問＋学年選択flexを送る。つづもん専用Botに同じロジックを流用すると、**既存の一問一答ユーザーがつづもんBotを新規フォローした瞬間にオンボーディング状態が上書きされる**リスクがある（§6）。
- `handleUnfollow`（`5027-5048`）: `users/{uid}.blocked = true`を書く。**この`blocked`フラグは一問一答側のcron群（dailyQuiz / winback / remindIncompleteOnboarding等、コメント`5019-5022`に列挙）が配信除外判定に使っている共有フィールド**。つづもんBotをブロックしただけで一問一答の配信も止まる（またはその逆）という**副作用の温床**（§6の最大リスク）。

### 2-4. QR出題・回答・AIチャットの実体まとめ

| 機能 | 入口 | 実処理 | 分類 |
|---|---|---|---|
| ワークQR出題 | `workbookLaunch`（HTTP）→`pushWorkbookStart`（`1554`） | `checkTsudumonAccess`ゲート→push | [つづもん] |
| 参考書QR出題 | `referenceLaunch`（HTTP）→`pushReferenceStart`（`2248`） | 同上 | [つづもん] |
| ワーク回答 | postback `wb_next`等 / テキスト直接入力（`handleWorkbookTextAnswer:2670`） | `answers`コレクションへ`source:'workbook'`付きで記録 | [つづもん]（ただし`onAnswerCreated`は共通処理） |
| AI先生への質問 | postback `ref_ask`→`handleReferenceTextInput`（`2497`） | Gemini呼び出し、`refSession.history`に保存 | [つづもん] |
| 毎日配信・Win-back・範囲設定 | cron / postback群 | 上表のとおり | [一問一答] |
| 「つづもん登録」的キーワード | テキスト完全一致ではなく**ライセンスコードの正規表現一致**（`extractTsudumonCode`, `keywordMatcher.ts`または`tsudumonCore.ts`実装は未確認箇所） | `handleTsudumonActivation` | [つづもん] |

---

## 3. LINE APIクライアント（token/secret）の生成箇所

### 3-1. チャネルアクセストークン（push/reply送信用）

**唯一の生成点**: `getLineClient()`（`lineWebhook.ts:577-588`）。

```
577: let cachedClient: messagingApi.MessagingApiClient | null = null;
578: export async function getLineClient(): Promise<messagingApi.MessagingApiClient> {
579:   if (cachedClient) return cachedClient;
580:   const channelAccessToken = process.env.LINE_MESSAGING_CHANNEL_ACCESS_TOKEN || '';
```

- モジュールスコープの変数 `cachedClient` にシングルトンでキャッシュ（インスタンス使い回し前提のCloud Functions最適化）。
- 引数なし・env固定・**呼び出し側でBotを選べない設計**。
- この関数を import している外部ファイル（`getLineClient`のimport元、grep結果）:
  `aiChat.ts` / `dailyQuiz.ts` / `expireTrialUsers.ts`（dormant） / `monthlyReport.ts` /
  `onAnswerCreated.ts` / `onPremiumApplicationCreated.ts` / `onTestScopeSaved.ts` /
  `postTrialFollowup.ts`（dormant） / `remindIncompleteOnboarding.ts` /
  `sendMonthlyReportInvite.ts` / `sendWinbackMessages.ts` / `stripeWebhook.ts` /
  `submitContactForm.ts` / `trialDripBase.ts`（dormant） / `trialFormAbandonReminder.ts`（dormant） /
  **`tsudumonTrialReminder.ts:23,92`**。
- `lineWebhook.ts`自身の内部でも60箇所以上（`grep`実測、`764`〜`10501`の範囲に散在）で`await getLineClient()`を呼んでいる。

**注入点の評価**: 「グローバル定数1箇所」に見えるが、呼び出し側は**トークンを意識せず単に`getLineClient()`を呼ぶだけ**という設計のため、Bot振り分けをするには
1. `getLineClient(channel: 'ichimon' | 'tsudumon')`のように引数化し、
2. `cachedClient`をchannelごとの2つのキャッシュに分割し、
3. **上記16ファイル・60箇所超の全呼び出しに正しいchannel引数を渡す**

という改修が要る。**「新トークンに差し替える」は1箇所の変更では済まない**——`getLineClient()`は
「今どのBotとして動いているか」というコンテキストを一切持たないため、呼び出し側全部で「これは
一問一答の処理か、つづもんの処理か」を判定し分ける必要がある。とくに`onAnswerCreated.ts`
（daily quizとworkbook両方が経由）や`lineWebhook.ts`内の同一関数が両方の文脈で呼ばれるケース
（例: `handleWorkbookQuestion`はworkbook文脈のみだが、`replyMessage`はreply tokenベースなのでどのBotの
webhookが受けたイベントかは`event`側の情報から分かる——つまり「reply」は受信元Botで自動的に決まるが、
「push」は明示的にBotを選ぶ必要がある）という**reply/pushで注入の要否が異なる**点も見積もりに影響する。

現状**すでに`tsudumonTrialReminder.ts`（つづもん専用cron）が誤って（設計上は暫定的に）旧Botのクライアントを
使っている**（`tsudumonTrialReminder.ts:23,92`）。新Bot用トークンを`.env`に用意した意図から見て、
ここが最初に直すべき箇所と推測されるが、**現状は未接続のまま本番動作している**（つづもんの3日間お試し
リマインドは旧Bot＝一問一答アカウントから届く状態と推測される。実際の送信ログは未確認）。

### 3-2. チャネルシークレット（署名検証用）

**唯一の生成点**: `lineWebhook`関数内（`lineWebhook.ts:818-823`）。

```
818:   const channelSecret = process.env.LINE_MESSAGING_CHANNEL_SECRET || '';
```

`verifyLineSignature`（`590-597`）へ渡され、`@line/bot-sdk`の`validateSignature`で検証する。
**署名検証はwebhook関数の中に直書きされており、他ファイルから再利用される共通関数にはなっていない**
（`lineWebhook`という1つの`https.onRequest`の中でしか呼ばれない、grep確認済み）。

**注入点の評価**: 新Bot用webhookを別関数として新設する場合、この15行程度の検証ロジック
（`818-850`）をそのままコピーし、env参照だけ`LINE_TSUDUMON_MESSAGING_CHANNEL_SECRET`に差し替える形になる。
1箇所を複製するだけなので、ここは**軽い**（既存コードの改変ではなく新規追加で済む）。

### 3-3. リッチメニューAPI用トークン

`lineRichMenu.ts:50`でも独立に`process.env.LINE_MESSAGING_CHANNEL_ACCESS_TOKEN`を読んでいる
（`getLineClient()`とは別の生成点。`resolveConfig()`関数内、モジュールスコープではなく呼び出しのたびに
`process.env`を読む形）。つづもん用リッチメニューを新設する場合、ここも新Bot用トークンを注入できる形
（引数化）にする必要がある。

---

## 4. つづもん入口のハードコード箇所

### 4-1. `https://lin.ee/wxDOngU`（旧アカウント友だち追加リンク）

| ファイル:行 | 用途 | 判定 | 理由 |
|---|---|---|---|
| `marutto-study/src/pages/LiffWorkbookLaunchPage.tsx:18,140` | ワークQR起動LIFFの「友だち追加してね」導線 | **変えるべき（つづもん用）** | このページ自体がつづもんQRの着地点（`LiffWorkbookLaunchPage.tsx:1-11`のコメントで明言） |
| `marutto-study/src/pages/LiffWorkbookLaunchPage.tsx:20,80,123` `OA_TALK_URL = 'https://line.me/R/oaMessage/%40824cebif/?'` | 出題後にトークへ戻す遷移先 | **変えるべき（つづもん用）** | 同上。出題完了後は新Botのトークへ戻すべき |
| `marutto-study/src/pages/LiffReferenceLaunchPage.tsx:17,18`（同型） | 参考書QR起動LIFFの友だち追加・トーク遷移 | **変えるべき（つづもん用）** | 同上、参考書版 |
| `marutto-study/api/chat.js:32,45,80,91,99,127,133`（つづもんLPチャットAPI、コメントで「つづもんLP チャットボットAPI」と明記） | AIチャットのフォールバック文言 | **変えるべき（つづもん用）** | 冒頭コメントで明示的につづもんLP専用と分かる |
| `marutto-study/scripts/manage-tsudumon.ts:40` `LINE_BASIC_ID='@824cebif'`、`139`行目で`つづもん登録 {code}`のoaMessageリンクを構築 | ライセンス発行時の案内文生成（管理スクリプト） | **変えるべき（つづもん用）** | 生成物がつづもん購入者向け案内そのもの |
| `marutto-study/src/pages/TestRangePage.tsx:25` | 出題範囲設定ページの「トークに戻る」deep link | **変えてはいけない（一問一答用）** | `TestRangePage`は一問一答の`testScope`専用ページ（コメント`15-22`で「保存完了後に公式LINEのトーク画面へ戻す」と明記、つづもんとは無関係） |
| `marutto-study/src/pages/WelcomePage.tsx:5` | 一問一答の友だち追加導線（メインのオンボーディング） | **変えてはいけない（一問一答用）** | 一問一答本体のwelcomeフロー |
| `pdf-workbook/lp/index.html:1092,1105` | LPのCTAボタン2箇所 | **変えるべき（つづもん用）** | つづもんLP本体 |
| `pdf-workbook/lp/api/chat.js`（`marutto-study/api/chat.js`と同内容、複数箇所） | 同上フォールバック文言 | **変えるべき（つづもん用）** | 同上（2リポジトリに重複配置されている点は運用上の要注意事項。§6） |
| `pdf-workbook/make_intro_pdf.py:33` `FRIEND_URL` | 問題集PDFの「はじめにお読みください」 | **変えるべき（つづもん用）** | つづもん教材PDF生成 |
| `pdf-workbook/make_ref_intro_pdf.py:25` `FRIEND_URL` | 参考書PDFの「はじめにお読みください」 | **変えるべき（つづもん用）** | 同上 |

### 4-2. `@824cebif` / `%40824cebif`（旧アカウントBasic ID）

上表と重複する箇所（`LiffWorkbookLaunchPage.tsx` / `LiffReferenceLaunchPage.tsx` / `scripts/manage-tsudumon.ts`）に加え、

| ファイル:行 | 用途 | 判定 | 理由 |
|---|---|---|---|
| `pdf-workbook/generate_history_workbook.py:35` `LINE_BASIC_ID = "@824cebif"` | 変数として宣言のみ | **未使用（宣言のみ・死んでいるコード）** | 同ファイル内でこの変数を参照している箇所はgrepで0件。実際のQR URLは37-38行目の`LIFF_ID_UNITS`（`https://liff.line.me/{LIFF_ID_UNITS}/wb`）を使っており、Basic IDは使われていない。**変更してもしなくても実害はないが、死んでいる以上どちらでもよい／削除が望ましい** |
| `pdf-workbook/README.md:58` | ドキュメント内の説明文（QRの中身の解説） | 変えるべき（ドキュメント更新の範囲。ただし本調査は生成物・README以外のコード優先という指示のため参考情報扱い） | 実装ではなく説明文 |

### 4-3. LIFF ID `2009587166-LjyCza2c`（`LIFF_ID_UNITS`）

移行手順書の結論どおり**変更禁止**。4ジェネレータ（`generate_reference_web.py:77`, `generate_reference_book.py:35`,
`generate_history_workbook.py:38`, `generate_workbook_web.py:90`）すべてこの値を使うが、これは
「チャットでスタディ」のunits LIFFそのものであり、つづもん専用LIFFではない
（`marutto-study/src/pages/LiffWorkbookLaunchPage.tsx:4-6`のコメントで確認済み）。本棚卸しでもこの結論を
覆す事実は見つからなかった。

### 4-4. 表: 判定サマリ

| 分類 | 該当ファイル数 | 変更要否 |
|---|---|---|
| つづもんQR着地LIFF（友だち追加・トーク遷移） | 2ファイル（Workbook/Reference LaunchPage） | 変えるべき |
| つづもんLPチャットAPI | 2ファイル（marutto-study/api/chat.js, pdf-workbook/lp/api/chat.js。中身重複） | 変えるべき |
| つづもん教材PDF生成 | 2ファイル（make_intro_pdf.py, make_ref_intro_pdf.py） | 変えるべき |
| つづもんLP本体 | 1ファイル（lp/index.html） | 変えるべき |
| つづもん管理スクリプト | 1ファイル（manage-tsudumon.ts） | 変えるべき |
| 一問一答専用（変更禁止） | 2ファイル（TestRangePage.tsx, WelcomePage.tsx） | 変えてはいけない |
| 死んでいるコード | 1ファイル（generate_history_workbook.py の LINE_BASIC_ID） | どちらでもよい |

---

## 5. 分離の実装見積もり

### 案A: つづもん専用webhookを新設し完全分離（QR出題・回答・AIチャット・日次プッシュを新Bot化）

**既存ハンドラの再利用可否（最重要ポイント）**:

- `handleWorkbookQuestion` / `pushWorkbookStart` / `pushReferenceStart` / `handleWorkbook*`（`wb_next`等9関数） /
  `handleReference*`（4関数） / `handleTsudumonActivation` / `handleTsudumonContinueRequest` — これらは
  **すでに「つづもん専用」として明確に切り出されている**（一問一答のロジックとif分岐で混在していない）。
  reply送信はreply tokenベースなので、**新Botのwebhookが受けたイベントに対してこれらの関数をそのまま
  呼べば、reply自体はそのBotから返る**（LINE APIのreplyはトークン発行元のチャネルに紐づくため）。
  → **これらは「クライアント注入で済む」寄り**。ただし push（`pushWorkbookStart`/`pushReferenceStart`内の
  `getLineClient()`呼び出し、`1571,1594,1719,2065,2260,2276`等）は明示的にBotを選ぶ必要があり、
  `getLineClient()`のchannel引数化（§3-1）が前提になる。
- `dispatchEvent` / `handleMessage` / `handlePostback`は**一問一答とつづもんの分岐が1つの巨大関数に同居**
  している（§2-1, 2-2の表）。新Bot用に複製すると、一問一答固有の分岐（オンボーディング・範囲設定・
  Win-back・ストリーク等、20種以上のpostback type）を**全部読んで「これはつづもんBotには不要」と
  判断してから間引く**作業が発生する。**単純コピーでは条件分岐だらけになる**——素直にやるなら
  「`handleMessage`/`handlePostback`を新Bot用に薄く新設し、つづもん系の関数だけをexportして呼ぶ」形に
  リファクタリングするのが筋だが、それは`lineWebhook.ts`の**関数分割（別ファイル化）が前提**になり、
  10,952行の中からつづもん関連コード（ざっくり見積もり: `handleWorkbookQuestion`〜`handleWorkbookEndPostback`
  の帯`1229-4371`のうち約半分、`handleReference*`帯`2248-2497`、`checkTsudumonAccess`/`buildTsudumonGateText`
  `1153-1229`）を抽出する作業が要る。
- `follow`/`unfollow`（`handleFollow`/`handleUnfollow`）は**そのまま流用不可**。新Bot用に書き直しが要る
  （§6の最大リスク：`blocked`・`onboardingState`の共有フィールド事故を避けるため）。
- `onAnswerCreated`（つづもん回答も経由する共通Firestore trigger）は、pushをBot振り分けする対応
  （`source==='workbook'`なら新Botのクライアントを使う）を入れないと、**分離後もworkbook回答時のナッジ類が
  旧Botから届くという new bug** が発生する。
- `linkWorkbookMenuIfEligible`（`4217-4256`）・`RichMenuPlan='workbook'`（`lineRichMenu.ts:17,87`）は
  **旧Bot内のリッチメニュー切替ロジックとして丸ごと廃止**すべき（新Botが独自のリッチメニューを持つため）。
  削除しないと、つづもん利用者が旧Botのリッチメニューまで書き換えられ続ける無意味な副作用が残る。

**変更が要るファイル一覧（案A）**:

| ファイル | 変更内容 | 見積 |
|---|---|---|
| `functions/src/lineWebhook.ts` | `getLineClient`のchannel引数化、`verifyLineSignature`呼び出し口の複製、つづもん系ハンドラの新Bot用webhookからの呼び出し配線、`follow`/`unfollow`の新規実装、`linkWorkbookMenuIfEligible`等の旧Bot側廃止 | **L**（最大の作業。10,952行の中核ファイルを触るため回帰リスクも高い） |
| `functions/src/index.ts` | 新webhook関数のexport追加 | S |
| `functions/src/onAnswerCreated.ts` | `source`分岐でBotを選ぶpush処理に変更 | M |
| `functions/src/tsudumonTrialReminder.ts` | `getLineClient()`呼び出しを新Bot用に | S（channel引数化後は1行） |
| `functions/src/lineRichMenu.ts` | 新Bot用トークンを受けられる形に | S〜M |
| `functions/src/deliveryStats.ts` / `monthlyDeliveryReport.ts` | Botごとの枠管理に対応（プラン上限が別勘定になるため） | M |
| `src/pages/LiffWorkbookLaunchPage.tsx` / `LiffReferenceLaunchPage.tsx` | 友だち追加・トーク遷移URLの差し替え | S |
| `api/chat.js`（marutto-study・pdf-workbook 両方） | フォールバック文言のURL差し替え | S |
| `lp/index.html` / `make_intro_pdf.py` / `make_ref_intro_pdf.py` / `manage-tsudumon.ts` | URL/Basic ID差し替え | S |
| 新規: つづもん専用リッチメニュー画像・登録スクリプト | 新設 | M |
| Firestore運用: `users`ドキュメントの`blocked`等フィールドのBot別分離設計 | 設計＋実装 | **M〜L**（§6次第で影響範囲が変わる） |

**総合見積もり: L**（1つの大改修。中心は`lineWebhook.ts`の関数分割とfollow/unfollow・push経路の
Bot振り分け。テスト（`__tests__/`配下、`lineWebhook.ts`関連のユニットテストの有無は未確認）の手当ても
要る）。

### 案B: 新Botは日次プッシュ専用。QR出題・AIチャットは当面チャットでスタディのまま（最小分離）

- 変更が要るのは実質**`tsudumonTrialReminder.ts`（または新設する「つづもん日次プッシュ」cron）だけ**。
  `getLineClient()`をこの1ファイルの用途に限って新Bot用に差し替える最小改修で足りる
  （`getLineClient(channel)`化してこのファイルだけ`'tsudumon'`を渡す、あるいはこのファイル専用に
  ミニマムな`getTsudumonLineClient()`を新設する方が影響範囲が小さい）。
- 新Bot用webhook自体は**空でよい**（あいさつメッセージ無効化・応答モードBot、のURLだけ登録すればpushは
  受信不要。ただし友だち追加/ブロックのfollow/unfollowイベントだけは受けて`blocked`相当のフラグを
  Bot別に管理する最低限のwebhookは要る——でないと日次プッシュがブロック済みユーザーにも送られ続ける）。
- QR出題・AIチャットは**旧Botに残す**ため、`LiffWorkbookLaunchPage.tsx`等の遷移先URLも変更不要
  （旧Botのトークへ戻ればよいため）。ただし「日次プッシュは新Bot、QR出題は旧Bot」という**2つのトークに
  分裂した体験**になる点はUX上のトレードオフとして別途合意が要る（本棚卸しの範囲外）。

**変更が要るファイル一覧（案B）**:

| ファイル | 変更内容 | 見積 |
|---|---|---|
| `functions/src/tsudumonTrialReminder.ts`（または新設cron） | 新Bot用クライアントで送信 | S |
| `functions/src/lineWebhook.ts` | `getLineClient`の最小限のchannel対応（この1呼び出し元のためだけ） | S |
| 新Bot用の最小webhook（follow/unfollowのみ処理） | 新設 | S〜M |
| `functions/src/index.ts` | export追加 | S |

**総合見積もり: S**（1〜2日相当の改修規模。既存のつづもん体験・一問一答体験に手を入れない）。

---

## 6. リスク・落とし穴

1. **`blocked`フィールドの共有事故（最大リスク）**: `users/{uid}.blocked`は`handleUnfollow`
   （`lineWebhook.ts:5027-5048`）が一元的に立て、dailyQuiz/Win-back/onboarding系cronが配信除外判定に
   使う共有フィールド（コメント`5019-5022`で列挙）。**新Botのfollow/unfollowが同じフィールドに素朴に
   書き込む実装だと、「つづもんBotだけブロックした一問一答ユーザー」が一問一答の配信まで止まる**、
   あるいはその逆が起きる。Bot別フィールド（例: `blockedIchimon`/`blockedTsudumon`）への分離が必須。

2. **`onAnswerCreated`がworkbook回答も無差別処理**: `answers`コレクションは一問一答・つづもん共有
   （`source:'workbook'`で書き分けてはいるが読む側が見ていない、`lineWebhook.ts:2758-2771`と
   `onAnswerCreated.ts`全文grep結果）。ストリーク通知・範囲設定ナッジ・プレミアムナッジが
   つづもん回答後にも発火し得る。分離後は**pushの送り先Botを`source`で振り分けないと、つづもん専用
   Botのはずが旧Botから通知が届く**という体験の不整合が残る。

3. **リッチメニューの二重管理**: `linkWorkbookMenuIfEligible`（`lineWebhook.ts:4217-4256`）が
   旧Bot内で`richMenuType:'workbook'`に自動切替する仕組みが現存する。新Bot導入後もこれを放置すると、
   つづもん利用者の**旧Botのリッチメニューまで書き換わり続ける**（無意味だが実害はUXの混乱として残る）。
   案Aでは廃止、案Bでも「日次プッシュだけ新Bot」なのでQR出題は旧Bot経由のままとなり、この仕組みは
   **当面残す判断もあり得る**（要合意）。

4. **3,000人の既存フォロワーへの影響**: 移行手順書§8の1通配信以外に、コードレベルでは
   `handleFollow`（`4955`）のオンボ状態上書きに注意——既存一問一答ユーザーが新規に**つづもんBotを
   フォロー**した場合、もし新Bot側で`handleFollow`を安易に流用実装すると、共有`users/{uid}`ドキュメントの
   `onboardingState`等が意図せず初期化されるおそれがある（uid共有はプロバイダー共通なので、
   `buildUid`関数`lineWebhook.ts:4768-4778`の`line:${userId}`キーがそのまま両Botで一致することは
   コード上確認済み）。

5. **応答モード・あいさつメッセージ**: 移行手順書§3で「あいさつメッセージ・自動応答を無効化」と
   チェックリスト化されているが、これはLINE Official Account Manager側の設定でコード外。
   本棚卸しでは**コード側に「LINEの自動応答」を無効化する処理はない**ことのみ確認（未確認: 実際の
   管理画面設定状態）。

6. **二重配信の可能性**: 現状`onAnswerCreated`のnudge・Win-back・毎日配信は「同一Bot内の別イベント」
   として設計されているため二重配信の考慮がされていない。分離後、もし`onAnswerCreated`のpush先を
   誤って両Botに送るような実装ミスがあると、**同じ内容の通知が2つのトークに二重に届く**構造的リスクが
   ある（現状はコード上そのような二重送信は起きていない。あくまで分離実装時の落とし穴として明記）。

7. **通数プラン・`deliveryStats`集計の分離漏れ**: `monthlyDeliveryReport`（`monthlyDeliveryReport.ts:31`）
   は現状1つの`deliveryStats`コレクションを1つのプラン上限（仮30,000通/月、CLAUDE.md記載）に対して
   集計している。新Botは別プラン・別上限になるため、**Botごとに集計を分けないと超過警告が正しく
   出ない**（`tsudumonTrialReminder.ts:176`の`recordPushDelivery('tsudumonTrial')`は種別としては
   区別されているが、レポート側が合算している前提は未確認・要検証）。

8. **`api/chat.js`の二重配置**: `marutto-study/api/chat.js`と`pdf-workbook/lp/api/chat.js`が
   ほぼ同内容で2箇所に存在する（grep結果、両方に同じ7箇所のURL言及）。どちらが実際にVercelへ
   デプロイされる本体かは**未確認**（`docs/chatstudy配信構成`メモリには「つづもんはFirebase Hosting
   分離+Vercelプロキシ」とあるが、`api/chat.js`がどちらのリポジトリからデプロイされるかは本調査では
   特定できなかった）。URL差し替え時は**両方編集し忘れないこと**、または実体を1つに統合することを
   推奨。

9. **`referenceChat`/`gradeWritten`のAI枠共有**: つづもんWeb版（`referenceChat.ts`, `gradeWritten.ts`）は
   LINEの`ref_ask`/採点機能と同じ1日40回枠（`users/{uid}.aiChat.count`または類似カウンタ、
   `referenceChat.ts:1-16`コメント）を共有している。Bot分離後もこの枠は`uid`（=共有LINE userId）ベースで
   変わらず機能するはずだが、**「新Botのつづもん利用」と「旧Botのつづもん利用（もし残す場合）」を
   合算カウントしてよいか**は運用判断が要る（未確認・要合意）。

10. **テストカバレッジ**: `functions/src/__tests__/`配下に`lineWebhook.ts`のロジックに対するユニット
    テストがどこまであるかは本調査では深掘りしていない（未確認）。案Aの大規模リファクタリングを
    行う場合、テスト無しでの分割は回帰リスクが高い。着手前にテスト状況を別途確認することを推奨する。

---

## 未確認事項一覧

- `getLineClient()`をchannel引数化した場合の`@line/bot-sdk`側の制約（複数チャネルのクライアントを
  同一プロセス内で問題なく共存させられるか）は未検証。
- LINE Official Account Manager側の「応答モード」「あいさつメッセージ」の現在の設定状態。
- `monthlyDeliveryReport`が実際にBot別集計になっていない場合の具体的な誤警告シナリオ（ロジックは
  読んだが実行時の挙動までは未検証）。
- `marutto-study/api/chat.js`と`pdf-workbook/lp/api/chat.js`のどちらが実デプロイ対象か。
- `functions/src/__tests__/`のカバレッジ範囲。
- つづもん購入者のうち、すでに一問一答アカウントの友だちでない（＝一問一答は使っていない）ユーザーが
  どれくらいいるか（影響範囲の定量化は未実施）。
