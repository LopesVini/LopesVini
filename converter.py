from html import escape
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps


# ============================================================
# ARQUIVOS
# ============================================================

ASSETS_DIR = Path("assets")

IMAGE_PATH = next(
    (
        path
        for path in (
            ASSETS_DIR / "foto.png",
            ASSETS_DIR / "foto.jpg",
            ASSETS_DIR / "foto.jpeg",
        )
        if path.exists()
    ),
    None,
)

if IMAGE_PATH is None:
    raise FileNotFoundError(
        "Foto não encontrada. Use assets/foto.jpg, "
        "assets/foto.jpeg ou assets/foto.png."
    )

SVG_PATH = ASSETS_DIR / "profile.svg"
ASCII_TEXT_PATH = ASSETS_DIR / "foto-ascii.txt"


# ============================================================
# CONFIGURAÇÕES
# ============================================================

CANVAS_WIDTH = 1600
CANVAS_HEIGHT = 900

BACKGROUND_COLOR = "#161b22"

ASCII_COLUMNS = 86
ASCII_ROWS = 64

# Caracteres do mais escuro para o mais claro.
ASCII_CHARACTERS = "@%#*+=-:,."

# Pixels claros acima deste valor viram espaços vazios.
HIGHLIGHT_CUTOFF = 224

# Aumente para aproximar mais o rosto.
PORTRAIT_ZOOM = 1.20

CONTRAST = 1.35
SHARPNESS = 1.65
GAMMA = 1.05

# Intensidade do reforço de olhos, nariz, boca e barba.
EDGE_STRENGTH = 0.40


# ============================================================
# PREPARAÇÃO DA IMAGEM
# ============================================================

def flatten_and_crop(image: Image.Image) -> Image.Image:
    """
    Remove transparência, adiciona fundo branco e tenta
    cortar espaços vazios ao redor da pessoa.
    """

    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")

    # Caso a imagem tenha transparência.
    if alpha.getextrema()[0] < 255:
        mask = alpha.point(
            lambda value: 255 if value > 10 else 0
        )

        bounding_box = mask.getbbox()

        if bounding_box:
            left, top, right, bottom = bounding_box

            width = right - left
            height = bottom - top

            padding_x = int(width * 0.025)
            padding_y = int(height * 0.025)

            rgba = rgba.crop(
                (
                    max(0, left - padding_x),
                    max(0, top - padding_y),
                    min(rgba.width, right + padding_x),
                    min(rgba.height, bottom + padding_y),
                )
            )

        white_background = Image.new(
            "RGBA",
            rgba.size,
            (255, 255, 255, 255),
        )

        return Image.alpha_composite(
            white_background,
            rgba,
        ).convert("RGB")

    # Caso seja JPG, tenta detectar o fundo pelas extremidades.
    rgb = rgba.convert("RGB")

    corners = [
        rgb.getpixel((0, 0)),
        rgb.getpixel((rgb.width - 1, 0)),
        rgb.getpixel((0, rgb.height - 1)),
        rgb.getpixel((rgb.width - 1, rgb.height - 1)),
    ]

    background_color = tuple(
        sum(color[channel] for color in corners) // len(corners)
        for channel in range(3)
    )

    background = Image.new(
        "RGB",
        rgb.size,
        background_color,
    )

    difference = ImageChops.difference(
        rgb,
        background,
    ).convert("L")

    difference = difference.filter(
        ImageFilter.GaussianBlur(1.0)
    )

    mask = difference.point(
        lambda value: 255 if value > 18 else 0
    )

    bounding_box = mask.getbbox()

    if bounding_box:
        left, top, right, bottom = bounding_box

        width = right - left
        height = bottom - top

        padding_x = int(width * 0.025)
        padding_y = int(height * 0.025)

        rgb = rgb.crop(
            (
                max(0, left - padding_x),
                max(0, top - padding_y),
                min(rgb.width, right + padding_x),
                min(rgb.height, bottom + padding_y),
            )
        )

    return rgb


def apply_zoom(
    image: Image.Image,
    zoom: float,
) -> Image.Image:
    """
    Aproxima a pessoa e mantém o rosto levemente acima do centro.
    """

    if zoom <= 1:
        return image

    new_width = max(
        1,
        int(image.width / zoom),
    )

    new_height = max(
        1,
        int(image.height / zoom),
    )

    center_x = image.width / 2
    center_y = image.height * 0.43

    left = int(
        center_x - new_width / 2
    )

    top = int(
        center_y - new_height / 2
    )

    left = max(
        0,
        min(
            left,
            image.width - new_width,
        ),
    )

    top = max(
        0,
        min(
            top,
            image.height - new_height,
        ),
    )

    return image.crop(
        (
            left,
            top,
            left + new_width,
            top + new_height,
        )
    )


def prepare_image(
    image_path: Path,
) -> Image.Image:
    """
    Melhora contraste, nitidez e contornos faciais.
    """

    original = Image.open(image_path)

    flattened = flatten_and_crop(
        original
    )

    zoomed = apply_zoom(
        flattened,
        PORTRAIT_ZOOM,
    )

    fitted = ImageOps.fit(
        zoomed,
        (ASCII_COLUMNS, ASCII_ROWS),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.40),
    )

    grayscale = fitted.convert("L")

    grayscale = ImageOps.autocontrast(
        grayscale,
        cutoff=1,
    )

    grayscale = ImageEnhance.Contrast(
        grayscale
    ).enhance(CONTRAST)

    grayscale = grayscale.filter(
        ImageFilter.UnsharpMask(
            radius=1.2,
            percent=175,
            threshold=3,
        )
    )

    grayscale = ImageEnhance.Sharpness(
        grayscale
    ).enhance(SHARPNESS)

    # Cria um mapa de contornos.
    edges = grayscale.filter(
        ImageFilter.FIND_EDGES
    )

    edges = edges.filter(
        ImageFilter.GaussianBlur(0.45)
    )

    edges = ImageOps.autocontrast(
        edges,
        cutoff=2,
    )

    inverted_edges = ImageOps.invert(
        edges
    )

    white = Image.new(
        "L",
        grayscale.size,
        255,
    )

    controlled_edges = Image.blend(
        white,
        inverted_edges,
        EDGE_STRENGTH,
    )

    grayscale = ImageChops.multiply(
        grayscale,
        controlled_edges,
    )

    grayscale = grayscale.point(
        lambda pixel: round(
            255 * ((pixel / 255) ** GAMMA)
        )
    )

    return grayscale


# ============================================================
# CONVERSÃO PARA ASCII
# ============================================================

def image_to_ascii(
    image: Image.Image,
) -> list[str]:
    """
    Converte pixels claros em espaços e pixels escuros
    em caracteres mais densos.
    """

    pixels = list(
        image.getdata()
    )

    lines: list[str] = []

    last_character_index = (
        len(ASCII_CHARACTERS) - 1
    )

    for row in range(ASCII_ROWS):
        characters: list[str] = []

        for column in range(ASCII_COLUMNS):
            pixel = pixels[
                row * ASCII_COLUMNS + column
            ]

            if pixel >= HIGHLIGHT_CUTOFF:
                characters.append(" ")
                continue

            normalized = (
                pixel / HIGHLIGHT_CUTOFF
            )

            character_index = round(
                normalized
                * last_character_index
            )

            character_index = max(
                0,
                min(
                    character_index,
                    last_character_index,
                ),
            )

            characters.append(
                ASCII_CHARACTERS[
                    character_index
                ]
            )

        # Os espaços finais fazem parte da arte.
        lines.append(
            "".join(characters)
        )

    return lines


# ============================================================
# CRIAÇÃO DO SVG
# ============================================================

def create_ascii_svg(
    ascii_lines: list[str],
) -> tuple[str, float]:
    """
    Posiciona o retrato na metade esquerda do cartão.
    """

    area_x = 24
    area_y = 18

    area_width = 602
    area_height = 864

    character_width_ratio = 0.61
    line_height_ratio = 0.98

    font_size_by_width = (
        area_width
        / (
            ASCII_COLUMNS
            * character_width_ratio
        )
    )

    font_size_by_height = (
        area_height
        / (
            ASCII_ROWS
            * line_height_ratio
        )
    )

    font_size = min(
        font_size_by_width,
        font_size_by_height,
    )

    line_height = (
        font_size
        * line_height_ratio
    )

    portrait_width = (
        ASCII_COLUMNS
        * font_size
        * character_width_ratio
    )

    portrait_height = (
        ASCII_ROWS
        * line_height
    )

    start_x = (
        area_x
        + (
            area_width
            - portrait_width
        )
        / 2
    )

    start_y = (
        area_y
        + (
            area_height
            - portrait_height
        )
        / 2
        + font_size
    )

    svg_lines: list[str] = []

    for index, line in enumerate(
        ascii_lines
    ):
        y = (
            start_y
            + index * line_height
        )

        svg_lines.append(
            f'<text '
            f'x="{start_x:.2f}" '
            f'y="{y:.2f}" '
            f'class="ascii" '
            f'xml:space="preserve">'
            f'{escape(line)}'
            f'</text>'
        )

    return (
        "\n".join(svg_lines),
        font_size,
    )


def create_row(
    y: int,
    label: str,
    value: str,
) -> str:
    """
    Cria uma linha com marcador, título, pontilhado e valor.
    """

    return f"""
    <text
        x="650"
        y="{y}"
        class="bullet"
    >•</text>

    <text
        x="685"
        y="{y}"
        class="label"
    >{escape(label)}:</text>

    <line
        x1="975"
        y1="{y - 7}"
        x2="1088"
        y2="{y - 7}"
        class="leader"
    />

    <text
        x="1118"
        y="{y}"
        class="value"
    >{escape(value)}</text>
    """


def create_section(
    y: int,
    title: str,
    line_start: int = 850,
) -> str:
    """
    Cria um título de seção com linha horizontal.
    """

    return f"""
    <text
        x="650"
        y="{y}"
        class="section"
    >— {escape(title)}</text>

    <line
        x1="{line_start}"
        y1="{y - 8}"
        x2="1550"
        y2="{y - 8}"
        class="section-line"
    />
    """


def create_svg(
    ascii_lines: list[str],
) -> str:
    """
    Monta o cartão final.
    """

    ascii_svg, ascii_font_size = (
        create_ascii_svg(
            ascii_lines
        )
    )

    return f"""<svg
    xmlns="http://www.w3.org/2000/svg"
    width="{CANVAS_WIDTH}"
    height="{CANVAS_HEIGHT}"
    viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}"
>
    <style>
        .card {{
            fill: {BACKGROUND_COLOR};
        }}

        .ascii {{
            fill: #d0d7de;
            font-family:
                "Courier New",
                "Liberation Mono",
                monospace;
            font-size: {ascii_font_size:.2f}px;
            font-weight: 700;
            white-space: pre;
            letter-spacing: 0;
        }}

        .title,
        .label,
        .value,
        .section {{
            font-family:
                "Courier New",
                "Liberation Mono",
                monospace;
            font-weight: 700;
        }}

        .title {{
            fill: #d0d7de;
            font-size: 25px;
        }}

        .label {{
            fill: #ffa657;
            font-size: 19px;
        }}

        .value {{
            fill: #a5d6ff;
            font-size: 19px;
        }}

        .bullet {{
            fill: #6e7681;
            font-family: monospace;
            font-size: 20px;
            font-weight: 700;
        }}

        .section {{
            fill: #d0d7de;
            font-size: 20px;
        }}

        .leader {{
            stroke: #6e7681;
            stroke-width: 4;
            stroke-linecap: round;
            stroke-dasharray: 1 12;
        }}

        .header-line,
        .section-line {{
            stroke: #d0d7de;
            stroke-width: 2;
        }}
    </style>

    <rect
        class="card"
        width="{CANVAS_WIDTH}"
        height="{CANVAS_HEIGHT}"
        rx="28"
    />

    {ascii_svg}

    <text
        x="650"
        y="54"
        class="title"
    >vinicius@vivico</text>

    <line
        x1="885"
        y1="46"
        x2="1550"
        y2="46"
        class="header-line"
    />

    {create_row(106, "OS", "macOS · Linux Mint")}
    {create_row(145, "Host", "MacBook Air M4")}
    {create_row(184, "University", "Electrical Engineering · UFMG")}
    {create_row(223, "Editor", "VS Code · Obsidian")}

    {create_section(285, "Learning", 850)}

    {create_row(330, "Programming", "Python · TypeScript")}
    {create_row(370, "Systems", "Linux · Networks · Git")}
    {create_row(410, "Engineering", "Automation · Electronics · AI")}

    {create_section(475, "Projects", 840)}

    {create_row(520, "Website", "vivico.space")}
    {create_row(560, "Company", "VEBRAM")}
    {create_row(600, "Study Engine", "Engineering Codex")}

    {create_section(665, "Contact", 825)}

    {create_row(710, "GitHub", "github.com/LopesVini")}
    {create_row(750, "Website", "vivico.space")}

    {create_section(815, "Interests", 850)}

    {create_row(860, "Focus", "Homelab · Music · Engineering")}
</svg>
"""


# ============================================================
# EXECUÇÃO
# ============================================================

prepared_image = prepare_image(
    IMAGE_PATH
)

ascii_lines = image_to_ascii(
    prepared_image
)

ASCII_TEXT_PATH.write_text(
    "\n".join(ascii_lines),
    encoding="utf-8",
)

SVG_PATH.write_text(
    create_svg(ascii_lines),
    encoding="utf-8",
)

print(f"Foto utilizada: {IMAGE_PATH}")
print(f"ASCII criado: {ASCII_TEXT_PATH}")
print(f"SVG criado: {SVG_PATH}")