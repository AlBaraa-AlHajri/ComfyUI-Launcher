"""Render the original SVG geometry with Pillow at 4x supersampling, without web assets."""

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SCALE = 4
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def render() -> Image.Image:
    """Read coordinates and colors from the checked-in, hand-written SVG source of truth."""
    document = ET.parse(ASSETS / "icon.svg").getroot()
    ns = {"svg": "http://www.w3.org/2000/svg"}
    stops = document.findall(".//svg:stop", ns)
    top, bottom = [ImageColor.getrgb(stop.attrib["stop-color"]) for stop in stops]
    size = 1024 * SCALE
    canvas = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(canvas)
    for y in range(size):
        fraction = y / (size - 1)
        color = tuple(round(a + (b - a) * fraction) for a, b in zip(top, bottom, strict=True))
        draw.line((0, y, size, y), fill=color + (255,))
    rect = document.find("svg:rect", ns)
    assert rect is not None
    x, y, width, height, radius = [
        float(rect.attrib[key]) * SCALE for key in ("x", "y", "width", "height", "rx")
    ]
    mask = Image.new("L", canvas.size)
    ImageDraw.Draw(mask).rounded_rectangle((x, y, x + width, y + height), radius, fill=255)
    canvas.putalpha(mask)
    glow_node = document.find("svg:g/svg:circle", ns)
    assert glow_node is not None
    glow = Image.new("RGBA", canvas.size)
    cx, cy, r = [float(glow_node.attrib[key]) * SCALE for key in ("cx", "cy", "r")]
    ImageDraw.Draw(glow).ellipse((cx - r, cy - r, cx + r, cy + r), fill=(216, 255, 62, 51))
    canvas = Image.alpha_composite(canvas, glow.filter(ImageFilter.GaussianBlur(14 * SCALE)))
    draw = ImageDraw.Draw(canvas)
    graph = document.find("svg:g[@id='graph']", ns)
    assert graph is not None
    for node in graph:
        name = node.tag.rsplit("}", 1)[-1]
        if name == "path":
            # Sample cubic Bezier curves from the SVG coordinates. / أخذ عينات من منحنيات المصدر.
            numbers = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", node.attrib["d"])]
            p0, p1, p2, p3 = [numbers[index : index + 2] for index in range(0, 8, 2)]
            points = []
            for step in range(161):
                t = step / 160
                points.append(
                    tuple(
                        SCALE
                        * (
                            (1 - t) ** 3 * p0[axis]
                            + 3 * (1 - t) ** 2 * t * p1[axis]
                            + 3 * (1 - t) * t * t * p2[axis]
                            + t**3 * p3[axis]
                        )
                        for axis in (0, 1)
                    )
                )
            line_width = round(float(node.attrib["stroke-width"]) * SCALE)
            draw.line(points, fill=node.attrib["stroke"], width=line_width, joint="curve")
            for px, py in (points[0], points[-1]):
                half = line_width / 2
                draw.ellipse(
                    (px - half, py - half, px + half, py + half), fill=node.attrib["stroke"]
                )
        elif name == "circle":
            cx, cy, r = [float(node.attrib[key]) * SCALE for key in ("cx", "cy", "r")]
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=node.attrib["fill"])
        elif name == "polygon":
            points = [
                tuple(float(value) * SCALE for value in point.split(","))
                for point in node.attrib["points"].split()
            ]
            draw.polygon(points, fill=node.attrib["fill"])
        else:
            raise ValueError(f"Unsupported SVG element: {name}")
    return canvas.resize((1024, 1024), Image.Resampling.LANCZOS)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Use standard Windows fonts with a bundled Pillow fallback for other hosts."""
    try:
        return ImageFont.truetype("segoeuib.ttf" if bold else "segoeui.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def main() -> None:
    """Write every release icon, a social card and actual-size small-icon previews."""
    ASSETS.mkdir(exist_ok=True)
    original = render()
    original.save(ASSETS / "icon_1024.png")
    for name, size in (
        ("icon_256.png", 256),
        ("icon.png", 512),
        ("tray_icon.png", 64),
        ("splash_logo.png", 512),
        ("preview_16.png", 16),
        ("preview_32.png", 32),
    ):
        original.resize((size, size), Image.Resampling.LANCZOS).save(ASSETS / name)
    original.save(ASSETS / "icon.ico", sizes=[(size, size) for size in SIZES])
    with Image.open(ASSETS / "icon.ico") as ico:
        assert ico.ico.sizes() == {(size, size) for size in SIZES}
    social = Image.new("RGB", (1280, 640), "#1E1828")
    draw = ImageDraw.Draw(social)
    for x in range(40, 1280, 48):
        for y in range(40, 640, 48):
            if math.hypot(x - 980, y - 280) < 300:
                draw.ellipse((x, y, x + 2, y + 2), fill="#423553")
    tile = original.resize((340, 340), Image.Resampling.LANCZOS)
    social.paste(tile, (90, 150), tile)
    draw.text((488, 180), "COMFYUI LAUNCHER", font=font(20, True), fill="#D8FF3E")
    draw.text((485, 230), "Your workflows.", font=font(61, True), fill="#F4F0FA")
    draw.text((485, 306), "One click.", font=font(61, True), fill="#F4F0FA")
    draw.text(
        (490, 409), "Windows  /  Open source  /  Community built", font=font(22), fill="#ACA2BC"
    )
    social.save(ASSETS / "social_preview.png")
    preview = Image.new("RGB", (640, 260), "#292332")
    draw = ImageDraw.Draw(preview)
    for index, size in enumerate((16, 32)):
        small = original.resize((size, size), Image.Resampling.LANCZOS)
        x = 40 + index * 320
        preview.paste(small, (x, 55), small)
        expanded = small.resize((128, 128), Image.Resampling.NEAREST)
        preview.paste(expanded, (x + 65, 50), expanded)
        draw.text((x, 205), f"{size}px actual + 128px enlarged", fill="white", font=font(15))
    preview.save(ASSETS / "small_size_preview.png")
    print("Generated original artwork and ICO sizes:", SIZES)


if __name__ == "__main__":
    main()
