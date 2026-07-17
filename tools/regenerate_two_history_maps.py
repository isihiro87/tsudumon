from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
GEOJSON = ROOT / "tmp" / "geo" / "countries.geojson"

W, H = 1200, 900
S = 3

FONT_BOLD = "C:/Windows/Fonts/meiryob.ttc"
FONT_FALLBACK_BOLD = "C:/Windows/Fonts/YuGothB.ttc"

INK = (14, 14, 14)
LAND = (239, 238, 218)
LAND_ALT = (225, 237, 218)
CHINA = (242, 233, 207)
WATER = (249, 253, 255)
COAST = (42, 42, 42)
RED = (201, 35, 35)
BLUE = (24, 77, 165)
MANCHUKUO = (246, 203, 139)


def font(size: int) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if Path(FONT_BOLD).exists() else FONT_FALLBACK_BOLD
    return ImageFont.truetype(path, size * S)


def sc(v: float) -> int:
    return int(round(v * S))


def sxy(xy: tuple[float, float]) -> tuple[int, int]:
    return sc(xy[0]), sc(xy[1])


def rect(xy: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    return tuple(sc(v) for v in xy)  # type: ignore[return-value]


def new_canvas() -> Image.Image:
    return Image.new("RGB", (W * S, H * S), "white")


def text(
    d: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    value: str,
    size: int,
    fill: tuple[int, int, int] = INK,
    anchor: str = "la",
    stroke: int = 4,
) -> None:
    d.text(sxy(xy), value, font=font(size), fill=fill, anchor=anchor, stroke_width=sc(stroke) // S, stroke_fill="white")


def centered_text(
    d: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    value: str,
    size: int,
    fill: tuple[int, int, int] = INK,
) -> None:
    d.multiline_text(
        ((sc(box[0] + box[2]) // 2), (sc(box[1] + box[3]) // 2)),
        value,
        font=font(size),
        fill=fill,
        anchor="mm",
        align="center",
        spacing=sc(7),
        stroke_width=2,
        stroke_fill="white",
    )


def feature_by_name(names: set[str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    with GEOJSON.open("r", encoding="utf-8") as f:
        for raw in f:
            if '"type": "Feature"' not in raw:
                continue
            line = raw.strip()
            if line.endswith(","):
                line = line[:-1]
            if not any(f'"name": "{name}"' in line for name in names):
                continue
            feat = json.loads(line)
            name = feat["properties"]["name"]
            if name in names:
                found[name] = feat
    missing = names - set(found)
    if missing:
        raise RuntimeError(f"Missing GeoJSON features: {sorted(missing)}")
    return found


def iter_rings(feature: dict):
    geom = feature["geometry"]
    coords = geom["coordinates"]
    if geom["type"] == "Polygon":
        for ring in coords:
            yield ring
    elif geom["type"] == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                yield ring


def project(lon: float, lat: float, bbox: tuple[float, float, float, float], box: tuple[float, float, float, float]):
    lon0, lat0, lon1, lat1 = bbox
    x0, y0, x1, y1 = box
    x = x0 + (lon - lon0) / (lon1 - lon0) * (x1 - x0)
    y = y1 - (lat - lat0) / (lat1 - lat0) * (y1 - y0)
    return x, y


def ring_bbox(ring) -> tuple[float, float, float, float]:
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return min(lons), min(lats), max(lons), max(lats)


def intersects(a, b) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def draw_countries(
    base: Image.Image,
    countries: dict[str, dict],
    names: list[str],
    bbox: tuple[float, float, float, float],
    box: tuple[float, float, float, float],
    fill: tuple[int, int, int],
    width: int = 2,
) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lonlat_bbox = bbox
    for name in names:
        for ring in iter_rings(countries[name]):
            if not intersects(ring_bbox(ring), lonlat_bbox):
                continue
            pts = [sxy(project(lon, lat, bbox, box)) for lon, lat in ring]
            if len(pts) >= 3:
                d.polygon(pts, fill=fill + (255,), outline=COAST + (255,))
                d.line(pts + [pts[0]], fill=COAST + (255,), width=sc(width), joint="curve")
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).rectangle(rect(box), fill=255)
    alpha = layer.getchannel("A")
    layer.putalpha(ImageChops.multiply(alpha, mask))
    base.alpha_composite(layer) if base.mode == "RGBA" else base.paste(Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB"))


def title(d: ImageDraw.ImageDraw, value: str) -> None:
    centered_text(d, (0, 22, W, 92), value, 44)
    d.line((sc(330), sc(108), sc(870), sc(108)), fill=(175, 145, 78), width=sc(5))


def marker(d: ImageDraw.ImageDraw, xy, color=RED, r=10) -> None:
    x, y = xy
    d.ellipse(rect((x - r, y - r, x + r, y + r)), fill=color, outline=INK, width=sc(3))


def symbol(d: ImageDraw.ImageDraw, xy, value: str, size: int = 42) -> None:
    x, y = xy
    d.ellipse(rect((x - 36, y - 36, x + 36, y + 36)), fill="white", outline=INK, width=sc(5))
    centered_text(d, (x - 34, y - 38, x + 34, y + 35), value, size)


def arrow(d: ImageDraw.ImageDraw, points: list[tuple[float, float]], fill=RED, width=9) -> None:
    pts = [sxy(p) for p in points]
    d.line(pts, fill=fill, width=sc(width), joint="curve")
    p1 = points[-2]
    p2 = points[-1]
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    length = 32
    spread = 0.55
    head = [
        sxy(p2),
        sxy((p2[0] - length * math.cos(ang - spread), p2[1] - length * math.sin(ang - spread))),
        sxy((p2[0] - length * math.cos(ang + spread), p2[1] - length * math.sin(ang + spread))),
    ]
    d.polygon(head, fill=fill)


def save(img: Image.Image, name: str) -> None:
    final = img.resize((W, H), Image.Resampling.LANCZOS)
    final.save(ASSETS / name, "WEBP", quality=96, method=6)


def treaty_ports_map(countries: dict[str, dict]) -> None:
    img = new_canvas()
    d = ImageDraw.Draw(img)
    title(d, "開国後の開港地")
    box = (85, 125, 1115, 820)
    d.rectangle(rect(box), fill=WATER, outline=(210, 218, 220), width=sc(2))
    bbox = (127.0, 30.0, 147.5, 46.6)
    draw_countries(img, countries, ["Japan"], bbox, box, LAND, width=3)
    d = ImageDraw.Draw(img)

    ports = {
        "函館": (140.73, 41.77),
        "新潟": (139.05, 37.92),
        "A": (139.64, 35.45),
        "兵庫(神戸)": (135.19, 34.69),
        "B": (129.87, 32.75),
        "浦賀": (139.72, 35.24),
    }
    projected = {k: project(*v, bbox, box) for k, v in ports.items()}

    marker(d, projected["函館"])
    text(d, (projected["函館"][0] + 18, projected["函館"][1] - 33), "函館", 35)
    marker(d, projected["新潟"])
    text(d, (projected["新潟"][0] + 18, projected["新潟"][1] - 34), "新潟", 34)
    marker(d, projected["兵庫(神戸)"])
    text(d, (projected["兵庫(神戸)"][0] - 190, projected["兵庫(神戸)"][1] + 3), "兵庫(神戸)", 33)

    marker(d, projected["A"], r=12)
    symbol(d, (projected["A"][0] + 78, projected["A"][1] - 18), "A", 48)
    marker(d, projected["B"], r=12)
    symbol(d, (projected["B"][0] - 68, projected["B"][1] + 10), "B", 48)

    marker(d, projected["浦賀"], color=BLUE, r=7)
    text(d, (projected["浦賀"][0] + 24, projected["浦賀"][1] + 18), "浦賀", 26)
    centered_text(d, (765, 735, 1085, 800), "● 開港地　● 浦賀", 28)
    save(img, "treaty-ports-map.webp")


def manchuria_war_route(countries: dict[str, dict]) -> None:
    img = new_canvas()
    d = ImageDraw.Draw(img)
    title(d, "満州事変と日中戦争")
    box = (70, 125, 1125, 815)
    d.rectangle(rect(box), fill=WATER, outline=(210, 218, 220), width=sc(2))
    bbox = (101.0, 20.0, 151.0, 53.5)

    draw_countries(img, countries, ["China"], bbox, box, CHINA, width=2)
    draw_countries(img, countries, ["North Korea", "South Korea"], bbox, box, LAND_ALT, width=2)
    draw_countries(img, countries, ["Japan"], bbox, box, LAND, width=2)
    draw_countries(img, countries, ["Mongolia", "Russia"], bbox, box, (232, 232, 220), width=2)
    d = ImageDraw.Draw(img)

    manchukuo_ll = [
        (119.0, 40.0),
        (121.0, 44.8),
        (122.5, 50.4),
        (128.8, 51.6),
        (134.5, 48.2),
        (133.3, 43.7),
        (130.2, 40.7),
        (124.1, 39.4),
    ]
    d.polygon([sxy(project(lon, lat, bbox, box)) for lon, lat in manchukuo_ll], fill=MANCHUKUO, outline=(142, 82, 37))
    d.line([sxy(project(lon, lat, bbox, box)) for lon, lat in manchukuo_ll + [manchukuo_ll[0]]], fill=(142, 82, 37), width=sc(4))

    def p(lon, lat):
        return project(lon, lat, bbox, box)

    centered_text(d, (545, 235, 755, 292), "満州国", 34, fill=(55, 35, 20))
    text(d, (230, 480), "中国", 39)
    text(d, (640, 470), "朝鮮", 35)
    text(d, (865, 455), "日本", 36)

    loc1 = p(123.45, 41.8)
    loc2 = p(116.2, 39.85)
    nanjing = p(118.8, 32.06)
    chongqing = p(106.55, 29.56)

    arrow(d, [p(131.5, 44.2), p(127.5, 42.8), p(123.8, 41.9)], width=10)
    arrow(d, [p(123.7, 40.9), p(120.2, 40.0), p(116.4, 39.9)], width=10)
    arrow(d, [p(116.2, 39.2), p(117.7, 35.4), p(118.8, 32.3)], width=10)
    arrow(d, [p(118.1, 31.5), p(113.5, 30.4), p(106.8, 29.7)], width=10)

    marker(d, loc1, r=11)
    symbol(d, (loc1[0] + 65, loc1[1] - 42), "①", 42)
    marker(d, loc2, r=11)
    symbol(d, (loc2[0] - 62, loc2[1] - 30), "②", 42)

    marker(d, nanjing, color=BLUE, r=8)
    text(d, (nanjing[0] + 16, nanjing[1] - 33), "南京", 32)
    marker(d, chongqing, color=BLUE, r=8)
    text(d, (chongqing[0] + 18, chongqing[1] - 54), "重慶", 32)

    d.rounded_rectangle(rect((803, 650, 1092, 750)), radius=sc(10), fill="white", outline=INK, width=sc(3))
    centered_text(d, (820, 665, 1076, 735), "①1931年　②1937年", 30)
    save(img, "manchuria-war-route.webp")


def main() -> None:
    countries = feature_by_name({"Japan", "China", "North Korea", "South Korea", "Mongolia", "Russia"})
    treaty_ports_map(countries)
    manchuria_war_route(countries)


if __name__ == "__main__":
    main()
