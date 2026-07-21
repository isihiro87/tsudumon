# 設計書

## アーキテクチャ概要

既存の `generate_reference_web.py`（reference JSON → 単一 index.html のステップ型プレイヤー）に、
section 単位の横帯画像レンダリングを追加する。データ拡張は section への `image`/`imageCaption` の追加のみ。

```
reference/04-ancient-state.json (section に image/imageCaption 追加)
        │
        ▼
generate_reference_web.py  ── build() の section ループで <figure class="sec-fig"> を本文の上に出力
        │                     use_img() が assets/reference/ から img/ へコピー
        ▼
tsudumon/ref/04/index.html + img/*.webp
```

## コンポーネント設計

### 1. データ層（reference/04-ancient-state.json）

**責務**: 各 section にどの画像を出すかを保持
- `section.image`: `assets/reference/` 配下のファイル名（例 `hist04-sec-kenzuishi.webp`）
- `section.imageCaption`: 任意。無ければ省略

**要点**: topic の既存 `image`/`imageCaption` と同じ命名。PDF生成側は section.image を参照しないので無害。

### 2. レンダリング層（generate_reference_web.py）

**責務**: section ステップの本文上に横帯画像を出す
- section ループ内で `use_img(s.get("image",""))` を呼ぶ（既存 use_img を再利用＝img/へコピー＆パス返却）
- 画像があれば `<figure class="sec-fig"><img loading="lazy"><figcaption?></figure>` を heading の直後・本文(lead/p)の前に挿入
- 画像が無ければ何も出さない（後方互換）

**要点**:
- 既存の step テンプレート文字列に `{sec_fig}` を差し込むだけ。CSS `.sec-fig` を TEMPLATE に追加。
- 横帯＝フル幅・角丸・上下マージン。高さは `aspect-ratio` で頭打ちにし縦長画像でも崩れない。

### 3. 画像素材

**実物写真（PD/CC0/CC BY・既存 assets 再利用）**:
- `horyuji.jpg`（法隆寺）/ `daibutsu.jpg`（大仏）/ `shosoin.jpg`（正倉院）/ `byodoin.jpg`（平等院鳳凰堂）

**既存の図版（再利用）**:
- `ritsuryo-central-org.webp`（律令の中央官制）/ `handen-shuju-cycle.webp`（班田収授のしくみ）

**codex（image-2）オリジナル生成**（`assets/reference/hist04-sec-*.webp`・約18枚）:
- 人物・シーン・概念図。トーンは既存ヒーローと同じ「やわらかい水彩調フラットイラスト」。
- 日本語ラベルが要る図（白村江の地図・摂関政治の外戚関係図）は image-2 の日本語生成を使う。
- 生成フロー: codex が PNG を `~/.codex/generated_images/` に作る → 指定パスに copy → cwebp で .webp 化。

## データフロー（生成）

```
1. codex exec でブリーフ（表: 出力名×内容）を渡し、18枚を tmp/gen/*.png に生成
2. cwebp で assets/reference/hist04-sec-*.webp に変換
3. 04-ancient-state.json の各 section に image/imageCaption を追記
4. python generate_reference_web.py --deploy 04（or 既定の生成）→ tsudumon/ref/04/
5. ブラウザで目視確認
```

## ディレクトリ構造（追加・変更）

```
pdf-workbook/
  generate_reference_web.py            # 変更: section 横帯画像レンダリング + CSS
  reference/04-ancient-state.json      # 変更: section に image/imageCaption
  assets/reference/hist04-sec-*.webp   # 追加: codex生成の節画像
  assets/credits.json                  # 変更: 実物写真の出典（既に horyuji等あり）
  .steering/20260721-reference-web-illustrations/  # 本計画
```

## 実装の順序

1. generate_reference_web.py に section 横帯画像レンダリング + CSS を追加
2. 既存 assets を使って歴史④の一部 section に image を付け、レイアウトを目視検証
3. codex で残りの節画像を生成 → webp 化
4. 全 section に image/imageCaption を付与
5. 再生成 → 全ステップ目視確認

## パフォーマンス考慮事項

- `loading="lazy"` で初期表示を軽く。webp で軽量化。
- section 画像は横帯だが `max-height` 相当（aspect-ratio）で読み込み量を抑える。

## 将来の拡張性

- 同じ section.image 方式で歴史①〜⑲へ横展開可能。PDF版に出したくなった場合も
  generate_reference_book.py の section ループに同処理を足すだけ。
