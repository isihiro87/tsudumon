# タスクリスト

## 🚨 タスク完全完了の原則

**このファイルの全タスクが完了するまで作業を継続すること**（歴史④パイロットの範囲内で）

---

## フェーズ1: レイアウト実装（generate_reference_web.py）

- [x] section ループに横帯画像レンダリングを追加（`use_img(s.get("image"))` → `<figure class="sec-fig">`）
- [x] TEMPLATE に `.sec-fig` / `.sec-fig img` / `.sec-fig figcaption` の CSS を追加（+ `.fig-contain` で図版は contain）
- [x] 既存 assets（5枚）で section に image を付与し、生成→sec-fig 5枚レンダリング確認（contain/cover 出し分けOK）

## フェーズ2: 画像素材の割り当てとソース

- [x] 歴史④ 全23 section の画像割り当て表を確定（再利用5＋codex18）
- [x] 再利用素材を assets/reference/ にコピー（horyuji/shosoin/byodoin/ritsuryo-org/handen）
- [x] codex 用ブリーフ（CODEX_BRIEF_SEC_HIST04.md）を作成（出力名×内容×トーン統一ルール）

## フェーズ3: codex 画像生成（image-2）

- [x] codex exec でブリーフを渡し、節画像18枚を tmp/gen に生成（全18枚 exit0 完了）
- [x] PIL で assets/reference/hist04-sec-*.webp に変換（幅1200上限・q84）
- [x] 生成画像を目視確認（トーン統一・日本語ラベル正確＝白村江地図/摂関関係図とも文字化けなし）

## フェーズ4: データ付与と生成

- [x] 04-ancient-state.json の全23 section に image / imageCaption / imageFit を付与
- [x] assets/credits.json は実物写真（horyuji/shosoin/byodoin）を既に記録済み（追記不要）
- [x] generate_reference_web.py を実行し output/web/ref/04/ を再生成（section画像23/23コピー確認）

## フェーズ5: 検証

- [x] レイアウト方針変更（横帯フル幅→本文左・挿絵小さく右 float）をユーザー指示に沿って実装
- [x] Edge ヘッドレスで各ステップを目視（シーン画像＝小さく右／図版＝右で全ラベル可読・崩れなし）
- [x] ローカルプレビュー用サーバー起動＋確認URLをユーザーに案内
- [ ] ユーザー最終確認 → OKなら `--deploy 04` で本番反映（歴史④は限定公開中のため承認後）
- [x] 実装後の振り返りを記録

---

## 実装後の振り返り

### 実装完了日
2026-07-21（歴史④パイロット・ユーザー最終確認と本番反映を残す）

### 計画と実績の差分
- **レイアウトを途中で変更**: 当初「本文上の横帯フル幅」で実装したが、ユーザーから「でかすぎる／本文左・画像右の教科書レイアウトに、画像は目立たせない」との指示。`.sec-fig` を float:right の小さめサムネ（cover 158px／図版 176px・contain）に変更。`.step::after` で float 内包、`.point/.words` は clear:both。
- **PDF版はスコープ外に確定**: ユーザー方針で当面PDF版不使用。generate_reference_web.py のみ変更（section.image は PDF 生成側が無視するので無害）。
- **画像内訳**: 再利用5（実物写真3＝法隆寺/正倉院/平等院＋既存図版2＝律令官制/班田収授）＋ codex image-2 生成18＝計23。
- **地図は AI 生成をやめて実データ化**: 当初 image-2 で作った白村江の地図が地理でたらめ（ユーザー指摘）。**Natural Earth 50m（PD）を matplotlib で正確に描画＋日本語ラベル/矢印を重ねる**方式に変更し `tools/history_maps.py` にツール化。摂関外戚の関係図は地図でなく概念図なので image-2 のまま（日本語正確）。サイズは最終的に cover205px/図版230px・幅46%（1.3倍）に調整。

### 学んだこと
- **codex CLI の image-2 が実用レベル**: `codex exec --full-auto` にブリーフを渡すと ~/.codex/generated_images に生成→指定パスへ copy。水彩フラットの教材トーンで統一でき、日本語ラベルも正確。1セッションで18枚バッチ生成可（バックグラウンド）。
- **ヘッドレス目視**: Edge `--headless=new --screenshot` ＋ `#tNsM` ハッシュ直リンクでステップ単位のスクショが撮れる。ただし非デバイスエミュレーションのため狭幅では既存ヘッダー（.tband の再生ボタン nowrap）由来の全体右クリップが出る＝挿絵とは別要因。広幅(900px)で真のレイアウトを確認するのが確実。

### 次回への改善提案
- 横展開（他章）は本ブリーフ様式を流用：節ごとに「再利用/実物写真/codex」を割り当て、codex分を1バッチ生成→PIL変換→JSONにimage付与→再生成、の順で回す。
- 既存ヘッダーの狭幅オーバーフロー（.tband 再生ボタン）はスマホで確認し、必要なら別タスクで flex-wrap/min-width:0 対応。
