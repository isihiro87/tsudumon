# -*- coding: utf-8 -*-
"""
教科ごとに全冊を1つのPDFに結合した「総合版」を作る（各冊の先頭にしおり＝目次）。

使い方:
  python -X utf8 merge_pdf.py --subject history   # 歴史19冊 → output/_歴史_総合版.pdf
  python -X utf8 merge_pdf.py --subject science   # 理科12冊 → output/_理科_総合版.pdf
"""
import argparse
import re
from pathlib import Path

import fitz

from watermark_pdf import book_meta
from add_page_numbers import number

BASE = Path(__file__).parent
OUT_DIR = BASE / "output"


def collect(subject: str):
    """(表示名, path) を配本順で返す。"""
    items = []
    for src in OUT_DIR.glob("*.pdf"):
        if src.stem.startswith("_"):
            continue  # 既存の総合版はスキップ
        subj, grade, name = book_meta(src.stem)
        if subject == "history" and subj != "歴史":
            continue
        if subject == "science" and subj != "理科":
            continue
        # 並び順キー: 歴史=章番号 / 理科=学年→教科名
        if subj == "歴史":
            key = (int(re.match(r"(\d{2})", src.stem).group(1)),)
        else:
            key = (grade, name)
        items.append((key, name, src))
    items.sort(key=lambda x: x[0])
    return [(name, src) for _, name, src in items]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True, choices=["history", "science"])
    args = ap.parse_args()

    books = collect(args.subject)
    if not books:
        print("対象PDFが見つかりません")
        return

    merged = fitz.open()
    toc = []  # [level, title, start_page(1-indexed)]
    for name, src in books:
        start = merged.page_count
        with fitz.open(src) as doc:
            merged.insert_pdf(doc)
        toc.append([1, name, start + 1])

    merged.set_toc(toc)
    number(merged)  # 全体の通し番号（フッター中央）
    label = "歴史" if args.subject == "history" else "理科"
    out = OUT_DIR / f"_{label}_総合版.pdf"
    merged.save(out, garbage=4, deflate=True)
    print(f"{len(books)}冊を結合 → {out}（全{merged.page_count}ページ・しおり{len(toc)}件）")
    merged.close()


if __name__ == "__main__":
    main()
