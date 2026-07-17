# -*- coding: utf-8 -*-
"""
販売用PDFに購入者名・注文IDの透かしを焼き込む（コピー・再配布の抑止＋流出元の特定）。

- 各ページのフッター中央に「{購入者名} 専用 ・ 無断複製・再配布禁止 ・ {注文ID}」を薄く入れる
- 全ページの背景に、ごく薄い斜めの購入者名を敷く（スクショ流出時に誰のものか分かる）

購入者ごとに再生成する必要はなく、完成済みの output/*.pdf にスタンプするだけ。

使い方:
  # 1冊
  python -X utf8 watermark_pdf.py --name "山田太郎" --order "ORD-12345" \
      --in output/science-g1-biology.pdf --out dist/山田太郎/理科①生物.pdf

  # 教科×学年フォルダ構成で全31冊を一括（配布セットを作る）
  python -X utf8 watermark_pdf.py --name "山田太郎" --order "ORD-12345" --all
"""
import argparse
import re
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF

BASE = Path(__file__).parent
OUT_DIR = BASE / "output"

FOOT_COLOR = (0.62, 0.60, 0.58)   # 落ち着いたグレー（本文の邪魔をしない）
DIAG_COLOR = (0.90, 0.89, 0.87)   # 背景に敷くごく薄い斜め文字

# 冊子ID → 配布時のわかりやすいファイル名／フォルダ（教科・学年）
BOOK_LABELS = {
    # 歴史（章番号＝配本順）
    **{f"{i:02d}-": None for i in range(1, 20)},  # 実際の対応は下の関数で解決
}


def book_meta(stem: str):
    """冊子stem → (教科, 学年, 表示名) を返す。配布フォルダとファイル名に使う。"""
    hist_vol = {
        "01": ("中1", "歴史①歴史の始まり"), "02": ("中1", "歴史②古代の世界"),
        "03": ("中1", "歴史③日本の始まり"), "04": ("中1", "歴史④古代の国家"),
        "05": ("中1", "歴史⑤武士の台頭"), "06": ("中1", "歴史⑥中世の世界"),
        "07": ("中2", "歴史⑦近世ヨーロッパ"), "08": ("中2", "歴史⑧江戸幕府"),
        "09": ("中2", "歴史⑨欧米の近代"), "10": ("中2", "歴史⑩幕末"),
        "11": ("中2", "歴史⑪明治維新"), "12": ("中2", "歴史⑫明治後期"),
        "13": ("中3", "歴史⑬第一次世界大戦"), "14": ("中3", "歴史⑭大正デモクラシー"),
        "15": ("中3", "歴史⑮昭和恐慌"), "16": ("中3", "歴史⑯第二次世界大戦"),
        "17": ("中3", "歴史⑰戦後日本"), "18": ("中3", "歴史⑱冷戦"),
        "19": ("中3", "歴史⑲現代の世界"),
    }
    m = re.match(r"(\d{2})-", stem)
    if m and m.group(1) in hist_vol:
        g, name = hist_vol[m.group(1)]
        return "歴史", g, name
    sm = re.match(r"science-g(\d)-(\w+)", stem)
    if sm:
        g = f"中{sm.group(1)}"
        sci = {
            "biology": "生物", "chemistry": "化学", "physics": "物理",
            "earth": "地学", "electricity": "電気", "weather": "天気",
        }
        subj = sci.get(sm.group(2), sm.group(2))
        return "理科", g, f"理科_{g}_{subj}"
    return "その他", "", stem


def stamp(doc: fitz.Document, name: str, order: str) -> None:
    foot = f"{name} 専用　・　無断複製・再配布を禁じます　・　{order}"
    for page in doc:
        w, h = page.rect.width, page.rect.height
        # 背景の薄い斜め透かし（購入者名を対角に大きく1本）。
        # insert_textbox の rotate は90°単位のみなので、insert_text＋morph で45°回す。
        pivot = fitz.Point(w / 2, h / 2)
        mat = fitz.Matrix(1, 1).prerotate(-45)
        text_w = fitz.get_text_length(name, fontname="japan", fontsize=44)
        page.insert_text(
            fitz.Point(w / 2 - text_w / 2, h / 2),
            name, fontsize=44, fontname="japan", color=DIAG_COLOR,
            morph=(pivot, mat), overlay=False,
        )
        # フッター（下から 6pt、中央寄せ）
        page.insert_textbox(
            fitz.Rect(0, h - 20, w, h - 6),
            foot, fontsize=7.5, fontname="japan", color=FOOT_COLOR,
            align=fitz.TEXT_ALIGN_CENTER,
        )


def apply_one(src: Path, dst: Path, name: str, order: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(src)
    stamp(doc, name, order)
    # 透かしをテキスト検索・削除されにくくするため、目的が抑止であればこれで十分。
    doc.save(dst, garbage=4, deflate=True)
    doc.close()


def safe(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r'[\\/:*?"<>|]', "_", s).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="購入者名（透かしに入る）")
    ap.add_argument("--order", default="", help="注文ID（任意・流出元特定用）")
    ap.add_argument("--in", dest="src", help="入力PDF（単体）")
    ap.add_argument("--out", dest="dst", help="出力PDF（単体）")
    ap.add_argument("--all", action="store_true", help="output/ 全冊を教科×学年フォルダで一括")
    args = ap.parse_args()

    if args.all:
        root = BASE / "dist" / safe(f"{args.name}_{args.order}".strip("_"))
        n = 0
        for src in sorted(OUT_DIR.glob("*.pdf")):
            subj, grade, name = book_meta(src.stem)
            dst = root / subj / grade / f"{safe(name)}.pdf"
            apply_one(src, dst, args.name, args.order)
            n += 1
        print(f"透かし入り {n}冊 → {root}")
    else:
        if not args.src or not args.dst:
            ap.error("--all を使わない場合は --in と --out が必要です")
        apply_one(Path(args.src), Path(args.dst), args.name, args.order)
        print(f"透かし入り → {args.dst}")


if __name__ == "__main__":
    main()
