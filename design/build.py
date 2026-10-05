import base64
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design"
ASSETS = ROOT / "assets"
FONT_PATH = DESIGN / "fonts" / "PxPlus_IBM_VGA_8x16.ttf"

BASELINE_OFFSET = 12
UNDERLINE_OFFSET = 2
EDGE_COLUMNS = 2
MAN_INDENT = 7
INFO_GAP_COLUMNS = 4
LOGIN_TYPE_START = 0.6
LOGIN_KEY_INTERVAL = 0.12
PASSWORD_PAUSE = 0.35
SHELL_PAUSE = 0.6
SHELL_TYPE_DELAY = 0.3
SHELL_KEY_INTERVAL = 0.09
OUTPUT_PAUSE = 0.25
OUTPUT_ROW_INTERVAL = 0.03
CURSOR_BLINK_SECONDS = 1.06
TIME_PRECISION_MS = 1000
WHATIS_NAME_COLUMNS = 21
DECORATIVE_SECTIONS = frozenset({"pager"})
PERCENT = 100
WIDTH_DECIMALS = 2
FONT_CREDIT = (
    '<sub>Set in a subset of PxPlus IBM VGA 8x16 from <a href="https://int10h.org/oldschool-pc-fonts/">'
    "The Ultimate Oldschool PC Font Pack</a> by VileR, "
    '<a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.</sub>'
)
BRAILLE_BASE = 0x2800
BRAILLE_DOT_COLUMNS = 2
BRAILLE_DOT_ROWS = 4
BRAILLE_DOT_OFFSETS = ((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3))
DOT_SIZE = 3
OUTPUT_FIRST_ROW = 3
LANGUAGE_FIRST_ROW = 2
LANGUAGE_GAP_COLUMNS = 2
LANGUAGE_BAR_COLUMNS = 48
MIN_BAR_CELLS = 0.25
SHARE_DECIMALS = 1
BAR_INSET = 3


@dataclass(frozen=True)
class Palette:
    name: str
    foreground: str
    muted: str
    accent: str
    inverse_text: str


@dataclass(frozen=True)
class Padding:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


@dataclass
class Canvas:
    columns: int
    padding: Padding
    runs: list[tuple[int, int, str, str, float | None]] = field(default_factory=list)
    cursors: list[tuple[int, int, float, float | None]] = field(default_factory=list)
    underlines: list[tuple[int, int, int]] = field(default_factory=list)
    inverse: list[tuple[int, int, int]] = field(default_factory=list)
    braille: list[tuple[int, int, str, str, float | None]] = field(default_factory=list)
    bars: list[tuple[int, int, float]] = field(default_factory=list)
    rows: int = 0

    def text(self, column: int, row: int, value: str, role: str, at: float | None = None) -> None:
        if column < 0 or column + len(value) > self.columns:
            raise ValueError(f"text {value!r} at column {column} overflows {self.columns} columns")
        self.runs.append((column, row, value, role, at))
        self.rows = max(self.rows, row + 1)

    def typed(self, column: int, row: int, value: str, role: str, start: float, interval: float) -> float:
        for index, char in enumerate(value):
            self.text(column + index, row, char, role, start + index * interval)
        return start + len(value) * interval

    def cursor(self, column: int, row: int, start: float, end: float | None) -> None:
        self.cursors.append((column, row, start, end))
        self.rows = max(self.rows, row + 1)

    def dots(self, column: int, row: int, cells: str, role: str, at: float | None = None) -> None:
        self.braille.append((column, row, cells, role, at))
        self.rows = max(self.rows, row + 1)


@dataclass(frozen=True)
class Grid:
    cell_width: int
    cell_height: int

    def x(self, canvas: Canvas, column: int) -> int:
        return (column + canvas.padding.left) * self.cell_width

    def y(self, canvas: Canvas, row: int) -> int:
        return (row + canvas.padding.top) * self.cell_height


def load_json(name: str) -> dict:
    return json.loads((DESIGN / name).read_text())


def palettes(tokens: dict) -> list[Palette]:
    color = tokens["color"]
    return [
        Palette("dark", color["foreground"], color["muted"], color["accent"], color["background"]),
        Palette("light", color["lightForeground"], color["lightMuted"], color["lightAccent"], color["lightInverseText"]),
    ]


def font_face(characters: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "subset.woff2"
        subprocess.run(
            [
                "pyftsubset",
                str(FONT_PATH),
                f"--text={characters}",
                "--flavor=woff2",
                f"--output-file={output}",
                "--layout-features=",
                "--drop-tables+=FFTM",
                "--no-hinting",
            ],
            check=True,
        )
        encoded = base64.b64encode(output.read_bytes()).decode()
    return f'@font-face{{font-family:V;src:url(data:font/woff2;base64,{encoded}) format("woff2")}}'


def ms(seconds: float) -> int:
    return round(seconds * TIME_PRECISION_MS)


def base_styles(canvas: Canvas, palette: Palette, grid: Grid) -> list[str]:
    characters = "".join(sorted({c for run in canvas.runs for c in run[2]} | {" "}))
    return [
        font_face(characters),
        f"text{{font-family:V,monospace;font-size:{grid.cell_height}px;white-space:pre}}",
        f".fg{{fill:{palette.foreground}}}.mu{{fill:{palette.muted}}}.ac{{fill:{palette.accent}}}",
        f".iv{{fill:{palette.foreground}}}.ivt{{fill:{palette.inverse_text}}}.cur{{fill:{palette.foreground}}}",
        ".transient{opacity:0}",
        "@keyframes show{to{opacity:1}}@keyframes hide{to{opacity:0}}@keyframes blink{50%{opacity:0}}",
    ]


def text_elements(canvas: Canvas, grid: Grid) -> list[str]:
    elements = []
    for row, start, length in canvas.inverse:
        elements.append(
            f'<rect x="{grid.x(canvas, start)}" y="{grid.y(canvas, row)}" '
            f'width="{length * grid.cell_width}" height="{grid.cell_height}" class="iv"/>'
        )
    for column, row, value, role, at in canvas.runs:
        classes = role if at is None else f"{role} a d{ms(at)}"
        elements.append(
            f'<text x="{grid.x(canvas, column)}" y="{grid.y(canvas, row) + BASELINE_OFFSET}" '
            f'class="{classes}">{escape(value)}</text>'
        )
    for row, start, length in canvas.underlines:
        elements.append(
            f'<rect x="{grid.x(canvas, start)}" '
            f'y="{grid.y(canvas, row) + grid.cell_height - UNDERLINE_OFFSET}" '
            f'width="{length * grid.cell_width}" height="1" class="ac"/>'
        )
    return elements


def cursor_parts(canvas: Canvas, grid: Grid) -> tuple[list[str], list[str]]:
    styles, elements = [], []
    for index, (column, row, start, end) in enumerate(canvas.cursors):
        name = f"c{index}"
        if end is None:
            styles.append(
                f".{name}{{opacity:0;animation:show 0s {ms(start)}ms forwards,"
                f"blink {CURSOR_BLINK_SECONDS}s steps(1) {ms(start)}ms infinite}}"
            )
            classes = f"cur {name}"
        else:
            styles.append(f".{name}{{animation:show 0s {ms(start)}ms forwards,hide 0s {ms(end)}ms forwards}}")
            classes = f"cur transient {name}"
        elements.append(
            f'<rect x="{grid.x(canvas, column)}" y="{grid.y(canvas, row)}" '
            f'width="{grid.cell_width}" height="{grid.cell_height}" class="{classes}"/>'
        )
    return styles, elements


def braille_bits(char: str) -> int:
    return ord(char) - BRAILLE_BASE


def cell_segments(left: int, top: int, bits: int, pitch: tuple[int, int]) -> list[str]:
    return [
        f"M{left + dot_x * pitch[0]} {top + dot_y * pitch[1]}h{DOT_SIZE}v{DOT_SIZE}h-{DOT_SIZE}z"
        for bit, (dot_x, dot_y) in enumerate(BRAILLE_DOT_OFFSETS)
        if bits >> bit & 1
    ]


def braille_paths(canvas: Canvas, grid: Grid) -> list[str]:
    pitch = (grid.cell_width // BRAILLE_DOT_COLUMNS, grid.cell_height // BRAILLE_DOT_ROWS)
    elements = []
    for column, row, cells, role, at in canvas.braille:
        segments = [
            segment
            for index, char in enumerate(cells)
            for segment in cell_segments(
                grid.x(canvas, column + index), grid.y(canvas, row), braille_bits(char), pitch
            )
        ]
        if segments:
            classes = role if at is None else f"{role} a d{ms(at)}"
            elements.append(f'<path d="{"".join(segments)}" class="{classes}"/>')
    return elements


def bar_elements(canvas: Canvas, grid: Grid) -> list[str]:
    return [
        f'<rect x="{grid.x(canvas, column)}" y="{grid.y(canvas, row) + BAR_INSET}" '
        f'width="{cells * grid.cell_width:.1f}" height="{grid.cell_height - 2 * BAR_INSET}" class="ac"/>'
        for column, row, cells in canvas.bars
    ]


def svg(canvas: Canvas, palette: Palette, grid: Grid, label: str) -> str:
    width = (canvas.padding.left + canvas.columns + canvas.padding.right) * grid.cell_width
    height = (canvas.padding.top + canvas.rows + canvas.padding.bottom) * grid.cell_height
    timed = [run[4] for run in canvas.runs] + [line[4] for line in canvas.braille]
    delays = sorted({ms(at) for at in timed if at is not None})
    cursor_styles, cursor_elements = cursor_parts(canvas, grid)
    motion = [
        ".a{opacity:0;animation:show 0s linear forwards}",
        *[f".d{d}{{animation-delay:{d}ms}}" for d in delays],
        *cursor_styles,
    ]
    styles = base_styles(canvas, palette, grid)
    if delays or cursor_styles:
        styles += ["@media (prefers-reduced-motion:no-preference){", *motion, "}"]
    body = braille_paths(canvas, grid) + bar_elements(canvas, grid) + text_elements(canvas, grid) + cursor_elements
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}">'
        f"<title>{escape(label)}</title><style>{''.join(styles)}</style>{''.join(body)}</svg>"
    )


def info_lines(copy: dict) -> list[list[tuple[int, str, str]]]:
    identity = f"{copy['user']}@{copy['host']}"
    lines: list[list[tuple[int, str, str]]] = [[(0, identity, "ac")], [(0, "-" * len(identity), "fg")]]
    for key, value in copy["facts"]:
        label = f"{key}: "
        lines.append([(0, label, "ac"), (len(label), value, "fg")])
    return lines


def prompt(canvas: Canvas, row: int, identity: str, at: float) -> int:
    tail = ":~$ "
    canvas.text(0, row, identity, "ac", at)
    canvas.text(len(identity), row, tail, "fg", at)
    return len(identity) + len(tail)


def hero(copy: dict, mark: list[str], columns: int) -> Canvas:
    canvas = Canvas(columns, Padding(EDGE_COLUMNS, EDGE_COLUMNS, 1, 1))
    identity = f"{copy['user']}@{copy['host']}"
    login = f"{copy['host']} login: "
    canvas.text(0, 0, login, "fg")
    canvas.cursor(len(login), 0, 0, LOGIN_TYPE_START)
    password_at = canvas.typed(len(login), 0, copy["user"], "fg", LOGIN_TYPE_START, LOGIN_KEY_INTERVAL) + PASSWORD_PAUSE
    password = "Password: "
    canvas.text(0, 1, password, "fg", password_at)
    shell_at = password_at + SHELL_PAUSE
    canvas.cursor(len(password), 1, password_at, shell_at)
    command_column = prompt(canvas, 2, identity, shell_at)
    type_start = shell_at + SHELL_TYPE_DELAY
    canvas.cursor(command_column, 2, shell_at, type_start)
    output_at = canvas.typed(command_column, 2, "neofetch", "fg", type_start, SHELL_KEY_INTERVAL) + OUTPUT_PAUSE
    info = info_lines(copy)
    info_column = max(map(len, mark)) + INFO_GAP_COLUMNS
    info_offset = (len(mark) - len(info)) // 2
    output_rows = max(len(mark), info_offset + len(info))
    for index in range(output_rows):
        at = output_at + index * OUTPUT_ROW_INTERVAL
        if index < len(mark):
            canvas.dots(0, OUTPUT_FIRST_ROW + index, mark[index], "ac", at)
        info_index = index - info_offset
        if 0 <= info_index < len(info):
            for offset, value, role in info[info_index]:
                canvas.text(info_column + offset, OUTPUT_FIRST_ROW + index, value, role, at)
    final_row = OUTPUT_FIRST_ROW + output_rows + 1
    final_at = output_at + output_rows * OUTPUT_ROW_INTERVAL
    canvas.cursor(prompt(canvas, final_row, identity, final_at), final_row, final_at, None)
    return canvas


def heading(title: str, columns: int) -> Canvas:
    canvas = Canvas(columns, Padding(EDGE_COLUMNS, EDGE_COLUMNS, 1, 0))
    canvas.text(0, 0, title, "fg")
    return canvas


def languages(snapshot: dict, columns: int) -> Canvas:
    canvas = heading("LANGUAGES", columns)
    rows = snapshot["languages"]
    total = snapshot["totalBytes"]
    widest = max(count for _, count in rows)
    name_width = max(len(name) for name, _ in rows) + LANGUAGE_GAP_COLUMNS
    for index, (name, count) in enumerate(rows):
        row = LANGUAGE_FIRST_ROW + index
        bar_cells = max(count / widest * LANGUAGE_BAR_COLUMNS, MIN_BAR_CELLS)
        canvas.text(MAN_INDENT, row, name, "fg")
        canvas.bars.append((MAN_INDENT + name_width, row, bar_cells))
        share = f"{count / total * PERCENT:.{SHARE_DECIMALS}f}%"
        canvas.text(MAN_INDENT + name_width + LANGUAGE_BAR_COLUMNS + LANGUAGE_GAP_COLUMNS, row, share, "mu")
    source = f"share of code across {len(snapshot['repos'])} public repositories, from the GitHub API"
    canvas.text(MAN_INDENT, LANGUAGE_FIRST_ROW + len(rows) + 1, source, "mu")
    return canvas


def see_also_entry(entry: list[str], first: bool, last: bool) -> Canvas:
    name, section, _ = entry
    suffix = f"({section})" + ("" if last else ", ")
    indent = EDGE_COLUMNS + MAN_INDENT if first else 0
    canvas = Canvas(len(name) + len(suffix), Padding(left=indent))
    canvas.text(0, 0, name, "ac")
    canvas.text(len(name), 0, suffix, "mu")
    canvas.underlines.append((0, 0, len(name)))
    return canvas


def pager(copy: dict) -> Canvas:
    man = copy["man"]
    status = f" Manual page {man['name']}({man['section']}) line 1 (press h for help or q to quit)"
    canvas = Canvas(len(status), Padding(left=EDGE_COLUMNS))
    canvas.inverse.append((0, 0, len(status)))
    canvas.text(0, 0, status, "ivt")
    return canvas


def whatis(project: list[str]) -> Canvas:
    name, _, summary = project[:3]
    reference = f"{name} (1)"
    if len(reference) >= WHATIS_NAME_COLUMNS:
        raise ValueError(f"whatis name {reference!r} does not fit in {WHATIS_NAME_COLUMNS} columns")
    canvas = Canvas(WHATIS_NAME_COLUMNS + len(f"- {summary}"), Padding(left=EDGE_COLUMNS + MAN_INDENT))
    canvas.text(0, 0, name, "ac")
    canvas.text(len(name), 0, reference[len(name):], "mu")
    canvas.text(WHATIS_NAME_COLUMNS, 0, f"- {summary}", "mu")
    return canvas


def width_percent(canvas: Canvas, grid: Grid, display_width: int) -> str:
    pixels = (canvas.padding.left + canvas.columns + canvas.padding.right) * grid.cell_width
    return f"{pixels / display_width * PERCENT:.{WIDTH_DECIMALS}f}%"


def themed(name: str, width: str, alt: str) -> str:
    return (
        f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{name}-dark.svg">'
        f'<img src="assets/{name}-light.svg" width="{width}" alt="{escape(alt)}"></picture>'
    )


def recording_widths(projects: list[list[str]]) -> dict[str, str]:
    pixels = {}
    for name, *_ in projects:
        for suffix in ("webp", "png"):
            if not (ASSETS / f"{name}.{suffix}").is_file():
                raise FileNotFoundError(f"missing recording asset assets/{name}.{suffix}")
        with Image.open(ASSETS / f"{name}.webp") as animation:
            pixels[name] = animation.width
    widest = max(pixels.values())
    return {name: f"{width / widest * PERCENT:.{WIDTH_DECIMALS}f}%" for name, width in pixels.items()}


def recording(project: list[str], width: str) -> str:
    name, url, _, alt = project
    return (
        f'<a href="{url}"><picture><source media="(prefers-reduced-motion: reduce)" srcset="assets/{name}.png">'
        f'<img src="assets/{name}.webp" width="{width}" alt="{escape(alt)}"></picture></a>'
    )


def readme(sections: dict[str, tuple[Canvas, str]], copy: dict, grid: Grid, display_width: int) -> str:
    def block(name: str) -> str:
        canvas, label = sections[name]
        alt = "" if name in DECORATIVE_SECTIONS else label
        return themed(name, width_percent(canvas, grid, display_width), alt)

    links = "".join(
        f'<a href="{entry[2]}">{block(f"see-{index}")}</a>' for index, entry in enumerate(copy["man"]["seeAlso"])
    )
    widths = recording_widths(copy["projects"])
    parts = [f"<p>{block('hero')}</p>", f"<p>{block('projects')}</p>"]
    for project in copy["projects"]:
        parts.append(f"<p>{block(f'whatis-{project[0]}')}</p>")
        parts.append(f"<p>{recording(project, widths[project[0]])}</p>")
    parts += [
        f"<p>{block('languages')}</p>",
        f"<p>{block('see-also')}</p>",
        f"<p>{links}</p>",
        f"<p>{block('pager')}</p>",
        FONT_CREDIT,
    ]
    return "\n\n".join(parts) + "\n"


def braille_lines(lines: list[str]) -> list[str]:
    blank = chr(BRAILLE_BASE)
    filled = [index for index, line in enumerate(lines) if line.strip(blank)]
    lead = min(len(lines[index]) - len(lines[index].lstrip(blank)) for index in filled)
    width = max(len(lines[index].rstrip(blank)) for index in filled)
    return [lines[index][lead:width].ljust(width - lead, blank) for index in range(filled[0], filled[-1] + 1)]


def sections_for(copy: dict, mark: list[str], snapshot: dict, columns: int) -> dict[str, tuple[Canvas, str]]:
    entries = copy["man"]["seeAlso"]
    facts = ", ".join(f"{key} {value}" for key, value in copy["facts"])
    shares = ", ".join(
        f"{name} {count / snapshot['totalBytes'] * PERCENT:.{SHARE_DECIMALS}f}%" for name, count in snapshot["languages"]
    )
    sections = {
        "hero": (hero(copy, mark, columns), f"{copy['user']}@{copy['host']} neofetch. {facts}"),
        "projects": (heading("PROJECTS", columns), "Projects"),
        "languages": (languages(snapshot, columns), f"Languages across my public repositories: {shares}"),
        "see-also": (heading("SEE ALSO", columns), "See also"),
        "pager": (pager(copy), "Manual page pager status line"),
    }
    for index, entry in enumerate(entries):
        sections[f"see-{index}"] = (see_also_entry(entry, index == 0, index == len(entries) - 1), entry[0])
    for project in copy["projects"]:
        sections[f"whatis-{project[0]}"] = (whatis(project), f"{project[0]}: {project[2]}")
    return sections


def main() -> None:
    tokens = load_json("tokens.json")
    copy = load_json("copy.json")
    mark = braille_lines((DESIGN / "planet.braille").read_text().splitlines())
    grid = Grid(tokens["font"]["cellWidth"], tokens["font"]["cellHeight"])
    columns = tokens["layout"]["columns"] - 2 * EDGE_COLUMNS
    sections = sections_for(copy, mark, load_json("languages.json"), columns)
    ASSETS.mkdir(exist_ok=True)
    for palette in palettes(tokens):
        for name, (canvas, label) in sections.items():
            (ASSETS / f"{name}-{palette.name}.svg").write_text(svg(canvas, palette, grid, label))
    (ROOT / "README.md").write_text(readme(sections, copy, grid, tokens["layout"]["displayWidth"]))


if __name__ == "__main__":
    main()
