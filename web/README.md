# `web/` — 手書きで管理する静的ページの正本

ジェネレータ（`generate_*.py`）が生成しないページの**正本**を置く場所。
ビルド時に `dist-web/` へそのままコピーされ、Firebase Hosting（site: `tsudumon`）で配信される。

> 2026-07-25 のドメイン独立作業（`.steering/20260725-tsudumon-domain-independence/`）で、
> `marutto-study/public/tsudumon/` 配下にしか存在しなかったものをここへ移設した。
> 以前は marutto-study リポジトリ内で直接編集されており、pdf-workbook 側に正本が無かった。

## 中身

| パス | 役割 | 備考 |
|---|---|---|
| `login/index.html` | 教材ページ共通のログイン画面 | `?next=` を受けて LINE Login OAuth を完結させ、元のページへ戻す |
| `activate/index.html` | ライセンスコードの受け取り・有効化 | `tsudumonActivate` Function を叩く |
| `account/index.html` | 支払い・解約の管理 | Stripe Billing Portal へ遷移 |
| `_healthz.txt` | 死活確認用のテキスト | Firebase Hosting が生きているかの確認に使う |

## 🔴 LINE Console に登録が必要なコールバックURL

`login/` と `activate/` は**それぞれ別の** `REDIRECT_URI` を持ち、
どちらも LINE Developers Console の LINEログインチャネル（`2009587166`）に
コールバックURLとして登録されている必要がある。

| ページ | REDIRECT_URI |
|---|---|
| `login/index.html` | `https://tsudumon.jp/login/` |
| `activate/index.html` | `https://tsudumon.jp/activate/` |

移行の猶予期間中は、旧URL（`https://www.chatstudy.jp/tsudumon/login/` /
`.../activate/`）も**登録したまま残す**こと。301リダイレクトを追う既存ユーザーの保険になる。

## 編集時の注意

- 各ファイル先頭のホスト名ガードは、`tsudumon.web.app` に直接来た人を正規ドメインへ
  逃がすためのもの。**LINE の Callback URL と一致するホストへ寄せる**目的なので、
  ドメインを変えるときは必ずこの1行と LINE Console の両方を同時に直す。
- `login/` の `getNext()` はオープンリダイレクト防止のため戻り先を検証している。
  パス構成を変えるときにこの検証を緩めないこと。
- Firebase の APIキー等が直書きされているが、これはクライアント公開前提の値
  （Firebase Web SDK の設定）であり秘匿情報ではない。
