# -*- coding: utf-8 -*-
"""
総合版PDFのフッターに「全体の通し番号」でページ番号を焼き込む。

- 位置: フッター中央、下から約 12mm（購入者名の透かし h-20..h-6 と重ならない上側）
- 通し番号: 先頭ページを 1 として全ページ連番（章ごとにリセットしない）

merge_pdf.py / merge_reference_from_organized.py から呼ぶ（結合直後・保存前に number()）。
既存PDFに後から付けたいときは CLI:
  python -X utf8 add_page_numbers.py --in output/04_総合版/歴史参考書_総合版.pdf
"""
import argparse
from pathlib import Path

import fitz  # PyMuPDF

NUM_COLOR = (0.35, 0.33, 0.31)  # 落ち着いたグレー（本文の邪魔をしない・でも読める）


def number(doc: fitz.Document, start: int = 1, fontsize: float = 9.5) -> int:
    """doc の全ページに通し番号をふる。戻り値 = 次の開始番号。"""
    n = start
    for page in doc:
        w, h = page.rect.width, page.rect.height
        # 透かしフッター（h-20..h-6）の上に置いて重なりを避ける。
        # rect は行が収まる高さ（約16pt）が必要。低すぎると描画されない。
        page.insert_textbox(
            fitz.Rect(0, h - 38, w, h - 22),
            f"{n}", fontsize=fontsize, fontname="japan",
            color=NUM_COLOR, align=fitz.TEXT_ALIGN_CENTER,
        )
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True, help="入力PDF（上書き保存）")
    ap.add_argument("--out", dest="dst", help="出力PDF（省略時は入力を上書き）")
    ap.add_argument("--start", type=int, default=1, help="先頭ページ番号（既定1）")
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.dst) if args.dst else src
    doc = fitz.open(src)
    last = number(doc, start=args.start) - 1
    if dst == src:
        tmp = src.with_suffix(".numbering.tmp.pdf")
        doc.save(tmp, garbage=3, deflate=True)
        doc.close()
        tmp.replace(src)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        doc.save(dst, garbage=3, deflate=True)
        doc.close()
    print(f"ページ番号 1..{last} を付与 → {dst}")


if __name__ == "__main__":
    main()
