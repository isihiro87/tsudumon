# -*- coding: utf-8 -*-
"""
資料図の中に写り込んでいる「答えの語句」を、周囲色でていねいに塗りつぶし（＝空欄化）、
必要に応じて丸数字マーカー（①②③）を置く。gpt-image 再生成と違い文字が壊れないので、
教材として安全。原本は assets/_backup_answers/ に退避してから上書きする。

各図の塗り領域・マーカーは EDITS に定義。座標は原寸（多くは1200x900）基準。
"""
import os
import shutil
from collections import Counter
from statistics import median

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")
BACKUP = os.path.join(ASSETS, "_backup_answers")
FONT = "C:/Windows/Fonts/msgothic.ttc"


def sample_color(im, xy, r=6):
    """xy 周辺 r 画素の中央値色を返す（塗りつぶし用の背景色）。"""
    px = im.load()
    cols = [[], [], []]
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            x, y = xy[0] + dx, xy[1] + dy
            if 0 <= x < im.width and 0 <= y < im.height:
                p = px[x, y]
                for i in range(3):
                    cols[i].append(p[i])
    return tuple(int(median(c)) for c in cols)


def blank(im, rect, fill):
    """rect(x0,y0,x1,y1) を塗る。fill が (r,g,b) ならその色、(x,y) なら周囲色を採取。"""
    color = tuple(fill) if len(fill) == 3 else sample_color(im, fill)
    ImageDraw.Draw(im).rectangle(rect, fill=color)
    return color


def detext(im, rect, thresh=34):
    """rect 内で「背景色（最多色）と大きく違う画素＝文字」だけを背景色に置換して消す。
    箱の塗り色は残るので、箱内の文字だけをきれいに消せる。マーカーは後から描き直す前提。"""
    x0, y0, x1, y1 = [int(v) for v in rect]
    px = im.load()
    cnt = Counter()
    for x in range(x0, x1):
        for y in range(y0, y1):
            cnt[px[x, y]] += 1
    bg = cnt.most_common(1)[0][0]
    for x in range(x0, x1):
        for y in range(y0, y1):
            p = px[x, y]
            d = (p[0] - bg[0]) ** 2 + (p[1] - bg[1]) ** 2 + (p[2] - bg[2]) ** 2
            if d > thresh * thresh:
                px[x, y] = bg
    return bg


def marker(im, center, ch, size=54, color=(30, 30, 30)):
    """丸数字などの文字を中央そろえで描く。"""
    dr = ImageDraw.Draw(im)
    fnt = ImageFont.truetype(FONT, size)
    bb = dr.textbbox((0, 0), ch, font=fnt)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    dr.text((center[0] - w / 2 - bb[0], center[1] - h / 2 - bb[1]), ch, font=fnt, fill=color)


def apply_steps(im, steps):
    for step in steps:
        if step[0] == "blank":
            blank(im, step[1], step[2])
        elif step[0] == "detext":
            th = step[2] if len(step) > 2 else 34
            detext(im, step[1], th)
        elif step[0] == "marker":
            size = step[3] if len(step) > 3 else 54
            col = step[4] if len(step) > 4 else (30, 30, 30)
            marker(im, step[1], step[2], size, col)


# 画像名 -> 編集手順のリスト。手順: ("blank", rect, sample_xy) / ("marker", center, char[, size])
EDITS = {
    "ritsuryo-central-org.webp": [
        # 中央の箱の「八省」を消す（箱内の薄青で塗る）
        ("blank", (222, 440, 384, 582), (232, 452)),
    ],
    "handen-shuju-cycle.webp": [
        # タイトル「班田収授法のしくみ」を白ページ色で消す（上端の枠線ごと）
        ("blank", (228, 0, 972, 116), (120, 60)),
        # 「租を納める」の「租」だけを箱内クリーム色で消し、②を置く（「を納める」は残す）
        ("blank", (476, 800, 580, 882), (760, 842)),
        ("marker", (524, 841), "②", 52),
    ],
    "goon-hoko-relation.webp": [
        # 上段「① 御恩」の行の文字を消して①を描き直す（下段「領地の保護・給与」は残す）
        ("detext", (400, 122, 802, 224)),
        ("marker", (462, 170), "①", 52),
        # 下段「② 奉公」の行の文字を消して②を描き直す（「軍役・警備」は残す）
        ("detext", (400, 652, 802, 748)),
        ("marker", (508, 698), "②", 52),
    ],
    "kango-trade-system.webp": [
        # 「① 勘合（割符）」の勘合（割符）だけ消す（①は範囲外なので残る）
        ("detext", (500, 560, 792, 640)),
    ],
    "land-tax-reform.webp": [
        # タイトル「地租改正（1873年）」を丸枠ごと消す（白ページ上）
        ("blank", (172, 12, 1010, 146), (255, 255, 255)),
        # 「地券」の見出しを消す（証明書の絵は残す。印刷サイズでは絵中の文字は微小で不読）
        ("detext", (452, 250, 622, 346)),
    ],
    "bubble-economy-graph.webp": [
        # タイトルの「（バブル経済）」だけ消す（「株価と地価の推移」は残す）
        ("blank", (778, 8, 1192, 128), (255, 255, 255)),
        # 注釈「バブル経済」の文字を消して①（白）を置く（赤ベタ枠は残す）
        ("detext", (272, 150, 594, 232)),
        ("marker", (322, 190), "①", 46, (255, 255, 255)),
        # 注釈「バブル崩壊」の文字を消して②を置く（青枠は残す）
        ("detext", (650, 234, 876, 306)),
        ("marker", (690, 268), "②", 42),
    ],
    "jomon-yayoi-housing.webp": [
        # 「狩り・採集」の採集を消す（狩り・は残す）
        ("detext", (270, 752, 505, 838)),
        # 「水田・稲作」の稲作を白で消す（水田・は残す。米をたくわえるには触れない）
        ("blank", (828, 790, 980, 876), (255, 255, 255)),
    ],
    "ww1-two-alliances-map.webp": [
        # 「三国同盟」の見出しを消す（国名の並びは残す）
        ("detext", (296, 512, 600, 552)),
        # 「三国協商」の見出しを消す
        ("detext", (28, 604, 334, 648)),
    ],
    "cold-war-blocs.webp": [
        # 「資本主義陣営」の見出しを消す（アメリカ中心は残す）
        ("detext", (205, 184, 432, 224)),
        # 「社会主義陣営」の見出しを消す（ソ連中心は残す）
        ("detext", (670, 200, 872, 242)),
    ],
    "age-of-discovery-routes.webp": [
        # 「コロンブス」を白で消す（（1492）は残す。箱内白）
        ("blank", (320, 226, 486, 272), (255, 255, 255)),
        # 「バスコ=ダ=ガマ」を白で消す（インド航路は残す）
        ("blank", (446, 568, 662, 612), (255, 255, 255)),
    ],
    "pacific-war-relations.webp": [
        # 「日独伊三国同盟」の文字を白で消す（太字密集のためdetext不可。白背景）
        ("blank", (356, 212, 660, 252), (255, 255, 255)),
        # 「ABCD包囲陣」の文字を白で消す
        ("blank", (472, 812, 872, 872), (255, 255, 255)),
    ],
    "manchuria-war-route.webp": [
        # タイトル「満州事変と日中戦争」を消す（金色下線ごと）
        ("blank", (330, 26, 872, 120), (255, 255, 255)),
        # オレンジ地域内の「満州国」を消す（色地なのでしきい値低め）
        ("detext", (573, 253, 684, 298), 20),
    ],
    "genko-route-map.webp": [
        # 「対馬」を消す（朝鮮半島に最も近い島＝Q1の答え）
        ("detext", (368, 418, 458, 468)),
        # 「博多湾」を消す
        ("detext", (638, 602, 742, 648)),
    ],
    "sakoku-four-windows.webp": [
        # 「長崎」を消す（オランダ・中国 は残す）
        ("detext", (115, 548, 200, 588)),
        # 「琉球」を消す（薩摩 は残す）
        ("detext", (135, 786, 232, 824)),
    ],
    "triangular-trade-opium.webp": [
        # 緑の矢印上の「茶」を消す
        ("detext", (552, 178, 624, 234)),
    ],
    "era-scale-diagram.webp": [
        # タイトル「西暦・世紀・年代の表し方」を消す（西暦・世紀が答え）
        ("blank", (55, 30, 1145, 124), (255, 255, 255)),
        # 「1世紀/2世紀/3世紀」の“世紀”を消し、数字は残す
        ("detext", (525, 348, 672, 406)),
        ("detext", (750, 348, 898, 406)),
        ("detext", (965, 348, 1112, 406)),
    ],
    "treaty-ports-map.webp": [
        # A の近くの「浦賀」ラベルを消す（ペリー来航地＝Q3の答え）
        ("detext", (745, 635, 812, 668)),
        # 凡例の「浦賀」を消す
        ("detext", (972, 758, 1052, 792)),
    ],
    "meiji-constitution-org.webp": [
        # ③の説明「天皇が率いる」を消す（①＝天皇の答えが露出するため）。③マーカーは残す
        ("detext", (895, 608, 1100, 655)),
    ],
    "sino-japanese-war-caricature-diagram.webp": [
        # 「① 朝鮮」の朝鮮を消す（①は残す）
        ("detext", (575, 82, 668, 138)),
        # 「日清戦争（1894年)」のラベルを消す（Q2の答えにするため）
        ("detext", (418, 778, 748, 832)),
    ],
    "voter-increase-bar.webp": [
        # 注釈「1925年 普通選挙法」の“普通選挙法”を消す（1925年は残す）
        ("detext", (550, 350, 765, 405)),
    ],
    "land-reform-bar.webp": [
        # タイトル「農地改革」を消す
        ("blank", (455, 32, 725, 100), (255, 255, 255)),
    ],
    "high-growth-gnp-chart.webp": [
        # タイトル「高度経済成長期の実質GNP成長率」を消す（高度経済成長が答え）
        ("blank", (160, 24, 1145, 110), (255, 255, 255)),
        # 「石油危機（1973年)」の“石油危機”を消す（（1973年)は残す）
        ("detext", (1040, 455, 1165, 502)),
    ],
}


def main():
    os.makedirs(BACKUP, exist_ok=True)
    for name, steps in EDITS.items():
        src = os.path.join(ASSETS, name)
        bak = os.path.join(BACKUP, name)
        if not os.path.exists(bak):
            shutil.copy2(src, bak)  # 原本退避（初回のみ）
        im = Image.open(bak).convert("RGB")  # 常に原本から作り直す（多重加工を防ぐ）
        apply_steps(im, steps)
        im.save(src, quality=92)
        print(f"blanked: {name} ({len(steps)} steps)")


if __name__ == "__main__":
    main()
