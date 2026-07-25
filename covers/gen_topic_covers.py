from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / "reference"
HTML_DIR = ROOT / "covers" / "html" / "topics"
OUT_DIR = ROOT / "covers" / "out" / "topics"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def plain(value: str) -> str:
    return re.sub(r"\*\*(.*?)\*\*", r"\1", value or "")


def file_url(path: Path) -> str:
    return path.resolve().as_uri()


def topic_html(chapter_no: str, volume: str, chapter_title: str, topic_no: int, topic: dict) -> str:
    title = plain(topic["name"])
    title_class = " topic-title-long" if len(title) >= 15 else ""
    image = "../../../assets/reference/" + topic["image"]
    learn_items = topic.get("learn") or [section.get("heading", "") for section in topic.get("sections", [])]
    learn_items = [plain(item) for item in learn_items if item][:3]
    rotate_class = " topic-even" if topic_no % 2 == 0 else " topic-odd"
    lis = "\n".join(
        f'            <li><span class="learn-no">{i}</span><span>{html.escape(item)}</span></li>'
        for i, item in enumerate(learn_items, 1)
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>{html.escape(volume)} {html.escape(title)}</title>
  <link rel="stylesheet" href="../cover.css">
</head>
<body class="unit topic-cover topic-{chapter_no}{rotate_class}">
  <main class="page">
    <section class="paper" data-unit="{topic_no}">
      <i class="sparkle s1"></i>
      <i class="sparkle s2"></i>
      <i class="sparkle s3"></i>
      <header class="unit-header">
        <div class="badge">{html.escape(volume)}</div>
        <div class="unit-title-block">
          <h1 class="unit-title{title_class}">{html.escape(title)}</h1>
          <div class="unit-range">{html.escape(chapter_title)}／単元{topic_no}</div>
        </div>
      </header>
      <div class="unit-art topic-art">
        <img src="{html.escape(image)}" alt="">
      </div>
      <div class="unit-learn topic-learn">
        <div class="learn-main">
          <div class="learn-h">🎯 この単元でわかること</div>
          <ol class="learn-list topic-learn-list">
{lis}
          </ol>
        </div>
        <div class="learn-side">
          <div class="speech">この単元も<br>がんばろう！</div>
          <img class="unit-mascot" src="../../../assets/characters/sensei_m_banzai.png" alt="">
        </div>
      </div>
      <footer class="unit-footer">
        <div>つづもん 中学歴史 まとめて復習ワーク</div>
      </footer>
    </section>
  </main>
</body>
</html>
"""


def generate_html() -> list[tuple[Path, Path, Path]]:
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = []
    for ref in sorted(REFERENCE_DIR.glob("*.json")):
        chapter_no = ref.name[:2]
        data = json.loads(ref.read_text(encoding="utf-8"))
        for topic_no, topic in enumerate(data["topics"], 1):
            stem = f"{chapter_no}-{topic['topicId']}"
            html_path = HTML_DIR / f"{stem}.html"
            png_path = OUT_DIR / f"{stem}.png"
            pdf_path = OUT_DIR / f"{stem}.pdf"
            html_path.write_text(
                topic_html(chapter_no, data["volume"], data["title"], topic_no, topic),
                encoding="utf-8",
                newline="\n",
            )
            generated.append((html_path, png_path, pdf_path))
    return generated


def render(items: list[tuple[Path, Path, Path]]) -> None:
    if not EDGE.exists():
        raise FileNotFoundError(f"Edge not found: {EDGE}")
    for html_path, png_path, pdf_path in items:
        url = file_url(html_path)
        subprocess.run(
            [
                str(EDGE),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                "--window-size=1240,1754",
                f"--screenshot={png_path.resolve()}",
                url,
            ],
            check=True,
        )
        subprocess.run(
            [
                str(EDGE),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={pdf_path.resolve()}",
                url,
            ],
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html-only", action="store_true")
    args = parser.parse_args()
    items = generate_html()
    if not args.html_only:
        render(items)
    print(f"generated {len(items)} topic covers")


if __name__ == "__main__":
    main()
