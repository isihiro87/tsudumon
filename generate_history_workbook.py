# -*- coding: utf-8 -*-
"""
marutto-study の data/content/history のトピックJSONから、
市販ワーク（新ワーク・ワーク・必修テキスト）のいいところどり構成の
印刷用 A4 問題集 HTML を生成する。

構成（1冊 = 1章フォルダ）:
  0. 年表でチェック（穴埋め年表 — 新ワーク方式）
  各トピック:
    A 要点まとめ（穴埋め文 — 新ワーク方式）
    B 一問一答（チェックボックス＋右端解答欄 — ワーク/必修テキスト方式）
    C 実戦問題（4択 — アプリquiz由来）
  巻末: 解答

使い方:
  python generate_history_workbook.py            # 04-ancient-state を生成
その後 Edge ヘッドレスで PDF 化（build.ps1 参照）
"""
import base64
import io
import json
import random
import re
import html
import urllib.parse
from pathlib import Path

try:
    import segno
except ImportError:
    segno = None

# 公式LINE（チャットでスタディ）のベーシックID。oaMessage リンクの宛先。
# Messaging API GET /v2/bot/info の basicId で確認済み（@chatstudy はLP用の飾りIDで不可）。
LINE_BASIC_ID = "@824cebif"
# QR即出題用 LIFF（units の LIFF にパス /wb を連結して使う。VITE_LIFF_ID_UNITS と同じ値）。
# QRを読むと LIFF が開き、送信操作なしにワーク開始カードがトークに push される。
LIFF_ID_UNITS = "2009587166-LjyCza2c"

CONTENT_ROOT = Path(r"C:\Users\user\projects\education-apps\marutto-study\data\content")
# 歴史の章は books/*.json に contentDir が無いため history/{フォルダ名} を既定にする。
CONTENT_DIR = CONTENT_ROOT / "history"
OUT_DIR = Path(__file__).parent / "output"

RUBY_RE = re.compile(r"\{([^|{}]+)\|([^|{}]+)\}")


def to_ruby(text: str) -> str:
    """{漢字|よみ} → <ruby>漢字<rt>よみ</rt></ruby>"""
    return RUBY_RE.sub(lambda m: f"<ruby>{html.escape(m.group(1))}<rt>{html.escape(m.group(2))}</rt></ruby>",
                       html.escape(text).replace("&#x27;", "'"))


def esc(text: str) -> str:
    return html.escape(text)


CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def c_num(i: int) -> str:
    return CIRCLED[i] if i < len(CIRCLED) else f"({i + 1})"


# ============================================================
# 章データの読み込み（[[答え]] が空欄になる）
# ============================================================

BOOKS_DIR = Path(__file__).parent / "books"
# 章ごとの手書きデータ（年表・要点まとめ）は books/{章フォルダ}.json に置く
BOOKS = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(BOOKS_DIR.glob("*.json"))}

BLANK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")

N_ITTOITTO = 14   # 一問一答の既定数（歴史）
N_QUIZ = 8        # 実戦4択の既定数（歴史。Dの記述問題と同じページに収める）
KATAKANA = "アイウエ"


def resolve_count(spec, key, default, total):
    """章ごとの問題数上限を解決する。
    spec[key] が "all" なら全問（total）、数値ならその値、未指定なら default。
    理科は素材が豊富なので books に "nItto":"all" / "nQuiz":"all" を入れて全問収録する。"""
    v = spec.get(key)
    if v is None:
        return default
    if v == "all":
        return total
    return int(v)


def split_blanks(text: str):
    """[[答え]] 入りテキスト → (segments, answers)。segment は (kind, str)"""
    segments, answers = [], []
    pos = 0
    for m in BLANK_RE.finditer(text):
        if m.start() > pos:
            segments.append(("text", text[pos:m.start()]))
        answers.append(m.group(1))
        segments.append(("blank", m.group(1)))
        pos = m.end()
    if pos < len(text):
        segments.append(("text", text[pos:]))
    return segments, answers


def ruby_base(text: str) -> str:
    """ルビ記法を取り除いた表記本体"""
    return RUBY_RE.sub(lambda m: m.group(1), text)


def blank_width(answer: str, per: float = 5.0, pad: float = 5.0, lo: float = 15.0, hi: float = 50.0) -> float:
    """解答の文字数に応じた記入欄の幅(mm)"""
    return round(max(lo, min(hi, per * len(ruby_base(answer)) + pad)), 1)


def render_blank_text(text: str, start_idx: int = 0):
    """穴埋め文を HTML に。空欄幅は答えの長さに応じて可変。戻り値 (html, answers)"""
    segments, answers = split_blanks(text)
    out, i = [], start_idx
    for kind, s in segments:
        if kind == "text":
            out.append(esc(s))
        else:
            w = blank_width(s)
            out.append(f'<span class="blank">（{c_num(i)}<span class="bl" style="width:{w}mm"></span>）</span>')
            i += 1
    return "".join(out), answers


def pick_flashcards(cards, n):
    order = {"basic": 0, "standard": 1, "advanced": 2}
    ranked = sorted(range(len(cards)), key=lambda i: (order.get(cards[i].get("difficulty"), 3), i))
    chosen = sorted(ranked[:n])
    return [cards[i] for i in chosen]


def pick_quiz(questions, n):
    order = {"standard": 0, "advanced": 1, "basic": 2}
    ranked = sorted(range(len(questions)), key=lambda i: (order.get(questions[i].get("difficulty"), 3), i))
    chosen = sorted(ranked[:n])
    return [questions[i] for i in chosen]


def gen_targets(n: int, rng: random.Random, n_opts: int = 4):
    """正解位置の列を自然なランダムで生成する。制約:
    ①どの記号も1回以上（n>=n_opts のとき）
    ②1つの記号が多すぎない（ceil(n/n_opts)+1 回まで）
    連続は自然な現象なのであえて制限しない。"""
    max_count = -(-n // n_opts) + 1
    while True:
        seq = [rng.randrange(n_opts) for _ in range(n)]
        counts = [seq.count(k) for k in range(n_opts)]
        if max(counts) > max_count:
            continue
        if n >= n_opts and min(counts) < 1:
            continue
        return seq


def rebalance_quiz(quiz, seed: str):
    """元データの correctIndex は偏りがあるため、正解位置がア〜エに
    自然に散らばるよう選択肢を並べ替える（seed 固定で再現可能）。"""
    rng = random.Random(seed)
    targets = gen_targets(len(quiz), rng)
    out = []
    for q, t in zip(quiz, targets):
        opts = q["options"]
        correct = opts[q["correctIndex"]]
        others = [o for i, o in enumerate(opts) if i != q["correctIndex"]]
        rng.shuffle(others)
        t = min(t, len(others))
        new_opts = others[:t] + [correct] + others[t:]
        q2 = dict(q)
        q2["options"] = new_opts
        q2["correctIndex"] = t
        out.append(q2)
    return out


def build_qr_box(topic_name: str, description_html: str) -> str:
    """QR即出題（LIFF）へのQR＋クリックリンクの案内ボックスを組み立てる。
    QRを読むと LIFF ページが開き、送信操作なしに問題がトークへ届く。"""
    if segno is None:
        return ""
    qr_url = (f"https://liff.line.me/{LIFF_ID_UNITS}/wb"
              f"?t={urllib.parse.quote(topic_name)}")
    buf = io.BytesIO()
    segno.make(qr_url, error="m").save(buf, kind="png", scale=6, border=2)
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return f"""
  <div class="qr-box">
    <a href="{qr_url}" target="_blank" rel="noopener"><img class="qr-img" src="data:image/png;base64,{qr_b64}"></a>
    <div class="qr-text">
      <div class="qr-title">📱 スマホでこの単元の問題に挑戦！</div>
      <div>{description_html}</div>
      <div class="qr-link">PDFで見ている人はこちら → <a href="{qr_url}" target="_blank" rel="noopener">LINEで問題を解く</a></div>
    </div>
  </div>
"""


def build_book(folder: str) -> str:
    spec = BOOKS[folder]
    # 理科などは spec["contentDir"]（data/content からの相対パス）で章フォルダを指す
    era_dir = (CONTENT_ROOT / spec["contentDir"]) if spec.get("contentDir") else (CONTENT_DIR / folder)
    # 理科はファイル名（observation.json）と topicId（sci1-observation）が一致しないため、
    # フォルダを走査して topicId で引く。
    by_topic_id = {}
    for f in era_dir.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(d, dict) and "topicId" in d:
            by_topic_id[d["topicId"]] = d
    topics = [by_topic_id[tid] for tid in spec["topics"]]

    body = []
    answer_sections = []
    used_images = set()

    # ---------- 表紙帯 ----------
    body.append(f"""
<header class="cover">
  <div class="cover-vol">{esc(spec['volume'])}</div>
  <div class="cover-main">
    <h1>{esc(spec['title'])}　<span class="cover-sub">{esc(spec['subtitle'])}</span></h1>
    <div class="cover-note">まとめて復習ワーク（要点まとめ・一問一答・実戦問題）</div>
  </div>
  <div class="name-box">名前<span></span></div>
</header>""")

    # ---------- 年表でチェック（理科等は checkTitle/checkCols で差し替え可） ----------
    check_title = spec.get("checkTitle", "年表でチェック")
    check_cols = spec.get("checkCols", ["年代", "できごと"])
    tl_rows, tl_answers = [], []
    idx = 0
    for year, ev in spec["timeline"]:
        ev_html, ans = render_blank_text(ev, idx)
        idx += len(ans)
        tl_answers.extend(ans)
        tl_rows.append(f"<tr><td class='tl-year'>{esc(year)}</td><td>{ev_html}</td></tr>")
    tl_qr = ""
    if spec.get("lineQr"):
        tl_qr = build_qr_box(
            f"{spec['title']}の年表",
            f"QRコードを読み取ると、公式LINEで「{esc(spec['title'])}の年表」の穴埋めを入力形式で解けるよ。"
        )
    body.append(f"""
<section class="timeline">
  <h2 class="sec-band"><span class="sec-tag">{esc(check_title)}</span>（　）にあてはまる語句を答えよう</h2>
  <table class="tl-table"><tr><th class="tl-year">{esc(check_cols[0])}</th><th>{esc(check_cols[1])}</th></tr>{''.join(tl_rows)}</table>
{tl_qr}</section>""")
    answer_sections.append((check_title, [("", tl_answers, None)]))

    # ---------- 各トピック ----------
    for t_i, topic in enumerate(topics, 1):
        tid = topic["topicId"]
        summary_html, summary_ans = render_blank_text(spec["summaries"][tid])
        n_itto = resolve_count(spec, "nItto", N_ITTOITTO, len(topic["flashcards"]))
        n_quiz = resolve_count(spec, "nQuiz", N_QUIZ, len(topic["quiz"]["questions"]))
        cards = pick_flashcards(topic["flashcards"], n_itto)
        quiz = rebalance_quiz(pick_quiz(topic["quiz"]["questions"], n_quiz), tid)

        qa_rows = []
        for i, card in enumerate(cards, 1):
            w = blank_width(card["front"], per=7.0, pad=10.0, lo=30.0, hi=75.0)
            qa_rows.append(f"""
      <div class="qa-row">
        <div class="qa-q"><span class="chk"></span><span class="qa-no">({i})</span>{esc(card['back'])}</div>
        <div class="qa-ans" style="width:{w}mm"></div>
      </div>""")

        written = spec.get("written", {}).get(tid, [])
        w_rows = []
        for i, w in enumerate(written, 1):
            kw = ""
            if w.get("keywords"):
                chips = "".join(f"<span class='kw-chip'>{esc(k)}</span>" for k in w["keywords"])
                kw = f"<span class='kw-note'>指定語句{chips}</span>"
            w_rows.append(f"""
      <div class="w-row">
        <div class="w-q"><span class="qa-no">({i})</span>{esc(w['q'])}{kw}</div>
        <div class="wline"></div><div class="wline"></div>
      </div>""")
        written_html = ""
        if w_rows:
            written_html = f"""
  <h3 class="sec-band"><span class="sec-tag">D　記述問題</span>文章で説明しよう<span class="score">／{len(w_rows)}問</span></h3>
  <div class="w-list">{''.join(w_rows)}</div>
"""

        shiryo = spec.get("shiryo", {}).get(tid, [])
        s_rows = []
        s_no = 0
        for item in shiryo:
            img_path = (Path(__file__).parent / "assets" / item["image"]).as_uri()
            used_images.add(item["image"])
            qs = []
            for w in item["questions"]:
                s_no += 1
                aw = blank_width(w["a"], per=7.0, pad=10.0, lo=30.0, hi=70.0)
                qs.append(f"""
        <div class="s-q"><span class="qa-no">({s_no})</span>{esc(w['q'])}
          <div class="s-ans" style="width:{aw}mm"></div></div>""")
            cap = f"<div class='s-cap'>{esc(item['caption'])}</div>" if item.get("caption") else ""
            s_rows.append(f"""
      <div class="s-row">
        <div class="s-img"><img src="{img_path}">{cap}</div>
        <div class="s-qs">{''.join(qs)}</div>
      </div>""")
        shiryo_html = ""
        # 資料の呼び方は教科で切替（理科=図、歴史=写真）。books の shiryoVerb で上書き可。
        shiryo_verb = spec.get("shiryoVerb", "写真")
        if s_rows:
            shiryo_html = f"""
  <h3 class="sec-band"><span class="sec-tag">E　資料問題</span>{shiryo_verb}を見て答えよう<span class="score">／{s_no}問</span></h3>
  <div class="s-list">{''.join(s_rows)}</div>
"""

        # ---------- F 資料マッチング（複数資料 → 文と対応させる。手本の定番形式） ----------
        match = spec.get("shiryoMatch", {}).get(tid)
        match_html = ""
        if match:
            res_cards = "".join(
                f"""<figure class="m-res"><span class="m-lab">{esc(r['label'])}</span>"""
                f"""<img src="{(Path(__file__).parent / 'assets' / r['image']).as_uri()}"></figure>"""
                for r in match["resources"]
            )
            for r in match["resources"]:
                used_images.add(r["image"])
            item_rows = "".join(
                f"""<div class="m-item"><span class="qa-no">({i + 1})</span>{esc(it['text'])}"""
                f"""<span class="m-box"></span></div>"""
                for i, it in enumerate(match["items"])
            )
            labels = "・".join(esc(r["label"]) for r in match["resources"])
            match_html = f"""
  <h3 class="sec-band"><span class="sec-tag">F　資料の対応</span>次の文にあてはまる資料を{labels}から選ぼう<span class="score">／{len(match['items'])}問</span></h3>
  <div class="m-res-row">{res_cards}</div>
  <div class="m-list">{item_rows}</div>
"""

        qr_html = ""
        if tid in spec.get("lineQr", []):
            # QR即出題: 読み取ると LIFF 経由でこの単元の問題（4択/一問一答/記述）が
            # 送信操作なしにトークへ届く（webhook 側 workbookLaunch → pushWorkbookStart）。
            qr_html = build_qr_box(
                topic['name'],
                f"QRコードを読み取ると、公式LINEのトークに「{esc(topic['name'])}」の"
                "4択・一問一答・記述問題がすぐ届くよ。解説つきだから復習にぴったり！"
            )

        quiz_rows = []
        for i, q in enumerate(quiz, 1):
            opts = "".join(
                f"<div class='opt'><span class='opt-k'>{KATAKANA[j]}</span>{esc(o)}</div>"
                for j, o in enumerate(q["options"]))
            quiz_rows.append(f"""
      <div class="quiz-row">
        <div class="quiz-q"><span class="qa-no">({i})</span>{esc(q['question'])}
          <div class="opts">{opts}</div>
        </div>
        <div class="quiz-ans">〔　　〕</div>
      </div>""")

        body.append(f"""
<section class="topic">
  <h2 class="topic-band"><span class="topic-no">{t_i}</span>
    <span class="topic-name">{esc(topic['name'])}</span>
    <span class="topic-sub">{esc(topic['subtitle'])}</span></h2>
{qr_html}
  <h3 class="sec-band"><span class="sec-tag">A　要点まとめ</span>（　）にあてはまる語句を答えよう</h3>
  <div class="summary">{summary_html}</div>
  <div class="mini-ans">解答欄　{''.join(f"<span class='mini-cell' style='min-width:{blank_width(a, per=6.5, pad=12.0, lo=24.0, hi=72.0)}mm'>{c_num(i)}</span>" for i, a in enumerate(summary_ans))}</div>

  <h3 class="sec-band"><span class="sec-tag">B　一問一答</span>次の問いに答えよう<span class="score">／{len(cards)}問</span></h3>
  <div class="qa-list">{''.join(qa_rows)}</div>

  <h3 class="sec-band"><span class="sec-tag">C　実戦問題</span>正しいものを記号で選ぼう<span class="score">／{len(quiz)}問</span></h3>
  <div class="quiz-list">{''.join(quiz_rows)}</div>
{written_html}{shiryo_html}{match_html}</section>""")

        groups = [
            ("A 要点まとめ", summary_ans, None),
            ("B 一問一答", [card["front"] for card in cards], "ruby"),
            ("C 実戦問題", [(KATAKANA[q["correctIndex"]], q["options"][q["correctIndex"]]) for q in quiz], "quiz"),
        ]
        if written:
            groups.append(("D 記述問題", [w["a"] for w in written], "written"))
        if shiryo:
            groups.append(("E 資料問題", [w["a"] for item in shiryo for w in item["questions"]], None))
        if match:
            groups.append(("F 資料の対応", [it["answer"] for it in match["items"]], None))
        answer_sections.append((f"{t_i}　{topic['name']}", groups))

    # ---------- 巻末解答 ----------
    ans_html = []
    for title, groups in answer_sections:
        parts = []
        for label, items, kind in groups:
            if kind == "ruby":
                cells = "　".join(f"<span class='a-item'>({i + 1}) {to_ruby(a)}</span>" for i, a in enumerate(items))
            elif kind == "written":
                cells = "".join(f"<div class='a-written'>({i + 1}) {esc(a)}</div>" for i, a in enumerate(items))
            elif kind == "quiz":
                cells = "　".join(f"<span class='a-item'>({i + 1}) <b>{k}</b>（{esc(o)}）</span>"
                                  for i, (k, o) in enumerate(items))
            else:
                cells = "　".join(f"<span class='a-item'>{c_num(i)} {esc(a)}</span>" for i, a in enumerate(items))
            label_html = f"<span class='a-label'>{esc(label)}</span>" if label else ""
            parts.append(f"<div class='a-group'>{label_html}{cells}</div>")
        ans_html.append(f"<div class='a-topic'><div class='a-title'>{esc(title)}</div>{''.join(parts)}</div>")

    credits_html = ""
    credits_path = Path(__file__).parent / "assets" / "credits.json"
    if used_images and credits_path.exists():
        creds = {c["file"]: c for c in json.loads(credits_path.read_text(encoding="utf-8"))}
        lines = []
        for f in sorted(used_images):
            c = creds.get(f)
            if c:
                lines.append(f"{esc(c['source'])}（{esc(c['artist'])} / {esc(c['license'])} / Wikimedia Commons）")
        if lines:
            credits_html = "<div class='credits'>画像出典: " + "　".join(lines) + "</div>"

    body.append(f"""
<section class="answers">
  <h2 class="ans-band">解答</h2>
  {''.join(ans_html)}
  {credits_html}
</section>""")

    return HTML_TEMPLATE.replace("__TITLE__", f"{spec['volume']}　{spec['title']}").replace("__BODY__", "".join(body))


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  @page { size: A4; margin: 13mm 12mm 14mm 12mm; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Yu Gothic", "Meiryo", sans-serif;
    font-size: 10.5pt; line-height: 1.75; color: #1c1917;
  }
  ruby rt { font-size: 0.5em; }

  /* ---- 表紙帯 ---- */
  .cover { display: flex; align-items: center; gap: 6mm; border: 2.5px solid #b45309;
           border-radius: 3mm; padding: 3.2mm 6mm; margin-bottom: 4.5mm; }
  .cover-vol { background: #b45309; color: #fff; font-weight: bold; font-size: 13pt;
               padding: 2mm 4mm; border-radius: 2mm; white-space: nowrap; }
  .cover-main { flex: 1; }
  .cover h1 { font-size: 17pt; }
  .cover-sub { display: block; font-size: 11pt; font-weight: normal; color: #57534e; margin-top: 0.5mm; }
  .cover-note { font-size: 9pt; color: #78716c; }
  .name-box { font-size: 9pt; color: #57534e; align-self: flex-end; }
  .name-box span { display: inline-block; width: 42mm; border-bottom: 1px solid #78716c; margin-left: 2mm; }

  /* ---- セクション帯 ---- */
  .sec-band { font-size: 10.5pt; font-weight: normal; margin: 4.5mm 0 2mm;
              border-bottom: 2px solid #b45309; padding-bottom: 0.8mm; }
  .sec-tag { display: inline-block; background: #b45309; color: #fff; font-weight: bold;
             padding: 0.3mm 3.5mm; border-radius: 1.5mm 1.5mm 0 0; margin-right: 3mm; }
  .score { float: right; color: #57534e; font-size: 9.5pt; }

  /* ---- 年表 ---- */
  .tl-table { width: 100%; border-collapse: collapse; }
  .tl-table th, .tl-table td { border: 1px solid #44403c; padding: 0.4mm 2.2mm; line-height: 1.65; }
  .tl-table th { background: #f5f5f4; font-size: 9.5pt; }
  .tl-year { width: 22mm; text-align: center; white-space: nowrap; }

  /* ---- トピック帯 ---- */
  .topic { page-break-before: always; }
  .topic-band { display: flex; align-items: baseline; gap: 3mm; background: #fef3c7;
                border-left: 5mm solid #b45309; padding: 1.6mm 3mm; font-size: 13pt; }
  .topic-no { background: #b45309; color: #fff; border-radius: 50%; width: 7mm; height: 7mm;
              display: inline-flex; align-items: center; justify-content: center;
              font-size: 11pt; align-self: center; flex: none; }
  .topic-sub { font-size: 9.5pt; font-weight: normal; color: #78716c; margin-left: auto; }

  /* ---- 要点まとめ ---- */
  .summary { border: 1.5px solid #a8a29e; border-radius: 2mm; padding: 2.5mm 4mm;
             text-align: justify; }
  .blank { white-space: nowrap; }
  .blank .bl { display: inline-block; }
  .mini-ans { margin-top: 1.5mm; font-size: 9pt; color: #57534e; display: flex; flex-wrap: wrap; gap: 1.5mm; align-items: center; }
  .mini-cell { display: inline-block; border: 1px solid #a8a29e; padding: 0 1.5mm 6.5mm 1.5mm; border-radius: 1mm; }

  /* ---- 一問一答 ---- */
  .qa-row { display: flex; align-items: flex-end; gap: 3mm; padding: 0.9mm 0; }
  .qa-q { flex: 1; }
  .chk { display: inline-block; width: 3.2mm; height: 3.2mm; border: 1.2px solid #57534e;
         margin-right: 2mm; vertical-align: 0; }
  .qa-no { font-weight: bold; margin-right: 1.5mm; }
  .qa-ans { flex: none; border-bottom: 1px solid #44403c; height: 6mm; }

  /* ---- 実戦4択 ---- */
  .quiz-row { display: flex; align-items: flex-start; gap: 2mm; padding: 1.2mm 0; }
  .quiz-q { flex: 1; }
  .opts { display: grid; grid-template-columns: 1fr 1fr; gap: 0 4mm; margin: 0.5mm 0 0 6mm; font-size: 10pt; }
  .opt-k { display: inline-block; border: 1px solid #78716c; border-radius: 50%;
           width: 4.6mm; height: 4.6mm; text-align: center; line-height: 4.4mm;
           font-size: 8.5pt; margin-right: 1.6mm; }
  .quiz-ans { flex: none; white-space: nowrap; align-self: center; }

  /* ---- 記述問題 ---- */
  .w-row { padding: 1.2mm 0; }
  .kw-note { font-size: 9pt; color: #57534e; margin-left: 2.5mm; white-space: nowrap; }
  .kw-chip { display: inline-block; border: 1px solid #b45309; color: #b45309; border-radius: 1mm;
             padding: 0 1.8mm; margin-left: 1.5mm; font-size: 9pt; }
  .wline { border-bottom: 1px solid #78716c; height: 8.5mm; margin: 0 2mm 0 6mm; }
  .a-written { padding-left: 2mm; }

  /* ---- 資料問題 ---- */
  .s-row { display: flex; gap: 5mm; padding: 2mm 0; align-items: flex-start; }
  .s-img { flex: none; width: 84mm; }
  .s-img img { width: 100%; border: 1px solid #a8a29e; }
  .s-cap { font-size: 8.5pt; color: #78716c; text-align: center; }
  .s-qs { flex: 1; }
  .s-q { margin-bottom: 3mm; }
  .s-ans { border-bottom: 1px solid #44403c; height: 7mm; margin: 1mm 0 0 6mm; }
  .s-row { break-inside: avoid; }
  /* ---- F 資料の対応（マッチング） ---- */
  .m-res-row { display: flex; gap: 5mm; margin: 2mm 0 3mm; flex-wrap: wrap; }
  .m-res { flex: none; width: 52mm; text-align: center; break-inside: avoid; }
  .m-res img { width: 100%; border: 1px solid #a8a29e; }
  .m-lab { display: block; font-weight: bold; color: #b45309; font-size: 10pt; margin-bottom: 1mm; }
  .m-list { }
  .m-item { margin-bottom: 2.5mm; display: flex; align-items: baseline; gap: 2mm; }
  .m-box { display: inline-block; width: 14mm; height: 6mm; border: 1px solid #44403c; border-radius: 1mm;
           margin-left: auto; flex: none; }
  .credits { margin-top: 4mm; font-size: 7.5pt; color: #78716c; border-top: 1px solid #d6d3d1; padding-top: 1mm; }

  /* ---- LINE QR ---- */
  .qr-box { display: flex; gap: 4mm; align-items: center; border: 1.5px dashed #b45309;
            border-radius: 2mm; padding: 3mm 4mm; margin-top: 4mm; background: #fffbeb;
            break-inside: avoid; }
  .qr-img { width: 24mm; height: 24mm; flex: none; }
  .qr-text { font-size: 9.5pt; line-height: 1.6; }
  .qr-title { font-weight: bold; color: #b45309; margin-bottom: 1mm; }
  .qr-link a { color: #b45309; font-weight: bold; text-decoration: underline; }
  .qa-row, .quiz-row, .w-row, .a-topic, .summary { break-inside: avoid; }
  .sec-band { break-after: avoid; }

  /* ---- 解答 ---- */
  .answers { page-break-before: always; }
  .ans-band { background: #44403c; color: #fff; text-align: center; padding: 1mm 0;
              border-radius: 1.5mm; margin-bottom: 3mm; font-size: 13pt; }
  .answers { font-size: 9pt; line-height: 1.9; }
  .a-topic { border-bottom: 1px dashed #a8a29e; padding: 1.5mm 0; }
  .a-title { font-weight: bold; background: #f5f5f4; padding: 0 2mm; border-left: 3mm solid #b45309; }
  .a-label { font-weight: bold; color: #b45309; margin-right: 2mm; }
  .a-item { display: inline-block; margin-right: 1mm; }

  @media print { .sec-band, .topic-band, .ans-band, .sec-tag, .topic-no, .a-title
                 { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
</style>
</head>
<body>
__BODY__
</body>
</html>
"""


if __name__ == "__main__":
    OUT_DIR.mkdir(exist_ok=True)
    for folder in BOOKS:
        html_text = build_book(folder)
        out = OUT_DIR / f"{folder}.html"
        out.write_text(html_text, encoding="utf-8")
        print(f"generated: {out}")
