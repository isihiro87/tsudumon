from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
DATA = ROOT / "tmp" / "geo"
W, H = 1200, 900

FONT_B = "C:/Windows/Fonts/BIZ-UDGothicB.ttc"
FONT_R = "C:/Windows/Fonts/BIZ-UDGothicR.ttc"

INK = (28, 28, 28)
LINE = (42, 42, 42)
GOLD = (178, 155, 94)
WATER = (217, 239, 249)
LAND = (241, 237, 218)
LAND2 = (226, 236, 207)
GREEN = (224, 240, 222)
BLUE = (226, 238, 250)
BEIGE = (248, 240, 222)
PINK = (249, 231, 226)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_B if bold else FONT_R, size)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), "white")
    return img, ImageDraw.Draw(img)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.multiline_textbbox((0, 0), text, font=fnt, spacing=6)
    return box[2] - box[0], box[3] - box[1]


def center_text(draw: ImageDraw.ImageDraw, box, text: str, size: int, bold=False, fill=INK, spacing=6):
    fnt = font(size, bold)
    tw, th = text_size(draw, text, fnt)
    x0, y0, x1, y1 = box
    draw.multiline_text(
        (x0 + (x1 - x0 - tw) / 2, y0 + (y1 - y0 - th) / 2 - 2),
        text,
        font=fnt,
        fill=fill,
        align="center",
        spacing=spacing,
    )


def title(draw: ImageDraw.ImageDraw, text: str):
    center_text(draw, (0, 35, W, 100), text, 43, True)
    draw.line((330, 118, 870, 118), fill=GOLD, width=5)


def box(draw, xy, text, fill=BEIGE, size=35, bold=True, radius=20, width=4):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=LINE, width=width)
    center_text(draw, xy, text, size, bold)


def small_label(draw, xy, text, size=25):
    draw.rounded_rectangle(xy, radius=8, fill="white", outline=(145, 145, 145), width=2)
    center_text(draw, xy, text, size, False)


def line(draw, p1, p2, arrow=False, width=4, fill=LINE):
    draw.line((*p1, *p2), fill=fill, width=width)
    if arrow:
        ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        length = 18
        a1 = ang + math.pi * 0.82
        a2 = ang - math.pi * 0.82
        pts = [
            p2,
            (p2[0] + length * math.cos(a1), p2[1] + length * math.sin(a1)),
            (p2[0] + length * math.cos(a2), p2[1] + length * math.sin(a2)),
        ]
        draw.polygon(pts, fill=fill)


def save(img: Image.Image, name: str):
    path = ASSETS / name
    img.save(path, "WEBP", quality=96, method=6)
    return path


def kamakura():
    img, d = canvas()
    title(d, "鎌倉幕府のしくみ")
    line(d, (600, 220), (600, 270), True)
    line(d, (600, 345), (600, 430))
    line(d, (305, 430), (895, 430))
    for x in [305, 600, 895]:
        line(d, (x, 430), (x, 460), True)
    for x in [260, 600, 940]:
        line(d, (600, 410), (x, 660), True)
    box(d, (475, 145, 725, 220), "将軍", BEIGE, 38)
    box(d, (475, 270, 725, 345), "①", BLUE, 50)
    small_label(d, (485, 360, 715, 410), "将軍を補佐", 28)
    for x, t, c in [(180, "侍所", BLUE), (475, "政所", GREEN), (770, "問注所", BEIGE)]:
        box(d, (x, 460, x + 250, 535), t, c, 34)
    box(d, (135, 660, 385, 735), "②", BLUE, 50)
    small_label(d, (105, 750, 415, 805), "国ごと・軍事警察", 27)
    box(d, (475, 660, 725, 735), "③", GREEN, 50)
    small_label(d, (445, 750, 755, 805), "荘園ごと・年貢", 27)
    box(d, (815, 660, 1065, 735), "六波羅探題", PINK, 31)
    small_label(d, (865, 750, 1015, 805), "京都", 27)
    return save(img, "kamakura-bakufu-org.webp")


def get_geojson():
    DATA.mkdir(parents=True, exist_ok=True)
    p = DATA / "countries.geojson"
    if not p.exists():
        url = "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson"
        urllib.request.urlretrieve(url, p)
    return json.loads(p.read_text(encoding="utf-8"))


def feature_names(props):
    return {str(v) for k, v in props.items() if k.lower() in {"name", "admin", "name_long", "sovereignt", "geounit"}}


def country_polys(names: set[str]):
    gj = get_geojson()
    polys = []
    for feat in gj["features"]:
        if not (feature_names(feat["properties"]) & names):
            continue
        geom = feat["geometry"]
        coords = geom["coordinates"]
        if geom["type"] == "Polygon":
            polys.extend(coords)
        elif geom["type"] == "MultiPolygon":
            for poly in coords:
                polys.extend(poly)
    return polys


def project(lon, lat, bbox, box):
    lon0, lat0, lon1, lat1 = bbox
    x0, y0, x1, y1 = box
    x = x0 + (lon - lon0) / (lon1 - lon0) * (x1 - x0)
    y = y1 - (lat - lat0) / (lat1 - lat0) * (y1 - y0)
    return x, y


def draw_polys(d, names, bbox, box, fill=LAND, outline=(60, 60, 60), width=2):
    x0, y0, x1, y1 = box
    for ring in country_polys(names):
        pts = []
        for lon, lat in ring:
            x, y = project(lon, lat, bbox, box)
            x = min(max(x, x0), x1)
            y = min(max(y, y0), y1)
            pts.append((x, y))
        clipped = [(x, y) for x, y in pts if x0 - 2 <= x <= x1 + 2 and y0 - 2 <= y <= y1 + 2]
        if len(clipped) >= 3:
            d.polygon(clipped, fill=fill, outline=outline)


def marker(d, xy, label=None, color=(213, 42, 42), r=9, label_size=34):
    x, y = xy
    d.ellipse((x - r, y - r, x + r, y + r), fill=color, outline=INK, width=2)
    if label:
        d.ellipse((x + 12, y - 28, x + 74, y + 34), fill="white", outline=INK, width=4)
        center_text(d, (x + 12, y - 28, x + 74, y + 34), label, label_size, True)


def treaty_ports():
    img, d = canvas()
    title(d, "開国後の開港地")
    map_box = (120, 130, 1030, 790)
    d.rectangle(map_box, fill=WATER)
    bbox = (128, 30, 147, 46.5)
    draw_polys(d, {"Japan"}, bbox, map_box, fill=(236, 235, 205), width=3)
    coords = {
        "函館": (140.73, 41.77),
        "新潟": (139.05, 37.92),
        "A": (139.64, 35.45),
        "兵庫(神戸)": (135.19, 34.69),
        "B": (129.87, 32.75),
        "浦賀": (139.72, 35.24),
    }
    for name, ll in coords.items():
        x, y = project(*ll, bbox, map_box)
        if name == "A":
            marker(d, (x, y), "A", r=11, label_size=38)
        elif name == "B":
            marker(d, (x, y), "B", r=11, label_size=38)
        elif name == "浦賀":
            marker(d, (x, y), None, color=(50, 88, 180), r=6)
            d.text((x + 12, y + 10), "浦賀", font=font(24, True), fill=INK)
        else:
            marker(d, (x, y), None, r=8)
            d.text((x + 14, y - 18), name, font=font(28, True), fill=INK)
    small_label(d, (735, 690, 1040, 760), "● 開港地　● 浦賀", 27)
    return save(img, "treaty-ports-map.webp")


def meiji_constitution():
    img, d = canvas()
    title(d, "大日本帝国憲法下の国のしくみ")
    c = (600, 310)
    line(d, (600, 295), c)
    for target in [(235, 430), (600, 430), (965, 430), (600, 655)]:
        line(d, c, target, True)
    box(d, (475, 145, 725, 225), "①", BEIGE, 52)
    small_label(d, (455, 240, 745, 295), "主権を持つ元首", 27)
    items = [
        ((95, 430, 375, 520), "②", BLUE, "貴族院・衆議院", (70, 535, 400, 590)),
        ((460, 430, 740, 520), "内閣", GREEN, "国務大臣", (505, 535, 695, 590)),
        ((825, 430, 1105, 520), "裁判所", BEIGE, "司法", (880, 535, 1050, 590)),
        ((460, 655, 740, 745), "③", PINK, "天皇が率いる", (500, 760, 700, 815)),
    ]
    for xy, txt, fill, hint, hxy in items:
        box(d, xy, txt, fill, 45 if txt in {"②", "③"} else 35)
        small_label(d, hxy, hint, 26)
    return save(img, "meiji-constitution-org.webp")


def manchuria_route():
    img, d = canvas()
    title(d, "満州事変と日中戦争")
    map_box = (90, 125, 1060, 800)
    d.rectangle(map_box, fill=WATER)
    bbox = (101, 20, 150, 53)
    for names, fill in [
        ({"China"}, (238, 232, 202)),
        ({"Japan"}, (239, 238, 207)),
        ({"South Korea", "North Korea"}, (226, 236, 207)),
        ({"Russia"}, (232, 232, 220)),
        ({"Mongolia"}, (229, 226, 200)),
        ({"Taiwan"}, (239, 238, 207)),
    ]:
        draw_polys(d, names, bbox, map_box, fill=fill, width=2)
    manchukuo = [(119, 40.5), (123, 52), (132, 50), (135, 45), (131, 40.5), (124, 39.5)]
    pts = [project(lon, lat, bbox, map_box) for lon, lat in manchukuo]
    d.polygon(pts, fill=(246, 215, 166), outline=(165, 92, 50))
    center_text(d, (560, 235, 735, 285), "満州国", 28, True, fill=(70, 45, 25))
    locs = {
        "①": (123.45, 41.8),
        "②": (116.2, 39.85),
        "南京": (118.8, 32.06),
        "重慶": (106.55, 29.56),
    }
    for label, ll in locs.items():
        x, y = project(*ll, bbox, map_box)
        if label in {"①", "②"}:
            marker(d, (x, y), label, color=(213, 42, 42), r=8, label_size=34)
        else:
            marker(d, (x, y), None, color=(50, 88, 180), r=6)
            d.text((x + 12, y - 16), label, font=font(25, True), fill=INK)
    for text, lon, lat in [("日本", 139, 38), ("朝鮮", 127, 38), ("中国", 112, 34)]:
        x, y = project(lon, lat, bbox, map_box)
        d.text((x, y), text, font=font(28, True), fill=(55, 55, 55))
    def arrow_ll(a, b):
        line(d, project(*a, bbox, map_box), project(*b, bbox, map_box), True, width=5, fill=(180, 37, 37))
    arrow_ll((128.5, 39.5), (123.7, 41.8))
    arrow_ll((121, 39), (116.2, 39.85))
    arrow_ll((116.2, 39.85), (118.8, 32.06))
    arrow_ll((118.8, 32.06), (106.55, 29.56))
    small_label(d, (790, 635, 1050, 735), "① 1931年\n② 1937年", 29)
    return save(img, "manchuria-war-route.webp")


def land_reform():
    img, d = canvas()
    title(d, "農地改革による変化（自作地と小作地の割合）")
    left, right = 250, 1020
    y1, y2 = 285, 545
    h = 95
    colors = {"自作地": (87, 147, 205), "小作地": (237, 184, 82)}
    d.rectangle((left, y1, right, y1 + h), outline=INK, width=3)
    split = left + int((right - left) * 0.55)
    d.rectangle((left, y1, split, y1 + h), fill=colors["自作地"])
    d.rectangle((split, y1, right, y1 + h), fill=colors["小作地"])
    d.rectangle((left, y2, right, y2 + h), outline=INK, width=3)
    split2 = left + int((right - left) * 0.90)
    d.rectangle((left, y2, split2, y2 + h), fill=colors["自作地"])
    d.rectangle((split2, y2, right, y2 + h), fill=colors["小作地"])
    for y, yr, a, b in [(y1, "1940年", "自作地 55%", "小作地 45%"), (y2, "1950年", "自作地 90%", "小作地 10%")]:
        d.text((95, y + 24), yr, font=font(36, True), fill=INK)
        center_text(d, (left, y, left + (right-left)*(0.55 if yr=="1940年" else 0.90), y+h), a, 34, True, fill="white")
        sx = split if yr == "1940年" else split2
        center_text(d, (sx, y, right, y+h), b, 29 if yr=="1950年" else 34, True, fill=INK)
    d.rectangle((365, 735, 410, 775), fill=colors["自作地"], outline=INK, width=2)
    d.text((425, 735), "自作地", font=font(30, True), fill=INK)
    d.rectangle((610, 735, 655, 775), fill=colors["小作地"], outline=INK, width=2)
    d.text((670, 735), "小作地", font=font(30, True), fill=INK)
    return save(img, "land-reform-bar.webp")


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    for func in [kamakura, treaty_ports, meiji_constitution, manchuria_route, land_reform]:
        path = func()
        print(path.name, path.stat().st_size)
