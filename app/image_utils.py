import hashlib
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageStat

from . import config

Image.MAX_IMAGE_PIXELS = config.MAX_PIXELS


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def read_dimensions(path: Path) -> Tuple[int, int]:
    with Image.open(path) as img:
        img.verify()  # 基本校验
    # 重新打开以便后续操作
    with Image.open(path) as img:
        width, height = img.size
    if width * height > config.MAX_PIXELS:
        raise ValueError("像素数超限")
    return width, height


def make_thumbnail(source: Path, target: Path) -> Tuple[int, int]:
    with Image.open(source) as img:
        img.load()
        img.thumbnail(config.THUMB_SIZE)
        if config.THUMB_FORMAT == "WEBP":
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                rgb = img.convert("RGBA")
            else:
                rgb = img.convert("RGB")
        else:
            rgb = img.convert("RGB")
        target.parent.mkdir(parents=True, exist_ok=True)
        save_kwargs = {"quality": config.THUMB_QUALITY}
        if config.THUMB_FORMAT == "WEBP":
            save_kwargs["method"] = 6
        elif config.THUMB_FORMAT == "JPEG":
            save_kwargs["optimize"] = True
        rgb.save(target, format=config.THUMB_FORMAT, **save_kwargs)
        return rgb.size


def dominant_color(path: Path) -> str:
    with Image.open(path) as img:
        small = img.convert("RGB").resize((32, 32))
    stat = ImageStat.Stat(small)
    r, g, b = [int(c) for c in stat.mean]
    return f"#{r:02x}{g:02x}{b:02x}"
