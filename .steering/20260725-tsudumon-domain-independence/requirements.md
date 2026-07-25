# 要求内容

## 概要

つづもんの配信経路を `www.chatstudy.jp/tsudumon/`（Vercelプロキシ経由）から、
独自ドメイン `tsudumon.jp` による Firebase Hosting 直配信へ移行し、
chatstudy.jp（Vercelプロジェクト・ドメイン）への依存を配信面から取り除く。

## 背景

### なぜ必要か

- chatstudy.jp（チャットでスタディ）は**今後ほぼ使う予定がない**別サービス。
  にもかかわらず、つづもんの全ページが `chatstudy.jp/tsudumon/*` という
  Vercelプロキシ経由でしか到達できず、**chatstudy.jpのVercelプロジェクトや
  ドメインを止めるとつづもんが同時に死ぬ**状態にある。
- つづもんは月額1,280円の有料サブスク商品であり、
  「使う予定のない別サービスのドメインに間借りしている」状態は事業リスク。
- 公式LINEについては既に分離が進行中
  （`marutto-study/.steering/20260725-tsudumon-dedicated-line-bot/`、
  `docs/つづもん-公式LINE分離移行手順.md`）。本件はその「配信面」版にあたり、
  同じ独立化の方向性に沿う。

### 現状の構成（調査結果・2026-07-25）

```
ブラウザ
  → Vercel (chatstudy.jp プロジェクト)
      vercel.json rewrites: /tsudumon/(.*) → https://tsudumon.web.app/$1
  → Firebase Hosting site "tsudumon" (project: chatstudy-63477)
      public: marutto-study/public/tsudumon/
```

- コンテンツの実体は**すでに Firebase Hosting 上にある**。Vercelは転送のみ。
- バックエンド（Cloud Functions・Firebase Auth）はVercelを経由せず直接呼ばれている
  （例: `activate/index.html` は `cloudfunctions.net/tsudumonActivate` を直叩き）。
- **ただし1つだけVercel固有の機能がある**: LPのAIチャット `/api/chat` は
  Vercel Serverless Function（`marutto-study/api/chat.js` ← `pdf-workbook/lp/api/chat.js`）。
  Firebase Hosting は静的配信のみのため、**これは Cloud Function への移植が必須**。

### ドメイン

- `tsudumon.jp` 取得済み（レジストラ: お名前.com）。

## 実装対象の機能

### 1. ビルド成果物の出力先を pdf-workbook 配下へ移す

- `deploy_tsudumon.py` / `lp/deploy-to-chatstudy.mjs` の出力先を
  `marutto-study/public/tsudumon/` から `pdf-workbook/dist-web/` へ変更する。
- つづもんの成果物が marutto-study リポジトリにコミットされない状態にする。

### 2. pdf-workbook 単独でデプロイできるようにする

- `pdf-workbook/firebase.json` / `.firebaserc` を新設し、
  `firebase deploy --only hosting:tsudumon` を pdf-workbook ディレクトリから実行できる。
- Functions定義は含めない（Functionsは引き続き marutto-study 側が正本）。

### 3. LPチャットAPIの Cloud Function 化

- `lp/api/chat.js`（Vercel関数）を Firebase Cloud Function として移植する。
- Firebase Hosting の rewrite で `/api/chat` から呼べるようにし、
  LPのフロント側は**呼び出しURLを変えずに**動作する。

### 4. ドメイン依存箇所の書き換え

- ホスト名ガード（`if(location.hostname==='tsudumon.web.app'){location.replace('https://www.chatstudy.jp/tsudumon'+...)}`）を
  新ドメイン前提に修正する。生成元は3ジェネレータ＋LP静的3ページ。
- `/tsudumon/` プレフィックス前提の絶対パス・絶対URLを新ドメインの構成に合わせる。
- `/welcome`（chatstudy SPAのログイン画面）依存を、つづもん自前の `/login/` へ切り替える。

### 5. LINE Login Callback URL の更新

- LINE Developers Console のコールバックURLに新ドメインを登録する
  （現状 `https://www.chatstudy.jp/tsudumon/login/` 前提で、ホスト名ガードもそのために存在する）。

### 6. 旧URLからのリダイレクト維持

- 配布済みPDF・印刷物・過去のLINEメッセージが `chatstudy.jp/tsudumon/*` を指しているため、
  chatstudy.jp 側に **301リダイレクト**を残す。

## 受け入れ条件

### 配信の独立
- [ ] `https://tsudumon.jp/` でLPが表示される（SSL証明書が有効）
- [ ] `https://tsudumon.jp/wb/01/` `https://tsudumon.jp/ref/01/` `https://tsudumon.jp/map/` が表示される
- [ ] 上記ページ内のリンク（単元一覧へもどる等）がすべて新ドメイン内で完結する
- [ ] Vercel（chatstudy.jp）を停止した状態を想定しても、上記が成立する構成になっている

### 機能維持
- [ ] LPのAIチャットが新ドメインで応答する（Cloud Function経由）
- [ ] LINEログインが新ドメインで完了し、元のページへ戻る
- [ ] ライセンス有効化（`/activate/`）が動作する
- [ ] PDFダウンロード（`/dl`）が動作する
- [ ] 記述問題のAI採点・参考書のAI質問が動作する

### 移行の安全性
- [ ] `chatstudy.jp/tsudumon/*` へのアクセスが新ドメインの対応パスへ301される
- [ ] 配布済みPDFのQRから起動するLIFF経路が壊れていない
- [ ] chatstudy.jp 側の www / typing / mubista に影響がない

## 成功指標

- chatstudy.jp のVercelプロジェクトを削除しても、つづもんが単独で稼働する状態になること。
- `marutto-study/public/tsudumon/` および `marutto-study/api/chat.js` が不要になること。

## スコープ外

以下はこのフェーズでは**実装しません**:

- **Firebaseプロジェクトの分離**（`chatstudy-63477` は共有のまま）。
  Auth UID・Firestore・Stripe顧客の移行が必要でコストが見合わない。
- **Cloud Functions の別プロジェクト移設**（`tsudumonActivate` 等は marutto-study 側が正本のまま）。
- **公式LINEアカウントの分離**（別ステアリング
  `marutto-study/.steering/20260725-tsudumon-dedicated-line-bot/` が担当）。
- **LIFF の変更**（`docs/つづもん-公式LINE分離移行手順.md` 章2で「変更しない」と決定済み）。
- ムビスタ（`chatstudy.jp/mubista`）・typing の移設。

## 参照ドキュメント

- `docs/つづもん-公式LINE分離移行手順.md` - 公式LINE分離の正本
- `docs/つづもん-登録フロー設計.md` - LINEファースト登録フロー
- `.steering/20260724-tsudumon-flow-overhaul/` - ゲート基盤・自動ログイン・無料お試し
- `marutto-study/.steering/20260725-tsudumon-dedicated-line-bot/` - 専用Bot実装（**進行中・要調整**）
