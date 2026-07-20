# Codex 実装計画書：歴史クエスト（スマホ縦長）

## ▼ 実装ずみ（2026-07-20）— 計画との差分

この計画にもとづく実装は `generate_tsudumon_portal.py` に入っている。以下は計画から変わった点。

- **名前**: 「宝探しマップで」は付けない。タイトルは **「歴史クエスト」** のみ。
- **ごほうび機能はなし**（実物が未用意のため）。「次のごほうびまで」「ごほうび一覧」ボタン、
  「見つけた宝」カウントは作らない。冒険のきろくは
  **クリアマス数／集めたスタンプ／全問正解** の3つ。
- **学年ごとに独立したマップ**にした。中1＝章01〜06、中2＝07〜12、中3＝13〜19。
  マスの番号・進捗バーの分母・冒険のきろくは、すべて「いま選んでいる学年の中で」数える。
- **登録学年は配布URLのパラメータ**で渡す（`?g=1,2` / `?g=中1` / `?g=all`）。
  受け取ると `localStorage['tzmgrades']` に保存されるので2回目以降はパラメータ不要。
  **2学年以上のときだけ**上部に学年タブが出る（1学年ならタブなし）。
  いま見ている学年は `localStorage['tzmgrade']`、今日のミッションは `tzmportal-{学年}`。
- **島は背景画像**（`.era` の `background-image`）として敷き、マス丸・番号はすべてDOM。
  座標JSONは作らず、既存の snake 配置（`--row` / `--span`）をそのまま使った。
  島の絵は **中央20〜90%を淡い空き地にして、飾りを上端と左右のふちへ寄せる** 条件で生成する
  （その上にマスが乗るため）。道・点線・数字は絵に描かせない＝CSSの点線で描く。
- **マップは1行8マス・単元名なし**（カンプと同じ密度）。単元名は下の「単元一覧」で見せる。
- **「スタート」ボタンは置かない**（押せる先が無く飾りになるため）。ゴールは宝箱の
  横並びパネル1つに圧縮。
- 一覧の見出しは **「単元一覧」**（「本の一覧」ではない）。開閉アコーディオンはやめ、
  章の帯（冒険N）＋単元行をそのまま並べる。1行＝番号／単元名／状態／問題／参考書。
- **画像は WebP で配信**。`assets/quest/*.png`（Codex生成の原本）を
  `python -X utf8 tools/quest_assets_to_webp.py` で `.webp` 化し、
  `copy_assets()` は `.webp` だけを `img/` へ配る。合計 12.7MB → 0.55MB。
- 生成ずみアセット: `quest-bg` / `quest-title` / `quest-explorer` / `quest-bird` /
  `quest-chest` / `quest-island-{ancient,medieval,earlymod,modern,current}` /
  `quest-badge-{ref,some,all,perfect}`。
  どれも欠けてもCSSだけで成立する（`img` は `onerror` で消え、背景は色にフォールバック）。

以下は元の計画書。画像プロンプトや注意点は引き続き有効。

---

対象カンプ: `pdf-workbook/assets/quest/quest-top-mobile.png`（1024x1536）

`generate_tsudumon_portal.py` が出力する `/tsudumon/index.html` を、添付カンプの「宝探しマップで歴史クエスト」スマホ縦長デザインへ置き換えるための実装計画。ここでは **コード実装はしない**。画像生成・HTML/CSS/JS差し替え・データ接続の作業指示だけを定義する。

既存仕様の確認結果:
- 生成器: `pdf-workbook/generate_tsudumon_portal.py`
- 履歴データ: `books/*.json` の歴史19章、全92単元
- 現在の状態保存: `localStorage` の `tzmwb-{NN}` / `tzmref-{NN}` / `tzmportal`
- 既存キャラ: `char_manabi.png`, `char_manabi_sm.png`, `char_neko.png`, `char_neko_sm.png`, `char_owl.png`, `char_owl_sm.png`, `char_pencil.png`, `char_pencil_sm.png`, `manabi_banzai.png`, `manabi_banzai_sm.png`, `manabi_ok.png`, `manabi_ok_sm.png`, `manabi_point.png`, `manabi_point_sm.png`, `manabi_think.png`, `manabi_think_sm.png`, `owl_think.png`, `owl_think_sm.png`

## 1. 全体方針

イラスト部分は画像アセット（Codex の `image_generation` で生成）にする。UI・状態・テキストは HTML + CSS + JS で描画する。

カンプは1枚絵に見えるが、進捗、マス状態、スタンプ、クリア数、一覧、遷移先がユーザーごとに変わる。静的な1枚画像として実装しない。テキスト検索性、可読性、画面読み上げ、ボタン操作、既存 `localStorage` との連動を維持するため、文字と状態はDOMで持つ。

| カンプのパーツ | 画像にするもの | DOM/CSS/JSにするもの | 理由 |
|---|---|---|---|
| 画面全体の羊皮紙 | 縦タイル可能な背景テクスチャ | 外枠、余白、最大幅 | 軽量化しつつ縦伸びに対応 |
| ヘッダー装飾 | 地図紙、方位磁針、小物、左右キャラ | タイトル文字、サブコピー、吹き出し文字 | 文字の鮮明さと差し替えやすさ |
| 進捗パネル | 巻物/羊皮紙枠の9スライス | `クリア 3 / 92 マス (3%)`、進捗バー | ユーザー状態で変わる |
| 凡例 | 必要なら状態アイコン | 凡例ラベル、横罫線、配置 | テキスト可読性を優先 |
| マップ島4種 | 島の背景イラスト、海、建物、道の下絵 | マス丸、状態バッジ、番号、時代ラベル | 92単元の状態を反映するため |
| スタート/ゴール | 旗、船、光る宝箱 | クリック不可の装飾位置 | 視覚演出のみ |
| 本の一覧 | 見出し巻物枠、一覧外枠 | 章・単元名、問題/参考書ボタン、スタンプ丸 | 実データとリンク先が必要 |
| 冒険のきろく | 巻物パネル枠、左右キャラ | クリア数、スタンプ数、宝数、あとNマス | 動的集計が必要 |
| ごほうび一覧ボタン | 必要なら王冠アイコン | ボタン本体、ラベル、遷移 | a11yと押下状態のため |

カンプ上の島マップには30個の大きな丸が描かれているが、既存生成器の実データは全92単元である。実装では **全92単元を進捗単位として維持**し、表示は次のどちらかを選ぶ。

- 推奨: 92単元を小さめの絶対配置マスとして全表示する。カンプの「クリア 3 / 92 マス」と完全に一致する。
- 代替: カンプと同じ30ノードを「章/区間の代表ノード」として表示し、内部に92単元を紐づける。ただしタップ先が曖昧になるため、今回の実装では採用しない。

## 2. 生成すべき画像アセット一覧

出力先は `pdf-workbook/assets/quest/`。生成後、`generate_tsudumon_portal.py` の `copy_assets()` で `dest/img/` にコピーする。形式は原則 PNG。背景島は容量を見て WebP 変換してよいが、マス丸と文字は焼き込まない。

共通スタイル指定は各プロンプト末尾に必ず付ける:

```text
手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG
```

| ファイル名 | 用途 | サイズ(@2x) | 透過 | 生成用プロンプト |
|---|---:|---:|---|---|
| `quest-paper-tile.png` | body背景。左右の淡い古地図模様 | 720x720 | なし | 中学生向け歴史クエスト画面の背景に使う、薄い羊皮紙テクスチャ。縦横に自然につながるシームレスパターン。薄いコンパス、地図線、星、宝箱の輪郭を低コントラストで散らす。画面上の文字を邪魔しない淡さ。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし |
| `quest-shell-scroll-9.png` | 画面全体の内側羊皮紙。9スライス | 1440x2200 | あり | スマホ縦長のWebページ外枠に使う大きな羊皮紙の巻物フレーム。四隅は少し丸まり、端は焦げ茶の手描き線、内側は薄いベージュ。中央は空白でUIを載せる。上下左右を9スライスで伸ばしても破綻しない均一な縁。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-panel-scroll-9.png` | 進捗・凡例・記録パネルの9スライス | 1120x280 | あり | 横長UIパネル用の羊皮紙巻物フレーム。中央は淡い紙で空白、左右端に少し巻いた紙、細い茶色の縁取り。9スライスで横にも縦にも伸ばせる。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-heading-scroll-9.png` | 「本の一覧」「冒険のきろく」見出し | 900x160 | あり | 見出し用の小さな巻物リボン。中央は文字を置ける空白、左右が少し巻かれた羊皮紙、羽ペンや本の小さな飾りは端だけに配置。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-island-ancient.png` | 原始・古代 1〜8 周辺の島背景 | 1440x360 | あり | 横長の小島。上部に森、鹿、古代の竪穴住居、古墳、神社風の小さな建物、右側に海岸と岩。中央に白い点線の道をうっすら入れるが、丸いマスと番号は入れない。上にDOMのマスを重ねやすい余白を残す。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-island-medieval.png` | 中世 9〜16 周辺の島背景 | 1440x360 | あり | 横長の桜の島。左に鎧武者、中央に山道と桜、右に日本の城。海に囲まれた中世の島。白い点線の道だけ薄く入れ、丸いマスと番号は入れない。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-island-earlymodern.png` | 近世 17〜24 周辺の島背景 | 1440x330 | あり | 横長の南国風の島。中央に江戸時代の町、港、帆船、城、ヤシの木、穏やかな海。白い点線の道だけ薄く入れ、丸いマスと番号は入れない。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-island-modern.png` | 近代・現代 25〜30/92 終盤の島背景 | 1440x360 | あり | 横長の近代から現代の島。左に黒い蒸気機関車、中央に工場と煙突、右に明るい近代都市への道。紫がかった岩場と草地。白い点線の道だけ薄く入れ、丸いマスと番号は入れない。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-ocean-band.png` | 島間の海の帯。必要なら背景合成用 | 1440x280 | あり | 手描き水彩の明るい青い海。小さな波、泡、遠くの小舟を少しだけ配置。上下を島画像と重ねても自然につながる。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-sign-ancient.png` | 木の看板 原始・古代 | 420x150 | あり | 木製の時代ラベル看板。板2枚、ロープ、葉の飾り。中央は文字をDOMで載せるため空白。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-sign-medieval.png` | 木の看板 中世 | 420x150 | あり | 木製の時代ラベル看板。少し濃い茶色、和風の飾り紐、桜の花びらを端に少し。中央は空白。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-sign-earlymodern.png` | 木の看板 近世 | 420x150 | あり | 木製の時代ラベル看板。港町風、小さな波と帆船の飾り。中央は空白。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-sign-modern.png` | 木の看板 近代・現代 | 420x150 | あり | 木製の時代ラベル看板。端に小さな歯車と線路の飾り。中央は空白。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-flag-start.png` | スタート旗 | 360x180 | あり | 赤いリボン旗と小さな旗竿。スマホ画面の地図左上に置くスタート装飾。中央に文字をDOMで重ねるので文字なし。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-flag-goal.png` | ゴール旗 | 360x180 | あり | 赤いリボン旗と金色のきらめき。宝箱のそばに置くゴール装飾。中央に文字をDOMで重ねるので文字なし。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-treasure-glow.png` | ゴールの光る宝箱 | 420x300 | あり | 金貨の山に置かれた大きな宝箱。宝箱が開きかけ、周囲に星のきらめき。教材アプリのゴール報酬らしく明るい。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-char-book-boat.png` | 探検帽の本キャラ。ヘッダー左/スタート横 | 420x420 | あり | コルク色の本のキャラクターが探検帽をかぶり、小さな木の船に乗って手を振っている。旗とリュックつき。表情は元気。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-char-treasure.png` | 冒険のきろく左下 | 320x320 | あり | 宝箱のキャラクター。金貨が入った宝箱に顔と手足があり、探検帽をかぶって歩いている。かわいい教材マスコット。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-char-bird-compass.png` | ヘッダー右のコンパス鳥 | 360x360 | あり | 白い小鳥のキャラクターが探検帽をかぶり、丸いコンパスを持っている。歴史クエストの案内役。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-char-scroll-guide.png` | 冒険のきろく右下 | 320x320 | あり | 巻物の紙キャラクター。緑の探検帽、リュック、指し棒を持って案内している。笑顔。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-badge-none.png` | 未状態 | 96x96 | あり | 白い空の四角チェック枠。未着手を示すシンプルな教材UIアイコン。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-badge-ref.png` | 参考書を読んだ | 96x96 | あり | 青い開いた本のアイコン。参考書を読んだ状態を示す。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-badge-some.png` | 一部を解いた | 96x96 | あり | オレンジ色の鉛筆アイコン。問題を一部解いた状態を示す。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-badge-all.png` | 全部解いた | 96x96 | あり | 緑のチェックマークアイコン。全部解いた状態を示す。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |
| `quest-badge-perfect.png` | 全問正解 | 96x96 | あり | 金色の王冠アイコン。全問正解を示す。手描き水彩イラスト、古地図風、羊皮紙の温かい質感、子ども向け教材、線は濃い茶色、配色は #f5e6c8 / #8b5a2b / #b45309 を基調、明るく清潔、影なし、文字なし、記号なし、UIテキストなし、透過PNG |

ボタン素材は原則不要。`ごほうび一覧` ボタンは青いCSSグラデーション、角丸、王冠アイコン画像または既存バッジを使う。テキストを画像化しないため、押下状態・フォーカスリング・a11yを保てる。

## 3. HTML構造

生成後の `TEMPLATE` は、既存の `__TOTAL__`, `__CELLS__`, `__BOOKS__`, `__ERAS__`, `__MANIFEST__` の置換方式を残しつつ、見た目用のセクションをカンプ順に組む。

```html
<body class="quest-page">
  <main class="quest-shell" aria-label="宝探しマップで歴史クエスト">
    <header class="quest-hero">
      <img class="quest-hero__book" src="img/quest-char-book-boat.png" alt="">
      <div class="quest-hero__title">
        <p class="quest-hero__eyebrow">宝探しマップで</p>
        <h1>歴史クエスト</h1>
        <p class="quest-hero__ribbon">中学歴史の冒険に出発しよう！</p>
      </div>
      <div class="quest-hero__bubble">
        <p>歴史の宝を集めて<br>日本の歴史を制覇しよう！</p>
        <strong>「問題」でクイズに挑戦だ！</strong>
      </div>
      <img class="quest-hero__bird" src="img/quest-char-bird-compass.png" alt="">
    </header>

    <section class="quest-progress" aria-labelledby="quest-progress-title">
      <h2 id="quest-progress-title">あなたの冒険の進み具合</h2>
      <p><span id="clearCount">0</span> / <span id="totalCount">__TOTAL__</span> マス <span id="clearPct">(0%)</span></p>
      <div class="progressbar" role="progressbar" aria-valuemin="0" aria-valuemax="__TOTAL__" aria-valuenow="0">
        <span id="progressFill"></span>
      </div>
    </section>

    <section class="quest-legend" aria-label="状態の説明">
      <span class="legend-item"><img src="img/quest-badge-none.png" alt="">まだ</span>
      <span class="legend-item"><img src="img/quest-badge-ref.png" alt="">参考書を読んだ</span>
      <span class="legend-item"><img src="img/quest-badge-some.png" alt="">一部を解いた</span>
      <span class="legend-item"><img src="img/quest-badge-all.png" alt="">全部解いた</span>
      <span class="legend-item"><img src="img/quest-badge-perfect.png" alt="">全問正解</span>
    </section>

    <section class="quest-map" aria-label="歴史クエストマップ">
      <div class="map-start">
        <img src="img/quest-flag-start.png" alt="">
        <span>スタート!</span>
      </div>

      <section class="map-island island-ancient" data-era="ancient" aria-labelledby="era-ancient-title">
        <img class="island-bg" src="img/quest-island-ancient.png" alt="">
        <h2 id="era-ancient-title" class="era-sign">原始・古代 <small>1〜17</small></h2>
        <div class="map-cells" data-era-cells="ancient"></div>
      </section>

      <section class="map-island island-medieval" data-era="medieval" aria-labelledby="era-medieval-title">
        <img class="island-bg" src="img/quest-island-medieval.png" alt="">
        <h2 id="era-medieval-title" class="era-sign">中世 <small>18〜30</small></h2>
        <div class="map-cells" data-era-cells="medieval"></div>
      </section>

      <section class="map-island island-earlymodern" data-era="earlymod" aria-labelledby="era-earlymod-title">
        <img class="island-bg" src="img/quest-island-earlymodern.png" alt="">
        <h2 id="era-earlymod-title" class="era-sign">近世 <small>31〜56</small></h2>
        <div class="map-cells" data-era-cells="earlymod"></div>
      </section>

      <section class="map-island island-modern" data-era="modern-current" aria-labelledby="era-modern-title">
        <img class="island-bg" src="img/quest-island-modern.png" alt="">
        <h2 id="era-modern-title" class="era-sign">近代・現代 <small>57〜92</small></h2>
        <div class="map-cells" data-era-cells="modern"></div>
        <div class="map-goal">
          <img src="img/quest-flag-goal.png" alt="">
          <img src="img/quest-treasure-glow.png" alt="">
          <span>ゴール!</span>
        </div>
      </section>
    </section>

    <section class="quest-books" aria-labelledby="quest-books-title">
      <h2 id="quest-books-title">本の一覧（冒険の書）</h2>
      <div class="books-table">
        __BOOKS__
      </div>
    </section>

    <section class="quest-record" aria-labelledby="quest-record-title">
      <img class="record-char record-char--left" src="img/quest-char-treasure.png" alt="">
      <h2 id="quest-record-title">冒険のきろく</h2>
      <dl>
        <div><dt>クリアマス数</dt><dd><span id="recordClear">0</span> / __TOTAL__ マス</dd></div>
        <div><dt>集めたスタンプ</dt><dd><span id="recordStamps">0</span> 個</dd></div>
        <div><dt>見つけた宝</dt><dd><span id="recordTreasures">0</span> 個</dd></div>
        <div><dt>次のごほうびまで</dt><dd>あと <span id="nextReward">0</span> マス!</dd></div>
      </dl>
      <button class="reward-button" type="button" id="rewardButton">ごほうび一覧</button>
      <img class="record-char record-char--right" src="img/quest-char-scroll-guide.png" alt="">
    </section>

    <div id="cellSource" hidden>__CELLS__</div>
  </main>
</body>
```

## 4. CSS設計

基準はスマホ幅390px。`max-width: 720px` で中央寄せする。カンプ画像は1024px幅だが、実装はスマホ実機での読みやすさを優先し、CSSピクセルでは390px基準、画像は@2x以上で用意する。

```css
:root {
  --paper: #f5e6c8;
  --paper-light: #fff4d9;
  --ink: #3f2413;
  --brown: #8b5a2b;
  --brand: #b45309;
  --gold: #f7b718;
  --line: #d6a85b;
  --sea: #58b9d0;
  --s-none: #ffffff;
  --s-ref: #8ec5f4;
  --s-some: #f2a23a;
  --s-all: #55bf6b;
  --s-perfect: #f6c431;
  --shell-w: min(100vw, 720px);
}

body {
  margin: 0;
  color: var(--ink);
  background: #f5e6c8 url("img/quest-paper-tile.png") repeat-y top center / min(720px, 100vw) auto;
  font-family: "Zen Maru Gothic", "M PLUS Rounded 1c", "Hiragino Maru Gothic ProN", "Yu Gothic", sans-serif;
}

.quest-shell {
  width: min(100vw - 16px, 720px);
  margin: 0 auto;
  padding: max(8px, env(safe-area-inset-top)) 12px max(20px, env(safe-area-inset-bottom));
  background: url("img/quest-shell-scroll-9.png") center / 100% 100% no-repeat;
}

.quest-title-stroke {
  color: #ffc928;
  -webkit-text-stroke: 2px #6b360f;
  text-shadow:
    0 2px 0 #ffffff,
    2px 3px 0 #8b5a2b,
    0 5px 8px rgba(88, 45, 12, .28);
  letter-spacing: 0;
}
```

フォント候補:
- 第一候補: Google Fonts `Zen Maru Gothic`。丸く、本文にも使いやすい。
- タイトル候補: `M PLUS Rounded 1c` の `900`。カンプの太いポップ体に近い。
- 補助候補: `Kiwi Maru`。本文に使うと古地図感は出るが、タイトルの太さは不足する。

Google Fonts を使う場合:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=M+PLUS+Rounded+1c:wght@700;900&family=Zen+Maru+Gothic:wght@500;700;900&display=swap" rel="stylesheet">
```

巻物パネルは `border-image` で9スライスする。画像が未生成でもCSSの単色枠で崩れないようにする。

```css
.scroll-panel {
  background: rgba(255, 246, 220, .92);
  border: 18px solid transparent;
  border-image: url("img/quest-panel-scroll-9.png") 36 fill / 18px / 0 stretch;
}

.heading-scroll {
  border: 16px solid transparent;
  border-image: url("img/quest-heading-scroll-9.png") 32 fill / 16px / 0 stretch;
}
```

マス丸は島画像を `position: relative` のコンテナに敷き、マスを `%` 座標で絶対配置する。座標はJS内またはJSONデータとして持つ。画像にはマス丸、番号、状態アイコン、テキストを焼き込まない。

```css
.map-island {
  position: relative;
  min-height: clamp(150px, 39vw, 260px);
}

.island-bg {
  display: block;
  width: 100%;
  height: auto;
}

.quest-cell {
  position: absolute;
  left: calc(var(--x) * 1%);
  top: calc(var(--y) * 1%);
  transform: translate(-50%, -50%);
  width: clamp(30px, 8.5vw, 54px);
  aspect-ratio: 1;
  border-radius: 50%;
  border: 2px solid #c99a4a;
  background: #fff8e8;
}
```

座標データ例:

```js
const QUEST_CELL_POSITIONS = {
  ancient: [
    { n: 1, x: 20, y: 60 },
    { n: 2, x: 31, y: 51 },
    { n: 3, x: 43, y: 46 }
  ],
  medieval: [],
  earlymod: [],
  modern: []
};
```

## 5. データ構造

既存生成器は `build_manifest()` で歴史19章を読み、合計92単元を生成する。30マスではなく92マスで扱う。

章ごとの実単元数:

| 章 | 学年 | 巻 | タイトル | 単元数 | 表示範囲 |
|---|---|---|---|---:|---|
| 01 | 中1 | 歴史 ① | 年代の表し方 | 1 | 1 |
| 02 | 中1 | 歴史 ② | 古代の世界 | 5 | 2〜6 |
| 03 | 中1 | 歴史 ③ | 日本の始まり | 3 | 7〜9 |
| 04 | 中1 | 歴史 ④ | 古代の国家 | 8 | 10〜17 |
| 05 | 中1 | 歴史 ⑤ | 武士と鎌倉幕府 | 5 | 18〜22 |
| 06 | 中1 | 歴史 ⑥ | 室町時代と中世の世界 | 8 | 23〜30 |
| 07 | 中2 | 歴史 ⑦ | ヨーロッパと天下統一 | 6 | 31〜36 |
| 08 | 中2 | 歴史 ⑧ | 幕藩体制の確立 | 9 | 37〜45 |
| 09 | 中2 | 歴史 ⑨ | 市民革命と近代化 | 8 | 46〜53 |
| 10 | 中2 | 歴史 ⑩ | 幕末の動乱 | 3 | 54〜56 |
| 11 | 中2 | 歴史 ⑪ | 明治維新と立憲国家 | 6 | 57〜62 |
| 12 | 中2 | 歴史 ⑫ | 日清・日露の時代 | 6 | 63〜68 |
| 13 | 中3 | 歴史 ⑬ | 第一次世界大戦と日本 | 4 | 69〜72 |
| 14 | 中3 | 歴史 ⑭ | 大正デモクラシー | 3 | 73〜75 |
| 15 | 中3 | 歴史 ⑮ | 昭和の危機 | 3 | 76〜78 |
| 16 | 中3 | 歴史 ⑯ | 第二次世界大戦と日本 | 4 | 79〜82 |
| 17 | 中3 | 歴史 ⑰ | 占領と日本国憲法 | 2 | 83〜84 |
| 18 | 中3 | 歴史 ⑱ | 冷戦と日本の復興 | 5 | 85〜89 |
| 19 | 中3 | 歴史 ⑲ | 現代の世界 | 3 | 90〜92 |

既存のマス生成に必要なデータ属性は維持する。

```html
<button
  class="quest-cell"
  type="button"
  data-ch="02"
  data-tid="ancient-civilizations"
  data-wb="3"
  data-ref="2"
  data-nq="18"
  data-n="4"
  data-grade="中1"
  data-era="ancient"
  data-vol="歴史 ②"
  style="--x:42;--y:58"
>
  <span class="quest-cell__num">4</span>
  <span class="quest-cell__badge" aria-hidden="true"></span>
</button>
```

座標JSONスキーマ:

```js
/**
 * n は全92単元の通し番号。
 * x/y は島コンテナ左上を 0/0、右下を 100/100 とする。
 */
const QUEST_MAP_COORDS = {
  ancient: [{ n: 1, x: 20.5, y: 60.0 }],
  medieval: [{ n: 18, x: 18.0, y: 55.0 }],
  earlymod: [{ n: 31, x: 15.5, y: 50.0 }],
  modern: [{ n: 57, x: 12.0, y: 56.0 }]
};
```

保存先は既存方式を踏襲する。

```js
// 問題集の解答状態
localStorage.getItem(`tzmwb-${ch}`)
// shape: { r: { "qa-{tid}-{i}": 1, "qz-{tid}-{i}": 0, "wr-{tid}-{i}": 1 } }

// 参考書の読了状態
localStorage.getItem(`tzmref-${ch}`)
// shape: { "d{refView}": 1 }

// 今日のミッション基準値
localStorage.getItem("tzmportal")
// shape: { date: "YYYY-MM-DD", base: clearedCount }
```

## 6. JS挙動

既存の関数責務を残し、見た目用に関数名を整理する。

1. `ls(key)`
   - `localStorage` をJSONとして安全に読む。
   - 失敗時は `{}`。

2. `stateOf(ch, tid, nq, refV)`
   - 既存ロジックをそのまま使う。
   - `tzmwb-{ch}.r` の `qa-{tid}-`, `qz-{tid}-`, `wr-{tid}-` 前方一致で解答済み/正解数を数える。
   - `tzmref-{ch}.d{refView} === 1` で参考書読了。
   - 戻り値は `perfect` / `all` / `some` / `ref` / `none`。

3. `buildQuestCells(manifest, coords)`
   - `__CELLS__` で生成済みの `.cell` を読み、`.quest-cell` として各島の `.map-cells` に移動する。
   - `data-n` と `QUEST_MAP_COORDS` を照合して `--x`, `--y` を設定する。
   - 座標未定義のマスは章内順に仮配置し、検証時に必ず潰す。

4. `paintStates()`
   - 全マスを走査して状態クラス `is-none`, `is-ref`, `is-some`, `is-all`, `is-perfect` を付ける。
   - 状態バッジ画像を差し替える。
   - 最後に進んだマスへ `is-here`、次のマスへ `is-current` を付ける。

5. `updateProgress(counts)`
   - `clearCount`, `totalCount`, `clearPct`, `progressFill`, `progressbar[aria-valuenow]` を更新。
   - カンプ例の `クリア 3 / 92 マス (3%)` 形式にする。

6. `updateBookList()`
   - 既存 `__BOOKS__` の章/単元行をカンプの表レイアウトへ寄せる。
   - 問題リンクは `wb/{ch}/index.html#t{wbView}`。
   - 参考書リンクは `ref/{ch}/index.html#t{refView}`。`refView` が無い場合は無効表示。
   - スタンプ丸は `stateOf()` の結果で塗る。

7. `updateRecord(counts)`
   - `クリアマス数`: `none` 以外の合計。
   - `集めたスタンプ`: `some` + `all` + `perfect`。参考書のみはスタンプに含めない。
   - `見つけた宝`: `perfect` の数、または10マスごとの報酬数。最初は `Math.floor(cleared / 10)` を推奨。
   - `次のごほうびまで`: `10 - (cleared % 10)`。0なら `0` または `達成!` 表示。

8. `mission(cleared)`
   - 既存の `tzmportal` キーを継続。
   - `date` が今日でなければ `{ date, base: cleared }` に初期化。
   - カンプでは記録パネル内の「次のごほうびまで」に統合できる。今日のミッションUIを残す場合は上部ではなく記録内に小さく収める。

9. `bindNavigation()`
   - マスタップで `location.href = 'wb/' + ch + '/index.html#t' + wbView`。
   - `ごほうび一覧` は初期実装では `#rewards` へのスクロールまたは未実装の無効ボタンにせず、クリック可能にするなら報酬モーダルをDOMで用意する。

## 7. `generate_tsudumon_portal.py` への組み込み手順

1. 画像置き場を追加する。

```py
QUEST_IMG_DIR = BASE / "assets" / "quest"
```

2. `copy_assets(dest_root)` に `quest-*` のコピーを追加する。既存の `CHAR_DIR` コピーと `PORTAL_IMG_DIR` コピーは残す。

```py
if QUEST_IMG_DIR.exists():
    for src in QUEST_IMG_DIR.glob("quest-*"):
        shutil.copyfile(src, img_dir / src.name)
```

3. `build_manifest()` は維持する。全92単元を正にするため、`total_units = sum(len(c["units"]) for c in manifest)` のまま使う。

4. `ERAS` は見た目上4島にまとめる。既存キーとの互換を保つなら、内部状態は5キーのまま、DOM配置時に `modern` と `current` を同じ `quest-island-modern.png` に流す。

```js
const ERA_TO_ISLAND = {
  ancient: "ancient",
  medieval: "medieval",
  earlymod: "earlymod",
  modern: "modern",
  current: "modern"
};
```

5. `TEMPLATE` をカンプ準拠のHTML構造へ差し替える。既存の置換トークンは最低限残す。

```py
return (TEMPLATE
        .replace("__TOTAL__", str(total_units))
        .replace("__CELLS__", "".join(cells))
        .replace("__BOOKS__", "".join(books))
        .replace("__ERAS__", json.dumps(ERAS, ensure_ascii=False))
        .replace("__MANIFEST__", json.dumps(manifest_min, ensure_ascii=False)))
```

6. `cells` 生成は `button` と `data-*` を維持する。クラス名だけ `.cell quest-cell` のように増やす。

7. 再生成コマンド:

```powershell
cd C:\Users\user\projects\education-apps\pdf-workbook
python -X utf8 generate_tsudumon_portal.py
```

8. 公開用への反映:

```powershell
cd C:\Users\user\projects\education-apps\pdf-workbook
python -X utf8 generate_tsudumon_portal.py --deploy
```

9. 生成物の確認先:

```text
pdf-workbook/output/web/index.html
marutto-study/public/tsudumon/index.html
```

## 8. 作業順序とチェックリスト

- [ ] カンプを再確認し、ヘッダー、進捗、凡例、島、本一覧、記録パネルの高さ比率を測る。
- [ ] `assets/quest/` に画像生成アセットを作る。
- [ ] `quest-island-*.png` にマス丸・番号・時代名テキストが焼き込まれていないことを確認する。
- [ ] 92単元ぶんの `QUEST_MAP_COORDS` を作る。
- [ ] `generate_tsudumon_portal.py` に `QUEST_IMG_DIR` とコピー処理だけ追加する。
- [ ] `TEMPLATE` のHTMLをカンプ順のセクション構成へ差し替える。
- [ ] CSS変数、フォント、羊皮紙9スライス、島の絶対配置マスを実装する。
- [ ] 既存 `stateOf()` ロジックを維持して状態バッジを画像化する。
- [ ] 進捗バー、凡例、本の一覧、冒険のきろくを `paintStates()` から更新する。
- [ ] `python -X utf8 generate_tsudumon_portal.py` を実行する。
- [ ] 390px幅、430px幅、720px幅でスクリーンショット確認する。
- [ ] iPhone Safari相当で safe-area とフォント太りを確認する。
- [ ] 画像容量を確認し、島背景が重い場合は WebP 化する。
- [ ] `python -X utf8 generate_tsudumon_portal.py --deploy` で公開先を再生成する。

## 9. 再現度を上げるための注意点

- フォント差: カンプのタイトルは極太ポップ体。Webフォントだけでは弱いので `-webkit-text-stroke` と複数 `text-shadow` で白フチ・茶縁・黄塗りを再現する。
- 島の縦横比: 島画像をCSSで無理に引き伸ばすと道とマス座標がズレる。島ごとに `aspect-ratio` を固定し、画像と座標の基準を一致させる。
- マス座標のズレ: 最初から92個を完璧に置こうとせず、時代ごとに代表点を置いてから間を補間し、最後にスクリーンショットで手調整する。
- 30表記との混乱: カンプの丸番号は30までだが、実データは92単元。UIテキストは必ず `__TOTAL__` を使い、固定値を書かない。
- 状態バッジ: マス内にDOMで重ねる。島画像に焼き込むと `ref` / `some` / `all` / `perfect` が更新できない。
- 本の一覧: カンプは8行まで見えているが、実データは19章。全章表示にすると長くなるため、学年見出し帯で区切り、行高を詰める。
- iOS safe-area: `padding-top/bottom: env(safe-area-inset-*)` を加え、下部ボタンがホームバーに近づきすぎないようにする。
- 画像容量: 島4枚、キャラ4枚、パネル複数で重くなる。背景島はPNG生成後に `webp` へ変換し、透過が必要な小物だけPNGに残す。
- a11y: マスは `button` のままにし、`aria-label="歴史 ② 古代の世界 4マス目"` のように章・単元名を読む。装飾画像は `alt=""`。
- フォールバック: 画像が欠けても `onerror="this.remove()"` とCSS背景色で崩れないようにする。ただし最終再現では全画像が存在する状態を必須とする。
