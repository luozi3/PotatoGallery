import json
import os
import shutil
import time
from urllib.parse import quote
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config
from .storage import fsync_path

TEMPLATE_DIR = config.STATIC / "templates"
ASSET_DIR = config.STATIC
DEFAULT_COLLECTION_META = {
    "mine": {
        "title": "我的作品",
        "description": "luozi_sama 的原创插画，持续更新与打磨。",
    },
    "favorites": {
        "title": "他人作品",
        "description": "精挑细选的二次元插画，展示我喜欢的画风。",
    },
}
DEFAULT_SITE_CONFIG = {
    "site_name": "luozi_sama 的插画馆",
    "site_description": "静态插画展示站点，包含原创与精选收藏。",
    "site_url": "https://luozi.de5.net",
    "theme_color": "#4c7cff",
    "locale": "zh_CN",
    "live2d": {
        "enabled": False,
        "base_url": "/static/live2d",
        "model": "/static/live2d/assets/Pio/Pio.model.json",
        "canvas_id": "live2dcanvas",
    },
    "counter": {
        "enabled": False,
        "img_url": "https://luozi.de5.net/counter/get/@luozisamaworld?theme=gelbooru",
    },
}


def load_collections_config() -> Tuple[dict, str, List[str]]:
    """
    读取手工分区配置，允许将特定 UUID 放入“我的作品”或“他人作品”。
    未命中时使用默认分区。
    """
    cfg_path = ASSET_DIR / "data" / "collections.json"
    meta: Dict[str, dict] = {}
    default_collection = "favorites"
    if not cfg_path.exists():
        meta = {
            key: {**value, "uuids": set()}
            for key, value in DEFAULT_COLLECTION_META.items()
        }
        order = list(meta.keys())
        return meta, default_collection, order

    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        collections = raw.get("collections") or {}
        order = []
        if isinstance(collections, list):
            for info in collections:
                if not isinstance(info, dict):
                    continue
                name = info.get("slug") or info.get("name")
                if not name:
                    continue
                title = info.get("title") or DEFAULT_COLLECTION_META.get(name, {}).get("title", name)
                description = info.get("description") or DEFAULT_COLLECTION_META.get(name, {}).get("description", "")
                uuids = info.get("uuids") or []
                meta[name] = {"title": title, "description": description, "uuids": set(uuids)}
                order.append(name)
        elif isinstance(collections, dict):
            for name, info in collections.items():
                if not isinstance(info, dict):
                    continue
                title = info.get("title") or DEFAULT_COLLECTION_META.get(name, {}).get("title", name)
                description = info.get("description") or DEFAULT_COLLECTION_META.get(name, {}).get("description", "")
                uuids = info.get("uuids") or []
                meta[name] = {"title": title, "description": description, "uuids": set(uuids)}
                order.append(name)
        config_order = raw.get("order") or []
        if isinstance(config_order, list) and config_order:
            order = [name for name in config_order if name in meta]
        default_collection = raw.get("default_collection", default_collection)
    except Exception:
        # 配置异常时回退默认分区，避免影响生成
        meta = {
            key: {**value, "uuids": set()}
            for key, value in DEFAULT_COLLECTION_META.items()
        }
        order = list(meta.keys())
        return meta, default_collection, order

    if not meta:
        meta = {
            key: {**value, "uuids": set()}
            for key, value in DEFAULT_COLLECTION_META.items()
        }
        order = list(meta.keys())
    if default_collection not in meta:
        default_collection = order[0] if order else "favorites"
    if not order:
        order = list(meta.keys())
    return meta, default_collection, order


def _merge_dict(base: dict, overrides: dict) -> dict:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_site_config() -> dict:
    cfg_path = config.SITE_CONFIG_PATH
    site = dict(DEFAULT_SITE_CONFIG)
    if not cfg_path.exists():
        return site
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            site = _merge_dict(site, raw)
    except Exception:
        return site
    site_url = str(site.get("site_url") or "").rstrip("/")
    site["site_url"] = site_url
    return site


def classify_orientation(width: Optional[int], height: Optional[int]) -> str:
    if not width or not height:
        return "unknown"
    if width / height >= 1.1:
        return "landscape"
    if height / width >= 1.1:
        return "portrait"
    return "square"


def size_bucket(width: Optional[int], height: Optional[int]) -> str:
    if not width or not height:
        return "unknown"
    pixels = width * height
    if pixels >= 12_000_000:
        return "ultra"
    if pixels >= 6_000_000:
        return "large"
    if pixels >= 3_000_000:
        return "medium"
    return "compact"


def simple_title(name: str) -> str:
    return Path(name).stem or name


def human_bytes(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num < 1024:
            return f"{num:.1f}{unit}" if unit != "B" else f"{num}B"
        num /= 1024
    return f"{num:.1f}TB"


def parse_tags(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if isinstance(data, list):
        return [str(tag) for tag in data if str(tag).strip()]
    return []


def tag_slug(tag: str) -> str:
    return quote(tag, safe="")


def build_site(images: Iterable[Mapping[str, object]]) -> Path:
    build_id = f"build_{int(time.time())}"
    staging_dir = config.WWW_STAGING / build_id
    staging_dir.mkdir(parents=True, exist_ok=True)
    static_version = int(time.time())

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["urlencode"] = lambda value: quote(str(value), safe="")

    site = load_site_config()
    site_name = site.get("site_name", "luozi_sama 的插画馆")
    site_description = site.get("site_description", "")
    site_url = site.get("site_url", "")

    collections_meta, default_collection, collection_order = load_collections_config()
    collections_ctx = {
        key: {
            "title": value["title"],
            "description": value["description"],
            "uuids": sorted(value["uuids"]),
            "count": 0,
        }
        for key, value in collections_meta.items()
    }

    images_ctx: List[dict] = []
    stats = {"total": 0, "collections": {}}
    for img in images:
        img_ctx = dict(img)
        thumb_path_value = img_ctx.get("thumb_path")
        img_ctx["thumb_filename"] = Path(thumb_path_value).name if thumb_path_value else f"{img['uuid']}.jpg"
        img_ctx["raw_filename"] = f"{img['uuid']}{img['ext']}"
        img_ctx["bytes_human"] = human_bytes(int(img["bytes"]))
        img_ctx["title"] = img_ctx.get("title_override") or simple_title(str(img["original_name"]))
        img_ctx["description"] = img_ctx.get("description") or ""
        img_ctx["tags"] = parse_tags(img_ctx.get("tags_json"))
        img_ctx["orientation"] = classify_orientation(
            int(img["width"]) if img["width"] else None,
            int(img["height"]) if img["height"] else None,
        )
        img_ctx["size_bucket"] = size_bucket(
            int(img["width"]) if img["width"] else None,
            int(img["height"]) if img["height"] else None,
        )

        collection_override = img_ctx.get("collection_override")
        collection = collection_override or default_collection
        if not collection_override:
            for key, meta in collections_meta.items():
                if img_ctx["uuid"] in meta.get("uuids", set()):
                    collection = key
                    break

        img_ctx["collection"] = collection
        stats["total"] += 1
        stats["collections"][collection] = stats["collections"].get(collection, 0) + 1
        if collection in collections_ctx:
            collections_ctx[collection]["count"] = stats["collections"][collection]
        images_ctx.append(img_ctx)

    collections_list = []
    for key in collection_order:
        info = collections_ctx.get(key)
        if not info:
            continue
        collections_list.append(
            {
                "slug": key,
                "title": info["title"],
                "description": info["description"],
                "count": info.get("count", 0),
            }
        )

    tag_counts: Dict[str, int] = {}
    tag_images: Dict[str, List[dict]] = {}
    for img in images_ctx:
        for tag in img.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
            tag_images.setdefault(tag, []).append(img)
    tags_list = [
        {"tag": tag, "slug": tag_slug(tag), "count": count}
        for tag, count in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))
    ]

    og_image = ""
    if images_ctx:
        thumb_name = images_ctx[0].get("thumb_filename") or ""
        if thumb_name:
            og_image = f"{site_url}/thumb/{thumb_name}" if site_url else f"/thumb/{thumb_name}"

    index_json_ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "ImageGallery",
            "name": site_name,
            "description": site_description,
            "url": f"{site_url}/" if site_url else "/",
        },
        ensure_ascii=False,
    )

    # 拷贝静态资源
    static_target = staging_dir / "static"
    if static_target.exists():
        shutil.rmtree(static_target)
    shutil.copytree(ASSET_DIR, static_target, dirs_exist_ok=True)

    data_dir = static_target / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    search_index = {
        "generated_at": int(time.time()),
        "images": [
            {
                "uuid": img["uuid"],
                "title": img["title"],
                "description": img.get("description", ""),
                "tags": img.get("tags", []),
                "collection": img.get("collection"),
                "created_at": img.get("created_at"),
                "thumb_filename": img.get("thumb_filename"),
                "raw_filename": img.get("raw_filename"),
                "width": img.get("width"),
                "height": img.get("height"),
                "thumb_width": img.get("thumb_width"),
                "thumb_height": img.get("thumb_height"),
                "bytes": img.get("bytes"),
                "bytes_human": img.get("bytes_human"),
                "orientation": img.get("orientation"),
                "size_bucket": img.get("size_bucket"),
                "dominant_color": img.get("dominant_color"),
            }
            for img in images_ctx
        ],
        "tags": tags_list,
        "collections": collections_list,
    }
    (data_dir / "search_index.json").write_text(
        json.dumps(search_index, ensure_ascii=False), encoding="utf-8"
    )

    index_html = env.get_template("index.html.j2").render(
        images=images_ctx,
        stats=stats,
        collections=collections_ctx,
        collections_list=collections_list,
        tags=tags_list,
        site=site,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        og_image=og_image,
        json_ld=index_json_ld,
        static_version=static_version,
    )
    (staging_dir / "index.html").write_text(index_html, encoding="utf-8")

    flow_html = env.get_template("flow.html.j2").render(
        site=site,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        static_version=static_version,
    )
    (staging_dir / "flow.html").write_text(flow_html, encoding="utf-8")

    search_dir = staging_dir / "search"
    search_dir.mkdir(parents=True, exist_ok=True)
    search_html = env.get_template("search.html.j2").render(
        site=site,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        collections_list=collections_list,
        tags=tags_list,
        static_version=static_version,
    )
    (search_dir / "index.html").write_text(search_html, encoding="utf-8")

    tags_dir = staging_dir / "tags"
    tags_dir.mkdir(parents=True, exist_ok=True)
    tags_index_html = env.get_template("tags.html.j2").render(
        site=site,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        tags=tags_list,
        static_version=static_version,
    )
    (tags_dir / "index.html").write_text(tags_index_html, encoding="utf-8")
    tag_tpl = env.get_template("tag.html.j2")
    for tag in tags_list:
        tag_dir = tags_dir / tag["slug"]
        tag_dir.mkdir(parents=True, exist_ok=True)
        tag_html = tag_tpl.render(
            site=site,
            site_name=site_name,
            site_description=site_description,
            site_url=site_url,
            tag=tag,
            images=tag_images.get(tag["tag"], []),
            collections=collections_ctx,
            collections_list=collections_list,
            static_version=static_version,
        )
        (tag_dir / "index.html").write_text(tag_html, encoding="utf-8")

    admin_dir = staging_dir / "admin"
    admin_dir.mkdir(parents=True, exist_ok=True)
    admin_html = env.get_template("admin.html.j2").render(
        site=site,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        collections_list=collections_list,
        static_version=static_version,
    )
    (admin_dir / "index.html").write_text(admin_html, encoding="utf-8")

    admin_tags_dir = admin_dir / "tags"
    admin_tags_dir.mkdir(parents=True, exist_ok=True)
    admin_tags_html = env.get_template("admin_tags.html.j2").render(
        site=site,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        static_version=static_version,
    )
    (admin_tags_dir / "index.html").write_text(admin_tags_html, encoding="utf-8")

    # 直接拷贝静态根页（例如 wall.html），方便非模板页随发布同步
    wall_src = ASSET_DIR / "wall.html"
    if wall_src.exists():
        shutil.copy2(wall_src, staging_dir / "wall.html")

    detail_tpl = env.get_template("detail.html.j2")
    images_dir = staging_dir / "images"
    images_dir.mkdir(exist_ok=True)
    for img in images_ctx:
        detail_url = f"{site_url}/images/{img['uuid']}/index.html" if site_url else ""
        image_url = f"{site_url}/raw/{img['raw_filename']}" if site_url else f"/raw/{img['raw_filename']}"
        detail_json_ld = json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "ImageObject",
                "name": img.get("title"),
                "description": img.get("original_name"),
                "contentUrl": image_url,
                "thumbnailUrl": f"{site_url}/thumb/{img['thumb_filename']}" if site_url else f"/thumb/{img['thumb_filename']}",
                "width": img.get("width"),
                "height": img.get("height"),
            },
            ensure_ascii=False,
        )
        page_dir = images_dir / img["uuid"]
        page_dir.mkdir(parents=True, exist_ok=True)
        html = detail_tpl.render(
            image=img,
            site=site,
            site_name=site_name,
            site_description=site_description,
            site_url=site_url,
            canonical_url=detail_url,
            image_url=image_url,
            json_ld=detail_json_ld,
            collections=collections_ctx,
            static_version=static_version,
        )
        (page_dir / "index.html").write_text(html, encoding="utf-8")

    status_html = env.get_template("status.html.j2").render(
        site=site,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        static_version=static_version,
    )
    status_path = staging_dir / "status.html"
    status_path.write_text(status_html, encoding="utf-8")
    status_dir = staging_dir / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    (status_dir / "index.html").write_text(status_html, encoding="utf-8")

    for name, target in [
        ("404.html.j2", staging_dir / "404.html"),
        ("maintenance.html.j2", staging_dir / "maintenance.html"),
    ]:
        html = env.get_template(name).render(
            site=site,
            site_name=site_name,
            site_description=site_description,
            site_url=site_url,
            static_version=static_version,
        )
        target.write_text(html, encoding="utf-8")

    for name, subdir in [
        ("error.html.j2", staging_dir / "error"),
        ("legal.html.j2", staging_dir / "legal"),
    ]:
        subdir.mkdir(parents=True, exist_ok=True)
        html = env.get_template(name).render(
            site=site,
            site_name=site_name,
            site_description=site_description,
            site_url=site_url,
            static_version=static_version,
        )
        (subdir / "index.html").write_text(html, encoding="utf-8")

    urls = [
        {"loc": f"{site_url}/" if site_url else "/"},
        {"loc": f"{site_url}/wall.html" if site_url else "/wall.html"},
        {"loc": f"{site_url}/flow.html" if site_url else "/flow.html"},
        {"loc": f"{site_url}/search/" if site_url else "/search/"},
        {"loc": f"{site_url}/tags/" if site_url else "/tags/"},
        {"loc": f"{site_url}/status/" if site_url else "/status/"},
    ]
    for tag in tags_list:
        tag_loc = f"{site_url}/tags/{tag['slug']}/" if site_url else f"/tags/{tag['slug']}/"
        urls.append({"loc": tag_loc})
    for img in images_ctx:
        loc = f"{site_url}/images/{img['uuid']}/index.html" if site_url else f"/images/{img['uuid']}/index.html"
        lastmod = str(img.get("created_at") or "")
        urls.append({"loc": loc, "lastmod": lastmod})

    sitemap = env.get_template("sitemap.xml.j2").render(urls=urls)
    (staging_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    robots = env.get_template("robots.txt.j2").render(site_url=site_url)
    (staging_dir / "robots.txt").write_text(robots, encoding="utf-8")

    fsync_path(staging_dir)
    fsync_path(staging_dir.parent)
    return staging_dir


def _set_world_readable(path: Path) -> None:
    """
    确保发布目录对 www-data 可读，防止权限导致 403。
    """
    for p in path.rglob("*"):
        try:
            if p.is_dir():
                os.chmod(p, 0o755)
            else:
                os.chmod(p, 0o644)
        except PermissionError:
            continue
    try:
        os.chmod(path, 0o755)
    except PermissionError:
        pass


def ensure_www_readable() -> None:
    """
    修复已发布目录的权限，避免静态资源偶发 403。
    """
    for base in [config.STORAGE, config.WWW_DIR, config.WWW_DIR / "static"]:
        if base.exists():
            try:
                os.chmod(base, 0o755)
            except PermissionError:
                pass
    if config.WWW_DIR.exists():
        _set_world_readable(config.WWW_DIR)


def publish(staging_dir: Path) -> None:
    target = config.WWW_DIR
    tmp_old = target.parent / f"www_old_{int(time.time())}"
    _set_world_readable(staging_dir)
    if target.exists():
        os.replace(target, tmp_old)
    os.replace(staging_dir, target)
    _set_world_readable(target)
    fsync_path(target.parent)
    if tmp_old.exists():
        shutil.rmtree(tmp_old, ignore_errors=True)
