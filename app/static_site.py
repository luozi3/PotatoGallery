import json
import os
import shutil
import time
from urllib.parse import quote
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config
from . import tagging
from .storage import fsync_path

TEMPLATE_DIR = config.STATIC / "templates"
ASSET_DIR = config.STATIC
PAGES_TEMPLATE_DIR = TEMPLATE_DIR / "pages"
PAGES_STATIC_DIR = ASSET_DIR / "pages"
RESERVED_PAGE_PREFIXES = {
    "api",
    "admin",
    "auth",
    "error",
    "images",
    "legal",
    "raw",
    "search",
    "static",
    "status",
    "tags",
    "thumb",
    "upload",
}
RESERVED_PAGE_FILES = {
    "404.html",
    "index.html",
    "maintenance.html",
    "robots.txt",
    "sitemap.xml",
    "status.html",
}
DEFAULT_COLLECTION_META = {
    "mine": {
        "title": "我的作品",
        "description": "站点原创插画与练习稿，持续更新与打磨。",
    },
    "favorites": {
        "title": "他人作品",
        "description": "精挑细选的二次元插画，展示收藏的画风。",
    },
}
DEFAULT_SITE_CONFIG = {
    "site_name": "PotatoGallery 插画馆",
    "site_description": "静态插画展示站点，包含原创与精选收藏。",
    "site_url": "",
    "theme_color": "#4c7cff",
    "locale": "zh_CN",
    "brand_name": "",
    "brand_tagline": "Illustration Gallery",
    "copyright_year": None,
    "copyright_holder": "",
    "live2d": {
        "enabled": False,
        "base_url": "/static/live2d",
        "model": "/static/live2d/assets/Pio/Pio.model.json",
        "canvas_id": "live2dcanvas",
        "width": 300,
        "height": 336,
    },
    "counter": {"enabled": False, "img_url": ""},
    "auth_avatar_url": "/thumb/39e2f18e62ab45f5aa871860919516d0.webp",
    "thumb_bg_color": "#f3e7ff",
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


def _read_json_dict(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(raw, dict):
        return raw
    return None


def load_site_config() -> dict:
    site = dict(DEFAULT_SITE_CONFIG)
    for cfg_path in (config.SITE_CONFIG_PATH, config.SITE_CONFIG_LOCAL_PATH):
        raw = _read_json_dict(cfg_path)
        if raw:
            site = _merge_dict(site, raw)
    site_url = str(site.get("site_url") or "").rstrip("/")
    site["site_url"] = site_url
    if not site.get("brand_name"):
        site["brand_name"] = site.get("site_name") or ""
    if not site.get("copyright_holder"):
        site["copyright_holder"] = site.get("brand_name") or site.get("site_name") or ""
    current_year = time.gmtime().tm_year
    try:
        year_value = site.get("copyright_year")
        if year_value in (None, ""):
            raise ValueError
        site["copyright_year"] = int(year_value)
    except (TypeError, ValueError):
        site["copyright_year"] = current_year
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


def parse_tags(raw: Optional[str], alias_map: Optional[Dict[str, str]] = None) -> List[str]:
    return tagging.parse_tags_json(raw, alias_map, drop_unknown=True)


def tag_slug(tag: str) -> str:
    return tagging.safe_tag_slug(tag)


def _strip_template_suffix(name: str) -> str:
    if name.endswith(".html.j2"):
        return name[:-8]
    if name.endswith(".j2"):
        return name[:-3]
    return Path(name).stem


def _ensure_extra_page_allowed(url_path: str, source: Path, seen: set) -> None:
    cleaned = url_path.lstrip("/")
    if not cleaned:
        raise ValueError(f"extra page path is empty: {source}")
    first = cleaned.split("/", 1)[0]
    if first in RESERVED_PAGE_PREFIXES:
        raise ValueError(f"extra page path {url_path} conflicts with reserved prefix: {source}")
    if cleaned in RESERVED_PAGE_FILES:
        raise ValueError(f"extra page path {url_path} conflicts with reserved file: {source}")
    if url_path in seen:
        raise ValueError(f"duplicate extra page path {url_path}: {source}")
    seen.add(url_path)


def _render_extra_pages(
    env: Environment,
    staging_dir: Path,
    context: Dict[str, object],
) -> List[str]:
    extra_urls: List[str] = []
    seen_urls: set = set()

    if PAGES_TEMPLATE_DIR.exists():
        for tpl_path in sorted(PAGES_TEMPLATE_DIR.rglob("*.html.j2")):
            rel = tpl_path.relative_to(PAGES_TEMPLATE_DIR)
            base_name = _strip_template_suffix(rel.name)
            if base_name == "index" and rel.parent == Path("."):
                continue
            if base_name == "index":
                target_dir = staging_dir.joinpath(*rel.parent.parts)
                url_parts = rel.parent.parts
            else:
                target_dir = staging_dir.joinpath(*rel.parent.parts, base_name)
                url_parts = (*rel.parent.parts, base_name)
            if not url_parts:
                continue
            url_path = "/" + "/".join(url_parts) + "/"
            _ensure_extra_page_allowed(url_path, tpl_path, seen_urls)
            target = target_dir / "index.html"
            if target.exists():
                raise ValueError(f"extra page output already exists: {target}")
            target_dir.mkdir(parents=True, exist_ok=True)
            template_name = str(tpl_path.relative_to(TEMPLATE_DIR))
            html = env.get_template(template_name).render(**context)
            target.write_text(html, encoding="utf-8")
            extra_urls.append(url_path)

    if PAGES_STATIC_DIR.exists():
        for src in sorted(PAGES_STATIC_DIR.rglob("*.html")):
            rel = src.relative_to(PAGES_STATIC_DIR)
            if rel.name.startswith("."):
                continue
            url_path = "/" + "/".join(rel.parts)
            _ensure_extra_page_allowed(url_path, src, seen_urls)
            target = staging_dir / rel
            if target.exists():
                raise ValueError(f"extra page output already exists: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            extra_urls.append(url_path)

    return extra_urls


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
    auth_config = dict(config.AUTH_CONFIG)
    auth_config["registration_mode"] = config.AUTH_REGISTRATION_MODE
    auth_config["require_https"] = config.AUTH_REQUIRE_HTTPS
    site_name = site.get("site_name", DEFAULT_SITE_CONFIG.get("site_name", "PotatoGallery 插画馆"))
    site_description = site.get("site_description", "")
    site_url = site.get("site_url", "")

    collections_meta, default_collection, collection_order = load_collections_config()
    tags_meta, tag_order = tagging.load_tags_config()
    alias_map = tagging.build_alias_map(tags_meta)
    parent_map = tagging.build_parent_map(tags_meta, alias_map)
    child_map: Dict[str, List[str]] = {}
    for tag, parents in parent_map.items():
        for parent in parents:
            child_map.setdefault(parent, []).append(tag)
    tag_slug_map = {
        tag: (info.get("slug") or tag_slug(tag))
        for tag, info in tags_meta.items()
        if not info.get("alias_to")
    }
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
        img_ctx["thumb_filename"] = (
            Path(thumb_path_value).name if thumb_path_value else f"{img['uuid']}{config.THUMB_EXT}"
        )
        img_ctx["raw_filename"] = f"{img['uuid']}{img['ext']}"
        img_ctx["bytes_human"] = human_bytes(int(img["bytes"]))
        img_ctx["title"] = img_ctx.get("title_override") or simple_title(str(img["original_name"]))
        img_ctx["description"] = img_ctx.get("description") or ""
        img_ctx["tags"] = parse_tags(img_ctx.get("tags_json"), alias_map)
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

    tag_images: Dict[str, List[dict]] = {}
    tag_seen: Dict[str, set] = {}

    def get_ancestors(tag: str, cache: Dict[str, List[str]]) -> List[str]:
        if tag in cache:
            return cache[tag]
        parents = parent_map.get(tag, [])
        ancestors: List[str] = []
        for parent in parents:
            if parent not in ancestors:
                ancestors.append(parent)
            for ancestor in get_ancestors(parent, cache):
                if ancestor not in ancestors:
                    ancestors.append(ancestor)
        cache[tag] = ancestors
        return ancestors

    ancestors_cache: Dict[str, List[str]] = {}
    for img in images_ctx:
        uu = img.get("uuid")
        for tag in img.get("tags", []):
            for resolved in [tag] + get_ancestors(tag, ancestors_cache):
                tag_seen.setdefault(resolved, set())
                if uu in tag_seen[resolved]:
                    continue
                tag_seen[resolved].add(uu)
                tag_images.setdefault(resolved, []).append(img)

    tag_counts: Dict[str, int] = {tag: len(items) for tag, items in tag_seen.items()}
    tags_list = []
    ordered_tags = (tag_order or []) + sorted(tags_meta.keys())
    seen_tags = set()
    for tag in ordered_tags:
        if tag in seen_tags:
            continue
        seen_tags.add(tag)
        meta = tags_meta.get(tag, {})
        if not meta or meta.get("alias_to"):
            continue
        slug = meta.get("slug") or tag_slug(tag)
        tags_list.append(
            {
                "tag": tag,
                "slug": slug,
                "count": tag_counts.get(tag, 0),
                "intro": meta.get("intro") or "",
                "aliases": meta.get("aliases") or [],
                "parents": parent_map.get(tag, []),
                "children": child_map.get(tag, []),
                "type": meta.get("type") or "general",
            }
        )
    top_tags = sorted(
        tags_list,
        key=lambda item: (-int(item.get("count") or 0), str(item.get("tag") or "")),
    )
    alias_pages = []
    seen_alias = set()
    for tag in ordered_tags:
        if tag in seen_alias:
            continue
        seen_alias.add(tag)
        meta = tags_meta.get(tag, {})
        if not meta:
            continue
        alias_to = tagging.normalize_tag(meta.get("alias_to") or "")
        if not alias_to:
            continue
        canonical_meta = tags_meta.get(alias_to)
        if not canonical_meta or canonical_meta.get("alias_to"):
            continue
        canonical_slug = canonical_meta.get("slug") or tag_slug(alias_to)
        alias_slug = meta.get("slug") or tag_slug(tag)
        if alias_slug == canonical_slug:
            continue
        alias_pages.append(
            {
                "tag": tag,
                "slug": alias_slug,
                "count": tag_counts.get(alias_to, 0),
                "intro": meta.get("intro") or "",
                "aliases": meta.get("aliases") or [],
                "alias_of": alias_to,
                "alias_of_slug": canonical_slug,
                "type": canonical_meta.get("type") or "general",
            }
        )

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
    tag_index_tags = []
    ordered_tags_all = (tag_order or []) + sorted(tags_meta.keys())
    seen_all: set = set()
    for tag in ordered_tags_all:
        if tag in seen_all:
            continue
        seen_all.add(tag)
        meta = tags_meta.get(tag) or {}
        alias_to = tagging.normalize_tag(meta.get("alias_to") or "")
        canonical = alias_to or tag
        canonical_meta = tags_meta.get(canonical) or {}
        canonical_slug = canonical_meta.get("slug") or tag_slug(canonical)
        tag_type = canonical_meta.get("type") or meta.get("type") or "general"
        tag_index_tags.append(
            {
                "tag": tag,
                "slug": meta.get("slug") or tag_slug(tag),
                "aliases": meta.get("aliases") or [],
                "parents": parent_map.get(tag, []) if not alias_to else [],
                "alias_of": alias_to,
                "alias_of_slug": canonical_slug if alias_to else "",
                "type": tag_type,
            }
        )
    tag_index = {
        "generated_at": int(time.time()),
        "tags": tag_index_tags,
    }
    (data_dir / "tag_index.json").write_text(
        json.dumps(tag_index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "version": 1,
        "chunked": False,
        "generated_at": int(time.time()),
        "chunks": [
            {
                "path": "search_index.json",
                "images": len(images_ctx),
                "tags": len(tags_list),
            }
        ],
    }
    (data_dir / "search_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    index_html = env.get_template("index.html.j2").render(
        images=images_ctx,
        stats=stats,
        collections=collections_ctx,
        collections_list=collections_list,
        tags=tags_list,
        top_tags=top_tags,
        site=site,
        auth=auth_config,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        og_image=og_image,
        json_ld=index_json_ld,
        tag_slug_map=tag_slug_map,
        static_version=static_version,
    )
    (staging_dir / "index.html").write_text(index_html, encoding="utf-8")

    search_dir = staging_dir / "search"
    search_dir.mkdir(parents=True, exist_ok=True)
    search_html = env.get_template("search.html.j2").render(
        site=site,
        auth=auth_config,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        collections_list=collections_list,
        tags=tags_list,
        tag_slug_map=tag_slug_map,
        static_version=static_version,
    )
    (search_dir / "index.html").write_text(search_html, encoding="utf-8")

    tags_dir = staging_dir / "tags"
    tags_dir.mkdir(parents=True, exist_ok=True)
    tags_index_html = env.get_template("tags.html.j2").render(
        site=site,
        auth=auth_config,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        tags=tags_list,
        tag_slug_map=tag_slug_map,
        static_version=static_version,
    )
    (tags_dir / "index.html").write_text(tags_index_html, encoding="utf-8")
    tag_tpl = env.get_template("tag.html.j2")
    for tag in tags_list:
        tag_dir = tags_dir / tag["slug"]
        tag_dir.mkdir(parents=True, exist_ok=True)
        tag_html = tag_tpl.render(
            site=site,
            auth=auth_config,
            site_name=site_name,
            site_description=site_description,
            site_url=site_url,
            tag=tag,
            images=tag_images.get(tag["tag"], []),
            collections=collections_ctx,
            collections_list=collections_list,
            tag_slug_map=tag_slug_map,
            static_version=static_version,
        )
        (tag_dir / "index.html").write_text(tag_html, encoding="utf-8")
    for alias in alias_pages:
        tag_dir = tags_dir / alias["slug"]
        tag_dir.mkdir(parents=True, exist_ok=True)
        tag_html = tag_tpl.render(
            site=site,
            auth=auth_config,
            site_name=site_name,
            site_description=site_description,
            site_url=site_url,
            tag=alias,
            images=tag_images.get(alias["alias_of"], []),
            collections=collections_ctx,
            collections_list=collections_list,
            tag_slug_map=tag_slug_map,
            static_version=static_version,
        )
        (tag_dir / "index.html").write_text(tag_html, encoding="utf-8")

    admin_dir = staging_dir / "admin"
    admin_dir.mkdir(parents=True, exist_ok=True)
    admin_html = env.get_template("admin.html.j2").render(
        site=site,
        auth=auth_config,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        collections_list=collections_list,
        static_version=static_version,
    )
    (admin_dir / "index.html").write_text(admin_html, encoding="utf-8")

    admin_images_dir = admin_dir / "images"
    admin_images_dir.mkdir(parents=True, exist_ok=True)
    admin_images_html = env.get_template("admin_images.html.j2").render(
        site=site,
        auth=auth_config,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        collections_list=collections_list,
        static_version=static_version,
    )
    (admin_images_dir / "index.html").write_text(admin_images_html, encoding="utf-8")

    admin_upload_dir = admin_dir / "upload"
    admin_upload_dir.mkdir(parents=True, exist_ok=True)
    admin_upload_html = env.get_template("admin_upload.html.j2").render(
        site=site,
        auth=auth_config,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        collections_list=collections_list,
        static_version=static_version,
    )
    (admin_upload_dir / "index.html").write_text(admin_upload_html, encoding="utf-8")

    admin_collections_dir = admin_dir / "collections"
    admin_collections_dir.mkdir(parents=True, exist_ok=True)
    admin_collections_html = env.get_template("admin_collections.html.j2").render(
        site=site,
        auth=auth_config,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        collections_list=collections_list,
        static_version=static_version,
    )
    (admin_collections_dir / "index.html").write_text(admin_collections_html, encoding="utf-8")

    admin_auth_dir = admin_dir / "auth"
    admin_auth_dir.mkdir(parents=True, exist_ok=True)
    admin_auth_html = env.get_template("admin_auth.html.j2").render(
        site=site,
        auth=auth_config,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        collections_list=collections_list,
        static_version=static_version,
    )
    (admin_auth_dir / "index.html").write_text(admin_auth_html, encoding="utf-8")

    admin_tags_dir = admin_dir / "tags"
    admin_tags_dir.mkdir(parents=True, exist_ok=True)
    admin_tags_html = env.get_template("admin_tags.html.j2").render(
        site=site,
        auth=auth_config,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        static_version=static_version,
    )

    auth_dir = staging_dir / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    login_dir = auth_dir / "login"
    login_dir.mkdir(parents=True, exist_ok=True)
    login_html = env.get_template("auth_login.html.j2").render(
        site=site,
        auth=auth_config,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        static_version=static_version,
    )
    (login_dir / "index.html").write_text(login_html, encoding="utf-8")

    register_dir = auth_dir / "register"
    register_dir.mkdir(parents=True, exist_ok=True)
    register_html = env.get_template("auth_register.html.j2").render(
        site=site,
        auth=auth_config,
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        static_version=static_version,
    )
    (register_dir / "index.html").write_text(register_html, encoding="utf-8")
    (admin_tags_dir / "index.html").write_text(admin_tags_html, encoding="utf-8")

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
            auth=auth_config,
            site_name=site_name,
            site_description=site_description,
            site_url=site_url,
            canonical_url=detail_url,
            image_url=image_url,
            json_ld=detail_json_ld,
            collections=collections_ctx,
            tag_slug_map=tag_slug_map,
            static_version=static_version,
        )
        (page_dir / "index.html").write_text(html, encoding="utf-8")

    status_html = env.get_template("status.html.j2").render(
        site=site,
        auth=auth_config,
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
            auth=auth_config,
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
            auth=auth_config,
            site_name=site_name,
            site_description=site_description,
            site_url=site_url,
            static_version=static_version,
        )
        (subdir / "index.html").write_text(html, encoding="utf-8")

    extra_urls = _render_extra_pages(
        env,
        staging_dir,
        {
            "site": site,
            "auth": auth_config,
            "site_name": site_name,
            "site_description": site_description,
            "site_url": site_url,
            "static_version": static_version,
            "tags": tags_list,
            "collections_list": collections_list,
            "collections": collections_ctx,
            "stats": stats,
        },
    )

    urls = [
        {"loc": f"{site_url}/" if site_url else "/"},
        {"loc": f"{site_url}/search/" if site_url else "/search/"},
        {"loc": f"{site_url}/tags/" if site_url else "/tags/"},
        {"loc": f"{site_url}/status/" if site_url else "/status/"},
    ]
    for path in extra_urls:
        urls.append({"loc": f"{site_url}{path}" if site_url else path})
    for tag in tags_list:
        tag_slug_value = quote(str(tag["slug"]), safe="")
        tag_loc = f"{site_url}/tags/{tag_slug_value}/" if site_url else f"/tags/{tag_slug_value}/"
        urls.append({"loc": tag_loc})
    for alias in alias_pages:
        alias_slug_value = quote(str(alias["slug"]), safe="")
        alias_loc = f"{site_url}/tags/{alias_slug_value}/" if site_url else f"/tags/{alias_slug_value}/"
        urls.append({"loc": alias_loc})
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
