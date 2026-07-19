# Codex 画像ブリーフ：歴史すごろく（つづもん本一覧トップ）

`generate_tsudumon_portal.py` が出力する `/tsudumon/index.html`（歴史すごろく）の
見た目を、CSS/絵文字ベースから「本格的な3Dすごろく盤」に引き上げるための画像。
**画像がなくても現状で完全動作する**（絵文字・CSSで代替済み）。下記は任意の強化用。

出力先: `pdf-workbook/assets/sugoroku/`（生成器に読み込ませるときは img/ へコピー）
形式: PNG（透過）。スマホ幅720px想定なので @2x（幅1440px相当）で作成。

## 1. プレイヤーの駒（marker） … 現在 🧑‍🎓 絵文字
- ファイル: `player.png`（正方形・透過・約120x120@2x）
- 中学生（男女どちらでもない中性的）が「本を持って歩く」かわいいちびキャラ。
- つづもんの既存マスコット（`assets/characters/char_manabi_*.png`, `manabi_*`）の
  トーン（丸っこい・温かみ・茶系アクセント #b45309）に合わせる。
- 影つき（真下に楕円のドロップシャドウ）。

## 2. マスの状態アイコン（badge） … 現在 📖✏️✅👑 絵文字
- `badge-ref.png`（📖 参考書を読んだ）/ `badge-some.png`（✏️ 一部）/
  `badge-all.png`（✅ 全部）/ `badge-perfect.png`（👑 全問正解）
- 各 64x64@2x・透過・フラットで視認性重視。色は index.html の
  --s-ref(#93c5fd)/--s-some(#fcd34d)/--s-all(#86efac)/--s-perfect(#fbbf24) と調和。

## 3. スタート/ゴールの旗 … 現在 🏁🏆 絵文字
- `flag-start.png` / `flag-goal.png`（各 100x100@2x・透過）
- ゴールは「城／日本地図／トロフィー」いずれかで“歴史マスター”らしさ。

## 4. 盤の背景テクスチャ（任意）
- `board-bg.png`（横720@2x・縦タイル可能なシームレス）
- 和紙／古地図風の淡いテクスチャ。文字可読性を落とさない薄さ。

## 反映方法（画像ができたら）
1. `pdf-workbook/assets/sugoroku/` に配置。
2. `generate_tsudumon_portal.py` の TEMPLATE で、絵文字を `<img src="img/...">` に差し替え、
   `generate()` で assets/sugoroku を dest/img へコピーする処理を追加。
3. `python -X utf8 generate_tsudumon_portal.py`（output/web）と `--deploy`（公開用）を再生成。

※ 学年の色分けや snake レイアウト、状態判定ロジックは JS 側で完結しているため、
   画像差し替えは見た目だけの変更で安全。
