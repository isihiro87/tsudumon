# -*- coding: utf-8 -*-
"""
つづもん Web（問題集 wb / 参考書 ref / 単元マップ map）を **全章まとめて**
配信ビルド `dist-web/` へ生成・反映し、リンク健全性を検証する。

背景（なぜ要るか）:
  既存の各ジェネレータの `--deploy` は 1 章ずつしか出せず、19 章 × wb/ref を
  手で回す運用だった。そのため「ローカル(output/web)だけ再生成して配信ビルドを
  更新し忘れる」ドリフトが起き、単元一覧リンクが旧LPを指したまま本番に残る事故が発生した。
  このスクリプトで「全章一括反映」と「デプロイ前のドリフト検知」を固定化する。

このスクリプトが書き込む範囲:
  - `dist-web/{wb,ref,map}/`      … ジェネレータ生成物
  - `dist-web/_shared/img/`        … 章をまたぐ共通画像の集約先
  - `dist-web/{login,activate,account,settings}/`      … LINEログイン・コード有効化・お支払い・設定
  - `dist-web/{parents,parents/link,parents/thanks,parents/dashboard,handoff}/` … 保護者導線
  - `dist-web/_healthz.txt`                             … 上記いずれも `web/` 配下を丸ごとコピー

LP（`index.html` / `privacy.html` / `tokushoho.html` と `img/`）は対象外。
LPは `node lp/build-lp.mjs` が同じ `dist-web/` へ出力する。

使い方:
  python -X utf8 deploy_tsudumon.py            # 全19章 wb+ref+map を dist-web へ再生成 → 検証
  python -X utf8 deploy_tsudumon.py --check     # dist-web のリンク健全性のみ検査（書き込み無し・CI/デプロイ前向き）
  python -X utf8 deploy_tsudumon.py --only wb    # wb だけ（ref/map をスキップ）。--only ref / --only map も可
  python -X utf8 deploy_tsudumon.py --chapters 04,07  # 指定章だけ反映（省略時は全19章）

配信:
  dist-web/ は Firebase Hosting（site: tsudumon / project: chatstudy-63477）が
  https://tsudumon.jp/ として配信する。反映は `firebase deploy --only hosting:tsudumon`。
  ※ dist-web/ は git 管理外（.gitignore）。正本は各ジェネレータ・`web/`・`lp/`。

終了コード: 検証で問題を検出したら 1（それ以外 0）。--check は CI で使える。
"""
import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
REF_DIR = BASE / "reference"
BOOKS_DIR = BASE / "books"
TSUDUMON = BASE / "dist-web"                # Firebase Hosting(site: tsudumon) の公開ディレクトリ
STATIC_SRC = BASE / "web"                   # 手書き静的ページの正本（login/ activate/ account/ settings/ ほか）
WB_DEPLOY = TSUDUMON / "wb"
REF_DEPLOY = TSUDUMON / "ref"
MAP_DEPLOY = TSUDUMON / "map" / "index.html"
SHARED_IMG = TSUDUMON / "_shared" / "img"   # 章をまたぐ共通画像の集約先（/_shared/img/）

WB_GEN = BASE / "generate_workbook_web.py"
REF_GEN = BASE / "generate_reference_web.py"
MAP_GEN = BASE / "generate_tsudumon_portal.py"

# 各ページ上部「単元一覧へもどる」リンクの正しい href（＝単元マップ）。
# これが ../../index.html（＝つづもんLP）だったら旧版ドリフト。
# 注: ゲート内の lb-buy ボタンは正当に ../../index.html を指すので、
#     tophome の href だけをピンポイントに検査して誤検知を避ける。
EXPECT_TOPHOME = "../../map/index.html"
TOPHOME_RE = re.compile(r'class="tophome"[^>]*href="([^"]*)"')


def discover_chapters() -> list[str]:
    """章番号（'01'..'19'）を reference/*.json から導出（science は reference に無い）。
    books/ の歴史章とも突き合わせて、両方に存在する章だけを対象にする。"""
    ref_ch = {p.stem[:2] for p in REF_DIR.glob("*.json") if p.stem[:2].isdigit()}
    book_ch = {p.stem[:2] for p in BOOKS_DIR.glob("*.json")
               if not p.stem.startswith("science") and p.stem[:2].isdigit()}
    return sorted(ref_ch & book_ch)


def run_gen(script: Path, args: list[str]) -> None:
    """ジェネレータを -X utf8 付きで実行。失敗したら例外。"""
    cmd = [sys.executable, "-X", "utf8", str(script), *args]
    subprocess.run(cmd, cwd=BASE, check=True)


def _file_hash(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def dedupe_shared_images() -> dict:
    """wb/ref の各章 img/ にまたがって重複する画像（UIアイコン ic-*・講師キャラ等）を
    _shared/img/ に1枚だけ集約し、各ページの src="img/NAME" を
    src="../../_shared/img/NAME" に書き換える（wb/{NN}・ref/{NN} から _shared までは ../../）。

    ジェネレータは章ごとに img/ へ画像をコピーし直すので、この後処理は deploy のたびに
    再適用する（冪等）。同名でも内容が異なるファイルは誤集約を避けるため対象外。
    map(portal) の img/ は1ディレクトリで重複が無いため触らない。"""
    # 1) basename -> [各章のパス] を収集（wb/*/img/* と ref/*/img/*）
    by_name: dict[str, list[Path]] = {}
    for root in (WB_DEPLOY, REF_DEPLOY):
        for img in root.glob("*/img/*"):
            if img.is_file():
                by_name.setdefault(img.name, []).append(img)

    # 2) 共有対象を決める。「2章以上に現れる」または「既に _shared にある」名前で、
    #    かつ内容(ハッシュ)が全コピー＋既存_sharedで一致するものだけ（誤集約防止）。
    #    後者の条件により、--chapters で1章だけ再生成しても既存の共有画像に畳み込める。
    shared_names = []
    for name, paths in by_name.items():
        hashes = {_file_hash(p) for p in paths}
        existing = SHARED_IMG / name
        if existing.exists():
            hashes.add(_file_hash(existing))
        if (len(paths) >= 2 or existing.exists()) and len(hashes) == 1:
            shared_names.append(name)
    if not shared_names:
        return {"names": 0, "removed": 0, "bytes_saved": 0}

    # 3) 代表1枚を _shared/img/ へ置き、各章の重複コピーは削除
    SHARED_IMG.mkdir(parents=True, exist_ok=True)
    removed = 0
    bytes_saved = 0
    for name in shared_names:
        paths = by_name[name]
        dest = SHARED_IMG / name
        pre_existed = dest.exists()
        shutil.copy2(paths[0], dest)         # 常に最新で上書き（同一内容なのでどれでも可）
        size = dest.stat().st_size
        for p in paths:
            p.unlink()
            removed += 1
        bytes_saved += len(paths) * size - (0 if pre_existed else size)

    # 4) 各ページの src="img/NAME" を ../../_shared/img/NAME に書き換え
    shared_set = set(shared_names)
    for page in list(WB_DEPLOY.glob("*/index.html")) + list(REF_DEPLOY.glob("*/index.html")):
        txt = page.read_text(encoding="utf-8")
        new = txt
        for name in shared_set:
            new = new.replace(f'src="img/{name}"', f'src="../../_shared/img/{name}"')
        if new != txt:
            page.write_text(new, encoding="utf-8")

    return {"names": len(shared_names), "removed": removed, "bytes_saved": bytes_saved}


def copy_static() -> int:
    """`web/` 配下の手書き静的ページを dist-web/ へそのままコピーする。

    login/ activate/ account/ settings/ は LINE ログイン・コード有効化・お支払い管理・
    お知らせとテストの設定のページ、parents/ handoff/ は保護者導線（子が渡すカード →
    保護者ページ → 決済 → 連携 → 学習の記録）のページで、
    ジェネレータの生成対象ではない（正本は web/、詳細は web/README.md）。
    冪等なので deploy のたびに実行してよい。README.md は配信対象外なので除外する。"""
    if not STATIC_SRC.is_dir():
        return 0
    copied = 0
    for src in STATIC_SRC.rglob("*"):
        if not src.is_file() or src.name == "README.md":
            continue
        dest = TSUDUMON / src.relative_to(STATIC_SRC)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1
    return copied


def deploy(chapters: list[str], only: str | None, dedupe: bool = True) -> None:
    do_wb = only in (None, "wb")
    do_ref = only in (None, "ref")
    do_map = only in (None, "map")

    if do_wb or do_ref:
        for ch in chapters:
            if do_wb:
                run_gen(WB_GEN, ["--deploy", ch])
                print(f"  wb  {ch} -> dist-web/wb/{ch}/")
            if do_ref:
                run_gen(REF_GEN, ["--deploy", ch])
                print(f"  ref {ch} -> dist-web/ref/{ch}/")
    if do_map:
        run_gen(MAP_GEN, ["--deploy"])
        print("  map     -> dist-web/map/")

    # 手書きの静的ページ（login/ activate/ account/ settings/ ほか）を毎回コピーし直す
    if only is None:
        n = copy_static()
        if n:
            print(f"  static  web/ から {n} ファイルを dist-web/ へコピー")

    # 章をまたぐ共通画像（アイコン・キャラ）を _shared/img/ に集約して重複を削減
    if dedupe and (do_wb or do_ref):
        stat = dedupe_shared_images()
        if stat["names"]:
            print(f"  dedupe  共通画像 {stat['names']}種 / 重複{stat['removed']}枚を "
                  f"_shared/img/ に集約（{stat['bytes_saved']/1048576:.1f}MB削減）")


def verify(chapters: list[str]) -> list[str]:
    """反映済み dist-web のリンク健全性を検査。問題点のリストを返す（空なら健全）。"""
    problems: list[str] = []

    for kind, root in (("wb", WB_DEPLOY), ("ref", REF_DEPLOY)):
        for ch in chapters:
            idx = root / ch / "index.html"
            if not idx.exists():
                problems.append(f"{kind}/{ch}: index.html が無い ({idx})")
                continue
            html = idx.read_text(encoding="utf-8", errors="replace")
            m = TOPHOME_RE.search(html)
            if not m:
                problems.append(f"{kind}/{ch}: 単元一覧リンク(class=\"tophome\")が見つからない")
            elif m.group(1) != EXPECT_TOPHOME:
                problems.append(
                    f"{kind}/{ch}: 単元一覧リンクが旧版 href=\"{m.group(1)}\" "
                    f"(期待 \"{EXPECT_TOPHOME}\") ← ドリフト")

    if not MAP_DEPLOY.exists():
        problems.append(f"map: index.html が無い ({MAP_DEPLOY})")
    else:
        map_html = MAP_DEPLOY.read_text(encoding="utf-8", errors="replace")
        if "歴史クエスト" not in map_html:
            problems.append("map: 単元マップの内容が想定と違う（『歴史クエスト』が無い）")

    return problems


def build_summary() -> None:
    """生成された dist-web/ の内容サマリを表示する。

    dist-web/ は git 管理外なので、以前の `git status` によるドリフト検知は使えない。
    代わりに「何が入っているか」を出して、LPビルド漏れなどに気づけるようにする。"""
    if not TSUDUMON.is_dir():
        print("  dist-web/ がありません")
        return
    files = [p for p in TSUDUMON.rglob("*") if p.is_file()]
    total_mb = sum(p.stat().st_size for p in files) / 1048576
    print(f"  dist-web/ … {len(files)} ファイル / {total_mb:.1f}MB")

    # LPは別ビルド（node lp/build-lp.mjs）なので、入っていなければ警告する
    if not (TSUDUMON / "index.html").exists():
        print("  ⚠ dist-web/index.html（LP）がありません。`node lp/build-lp.mjs` を実行してください")
    # 保護者導線（parents/ parents/thanks/ parents/dashboard/ handoff/）は
    # 中学生本人が決済できない以上、唯一の課金経路なので欠けたら必ず気づけるようにする。
    for name in ("login", "activate", "account", "settings",
                 "parents", "parents/link", "parents/thanks", "parents/dashboard",
                 "handoff"):
        if not (TSUDUMON / name / "index.html").exists():
            print(f"  ⚠ dist-web/{name}/index.html がありません（web/ の正本を確認）")


def main() -> int:
    ap = argparse.ArgumentParser(description="つづもんWeb（wb/ref/map）を全章一括で dist-web へ反映＋検証")
    ap.add_argument("--check", action="store_true",
                    help="反映済み dist-web のリンク健全性のみ検査（書き込み無し）")
    ap.add_argument("--only", choices=["wb", "ref", "map"],
                    help="wb / ref / map のいずれかだけを反映")
    ap.add_argument("--chapters",
                    help="対象章をカンマ区切りで指定（例 04,07）。省略時は全19章")
    ap.add_argument("--no-dedupe", action="store_true",
                    help="共通画像の _shared/img/ 集約をスキップ（デバッグ用）")
    args = ap.parse_args()

    all_chapters = discover_chapters()
    if not all_chapters:
        print("章が見つかりません（reference/ と books/ を確認）", file=sys.stderr)
        return 1

    if args.chapters:
        want = [c.strip().zfill(2) for c in args.chapters.split(",") if c.strip()]
        chapters = [c for c in all_chapters if c in want]
        missing = [c for c in want if c not in all_chapters]
        if missing:
            print(f"指定章が存在しません: {', '.join(missing)}", file=sys.stderr)
            return 1
    else:
        chapters = all_chapters

    if args.check:
        print(f"[check] dist-web のリンク健全性を検査（{len(chapters)}章）…")
        problems = verify(chapters)
        if problems:
            print(f"\n✗ 問題を {len(problems)} 件検出:")
            for p in problems:
                print(f"  - {p}")
            return 1
        print("✓ 健全（全章の単元一覧リンクが単元マップを指しています）")
        return 0

    print(f"[deploy] 対象章: {', '.join(chapters)}" + (f" / only={args.only}" if args.only else ""))
    deploy(chapters, args.only, dedupe=not args.no_dedupe)

    print("\n[verify] リンク健全性を検査…")
    problems = verify(chapters)
    if problems:
        print(f"✗ 反映後の検証で {len(problems)} 件の問題:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("✓ 健全")

    print("\n[build] 配信ビルドの内容:")
    build_summary()
    print("\n次の手順: `node lp/build-lp.mjs`（LP未ビルドなら）→ "
          "`firebase deploy --only hosting:tsudumon` で https://tsudumon.jp/ に反映")
    return 0


if __name__ == "__main__":
    sys.exit(main())
