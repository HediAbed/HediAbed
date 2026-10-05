import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
RECORDINGS = ROOT / "recordings"
BUILD = ROOT / "design" / "build.py"
MAX_BYTES = 3_000_000
MAX_SECONDS = 24.0
OPAQUE = 255
MS_PER_SECOND = 1000


class EncodingError(Exception):
    pass


def encode(source: Path, target: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-i", str(source),
            "-vf", "format=rgb24", "-c:v", "libwebp_anim", "-lossless", "1",
            "-compression_level", "6", "-loop", "0", "-an", str(target),
        ],
        check=True,
    )


def extract_still(source: Path, target: Path, seconds: float) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", str(seconds), "-i", str(source), "-frames:v", "1", str(target)],
        check=True,
    )


def validate(target: Path) -> tuple[int, float]:
    size = target.stat().st_size
    if size > MAX_BYTES:
        raise EncodingError(f"{target.name} is {size} bytes, limit {MAX_BYTES}")
    with Image.open(target) as animation:
        total_ms = 0
        for index in range(animation.n_frames):
            animation.seek(index)
            total_ms += animation.info.get("duration", 0)
            alpha_low, _ = animation.convert("RGBA").getchannel("A").getextrema()
            if alpha_low < OPAQUE:
                raise EncodingError(f"{target.name} frame {index} is not fully opaque")
    seconds = total_ms / MS_PER_SECOND
    if seconds > MAX_SECONDS:
        raise EncodingError(f"{target.name} runs {seconds:.2f}s, limit {MAX_SECONDS}s")
    return size, seconds


def publish(name: str, still_at: float) -> tuple[int, float]:
    source = RECORDINGS / f"{name}.mp4"
    if not source.is_file():
        raise EncodingError(f"missing recording {source.relative_to(ROOT)}")
    with tempfile.TemporaryDirectory() as staging:
        webp = Path(staging) / f"{name}.webp"
        still = Path(staging) / f"{name}.png"
        encode(source, webp)
        extract_still(source, still, still_at)
        result = validate(webp)
        webp.replace(ASSETS / webp.name)
        still.replace(ASSETS / still.name)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--still-at", type=float, required=True)
    args = parser.parse_args()
    try:
        size, seconds = publish(args.name, args.still_at)
    except EncodingError as error:
        sys.exit(f"invalid recording, published assets untouched: {error}")
    print(f"{args.name}.webp: {size} bytes, {seconds:.2f}s, every frame opaque")
    subprocess.run([sys.executable, str(BUILD)], check=True)


if __name__ == "__main__":
    main()
