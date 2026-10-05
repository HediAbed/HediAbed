import base64
import json
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design"
ASSETS = ROOT / "assets"
FONT_PATH = DESIGN / "fonts" / "PxPlus_IBM_VGA_8x16.ttf"

BASELINE_OFFSET = 12
UNDERLINE_OFFSET = 2
EDGE_COLUMNS = 2
SECTION_INDENT = 4
INFO_GAP_COLUMNS = 6
CURSOR_BLINK_SECONDS = 1.06
PERCENT = 100
WIDTH_DECIMALS = 2
BRAILLE_BASE = 0x2800
BRAILLE_DOT_COLUMNS = 2
BRAILLE_DOT_ROWS = 4
BRAILLE_DOT_OFFSETS = ((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3))
DOT_SIZE = 3
HERO_OUTPUT_ROW = 2
SKILL_GROUP_ROW = 2
SKILL_ITEM_ROW = 4
SKILL_LABEL_COLUMNS = 16
SKILL_COLUMN_GAP = 4
LANGUAGE_NAME_COLUMNS = 10
LANGUAGE_BAR_COLUMNS = 20
LANGUAGE_GAP_COLUMNS = 2
MIN_BAR_CELLS = 0.25
SHARE_DECIMALS = 1
BAR_INSET = 3
CARD_COLUMNS = 50
CARD_TEXT_COLUMNS = 44
CARD_WIDTH = "49%"
LINK_SEPARATOR = "   "
FONT_CREDIT = (
    '<sub>Set in a subset of PxPlus IBM VGA 8x16 from <a href="https://int10h.org/oldschool-pc-fonts/">'
    "The Ultimate Oldschool PC Font Pack</a> by VileR, "
    '<a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.</sub>'
)


@dataclass(frozen=True)
class Palette:
    name: str
    foreground: str
    muted: str
    accent: str


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
    runs: list[tuple[int, int, str, str]] = field(default_factory=list)
    cursors: list[tuple[int, int]] = field(default_factory=list)
    underlines: list[tuple[int, int, int]] = field(default_factory=list)
    braille: list[tuple[int, int, str]] = field(default_factory=list)
    bars: list[tuple[int, int, float]] = field(default_factory=list)
    rows: int = 0

    def text(self, column: int, row: int, value: str, role: str) -> None:
        if column < 0 or column + len(value) > self.columns:
            raise ValueError(f"text {value!r} at column {column} overflows {self.columns} columns")
        self.runs.append((column, row, value, role))
        self.rows = max(self.rows, row + 1)

    def cursor(self, column: int, row: int) -> None:
        self.cursors.append((column, row))
        self.rows = max(self.rows, row + 1)

    def dots(self, column: int, row: int, cells: str) -> None:
        if column + len(cells) > self.columns:
            raise ValueError(f"braille row at column {column} overflows {self.columns} columns")
        self.braille.append((column, row, cells))
        self.rows = max(self.rows, row + 1)


@dataclass(frozen=True)
class Grid:
    cell_width: int
    cell_height: int

    def x(self, canvas: Canvas, column: float) -> float:
        return (column + canvas.padding.left) * self.cell_width

    def y(self, canvas: Canvas, row: int) -> int:
        return (row + canvas.padding.top) * self.cell_height

    def width(self, canvas: Canvas) -> int:
        return (canvas.padding.left + canvas.columns + canvas.padding.right) * self.cell_width

    def height(self, canvas: Canvas) -> int:
        return (canvas.padding.top + canvas.rows + canvas.padding.bottom) * self.cell_height


def load_json(name: str) -> dict:
    return json.loads((DESIGN / name).read_text())


def palettes(tokens: dict) -> list[Palette]:
    color = tokens["color"]
    return [
        Palette("dark", color["foreground"], color["muted"], color["accent"]),
        Palette("light", color["lightForeground"], color["lightMuted"], color["lightAccent"]),
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


def styles(canvas: Canvas, palette: Palette, grid: Grid) -> str:
    characters = "".join(sorted({char for run in canvas.runs for char in run[2]} | {" "}))
    rules = [
        font_face(characters),
        f"text{{font-family:V,monospace;font-size:{grid.cell_height}px;white-space:pre}}",
        f".fg{{fill:{palette.foreground}}}.mu{{fill:{palette.muted}}}.ac{{fill:{palette.accent}}}",
    ]
    if canvas.cursors:
        rules += [
            "@keyframes blink{50%{opacity:0}}",
            f"@media (prefers-reduced-motion:no-preference){{.cur{{animation:blink {CURSOR_BLINK_SECONDS}s steps(1) infinite}}}}",
        ]
    return "".join(rules)


def text_elements(canvas: Canvas, grid: Grid) -> list[str]:
    texts = [
        f'<text x="{grid.x(canvas, column):g}" y="{grid.y(canvas, row) + BASELINE_OFFSET}" class="{role}">'
        f"{escape(value)}</text>"
        for column, row, value, role in canvas.runs
    ]
    lines = [
        f'<rect x="{grid.x(canvas, start):g}" y="{grid.y(canvas, row) + grid.cell_height - UNDERLINE_OFFSET}" '
        f'width="{length * grid.cell_width}" height="1" class="ac"/>'
        for row, start, length in canvas.underlines
    ]
    cursors = [
        f'<rect x="{grid.x(canvas, column):g}" y="{grid.y(canvas, row)}" '
        f'width="{grid.cell_width}" height="{grid.cell_height}" class="fg cur"/>'
        for column, row in canvas.cursors
    ]
    return texts + lines + cursors


def braille_bits(char: str) -> int:
    return ord(char) - BRAILLE_BASE


def cell_segments(left: float, top: int, bits: int, pitch: tuple[int, int]) -> list[str]:
    return [
        f"M{left + dot_x * pitch[0]:g} {top + dot_y * pitch[1]}h{DOT_SIZE}v{DOT_SIZE}h-{DOT_SIZE}z"
        for bit, (dot_x, dot_y) in enumerate(BRAILLE_DOT_OFFSETS)
        if bits >> bit & 1
    ]


def braille_path(canvas: Canvas, grid: Grid) -> list[str]:
    pitch = (grid.cell_width // BRAILLE_DOT_COLUMNS, grid.cell_height // BRAILLE_DOT_ROWS)
    segments = [
        segment
        for column, row, cells in canvas.braille
        for index, char in enumerate(cells)
        for segment in cell_segments(grid.x(canvas, column + index), grid.y(canvas, row), braille_bits(char), pitch)
    ]
    return [f'<path d="{"".join(segments)}" class="ac"/>'] if segments else []


def bar_elements(canvas: Canvas, grid: Grid) -> list[str]:
    return [
        f'<rect x="{grid.x(canvas, column):g}" y="{grid.y(canvas, row) + BAR_INSET}" '
        f'width="{cells * grid.cell_width:.1f}" height="{grid.cell_height - 2 * BAR_INSET}" class="ac"/>'
        for column, row, cells in canvas.bars
    ]


def svg(canvas: Canvas, palette: Palette, grid: Grid, label: str) -> str:
    width, height = grid.width(canvas), grid.height(canvas)
    body = braille_path(canvas, grid) + bar_elements(canvas, grid) + text_elements(canvas, grid)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}">'
        f"<title>{escape(label)}</title><style>{styles(canvas, palette, grid)}</style>{''.join(body)}</svg>"
    )


def prompt(canvas: Canvas, row: int, identity: str, command: str) -> None:
    tail = ":~$ "
    canvas.text(0, row, identity, "ac")
    canvas.text(len(identity), row, tail, "fg")
    if command:
        canvas.text(len(identity) + len(tail), row, command, "fg")
    else:
        canvas.cursor(len(identity) + len(tail), row)


def info_lines(copy: dict) -> list[list[tuple[int, str, str]]]:
    identity = f"{copy['user']}@{copy['host']}"
    label_width = max(len(key) for key, _ in copy["facts"]) + len(": ")
    lines: list[list[tuple[int, str, str]]] = [[(0, identity, "ac")], [(0, "-" * len(identity), "mu")]]
    for key, value in copy["facts"]:
        lines.append([(0, f"{key}:", "ac"), (label_width, value, "fg")])
    return lines


def hero(copy: dict, mark: list[str], columns: int) -> Canvas:
    canvas = Canvas(columns, Padding(EDGE_COLUMNS, EDGE_COLUMNS, 1, 1))
    identity = f"{copy['user']}@{copy['host']}"
    prompt(canvas, 0, identity, "fastfetch")
    info = info_lines(copy)
    info_column = max(map(len, mark)) + INFO_GAP_COLUMNS
    info_offset = (len(mark) - len(info)) // 2
    for index, line in enumerate(mark):
        canvas.dots(0, HERO_OUTPUT_ROW + index, line)
    for index, line in enumerate(info):
        for offset, value, role in line:
            canvas.text(info_column + offset, HERO_OUTPUT_ROW + info_offset + index, value, role)
    prompt(canvas, HERO_OUTPUT_ROW + max(len(mark), info_offset + len(info)) + 1, identity, "")
    return canvas


def link_entry(name: str, first: bool, last: bool) -> Canvas:
    suffix = "" if last else LINK_SEPARATOR
    canvas = Canvas(len(name) + len(suffix), Padding(left=EDGE_COLUMNS + SECTION_INDENT if first else 0))
    canvas.text(0, 0, name, "ac")
    canvas.underlines.append((0, 0, len(name)))
    if suffix:
        canvas.text(len(name), 0, suffix, "mu")
    return canvas


def heading(title: str, columns: int) -> Canvas:
    canvas = Canvas(columns, Padding(EDGE_COLUMNS, EDGE_COLUMNS, 1, 0))
    canvas.text(0, 0, title, "fg")
    return canvas


def devops_column(canvas: Canvas, groups: list[list[str]]) -> int:
    canvas.text(SECTION_INDENT, SKILL_GROUP_ROW, "DevOps", "ac")
    for index, (label, value) in enumerate(groups):
        canvas.text(SECTION_INDENT, SKILL_ITEM_ROW + index, label, "mu")
        canvas.text(SECTION_INDENT + SKILL_LABEL_COLUMNS, SKILL_ITEM_ROW + index, value, "fg")
    return SECTION_INDENT + SKILL_LABEL_COLUMNS + max(len(value) for _, value in groups)


def languages_column(canvas: Canvas, start: int, snapshot: dict) -> None:
    canvas.text(start, SKILL_GROUP_ROW, "Programming", "ac")
    rows = snapshot["languages"]
    widest = max(count for _, count in rows)
    bar_column = start + LANGUAGE_NAME_COLUMNS
    share_column = bar_column + LANGUAGE_BAR_COLUMNS + LANGUAGE_GAP_COLUMNS
    for index, (name, count) in enumerate(rows):
        row = SKILL_ITEM_ROW + index
        canvas.text(start, row, name, "mu")
        canvas.bars.append((bar_column, row, max(count / widest * LANGUAGE_BAR_COLUMNS, MIN_BAR_CELLS)))
        canvas.text(share_column, row, f"{count / snapshot['totalBytes'] * PERCENT:.{SHARE_DECIMALS}f}%", "fg")
    note = f"by code size, {len(snapshot['repos'])} public repos"
    canvas.text(start, SKILL_ITEM_ROW + len(rows) + 1, note, "mu")


def skills(copy: dict, snapshot: dict, columns: int) -> Canvas:
    canvas = heading("SKILLS", columns)
    devops_end = devops_column(canvas, copy["devops"])
    languages_column(canvas, devops_end + SKILL_COLUMN_GAP, snapshot)
    return canvas


def card(project: dict, rows: int) -> Canvas:
    canvas = Canvas(CARD_COLUMNS, Padding(top=1))
    canvas.text(0, 0, project["name"], "ac")
    canvas.underlines.append((0, 0, len(project["name"])))
    for index, line in enumerate(textwrap.wrap(project["summary"], CARD_TEXT_COLUMNS)):
        canvas.text(0, 2 + index, line, "fg")
    canvas.text(0, rows - 1, "$", "ac")
    canvas.text(2, rows - 1, project["command"], "mu")
    return canvas


def card_rows(projects: list[dict]) -> int:
    longest = max(len(textwrap.wrap(project["summary"], CARD_TEXT_COLUMNS)) for project in projects)
    return 2 + longest + 2


def width_percent(canvas: Canvas, grid: Grid, display_width: int) -> str:
    return f"{grid.width(canvas) / display_width * PERCENT:.{WIDTH_DECIMALS}f}%"


def themed(name: str, width: str, alt: str) -> str:
    return (
        f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{name}-dark.svg">'
        f'<img src="assets/{name}-light.svg" width="{width}" alt="{escape(alt)}"></picture>'
    )


def demo(project: dict) -> str:
    name = project["name"]
    for suffix in ("webp", "png"):
        if not (ASSETS / f"{name}.{suffix}").is_file():
            raise FileNotFoundError(f"missing recording asset assets/{name}.{suffix}")
    return (
        f'<a href="{project["url"]}"><picture>'
        f'<source media="(prefers-reduced-motion: reduce)" srcset="assets/{name}.png">'
        f'<img src="assets/{name}.webp" width="{CARD_WIDTH}" alt="{escape(project["alt"])}"></picture></a>'
    )


def readme(sections: dict[str, tuple[Canvas, str]], copy: dict, grid: Grid, display_width: int) -> str:
    def block(name: str, width: str | None = None) -> str:
        canvas, label = sections[name]
        return themed(name, width or width_percent(canvas, grid, display_width), label)

    links = "".join(f'<a href="{url}">{block(f"link-{index}")}</a>' for index, (_, url) in enumerate(copy["links"]))
    cards = " ".join(
        f'<a href="{project["url"]}">{block(f"card-{project["name"]}", CARD_WIDTH)}</a>' for project in copy["projects"]
    )
    demos = " ".join(demo(project) for project in copy["projects"])
    parts = [
        f"<p>{block('hero')}</p>",
        f"<p>{links}</p>",
        f"<p>{block('skills')}</p>",
        f"<p>{block('projects')}</p>",
        f"<p>{cards}</p>",
        f"<p>{demos}</p>",
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
    facts = ", ".join(f"{key} {value}" for key, value in copy["facts"])
    devops = "; ".join(f"{label}: {value}" for label, value in copy["devops"])
    shares = ", ".join(
        f"{name} {count / snapshot['totalBytes'] * PERCENT:.{SHARE_DECIMALS}f}%" for name, count in snapshot["languages"]
    )
    sections = {
        "hero": (hero(copy, mark, columns), f"fastfetch for {copy['user']}@{copy['host']}. {facts}"),
        "skills": (skills(copy, snapshot, columns), f"Skills. DevOps: {devops}. Programming by code size: {shares}"),
        "projects": (heading("PROJECTS", columns), "Projects"),
    }
    links = copy["links"]
    for index, (name, _) in enumerate(links):
        sections[f"link-{index}"] = (link_entry(name, index == 0, index == len(links) - 1), name)
    rows = card_rows(copy["projects"])
    for project in copy["projects"]:
        sections[f"card-{project['name']}"] = (card(project, rows), f"{project['name']}: {project['summary']}")
    return sections


def main() -> None:
    tokens = load_json("tokens.json")
    copy = load_json("copy.json")
    mark = braille_lines((DESIGN / "planet.braille").read_text().splitlines())
    grid = Grid(tokens["font"]["cellWidth"], tokens["font"]["cellHeight"])
    columns = tokens["layout"]["columns"] - 2 * EDGE_COLUMNS
    sections = sections_for(copy, mark, load_json("languages.json"), columns)
    for stale in ASSETS.glob("*.svg"):
        stale.unlink()
    for palette in palettes(tokens):
        for name, (canvas, label) in sections.items():
            (ASSETS / f"{name}-{palette.name}.svg").write_text(svg(canvas, palette, grid, label))
    (ROOT / "README.md").write_text(readme(sections, copy, grid, tokens["layout"]["displayWidth"]))


if __name__ == "__main__":
    main()
