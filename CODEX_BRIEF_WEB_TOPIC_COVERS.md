# つづもん トピック単元表紙【Web埋め込み用・コンパクト版】量産ブリーフ（Codex用）

参考書Web版（output/web/ref/{NN}/）の「この単元でわかること」画面に**画像として埋め込む**ための
単元表紙を全92トピックぶん作る。デザインは A4版（covers/out/topics/*.png、
生成元 = `covers/gen_topic_covers.py` ＋ `covers/html/cover.css`）とおそろい。

## ⚠️ 最重要: 縦に長くしない

スマホの最初の画面内に「🎯この単元でわかること」まで収まる必要がある。
- キャンバス: **幅900px × 高さ990px（縦横比 1.1 以下厳守）**
- そのために A4版から: 波形オレンジ帯（フッター）を**削除**、写真カードの高さを**340px程度に圧縮**、
  余白を詰める
- 「わかること」リストは必ず画像内に全文が入る（切れ・はみ出し禁止）

## 作るもの

1. **生成スクリプト** `covers/gen_web_topic_covers.py`
   - `covers/gen_topic_covers.py` と同様に reference/{章}.json 全19冊を読む
   - `covers/html/webtopics/{章番号}-{topicId}.html` を生成（共有 `cover.css` ＋ Web版用の追加クラス。
     既存の unit-02 / topics の見た目を壊さない）
   - Edge ヘッドレス `--screenshot` `--window-size=900,990` で PNG 出力
   - **Pillow で WebP（quality 82 前後）に変換**して `covers/out/webtopics/{章番号}-{topicId}.webp` に保存
     （ページに8枚埋め込むため軽さ必須。Pillow が無ければ `pip install pillow`）
2. **全92トピックの .webp**（PNG は中間生成物。残してよい）

## レイアウト（上から。フォントは A4版より相対的に大きく＝スマホ縮小表示でも読めるように）

1. ヘッダー行: 角丸バッジ「歴史 ④」＋ トピック名（太字・大きく）＋ 小さく「{章タイトル}／単元{n}」
2. 写真カード: `assets/reference/{t.image}`。マスキングテープ2枚＋少し傾き（奇数 -2deg/偶数 +2deg）、
   幅ほぼいっぱい × **高さ340px**（object-fit: cover）
3. 🎯この単元でわかること: 白カード・オレンジ枠・オレンジ丸番号＋点線区切り。
   本文フォント **28px以上**。右端にマスコット `assets/characters/manabi_banzai.png` 小さめ（110px程度）＋
   吹き出し「この単元もがんばろう！」を縦に添える（A4版の learn-side と同様の構成を小さく）
4. 背景: クリーム地＋水玉＋ごく薄い特大単元番号（A4版と同じ雰囲気）。外枠の茶色角丸ボーダーも同様

## 完了条件

- `covers/out/webtopics/` に .webp 92枚（各 250KB 以下目安）
- サンプル目視: `01-time-periods` と `04-taika-reform` を必ず確認
  （わかること全文が画像内に収まっている／日本語崩れなし／縦横比 900:990）
- 完了したら「生成枚数と、上記サンプル2枚のパス」のみ出力して終了
