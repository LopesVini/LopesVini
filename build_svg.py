import re
from html import escape
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

# ============================================================
# CONFIGURAÇÕES
# ============================================================

ASCII_COLUMNS = 43
ASCII_ROWS = 25

# Standard ASCII character scale from darkest to lightest
ASCII_CHARACTERS = "@%#*+=-:,."

HIGHLIGHT_CUTOFF = 145
PORTRAIT_ZOOM = 1.0

CONTRAST = 1.35
SHARPNESS = 1.65
GAMMA = 1.05
EDGE_STRENGTH = 0.40

# ============================================================
# PREPARAÇÃO DA IMAGEM
# ============================================================

def flatten_and_crop(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")

    if alpha.getextrema()[0] < 255:
        mask = alpha.point(lambda value: 255 if value > 10 else 0)
        bounding_box = mask.getbbox()

        if bounding_box:
            left, top, right, bottom = bounding_box
            width, height = right - left, bottom - top
            padding_x, padding_y = int(width * 0.025), int(height * 0.025)
            rgba = rgba.crop((
                max(0, left - padding_x), max(0, top - padding_y),
                min(rgba.width, right + padding_x), min(rgba.height, bottom + padding_y),
            ))

        white_background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(white_background, rgba).convert("RGB")

    rgb = rgba.convert("RGB")
    corners = [
        rgb.getpixel((0, 0)), rgb.getpixel((rgb.width - 1, 0)),
        rgb.getpixel((0, rgb.height - 1)), rgb.getpixel((rgb.width - 1, rgb.height - 1)),
    ]
    background_color = tuple(sum(color[channel] for color in corners) // len(corners) for channel in range(3))
    background = Image.new("RGB", rgb.size, background_color)
    difference = ImageChops.difference(rgb, background).convert("L")
    difference = difference.filter(ImageFilter.GaussianBlur(1.0))
    mask = difference.point(lambda value: 255 if value > 18 else 0)
    bounding_box = mask.getbbox()

    if bounding_box:
        left, top, right, bottom = bounding_box
        width, height = right - left, bottom - top
        padding_x, padding_y = int(width * 0.025), int(height * 0.025)
        rgb = rgb.crop((
            max(0, left - padding_x), max(0, top - padding_y),
            min(rgb.width, right + padding_x), min(rgb.height, bottom + padding_y),
        ))

    return rgb

def apply_zoom(image: Image.Image, zoom: float) -> Image.Image:
    if zoom <= 1: return image
    new_width, new_height = max(1, int(image.width / zoom)), max(1, int(image.height / zoom))
    center_x, center_y = image.width / 2, image.height * 0.43
    left, top = int(center_x - new_width / 2), int(center_y - new_height / 2)
    left, top = max(0, min(left, image.width - new_width)), max(0, min(top, image.height - new_height))
    return image.crop((left, top, left + new_width, top + new_height))

def prepare_image(image_path: Path) -> Image.Image:
    original = Image.open(image_path)
    flattened = flatten_and_crop(original)
    zoomed = apply_zoom(flattened, PORTRAIT_ZOOM)
    fitted = ImageOps.pad(zoomed, (ASCII_COLUMNS, ASCII_ROWS), method=Image.Resampling.LANCZOS, color=(255, 255, 255))
    grayscale = fitted.convert("L")
    grayscale = ImageOps.autocontrast(grayscale, cutoff=1)
    grayscale = ImageEnhance.Contrast(grayscale).enhance(CONTRAST)
    grayscale = grayscale.filter(ImageFilter.UnsharpMask(radius=1.2, percent=175, threshold=3))
    grayscale = ImageEnhance.Sharpness(grayscale).enhance(SHARPNESS)
    edges = grayscale.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(0.45))
    edges = ImageOps.autocontrast(edges, cutoff=2)
    inverted_edges = ImageOps.invert(edges)
    white = Image.new("L", grayscale.size, 255)
    controlled_edges = Image.blend(white, inverted_edges, EDGE_STRENGTH)
    grayscale = ImageChops.multiply(grayscale, controlled_edges)
    grayscale = grayscale.point(lambda pixel: round(255 * ((pixel / 255) ** GAMMA)))
    return grayscale

def image_to_ascii(image: Image.Image) -> list[str]:
    pixels = list(image.getdata())
    lines = []
    last_character_index = len(ASCII_CHARACTERS) - 1

    for row in range(ASCII_ROWS):
        characters = []
        for column in range(ASCII_COLUMNS):
            pixel = pixels[row * ASCII_COLUMNS + column]
            if pixel >= HIGHLIGHT_CUTOFF:
                characters.append(" ")
                continue
            normalized = pixel / HIGHLIGHT_CUTOFF
            # since terminal background is dark, lighter pixel should be smaller characters (start of string)
            character_index = round(normalized * last_character_index)
            character_index = max(0, min(character_index, last_character_index))
            characters.append(ASCII_CHARACTERS[character_index])
        lines.append("".join(characters))
    return lines

def format_row(label, value, key_style='key', value_style='value'):
    total_len = len(label) + len(value)
    dots_count = max(2, 35 - total_len)
    dots = " " + "." * dots_count + " "
    return f'<tspan class="cc">. </tspan><tspan class="{key_style}">{escape(label)}</tspan>:<tspan class="cc">{dots}</tspan><tspan class="{value_style}">{escape(value)}</tspan>'

def format_nested_row(prefix, label, value):
    total_len = len(prefix) + 1 + len(label) + len(value)
    dots_count = max(2, 35 - total_len)
    dots = " " + "." * dots_count + " "
    return f'<tspan class="cc">. </tspan><tspan class="key">{escape(prefix)}</tspan>.<tspan class="key">{escape(label)}</tspan>:<tspan class="cc">{dots}</tspan><tspan class="value">{escape(value)}</tspan>'

def create_svg(ascii_lines):
    svg_content = f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" width="1045px" height="530px" font-size="16px">
<style>
@font-face {{
src: local('Consolas'), local('Consolas Bold');
font-family: 'ConsolasFallback';
font-display: swap;
-webkit-size-adjust: 109%;
size-adjust: 109%;
}}
.key {{fill: #ffa657;}}
.value {{fill: #a5d6ff;}}
.addColor {{fill: #3fb950;}}
.delColor {{fill: #f85149;}}
.cc {{fill: #616e7f;}}
text, tspan {{
    white-space: pre;
    font-family: ConsolasFallback, Consolas, monospace;
    font-size: 16px;
}}
</style>
<rect width="1045px" height="530px" fill="#161b22" rx="15"/>
<text x="15" y="30" fill="#c9d1d9" class="ascii">
"""
    y = 30
    for line in ascii_lines:
        svg_content += f'<tspan x="15" y="{y}">{escape(line)}</tspan>\n'
        y += 20

    svg_content += f"""</text>
<text x="450" y="30" fill="#c9d1d9">
<tspan x="450" y="30">vinicius@lacerda</tspan> -———————————————————————————————————————————-—-
<tspan x="450" y="50">{format_row('OS', 'macOS, Linux')}</tspan>
<tspan x="450" y="70">{format_row('Location', 'Belo Horizonte, Brazil')}</tspan>
<tspan x="450" y="90">{format_row('University', 'Electrical Engineering, UFMG')}</tspan>
<tspan x="450" y="110" class="cc">. </tspan>
<tspan x="450" y="130">{format_nested_row('Learning', 'Programming', 'Python, TypeScript')}</tspan>
<tspan x="450" y="150">{format_nested_row('Learning', 'Systems', 'Linux, Networks, Git')}</tspan>
<tspan x="450" y="170">{format_nested_row('Learning', 'Engineering', 'Automation, Electronics, AI')}</tspan>
<tspan x="450" y="190" class="cc">. </tspan>
<tspan x="450" y="210">{format_nested_row('Personal', 'Interests', 'Music, Engineering')}</tspan>
<tspan x="450" y="230">{format_nested_row('Personal', 'Music', 'Rush, Tool, Milton')}</tspan>
<tspan x="450" y="250">{format_nested_row('Personal', 'Hobbies', 'Guitar, Math, Comics')}</tspan>
<tspan x="450" y="270" class="cc">. </tspan>
<tspan x="450" y="290">- Contact -——————————————————————————————————————————————-—-</tspan>
<tspan x="450" y="310">{format_row('Instagram', '@vllc.hub')}</tspan>
<tspan x="450" y="330">{format_row('Website', 'vivico.space')}</tspan>
<tspan x="450" y="350" class="cc">. </tspan>
</text>
</svg>
"""
    return svg_content

if __name__ == '__main__':
    IMAGE_PATH = Path("assets/foto.jpg")
    ASCII_TEXT_PATH = Path("assets/foto-ascii.txt")
    SVG_PATH = Path("assets/profile.svg")

    prepared_image = prepare_image(IMAGE_PATH)
    ascii_lines = image_to_ascii(prepared_image)
    ASCII_TEXT_PATH.write_text("\n".join(ascii_lines), encoding="utf-8")
    SVG_PATH.write_text(create_svg(ascii_lines), encoding="utf-8")
    print("Done!")
