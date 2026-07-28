# つづもん 公開前チェックリスト

2026-07-24 監査（LP/法務＋教材本体）の結果と、2026-07-24 決定
「**商品公開は月額プラン（Stripe決済）が整ってから**」を反映した公開前の残作業リスト。
LPの「月額登録できます」系の文言は、公開時点でStripeが動いていれば正しくなるため
書き換えない（ただし↓の整合確認は公開直前に必ず行う）。

## A. Stripe接続時に整合させる（公開の前提）

- [ ] 実装した購入導線と LP の記述が一致することを確認
      （`lp/index.html` CTA/STEP2/FAQ/JSON-LD、`lp/index.html:1622` チャットローカル回答、
      `lp/api/chat.js` ナレッジ「利用開始・解約方法」）
      ※「LINEメニューから登録」「その場で全単元」「いつでも解約」が実装どおりか
- [x] `lp/tokushoho.html` 支払い方法「Stripe決済を予定」→確定表記へ、引き渡し時期の時制統一
      → 2026-07-26 実施（決済代行=Stripe, Inc. と明記／引き渡しは「決済完了後ただちに」）
- [x] 解約導線の実装と特商法・FAQの解約記述の一致
      → 2026-07-26 実施。LPフッターに「アカウント・解約」、価格CTA下に規約・特商法・解約への導線を追加
- [x] **利用規約ページ `lp/terms.html` を新設**（2026-07-26）。LP・特商法・プライバシーの
      フッターから相互リンク。`build-lp.mjs` のコピー対象にも追加済み
      ⚠️ 管轄裁判所は「名古屋地方裁判所岡崎支部」と仮置き。公開前に事業所所在地と整合を確認する
- [x] LP脚注のLINE ID を `@824cebif`（一問一答）→ `@215uijik`（つづもん）に修正（2026-07-26）
- [ ] **LPの「今日やることがLINEに届く」と実装の整合**（日次プッシュは未実装）。
      実装するか表現を変えるかを公開前に決める（`docs/つづもん-登録フロー設計.md` §9 参照）

## B. 公開前に修正（Stripeと無関係・いつでも着手可）

- [x] `lp/privacy.html:65-70` 委託先に Firebase（Google Cloud Platform）を追加
      （あわせてVercelも実際の処理者として追記）
- [x] `lp/privacy.html:54` 利用目的の旧PDF販売文言（購入者名入りPDF）をWeb教材ライセンス方式に更新
- [x] LPソース内TODOコメント削除（GA4手順・お客様の声ダミー注記・実績数値待ち：
      `public/tsudumon/index.html:1048,1382-1406,1492`＝正本は `pdf-workbook/lp/index.html`）
- [x] `twitter:image` メタタグ追加（og:imageと同URL）
- [x] `tsudumon.web.app` 直アクセス対策：chatstudy.jp へのリダイレクト
      （`login/index.html:58` の redirect_uri が未登録URLになりOAuth失敗するため）
      → 2026-07-25 実装。サーバ側 redirect は Vercel プロキシがループするため不可。
      `<meta charset>` 直後のクライアント側1行ガード
      （`location.hostname==='tsudumon.web.app'` のときだけ `chatstudy.jp/tsudumon+path` へ replace）を
      手動管理8ページ＋生成器3種の TEMPLATE に挿入し、再生成→hosting デプロイ済み。
- [x] Vercel 環境変数 `GEMINI_API_KEY` 設定確認（LPチャット）
      → 2026-07-25 本番 `/api/chat/` に実POSTして応答を確認（設定済み・疎通OK）。
      ただし**本番の chat.js は旧版**（3日間体験を知らない）。`marutto-study` を
      commit & push すると Vercel が自動反映するので、公開前に push が必要。

## C. 公開時に判断

- [ ] 利用者の声セクション：実声3件が揃うまでコメントアウト維持（ダミーのまま有効化禁止）
- [ ] GA4 等の計測導入
- [ ] 全19章の教材公開状態の最終確認（ゲート動作・無料単元のみ開放）は
      tasklist.md フェーズ4の実機検証と同時に実施

## 監査でOK確認済み（再確認不要）

価格表記の全箇所整合（1,280円）／学歴表記（東大院まで）／data-lock付与の整合／
noindex／リンク健全性（deploy_tsudumon.py --check エラー0）／シークレット・デバッグ残りなし／
誇大表現・効果保証なし
