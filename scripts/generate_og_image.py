from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "assets" / "social" / "og-image.png"
WIDTH = 1200
HEIGHT = 630


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def gradient() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#070a12")
    pixels = image.load()
    for y in range(HEIGHT):
        ty = y / max(HEIGHT - 1, 1)
        for x in range(WIDTH):
            tx = x / max(WIDTH - 1, 1)
            r = lerp(7, 13, (tx + ty) / 2)
            g = lerp(10, 18, ty)
            b = lerp(18, 36, tx)
            pixels[x, y] = (r, g, b)
    return image


def glow(size: tuple[int, int], color: tuple[int, int, int, int]) -> Image.Image:
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse(size, fill=color)
    return layer.filter(ImageFilter.GaussianBlur(70))


def draw_grid(draw: ImageDraw.ImageDraw) -> None:
    for x in range(0, WIDTH, 42):
        draw.line((x, 0, x, HEIGHT), fill=(148, 163, 184, 18), width=1)
    for y in range(0, HEIGHT, 42):
        draw.line((0, y, WIDTH, y), fill=(148, 163, 184, 18), width=1)


def rounded_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(box, radius=34, fill=(13, 20, 35, 222), outline=(148, 163, 184, 62), width=2)


def main() -> None:
    image = gradient().convert("RGBA")
    image.alpha_composite(glow((-120, -110, 520, 480), (77, 163, 255, 58)))
    image.alpha_composite(glow((700, -140, 1330, 430), (247, 161, 61, 48)))
    image.alpha_composite(glow((520, 310, 1210, 850), (70, 217, 147, 42)))
    draw = ImageDraw.Draw(image)
    draw_grid(draw)

    rounded_panel(draw, (72, 70, 1128, 560))
    draw.rounded_rectangle((104, 102, 214, 140), radius=19, fill=(77, 163, 255, 38), outline=(77, 163, 255, 122), width=1)
    draw.text((130, 111), "Python", font=font(21, True), fill=(199, 229, 255))
    draw.rounded_rectangle((232, 102, 310, 140), radius=19, fill=(247, 161, 61, 42), outline=(247, 161, 61, 130), width=1)
    draw.text((256, 111), "Zig", font=font(21, True), fill=(255, 226, 189))
    draw.rounded_rectangle((328, 102, 444, 140), radius=19, fill=(70, 217, 147, 36), outline=(70, 217, 147, 120), width=1)
    draw.text((353, 111), "Pandas", font=font(21, True), fill=(202, 255, 230))

    draw.text((104, 178), "zh_catmut", font=font(86, True), fill=(238, 247, 255))
    draw.text((109, 267), "Native categorical remapping for Pandas", font=font(40, True), fill=(166, 183, 203))
    draw.text((109, 335), "Python metadata. Zig throughput. C ABI discipline.", font=font(30), fill=(198, 211, 226))

    draw.rounded_rectangle((108, 430, 460, 484), radius=27, fill=(77, 163, 255, 42), outline=(77, 163, 255, 132), width=2)
    draw.text((138, 444), "new_code = lut[old_code]", font=font(24, True), fill=(232, 246, 255))
    draw.rounded_rectangle((486, 430, 720, 484), radius=27, fill=(70, 217, 147, 34), outline=(70, 217, 147, 122), width=2)
    draw.text((516, 444), "Apache-2.0", font=font(24, True), fill=(219, 255, 237))

    draw.line((830, 170, 1042, 170), fill=(77, 163, 255, 200), width=4)
    draw.line((830, 248, 1042, 248), fill=(247, 161, 61, 200), width=4)
    draw.line((830, 326, 1042, 326), fill=(70, 217, 147, 200), width=4)
    for x, y, c in [(830, 170, "#4da3ff"), (1042, 170, "#4da3ff"), (830, 248, "#f7a13d"), (1042, 248, "#f7a13d"), (830, 326, "#46d993"), (1042, 326, "#46d993")]:
        draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill=c)
    draw.text((728, 392), "mohamedhossammohamed/zh_catmut", font=font(22), fill=(166, 183, 203))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(OUTPUT, quality=95)


if __name__ == "__main__":
    main()
