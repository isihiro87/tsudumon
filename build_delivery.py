# -*- coding: utf-8 -*-
"""
購入プラン別の納品パッケージを組み立てる（つづもん納品フローの本体）。

どのプランの購入者も、開いた瞬間に進め方がわかる同じ構成で受け取る:

  つづもん_中1/                      … 中2 / 中3 / 3学年セット も同じ形
  ├─ ★はじめにお読みください.pdf      … そのプラン専用（目次も購入分だけ）
  ├─ 1_問題集/
  │   └─ 歴史① 年代の表し方.pdf …     （3学年セットのみ 中1/中2/中3 のサブフォルダ）
  └─ 2_参考書/
      └─ 歴史① 年代の表し方（参考書）.pdf …

素材（先に用意しておく）:
  output/01_はじめに/★はじめにお読みください（{中1|中2|中3|3学年セット}）.pdf
  output/02_問題集/歴史/{中1..中3}/*.pdf
  output/03_参考書/歴史/{中1..中3}/*.pdf

使い方:
  # 納品テンプレート（透かしなし・全4プラン）を output/00_納品用/ に組み立て
  python -X utf8 build_delivery.py

  # 注文が入ったら: 購入者名入りで1プラン分を dist/ に作成（--zip でそのままzip化）
  python -X utf8 build_delivery.py --plan 中1 --name "山田太郎" --order ORD-12345 --zip
"""
import argparse
import shutil
from pathlib import Path

from watermark_pdf import apply_one, safe

BASE = Path(__file__).parent
OUT = BASE / "output"
INTRO_DIR = OUT / "01_はじめに"
WB_DIR = OUT / "02_問題集" / "歴史"
REF_DIR = OUT / "03_参考書" / "歴史"

PLANS = ["中1", "中2", "中3", "3学年セット"]
GRADES = ["中1", "中2", "中3"]


def package_files(plan: str):
    """プラン → [(コピー元PDF, パッケージ内の相対パス)] を返す。素材が欠けていれば例外。"""
    intro = INTRO_DIR / f"★はじめにお読みください（{plan}）.pdf"
    if not intro.exists():
        raise FileNotFoundError(f"はじめにPDFがありません: {intro}（make_intro_pdf.py → Edge → organize_output.py）")
    files = [(intro, Path("★はじめにお読みください.pdf"))]

    grades = GRADES if plan == "3学年セット" else [plan]
    for kind, src_root in (("1_問題集", WB_DIR), ("2_参考書", REF_DIR)):
        for g in grades:
            pdfs = sorted((src_root / g).glob("*.pdf"))
            if not pdfs:
                raise FileNotFoundError(f"素材がありません: {src_root / g}")
            for p in pdfs:
                # 学年別プランはフォルダを掘らずフラットに（迷いにくさ優先）
                rel = Path(kind) / g / p.name if plan == "3学年セット" else Path(kind) / p.name
                files.append((p, rel))
    return files


def build(plan: str, dest_root: Path, name: str = "", order: str = "") -> Path:
    pkg = dest_root / f"つづもん_{plan}"
    if pkg.exists():
        shutil.rmtree(pkg)
    for src, rel in package_files(plan):
        dst = pkg / rel
        if name:  # 注文モード: 全PDF（はじめに含む）へ購入者名の透かし
            apply_one(src, dst, name, order)
        else:     # テンプレートモード: そのままコピー
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return pkg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", choices=PLANS, help="プラン（省略時はテンプレートを全4プラン組み立て）")
    ap.add_argument("--name", default="", help="購入者名（指定すると透かし入りの注文モード）")
    ap.add_argument("--order", default="", help="注文ID（流出元特定用・任意）")
    ap.add_argument("--zip", action="store_true", help="パッケージをzip化する")
    args = ap.parse_args()

    if args.name:
        if not args.plan:
            ap.error("--name を使う場合は --plan も指定してください")
        dest = BASE / "dist" / safe(f"{args.name}_{args.order}".strip("_"))
        pkg = build(args.plan, dest, args.name, args.order)
        n = sum(1 for _ in pkg.rglob("*.pdf"))
        print(f"納品パッケージ（透かし入り {n}冊）: {pkg}")
        if args.zip:
            z = shutil.make_archive(str(pkg), "zip", root_dir=pkg.parent, base_dir=pkg.name)
            print(f"zip: {z}")
    else:
        plans = [args.plan] if args.plan else PLANS
        dest = OUT / "00_納品用"
        for plan in plans:
            pkg = build(plan, dest)
            n = sum(1 for _ in pkg.rglob("*.pdf"))
            print(f"テンプレート（{n}冊）: {pkg}")
            if args.zip:
                z = shutil.make_archive(str(pkg), "zip", root_dir=pkg.parent, base_dir=pkg.name)
                print(f"zip: {z}")


if __name__ == "__main__":
    main()
