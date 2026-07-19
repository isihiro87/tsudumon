# -*- coding: utf-8 -*-
"""
output/ 内に散らかった生成物を、わかりやすいフォルダ構成に整理する。

整理後:
  output/
  ├─ 01_はじめに/              ★はじめにお読みください.pdf
  ├─ 02_問題集/
  │   ├─ 歴史/中1〜中3/        歴史④ 古代の国家.pdf ...
  │   └─ 理科/中1〜中3/        理科① 生物のかんさつ.pdf ...
  ├─ 03_参考書/
  │   └─ 歴史/中1〜中3/        歴史④ 古代の国家（参考書）.pdf ...
  ├─ 04_総合版/                歴史_総合版.pdf / 理科_総合版.pdf
  └─ _html/                    中間HTML（作業用・配布不要）

再生成のたびに output 直下へ出るので、このスクリプトを再実行すればまた整う。
使い方: python -X utf8 organize_output.py
"""
import json
import re
import shutil
from pathlib import Path

BASE = Path(__file__).parent
OUT = BASE / "output"
BOOKS = BASE / "books"
REF = BASE / "reference"

GRADE_HISTORY = {**{f"{i:02d}": "中1" for i in range(1, 7)},
                 **{f"{i:02d}": "中2" for i in range(7, 13)},
                 **{f"{i:02d}": "中3" for i in range(13, 20)}}


def load_meta(stem: str):
    """章stem → (volume, title)。books/reference の JSON から引く。"""
    for d in (BOOKS, REF):
        p = d / f"{stem}.json"
        if p.exists():
            j = json.loads(p.read_text(encoding="utf-8"))
            return j.get("volume", ""), j.get("title", stem)
    return "", stem


def classify(pdf: Path):
    """PDF → (相対フォルダ, 新ファイル名)。分類できなければ None。"""
    stem = pdf.stem

    # はじめに / 総合版
    m = re.match(r"_はじめにお読みください_(.+)$", stem)
    if m:  # プラン別（中1/中2/中3/3学年セット）の統合版
        return Path("01_はじめに"), f"★はじめにお読みください（{m.group(1)}）.pdf"
    if stem == "_はじめにお読みください":
        return Path("01_はじめに"), "★はじめにお読みください.pdf"
    if stem == "_参考書はじめにお読みください":
        return Path("01_はじめに"), "★はじめにお読みください（参考書）.pdf"
    if stem.startswith("_") and "総合版" in stem:
        return Path("04_総合版"), stem.lstrip("_") + ".pdf"

    # 参考書（ref-XX-...）
    is_ref = stem.startswith("ref-")
    core = stem[len("ref-"):] if is_ref else stem

    # 教科・学年
    if re.match(r"\d{2}-", core):  # 歴史
        subj, grade = "歴史", GRADE_HISTORY[core[:2]]
    elif core.startswith("science-g"):  # 理科
        subj, grade = "理科", f"中{core[len('science-g')]}"
    else:
        return None

    vol, title = load_meta(core)
    label = f"{vol.replace(' ', '')} {title}".strip()
    kind = "03_参考書" if is_ref else "02_問題集"
    suffix = "（参考書）" if is_ref else ""
    return Path(kind) / subj / grade, f"{label}{suffix}.pdf"


def safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def main() -> None:
    # 1) 中間HTML を _html/ へ
    html_dir = OUT / "_html"
    html_dir.mkdir(exist_ok=True)
    n_html = 0
    for h in OUT.glob("*.html"):
        shutil.move(str(h), str(html_dir / h.name))
        n_html += 1

    # 2) PDF を分類フォルダへ
    n_pdf, skipped = 0, []
    for pdf in list(OUT.glob("*.pdf")):
        res = classify(pdf)
        if not res:
            skipped.append(pdf.name)
            continue
        rel, newname = res
        dst_dir = OUT / rel
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pdf), str(dst_dir / safe(newname)))
        n_pdf += 1

    print(f"HTML {n_html}件 → output/_html/")
    print(f"PDF {n_pdf}件を分類フォルダへ整理")
    if skipped:
        print("分類できず output 直下に残置:", skipped)

    # 整理後のツリーを表示
    print("\n=== 整理後の構成 ===")
    for d in sorted(OUT.rglob("*")):
        if d.is_dir():
            rel = d.relative_to(OUT)
            depth = len(rel.parts) - 1
            cnt = len(list(d.glob("*.pdf")))
            print("  " * depth + f"{rel.parts[-1]}/" + (f"  ({cnt}冊)" if cnt else ""))


if __name__ == "__main__":
    main()
