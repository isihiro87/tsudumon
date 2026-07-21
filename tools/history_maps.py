# -*- coding: utf-8 -*-
"""
参考書の歴史地図を「実在の海岸線データ（Natural Earth・パブリックドメイン）」から
正確に描画するツール。AIの自由生成だと地理が崩れるため、地形は本物のデータを使い、
日本語ラベル・矢印・マーカーだけを重ねる。

- ベースデータ: Natural Earth 50m Admin0 countries（public domain）。
  無ければ tools/_mapdata/ne_50m_admin_0_countries.geojson に自動ダウンロード。
- 出力: assets/reference/<name>.webp（幅1200・そのまま参考書 section.image に使える）
- 実行: python -X utf8 tools/history_maps.py            # 全地図を生成
        python -X utf8 tools/history_maps.py hakusukinoe # 指定だけ

新しい章の地図を足すときは MAKERS に関数を追加する（extent と label/arrow だけ書けばよい）。
地図は必ず生成後に目視で地形とラベル位置を確認すること（地図は崩れやすい）。
"""
import json
import urllib.request
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly, FancyArrowPatch
from matplotlib.font_manager import FontProperties
import matplotlib.patheffects as pe

BASE = Path(__file__).resolve().parent.parent
ASSET = BASE / "assets" / "reference"
DATA = Path(__file__).resolve().parent / "_mapdata"
GEOJSON = DATA / "ne_50m_admin_0_countries.geojson"
GEOJSON_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
               "master/geojson/ne_50m_admin_0_countries.geojson")
FONT = "C:/Windows/Fonts/YuGothB.ttc"

SEA = "#dCEBF2"
LAND = "#e4ecCf"
COAST = "#9db06f"


def _load_features():
    if not GEOJSON.exists():
        DATA.mkdir(parents=True, exist_ok=True)
        print("downloading Natural Earth 50m (public domain) ...")
        urllib.request.urlretrieve(GEOJSON_URL, GEOJSON)
    return json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]


def _rings(feat):
    g = feat["geometry"]
    if g["type"] == "Polygon":
        return [g["coordinates"][0]]
    if g["type"] == "MultiPolygon":
        return [p[0] for p in g["coordinates"]]
    return []


def base_map(extent, lands=("China", "North Korea", "South Korea", "Japan", "Russia")):
    """実在海岸線でベース地図を描き (fig, ax) を返す。extent=(lon0,lon1,lat0,lat1)。"""
    lon0, lon1, lat0, lat1 = extent
    ml = (lat0 + lat1) / 2
    feats = _load_features()
    fig = plt.figure(figsize=(12, 12 * ((lat1 - lat0) / np.cos(np.deg2rad(ml))) / (lon1 - lon0)))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(lon0, lon1); ax.set_ylim(lat0, lat1)
    ax.set_aspect(1 / np.cos(np.deg2rad(ml))); ax.axis("off")
    ax.add_patch(plt.Rectangle((lon0, lat0), lon1 - lon0, lat1 - lat0, facecolor=SEA, zorder=0))
    for f in feats:
        if f["properties"].get("NAME") not in lands:
            continue
        for ring in _rings(f):
            ax.add_patch(MplPoly(np.array(ring), closed=True,
                                 facecolor=LAND, edgecolor=COAST, linewidth=0.5, zorder=1))
    return fig, ax


def lab(ax, lon, lat, txt, size, color="#3a3327", ha="center", va="center"):
    t = ax.text(lon, lat, txt, fontproperties=FontProperties(fname=FONT, size=size),
                color=color, ha=ha, va=va, zorder=6)
    t.set_path_effects([pe.withStroke(linewidth=4, foreground="#fffdf8")])
    return t


def save(fig, name):
    ASSET.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    import io
    buf = io.BytesIO()
    fig.savefig(buf, dpi=130, format="png")
    plt.close(fig)
    buf.seek(0)
    im = Image.open(buf).convert("RGB")
    if im.width > 1200:
        im = im.resize((1200, round(im.height * 1200 / im.width)), Image.LANCZOS)
    out = ASSET / f"{name}.webp"
    im.save(out, "WEBP", quality=88, method=6)
    print("saved", out)


# ── 各地図 ───────────────────────────────────────────────
def hakusukinoe():
    """白村江の戦い（663）と九州の防衛。歴史④ taika-reform 節2。"""
    fig, ax = base_map((119.5, 143.5, 29.5, 43.0))
    lab(ax, 121.3, 38.6, "唐", 38)
    lab(ax, 126.0, 40.8, "高句麗", 25)
    lab(ax, 127.0, 37.4, "百済", 25, color="#7a3b12")
    lab(ax, 129.2, 36.0, "新羅", 25, color="#155e3a")
    lab(ax, 137.8, 35.5, "倭（日本）", 28)
    bx, by = 126.72, 36.02
    ax.plot(bx, by, "o", color="#c0392b", markersize=14, zorder=7, mec="#fff", mew=1.5)
    lab(ax, bx - 0.3, by + 0.05, "白村江", 24, color="#a01e12", ha="right", va="center")
    ax.plot(130.62, 33.55, "s", color="#4a4a4a", markersize=9, zorder=7, mec="#fff", mew=1.2)
    lab(ax, 130.92, 33.30, "大宰府", 20, ha="left", va="top")
    ax.plot([130.40, 130.52], [33.66, 33.60], color="#6b4b2a", lw=3, ls=(0, (3, 2)), zorder=7)
    lab(ax, 130.15, 33.78, "水城", 18, ha="right", va="bottom", color="#6b4b2a")
    lab(ax, 131.5, 32.0, "防人", 21, color="#333")
    ax.add_patch(FancyArrowPatch((133.4, 33.7), (bx + 0.45, by - 0.35),
                 connectionstyle="arc3,rad=-0.22", arrowstyle="-|>",
                 mutation_scale=30, lw=4, color="#2b6ca3", zorder=5))
    save(fig, "hist04-sec-hakusukinoe")


def genko():
    """元寇（文永の役1274・弘安の役1281）の襲来路。歴史⑥ mongol-invasion 節0。"""
    fig, ax = base_map((125.3, 133.8, 31.8, 36.7))
    lab(ax, 126.6, 36.3, "朝鮮半島", 24)
    lab(ax, 126.4, 35.6, "（元・高麗軍）", 15, color="#555")
    # 出発地・合浦
    ax.plot(128.62, 35.12, "o", color="#333", markersize=8, zorder=7, mec="#fff", mew=1.2)
    lab(ax, 128.42, 35.32, "合浦", 15, ha="right", va="bottom")
    # 経由地
    lab(ax, 129.30, 34.55, "対馬", 18)
    lab(ax, 129.78, 33.55, "壱岐", 18)
    # 上陸地・博多
    bx, by = 130.36, 33.60
    ax.plot(bx, by, "o", color="#c0392b", markersize=13, zorder=8, mec="#fff", mew=1.5)
    lab(ax, bx + 0.15, by + 0.18, "博多湾", 19, ha="left", va="bottom", color="#a01e12")
    lab(ax, 131.4, 32.7, "九州北部", 22)
    # 襲来路: 文永の役(橙)・弘安の役(紫) を 合浦→対馬→壱岐→博多 に
    via = [(129.35, 34.32), (129.72, 33.80)]
    for col, rad, off in [("#e08a1e", -0.16, 0.0), ("#7b52ab", -0.30, -0.06)]:
        pts = [(128.62 + off, 35.12)] + [(a + off, b) for a, b in via] + [(bx + off, by + 0.05)]
        for k in range(len(pts) - 1):
            style = "-|>" if k == len(pts) - 2 else "-"
            ax.add_patch(FancyArrowPatch(pts[k], pts[k + 1], connectionstyle=f"arc3,rad={rad}",
                         arrowstyle=style, mutation_scale=26, lw=4, color=col, zorder=6))
    lab(ax, 129.9, 35.15, "文永の役(1274)", 15, color="#b5670a", ha="left", va="bottom")
    lab(ax, 128.5, 34.35, "弘安の役(1281)", 15, color="#5b3a86", ha="right", va="top")
    save(fig, "hist06-sec-genko")


def voyage():
    """大航海時代の新航路（コロンブス・バスコ＝ダ＝ガマ・マゼラン）。歴史⑦ europe-spread 節0。
    マゼランの太平洋横断が日付変更線をまたぐため、陸地を lon-360 に複製して連続した世界図にする。"""
    import numpy as np
    feats = _load_features()
    LON0, LON1, LAT0, LAT1 = -262, 140, -58, 74
    ml = (LAT0 + LAT1) / 2
    fig = plt.figure(figsize=(14, 14 * ((LAT1 - LAT0) / np.cos(np.deg2rad(ml))) / (LON1 - LON0)))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(LON0, LON1); ax.set_ylim(LAT0, LAT1)
    ax.set_aspect(1 / np.cos(np.deg2rad(ml))); ax.axis("off")
    ax.add_patch(plt.Rectangle((LON0, LAT0), LON1 - LON0, LAT1 - LAT0, facecolor=SEA, zorder=0))
    for f in feats:
        if f["properties"].get("NAME") == "Antarctica":
            continue
        for ring in _rings(f):
            arr = np.array(ring)
            for shift in (0.0, -360.0):
                a = arr.copy(); a[:, 0] += shift
                if a[:, 0].max() < LON0 - 5 or a[:, 0].min() > LON1 + 5:
                    continue
                ax.add_patch(MplPoly(a, closed=True, facecolor=LAND, edgecolor=COAST, linewidth=0.4, zorder=1))
    lab(ax, -10, 50, "ヨーロッパ", 20)
    lab(ax, 20, 6, "アフリカ", 20)
    lab(ax, -58, -6, "アメリカ大陸", 20)
    lab(ax, 82, 24, "インド", 18)
    def route(pts, color, dashed=False):
        for k in range(len(pts) - 1):
            style = "-|>" if k == len(pts) - 2 else "-"
            ax.add_patch(FancyArrowPatch(pts[k], pts[k + 1], connectionstyle="arc3,rad=0.12",
                         arrowstyle=style, mutation_scale=22, lw=3.4, color=color, zorder=6,
                         linestyle="--" if dashed else "-"))
    # コロンブス（赤）
    route([(-8, 37.2), (-40, 30), (-74, 24)], "#c0392b")
    ax.plot(-74, 24, "o", color="#c0392b", markersize=9, zorder=7, mec="#fff", mew=1.2)
    lab(ax, -46, 33, "コロンブス（1492）", 15, color="#a01e12", ha="center", va="bottom")
    # バスコ＝ダ＝ガマ（青）
    route([(-9, 38.7), (-16, 5), (2, -20), (18.5, -34.4), (48, -12), (75.8, 11.2)], "#2b6ca3")
    ax.plot(75.8, 11.2, "o", color="#2b6ca3", markersize=9, zorder=7, mec="#fff", mew=1.2)
    lab(ax, 30, -30, "バスコ＝ダ＝ガマ", 15, color="#1c4f7c", ha="center")
    # マゼラン一行（緑）
    route([(-8, 37), (-28, 5), (-45, -22), (-68, -52), (-120, -25), (-185, -6), (-236, 10.3)], "#2e7d32")
    ax.plot(-236, 10.3, "o", color="#2e7d32", markersize=9, zorder=7, mec="#fff", mew=1.2)
    lab(ax, -140, -38, "マゼラン一行（世界一周）", 15, color="#1f5e22", ha="center")
    save(fig, "hist07-sec-voyage")


def treaty_ports():
    """日米修好通商条約(1858)で開かれた5港。歴史⑩ opening-japan 節2。"""
    fig, ax = base_map((128.5, 143.2, 31.0, 43.2))
    ports = [
        ("函館", 140.73, 41.77, "left", "bottom"),
        ("新潟", 139.05, 37.92, "right", "center"),
        ("神奈川（横浜）", 139.64, 35.44, "left", "top"),
        ("兵庫（神戸）", 135.19, 34.69, "right", "top"),
        ("長崎", 129.87, 32.74, "right", "center"),
    ]
    for name, lon, lat, ha, va in ports:
        ax.plot(lon, lat, "o", color="#c0392b", markersize=13, zorder=8, mec="#fff", mew=1.6)
        dx = 0.35 if ha == "left" else -0.35
        lab(ax, lon + dx, lat + (0.35 if va == "bottom" else -0.35 if va == "top" else 0),
            name, 19, color="#a01e12", ha=ha, va=("bottom" if va == "bottom" else "top" if va == "top" else "center"))
    lab(ax, 138.4, 36.6, "日本", 26, color="#6b5a3a")
    save(fig, "hist10-sec-treaty-ports")


MAKERS = {"hakusukinoe": hakusukinoe, "genko": genko, "voyage": voyage,
          "treaty_ports": treaty_ports}

if __name__ == "__main__":
    import sys
    targets = sys.argv[1:] or list(MAKERS)
    for t in targets:
        MAKERS[t]()
