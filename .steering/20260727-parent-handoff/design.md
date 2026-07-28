# 設計 — つづもん「子 → 保護者」受け渡し導線・親子連携・保護者ダッシュボード

作成 2026-07-27。要求: `requirements.md`。
実装先は2リポジトリにまたがる（Functions・LINE = `marutto-study/` ／ Web・LP = `pdf-workbook/`）。

## 0. 設計の芯

この機能の成否は**中学生がカードを出す気になるか**で決まる。技術的な難所は保護者ペイリンクだが、
現場のボトルネックは心理で、そこには2つの恐れがある。

1. **お金の話を切り出す恐れ** → 台本と実績（自分から勉強したがっている証拠）で埋める
2. **監視される恐れ** → 「トークは見えない」を**子に先に見せる**ことで埋める

したがって「保護者に何が見えて何が見えないか」の表は、保護者向けページより先に**子の画面**に出す。
プライバシー設計は付帯事項ではなく、この導線の**転換率そのもの**である。

もう1つの芯は摩擦の順序。**決済にLINE連携を必須にしない。** 保護者は「①払う」だけで完了でき、
「②公式LINEで進捗を見る」は完了画面から任意で誘う。連携を先に要求すると、いちばん熱がある
瞬間に友だち追加とOAuthを挟むことになり、必ず落ちる。

---

## 1. 全体フロー

```
[子] 体験2日目の夜 / 期限前日 / ロックカード / 「親に聞かないと」発言
        │
        ▼
  「おうちの人にわたすカード」            ← ここで先に “見えるもの/見えないもの” を子に見せる
   ・保護者ページURL   ・QRコード   ・台本3種
        │
        │  QR（保護者は自分の端末で読む＝スマホを渡さない）
        ▼
[親] https://tsudumon.jp/parents/?t=<token>
   ・お子さんから届いています ＋ 実績サマリ
   ・結論3行（1,280円／いつでも解約／1日最大2通）
   ・見えるもの / 見えないもの の表
        │
        ├─①─→ 「登録する」 → Stripe Checkout（課金先は【子】のuid）→ 完了
        │                                    │
        │                                    ▼
        │                        [子] 御礼push＋オンボーディング（既存のまま）
        │                        [親] 完了画面で ②へ誘導
        │
        └─②─→ 「公式LINEで進捗を見る」→ 友だち追加＋LINEログイン
                        → 親子連携成立 → 保護者ダッシュボード
                        → [子] 「◯◯とつながりました。見えるのは学習の記録だけです」
```

②は①を経由しなくても単独で成立する（体験中に親が様子だけ見る、というルートを塞がない）。

---

## 2. データモデル

`users/{uid}` は両Botで共有される（`marutto-study/CLAUDE.md`）。**Bot固有・ロール固有の状態は
必ず専用フィールドに置き、既存フィールドに相乗りしない。**

### 2-1. `users/{uid}` への追加フィールド

| フィールド | 保持者 | 型 | 説明 |
|---|---|---|---|
| `tsudumonRole` | 親 | `'parent'` | 保護者モード。**未設定＝子（既定）**。子側には書かない |
| `tsudumonChildren` | 親 | `Array<{uid, name, grade, linkedAt}>` | 連携中の子（最大4）。**ダッシュボードはこれ1件のreadで足りる** |
| `tsudumonParents` | 子 | `Array<{uid, linkedAt}>` | 自分を見ている保護者（最大2）。解除・通知に使う |
| `tsudumonParentName` | 子 | `string` | 保護者画面での呼ばれ方（本名は入れない。§8） |

`tsudumonChildren` に**子の呼び名と学年を非正規化して持つ**のが要点。ダッシュボードの見出しを
描くために子ドキュメントを読む必要がなくなり、契約状態と進捗が要るときだけ子を読む。

### 2-2. 新規コレクション `tsudumonInvites/{inviteId}`

```
inviteId   : ランダム22文字（crypto.randomBytes(16) の base64url）
childUid   : 'line:U...'
childName  : 保護者画面での呼び名
childGrade : '中1' | '中2' | '中3'
createdAt  : Timestamp
expiresAt  : Timestamp（発行から14日）
viewedAt   : Timestamp | null      … 初回閲覧
notifiedAt : Timestamp | null      … 子への「見てくれたみたい」送信済み（1回だけの担保）
linkedUids : string[]              … このカードから連携した保護者uid
```

子1人につき**有効なカードは1枚**（再発行すると前のものを失効させる）。`users/{child}.tsudumonInviteId`
に現行の inviteId を持ち、再発行時に旧docを削除する。カードURLが古いLINEトークに残り続けて
無期限に実績を晒す、という事故を防ぐ。

### 2-3. read 規律

保護者ダッシュボードは `users/{parent}` 1 read ＋ 子の人数ぶんの `doc().get()`。
**クエリを一切使わない**（`marutto-study/CLAUDE.md` の Firestore 規律・規則1/6）。
カード閲覧は `tsudumonInvites/{id}` 1 read ＋ 子 1 read。

---

## 3. トークン設計

```
t = <inviteId>.<HMAC-SHA256(inviteId, TSUDUMON_INVITE_SECRET) の先頭32hex>
```

- **uid を URL に載せない**。inviteId は推測不能なランダム値で、そこから uid は復元できない
- 署名は**Firestoreを引く前に**弾くためのもの（総当たりで read を焼かれない）
- 検証は「署名一致 → doc 取得 → `expiresAt > now`」の順。どれか失敗で `invalid` / `expired`
- 失効は doc 削除で即座に効く（署名鍵のローテーション不要）
- env: `TSUDUMON_INVITE_SECRET`（`functions/.env`。Stripe系と同じ扱い）

漏洩時の被害は「他人の子の学習実績が見える」「他人の子に課金してあげられる」に限定され、
書き込み・トーク閲覧・アカウント乗っ取りには繋がらない。14日で自然に失効する。

---

## 4. Cloud Functions（新規5本）

すべて `asia-northeast1`・CORS・`tsudumonActivate` と同型の作法。Stripe は既存どおり**生fetch**。

### 4-1. `tsudumonInviteCreate` — カード発行（子）

```
POST {idToken}  →  {ok, url, qrUrl, childName, expiresLabel}
```
- 既存カードがあれば削除して再発行（§2-2）
- `parent_link_created` を funnel 記録
- 呼び名が未設定なら `needsName: true` を返し、LINE側で本人に一度だけ聞く（§8）

### 4-2. `tsudumonInviteView` — カードを開く（保護者・未ログイン）

```
POST {t}  →  {ok, childName, childGrade, summary, subscription, alreadyLinked}
```
- `summary` は §6 の表示用サマリ（**会話・解答本文には触れない**）
- 初回のみ `viewedAt` を書き、子へ1通push（`notifiedAt` で二重送信を防ぐ）
- `parent_page_viewed` を funnel 記録

### 4-3. `tsudumonParentCheckout` — 保護者が決済（LINEログイン不要）

```
POST {t}  →  {ok, url} | {ok:false, reason:'already_subscribed'|'expired'|'invalid'}
```
- 既存 `tsudumonCreateCheckout` の**本体を純粋関数に切り出して共有**する
  （`buildTsudumonCheckoutParams(uid, tsudumonRaw, nowMs)` → URLSearchParams）。
  差分は「uid の取り出し方が idToken か token か」だけ。二重実装しない
- `client_reference_id` は**子のuid**（＝webhook は無改修で通る）
- `metadata[paidBy]='parent'` / `subscription_data[metadata][paidBy]='parent'` を追加
- `success_url` は `https://tsudumon.jp/parents/thanks/?t=<t>`（**②連携への導線を置く画面**）
- 体験中の残日数 → `trial_period_days` は既存ロジックをそのまま使う
- **きょうだい価格の判定**（§4-7）。任意の `idToken` を受け取り、保護者が連携済みなら
  2人目以降の価格を使う

### 4-7. きょうだい割引

決済に連携を必須にしない設計の帰結として、**決済時点で「同じ世帯の2人目」と判定できる材料は
連携情報しかない**。そこで割引の条件を連携済みに置く。1人目の摩擦は増えず、2人目で連携する
強い動機が生まれる（割引が連携の報酬になる）。

```
tsudumonParentCheckout(POST {t, idToken?})
  idToken 無し           → 通常価格（1,280円/月）
  idToken 有り & 連携済み → users/{parent}.tsudumonChildren のうち
                            「この子以外」で有効な契約が1件以上あれば 割引価格（980円/月）
```

- **coupon ではなく別 Price を使う**（`STRIPE_TSUDUMON_PRICE_ID_SIBLING`）。請求書と
  Billing Portal に正しい金額が出るため。金額変更は Price ID の差し替えだけで済む
- 判定は `users/{parent}` 1 read のみ（`tsudumonChildren` に契約状態を持たないので、
  **人数ではなく「連携済みの子が他に1人以上いるか」**で判定する。解約済みの子が混ざっても
  割引side に倒れるだけで、利用者に不利にならない）
- 1人目を解約しても、既存サブスクの価格は変えない（Stripe 側で自動更新される値をいじらない）
- **未連携で2人分払った場合の自動調整はしない**。代わりに導線で先回りする:
  - 2人目のカード閲覧画面に「公式LINEでつなぐと2人目から980円になります」
  - `/parents/thanks/` の②導線に同じ文言
  - それでも取りこぼした分は問い合わせで個別対応（スコープ外）

### 4-4. `tsudumonParentLink` — 親子連携の成立（保護者・LINEログイン後）

```
POST {idToken, t}  →  {ok, childName, childCount} | {ok:false, reason}
```
1. `idToken` → 保護者uid（`line:` 必須）
2. token 検証 → `childUid`
3. **自分自身を子として登録しようとしていないか**を弾く（`parentUid === childUid`）
4. 上限チェック（子側の保護者2人 / 親側の子4人）
5. トランザクションで `users/{parent}` と `users/{child}` を同時更新
   - 親: `tsudumonRole='parent'`、`tsudumonChildren` に append（重複はスキップ＝冪等）
   - 子: `tsudumonParents` に append
   - `mergeFields` で対象フィールドだけ書く（既存 `tsudumon` / `blocked` 等に触れない）
6. **保護者用リッチメニューをリンク**（§7-2）
7. 子へ「◯◯さんとつながりました／見えるのは学習の記録だけです」をpush
8. `parent_linked` を funnel 記録

**冪等性が要点**。同じカードを親が2回開いても、きょうだいの2枚目を開いても、正しく積み上がる。

### 4-5. `tsudumonParentDashboard` — 保護者ダッシュボードのデータ

```
POST {idToken}  →  {ok, children: [ChildSummary]}
```
- `users/{parent}` を読み、`tsudumonRole==='parent'` でなければ `403`
- `tsudumonChildren` の uid だけを `doc().get()`（**列挙・検索は一切しない**）
- 返すのは §6 の `ChildSummary` のみ

> **この関数は `aiThreads` / 会話ログ / 記述解答のコレクションを import すらしない。**
> 「レスポンスから削る」のではなく「読む手段を持たない」ことで担保する。
> レビュー時はこの import リストを見れば安全性が判定できる。

### 4-6. 既存の変更

| ファイル | 変更 |
|---|---|
| `tsudumonStripe.ts` | Checkout パラメータ生成を純粋関数へ切り出し。`checkout.session.completed` で `paidBy` を `users/{child}.tsudumon.paidBy` に保存。funnel の `tsudumon_activated` に `paidBy` を付与 |
| `tsudumonDailyUnit.ts` | `ensureTsudumonDaily` と配信対象から `tsudumonRole==='parent'` を除外（**保護者に「今日の1単元」を送らない**） |
| `aiChatPrompt.ts` | つづもんブロックに**保護者モード**を追加（§7-3） |
| `tsudumon/webhook.ts` | postback `tzm_parent_card`（カードを出す）／`tzm_parent_unlink`（子からの解除）を追加 |
| `tsudumonTrialReminder.ts` | day2・day3 の文面にカード導線を追加（§9） |
| 両生成器 TEMPLATE | ロックカードに「おうちの人にお願いする」ボタン（`generate_reference_web.py` / `generate_workbook_web.py`） |

---

## 5. Web ページ（`pdf-workbook/web/` → `dist-web`）

| パス | 中身 |
|---|---|
| `/parents/` | **保護者ページ**。`?t=` があればパーソナライズ、無ければ現行 `lp/parents.html` 相当 |
| `/parents/thanks/` | 決済完了。「②公式LINEで進捗を見る」への導線を主役に置く |
| `/parents/dashboard/` | 保護者ダッシュボード（保護者のLINEログイン） |

既存 `lp/parents.html` は**破棄せず、`/parents/` の下半分としてそのまま使う**（内容は良い）。
上に「文脈＋実績＋結論＋ボタン」を積む構成にする。

### 5-1. `/parents/?t=` の画面構成（上から）

```
┌──────────────────────────────┐
│ お子さん（けんた・中2）から届いています │  ← 文脈。ここが無いと広告に見える
├──────────────────────────────┤
│ 3日間の体験で                          │
│   3日とも学習   2時間14分   問題132問   │  ← 実績。最強の説得材料
│   正答率 71%    進んだ単元 4/19         │
├──────────────────────────────┤
│ 月1,280円（税込）／いつでも解約できます  │  ← 結論3行。ここまでスクロール無しで見える
│ LINEに届くのは1日最大2通です            │
│         [ 登録する ]                    │
│         [ まず中身を見る（無料の1単元）] │
├──────────────────────────────┤
│ 保護者の方に見えるもの / 見えないもの   │  ← 表（§6-2）。子との信頼の担保
├──────────────────────────────┤
│ 既存 parents.html の詳細（料金・解約・  │
│ 通知・AIの安全性・対象・問い合わせ）    │
└──────────────────────────────┘
```

スマホ縦画面で**結論とボタンがファーストビューに入る**ことを受け入れ条件にする（要求 受け入れ条件）。

### 5-2. QRコード

カード画面（子側）に、保護者ページURLのQRを表示する。**外部CDNを使わず自前生成**する
（教材ページは自己完結が原則）。軽量な QR 生成を1ファイル同梱するか、Functions で SVG を返す。
→ **Functions で SVG を返す方式にする**（`tsudumonInviteCreate` が `qrUrl` を返す）。
教材側にライブラリを増やさず、キャッシュも効く。

---

## 6. 保護者に見せるデータ（`ChildSummary`）

### 6-1. 構造

```ts
interface ChildSummary {
  uid: string;            // 画面内の識別のみ。表示しない
  name: string;           // 呼び名
  grade: '中1'|'中2'|'中3';
  plan: {
    state: 'trial' | 'active' | 'expired' | 'none';
    label: string;        // 「体験中（あと1日）」「◯月◯日まで」
    canManage: boolean;   // Billing Portal を出せるか
  };
  study: {
    daysThisWeek: number;      // 直近7日で学習した日数（0-7）
    minutesThisWeek: number;
    minutesTotal: number;
    unitsStarted: number;      // /19
    answered: number;
    accuracy: number;          // %
    lastStudiedLabel: string;  // 「きのう」「3日前」
  };
}
```

すべて `users/{child}.tsudumonProgress`（`tsudumonProgressCore.ts` の `TsudumonProgress`）から算出できる。
**新しい記録の仕組みは要らない。** 既に溜まっているのに使われていないデータを出すだけ。

⚠️ `TsudumonProgress.totals` には「直近7日の学習日数」が無い。`units[].lastAt` からは日付が1点しか
取れないので、**日単位の学習有無を記録する軽量フィールドが1つだけ必要**：
`tsudumonProgress.days: string[]`（`'2026-07-27'` を最大14件・古いものから捨てる）。
`recordTsudumonProgress` の既存トランザクションに相乗りさせる（**追加readゼロ**）。

### 6-2. 見えるもの / 見えないもの（子にも同じ表を見せる）

| | |
|---|---|
| ✅ 見える | 学習した日・時間・進んだ単元・解いた問題数・正答率・契約状態 |
| ❌ 見えない | **つづ先生とのトークの内容**／質問した文章／悩みの相談 |
| ❌ 見えない | 記述問題に書いた答えの本文・AIの講評 |
| ❌ 見えない | **まちがえた問題**（問題文も、まちがいが残っている**件数**も出さない） |
| ❌ 見えない | 本名・学校名・住所（そもそも保存していません） |

> **なぜ「間違えた問題」を件数すら出さないか**（2026-07-27 決定）：出せば保護者は必ず
> 問い詰める材料に使い、子は「間違えると親に見られる」と学習する。すると**わざと簡単な問題
> だけ解く**ようになり、学習データ自体が壊れる。精度の指標は正答率だけに留める。
> `unitsNeedingReview` / `topWrongQids` / `wrongLeft`（`tsudumonProgressCore.ts`）は
> **保護者向けの経路から一切呼ばない**。

---

## 7. LINE 側の設計

### 7-1. 子側：カードの出し方

- postback `tzm_parent_card` → reply で Flex 1枚（**配信枠ゼロ**）
  - 「見える／見えない」の要約2行 → 安心を先に置く
  - ボタン `おうちの人に見せる画面をひらく`（QR＋台本のページ）
  - ボタン `LINEで送る`（保護者ページURLをそのまま転送できる形）
- 台本3種はページ側に置く（Flexに詰め込まない）:
  1. **結果から言う型** … 「3日間ためしてみて、歴史がわかるようになった。続けたい」
  2. **お金から言う型** … 「月1,280円で、いつでもやめられるやつ。まず見てほしい」
  3. **見せるだけ型** … 「これ読んでみて」＋QR（言葉が出ない子の逃げ道。**これが要る**）

### 7-2. 保護者側：リッチメニュー

つづもんBotのリッチメニューは友だち全員に出るため、保護者用を**別に1枚**用意して uid 単位で
リンクする（`scripts/manage-line-richmenu.ts` の `sync-plan` と同じ仕組み）。

| 位置 | 保護者用 |
|---|---|
| 左上 | 📊 学習の記録をみる（→ ダッシュボード） |
| 中上 | 💳 お支払い・解約 |
| 右上 | ❓ よくある質問 |
| 左下 | 👨‍👩‍👧 お子さんの追加 |
| 中下 | 🔔 通知の設定 |
| 右下 | ✉️ 運営に相談する |

### 7-3. 保護者モードのAI（つづ先生）

`aiChatPrompt.ts` のつづもんブロックに `tsudumonRole==='parent'` の分岐を足す。

- 敬語。中学生向けの口調・絵文字を使わない
- 答えてよい: 料金・解約・通知・使い方・安全性・**子の学習記録の要約**（`ChildSummary` の範囲）
- **答えてはいけない**: 子のトーク内容、質問文、悩み、記述解答、間違えた問題。
  聞かれたら「学習の記録はお伝えできますが、お子さまとのやりとりの中身はお見せしない
  約束にしています」と**方針として断る**（できない、ではなく、しない）
- 実装上も、保護者uidのコンテキスト構築で**子の会話を一切ロードしない**（プロンプト任せにしない）

⚠️ 既存 `aiChatPrompt.ts` は「この公式LINEは全機能無料」と断言する箇所がある（CLAUDE.md 既知）。
保護者モードで矛盾しないことを `__tests__/aiChatPrompt.test.ts` に追加する。

### 7-4. 子からの連携解除

「保護者の連携を解除」→ 確認 → `tsudumonParents` / `tsudumonChildren` の双方から削除し、
保護者のリッチメニューを戻す。**課金は止まらない**（支払っているのは保護者なので、解約は
保護者のBilling Portalから）。この点は解除の確認文で正直に伝える。

---

## 8. 呼び名（`tsudumonParentName`）

きょうだいを保護者画面で見分けるために要る。LINEの表示名は本名のことが多く、
**「本名を保存しない」方針（`lp/parents.html` §4）と衝突する**ので流用しない。

→ **カード初回発行時に本人へ一度だけ聞く**（2026-07-27 決定）：「おうちの人の画面では、
なんて表示する？」。既定候補として学年（「中2のこども」）を Quick Reply に出し、
無回答でもそのまま進める。以後は聞かない（`tsudumonParentName` があればスキップ）。
きょうだいが同学年（双子など）の場合は保護者側で見分けられないため、その場合だけ
ダッシュボードから保護者が表示名を編集できるようにする（`tsudumonChildren[].name` のみ変更・
子のドキュメントには書かない）。

---

## 9. 出すタイミング（4か所）の文面方針

| 契機 | 方針 |
|---|---|
| A. 体験2日目の夜 | まだ2日ある＝**断られても余裕がある**ことを言う。「今日じゃなくていい」 |
| B. 期限前日 | 主CTA。実績を先に見せて「これ、見せられるよ」と言う |
| C. 体験終了後のロックカード | 「月額プランに登録」と**並置**（子が自分で払えるケースを塞がない） |
| D. 「親に聞かないと」発言 | AIが察知して1回だけ出す。**繰り返さない**（催促にしない） |

Dの検知は `keywordMatcher` 相当の正規表現で足りる（「親に聞く」「お母さん」「お金」「高い」等）。
AIのツール呼び出しにすると誤爆と遅延が増えるので、**パターン一致＋Quick Reply**にする。

---

## 10. セキュリティ・プライバシーの要点

| 論点 | 対策 |
|---|---|
| URLからuidが割れる | inviteId はランダム。uid を載せない（§3） |
| カードURLが古いトークに残り続ける | 有効期限14日＋再発行で旧docを削除（§2-2） |
| 保護者が他人の子を覗く | 連携は**子が発行したカード経由のみ**。uid指定・検索の口を作らない |
| 保護者が子のトークを読む | ダッシュボードAPIが会話コレクションを**import しない**（§4-5） |
| 子が知らないうちに繋がれる | 連携成立・解除を必ず子へ通知。子はいつでも解除可（§7-4） |
| 一問一答Bot（3,000人）への波及 | 追加フィールドは全て `tsudumon*` 接頭辞。既存フィールド不変（CLAUDE.md 原則3） |
| 保護者が日次配信を受け取る | `tsudumonRole==='parent'` を配信対象から除外（§4-6） |

---

## 11. 実装順序（依存順）

```
フェーズ1  保護者ペイリンク（塞がっている穴を開ける）
  ├ tsudumonInvites コレクション・トークン検証・env
  ├ Checkout パラメータの純粋関数切り出し（既存と共有）
  ├ tsudumonInviteCreate / tsudumonInviteView / tsudumonParentCheckout
  └ /parents/?t= のパーソナライズ ＋ /parents/thanks/

フェーズ2  子側のカード（案内しやすさ）
  ├ 学習日 days[] の記録（recordTsudumonProgress に相乗り）
  ├ postback tzm_parent_card ＋ Flex ＋ QR(SVG)
  ├ 台本ページ ＋「見える/見えない」表
  └ 出す4か所（trialReminder day2/day3・ロックカード・発言検知）

フェーズ3  親子連携（きょうだい対応）
  ├ tsudumonParentLink（冪等・上限・トランザクション）
  ├ きょうだい割引（Price 追加・連携済み判定・導線の文言）
  ├ 保護者用リッチメニュー ＋ 日次配信の除外
  ├ 保護者モードAI（プロンプト分岐＋コンテキスト遮断）
  └ 子からの連携解除

フェーズ4  保護者ダッシュボード
  ├ tsudumonParentDashboard
  ├ /parents/dashboard/（保護者LINEログイン）
  └ 子ごとの Billing Portal

フェーズ5  計測・整合
  ├ funnel: parent_link_created / parent_page_viewed / parent_checkout_started / parent_linked
  ├ tsudumon_activated に paidBy
  └ lp/parents.html・terms・特商法の記述更新（きょうだい料金の判断を反映）
```

フェーズ1だけで**保護者が払える**ようになり、単独で価値が出る。フェーズ2で到達率が上がる。
3・4は継続（解約抑止）に効く。

---

## 12. デプロイ上の注意

- Functions は**必ず名前指定**でデプロイする（本番の一問一答LINEを巻き込まない。CLAUDE.md）
  ```
  firebase deploy --only functions:tsudumonInviteCreate,functions:tsudumonInviteView,\
  functions:tsudumonParentCheckout,functions:tsudumonParentLink,functions:tsudumonParentDashboard,\
  functions:tsudumonStripeWebhook,functions:tsudumonCreateCheckout
  ```
- `TSUDUMON_INVITE_SECRET` と `STRIPE_TSUDUMON_PRICE_ID_SIBLING` を `functions/.env` に
  追加してからデプロイする（きょうだい価格の Price は Stripe 側で先に作成する）
- 教材ページ（両生成器）の再生成 → `--deploy` → `tsudumon.jp` 反映
- **push を伴う変更**（連携通知・閲覧通知・trialReminder）は配信枠を消費するため、
  アーム前にユーザー承認を取る（CLAUDE.md の慣習）

## 13. 参照

- `pdf-workbook/docs/つづもん-登録フロー設計.md` §5〜§8
- `marutto-study/functions/src/tsudumonStripe.ts` / `tsudumonProgressCore.ts` / `tsudumonActivate.ts`
- `marutto-study/functions/src/parentCopy.ts`（保護者向けコピーの鉄則）
- `marutto-study/docs/message-copy-guidelines.md`（文言の正本）
- `marutto-study/CLAUDE.md`（Bot 2本の分離・Firestore read 規律）
