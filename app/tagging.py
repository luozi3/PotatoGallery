import json
import re
from pathlib import Path
from urllib.parse import unquote
from typing import Dict, List, Optional, Tuple

from . import config

TAG_CONFIG_PATH = config.STATIC / "data" / "tags.json"
SLUG_RE = re.compile(r"^[a-z0-9_-]+$")
TAG_TYPE_RE = re.compile(r"^[a-z0-9_-]+$")
TAG_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
DEFAULT_TAG_TYPES = [
    {"type": "artist", "label": "画师", "color": "#f97316"},
    {"type": "character", "label": "角色", "color": "#8b5cf6"},
    {"type": "general", "label": "普通", "color": "#7b8794"},
]


def default_tag_type(tag_types_meta: Dict[str, dict], tag_types_order: List[str]) -> str:
    if "general" in tag_types_meta:
        return "general"
    if tag_types_order:
        return tag_types_order[0]
    return "general"


def _decode_percent(text: str) -> str:
    value = str(text)
    for _ in range(3):
        if "%25" in value:
            value = value.replace("%25", "%")
        if "%" not in value:
            break
        decoded = unquote(value)
        if decoded == value:
            break
        value = decoded
    return value


def normalize_tag(tag: str) -> str:
    cleaned = _decode_percent(str(tag))
    cleaned = " ".join(cleaned.strip().split())
    return cleaned.casefold()


def safe_tag_slug(tag: str) -> str:
    slug = normalize_tag(tag or "")
    slug = slug.replace("/", "-").replace("\\", "-")
    slug = slug.strip()
    return slug or "tag"


def normalize_slug(raw: object) -> str:
    slug = str(raw or "").strip().lower()
    return slug


def is_valid_slug(slug: str) -> bool:
    return bool(slug) and SLUG_RE.match(slug) is not None


def normalize_tag_type(raw: object, allowed_types: Optional[set] = None) -> str:
    value = str(raw or "").strip().lower()
    if not value:
        return ""
    if allowed_types is None:
        allowed_types = set(load_tag_types_config()[0].keys())
    return value if value in allowed_types else ""


def normalize_tag_type_key(raw: object) -> str:
    value = str(raw or "").strip().lower()
    if not value:
        return ""
    return value if TAG_TYPE_RE.match(value) else ""


def normalize_tag_color(raw: object) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if not value.startswith("#"):
        value = f"#{value}"
    if not TAG_COLOR_RE.match(value):
        return ""
    if len(value) == 4:
        value = "#" + "".join([ch * 2 for ch in value[1:]])
    return value.lower()


def _load_tags_config_raw() -> dict:
    if not TAG_CONFIG_PATH.exists():
        return {}
    try:
        raw = json.loads(TAG_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _default_tag_types() -> List[dict]:
    return [dict(item) for item in DEFAULT_TAG_TYPES]


def load_tag_types_config() -> Tuple[Dict[str, dict], List[str]]:
    raw = _load_tags_config_raw()
    items = raw.get("types")
    if not isinstance(items, list):
        items = []
    defaults = {item["type"]: item for item in DEFAULT_TAG_TYPES}
    meta: Dict[str, dict] = {}
    order: List[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        tag_type = normalize_tag_type_key(item.get("type") or "")
        if not tag_type or tag_type in meta:
            continue
        label = str(item.get("label") or item.get("name") or "").strip() or tag_type
        color = normalize_tag_color(item.get("color"))
        if not color:
            color = (defaults.get(tag_type) or {}).get("color") or "#7b8794"
        meta[tag_type] = {
            "type": tag_type,
            "label": label,
            "color": color,
        }
        order.append(tag_type)
    if not meta:
        meta = {item["type"]: dict(item) for item in _default_tag_types()}
        order = [item["type"] for item in DEFAULT_TAG_TYPES]
    return meta, order


def _serialize_tag_types(meta: Dict[str, dict], order: Optional[List[str]] = None) -> List[dict]:
    types: List[dict] = []
    seen: set = set()
    ordered = (order or []) + sorted(meta.keys())
    for tag_type in ordered:
        if tag_type in seen:
            continue
        info = meta.get(tag_type)
        if not info:
            continue
        label = str(info.get("label") or "").strip() or tag_type
        color = normalize_tag_color(info.get("color")) or "#7b8794"
        types.append({"type": tag_type, "label": label, "color": color})
        seen.add(tag_type)
    return types


def normalize_aliases(raw: object) -> List[str]:
    values: List[str] = []
    if raw is None:
        return []
    if isinstance(raw, str):
        values = [v for v in re.split(r"[,\n\r\t|]+", raw) if v.strip()]
    elif isinstance(raw, list):
        values = [str(v) for v in raw if str(v).strip()]
    else:
        return []

    aliases: List[str] = []
    for item in values:
        item = item.strip()
        if not item:
            continue
        if item.startswith("#"):
            item = item[1:]
        normalized = normalize_tag(item)
        if not normalized:
            continue
        if normalized not in aliases:
            aliases.append(normalized)
    return aliases


def normalize_parents(raw: object) -> List[str]:
    values: List[str] = []
    if raw is None:
        return []
    if isinstance(raw, str):
        values = [v for v in re.split(r"[,\n\r\t|]+", raw) if v.strip()]
    elif isinstance(raw, list):
        values = [str(v) for v in raw if str(v).strip()]
    else:
        return []

    parents: List[str] = []
    for item in values:
        item = item.strip()
        if not item:
            continue
        if item.startswith("#"):
            item = item[1:]
        normalized = normalize_tag(item)
        if not normalized:
            continue
        if normalized not in parents:
            parents.append(normalized)
    return parents


def load_tags_config() -> Tuple[Dict[str, dict], List[str]]:
    raw = _load_tags_config_raw()
    items = raw.get("tags") or []
    if not isinstance(items, list):
        return {}, []

    tag_types_meta, tag_types_order = load_tag_types_config()
    allowed_types = set(tag_types_meta.keys())
    default_type = default_tag_type(tag_types_meta, tag_types_order)

    meta: Dict[str, dict] = {}
    order: List[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        tag = normalize_tag(item.get("tag") or "")
        if not tag or tag in meta:
            continue
        intro = str(item.get("intro") or "").strip()
        aliases = normalize_aliases(item.get("aliases"))
        parents = normalize_parents(item.get("parents"))
        slug_raw = normalize_slug(item.get("slug") or "")
        slug = slug_raw if is_valid_slug(slug_raw) else safe_tag_slug(tag)
        alias_to = normalize_tag(item.get("alias_to") or "")
        tag_type = normalize_tag_type(item.get("type"), allowed_types) or default_type
        if alias_to == tag:
            alias_to = ""
        if alias_to:
            parents = []
        meta[tag] = {
            "tag": tag,
            "intro": intro,
            "aliases": aliases,
            "parents": parents,
            "slug": slug,
            "alias_to": alias_to,
            "type": tag_type,
        }
        order.append(tag)
    return meta, order


def _serialize_tags(
    meta: Dict[str, dict],
    order: Optional[List[str]] = None,
    allowed_types: Optional[set] = None,
    default_type: Optional[str] = None,
) -> List[dict]:
    tags: List[dict] = []
    seen: set = set()
    ordered = (order or []) + sorted(meta.keys())
    if allowed_types is None or default_type is None:
        tag_types_meta, tag_types_order = load_tag_types_config()
        allowed_types = set(tag_types_meta.keys())
        default_type = default_tag_type(tag_types_meta, tag_types_order)
    for tag in ordered:
        if tag in seen:
            continue
        info = meta.get(tag)
        if not info:
            continue
        slug_raw = normalize_slug(info.get("slug") or "")
        slug = slug_raw if is_valid_slug(slug_raw) else safe_tag_slug(tag)
        tag_type = normalize_tag_type(info.get("type"), allowed_types) or default_type
        tags.append(
            {
                "tag": info.get("tag") or tag,
                "intro": info.get("intro") or "",
                "aliases": info.get("aliases") or [],
                "parents": info.get("parents") or [],
                "slug": slug,
                "alias_to": info.get("alias_to") or "",
                "type": tag_type,
            }
        )
        seen.add(tag)
    return tags


def save_tags_config(meta: Dict[str, dict], order: Optional[List[str]] = None) -> None:
    tag_types_meta, tag_types_order = load_tag_types_config()
    data = {
        "types": _serialize_tag_types(tag_types_meta, tag_types_order),
        "tags": _serialize_tags(
            meta,
            order,
            allowed_types=set(tag_types_meta.keys()),
            default_type=default_tag_type(tag_types_meta, tag_types_order),
        ),
    }
    TAG_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = TAG_CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(TAG_CONFIG_PATH)


def save_tag_types_config(types: List[dict]) -> None:
    meta, order = normalize_tag_types_payload(types)
    tags_meta, tags_order = load_tags_config()
    data = {
        "types": _serialize_tag_types(meta, order),
        "tags": _serialize_tags(
            tags_meta,
            tags_order,
            allowed_types=set(meta.keys()),
            default_type=default_tag_type(meta, order or []),
        ),
    }
    TAG_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = TAG_CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(TAG_CONFIG_PATH)


def normalize_tag_types_payload(types: object) -> Tuple[Dict[str, dict], List[str]]:
    items = types if isinstance(types, list) else []
    meta: Dict[str, dict] = {}
    order: List[str] = []
    defaults = {item["type"]: item for item in DEFAULT_TAG_TYPES}
    for item in items:
        if not isinstance(item, dict):
            continue
        tag_type = normalize_tag_type_key(item.get("type") or "")
        if not tag_type or tag_type in meta:
            continue
        label = str(item.get("label") or item.get("name") or "").strip()
        if not label:
            continue
        color = normalize_tag_color(item.get("color"))
        if not color:
            color = (defaults.get(tag_type) or {}).get("color") or "#7b8794"
        meta[tag_type] = {"type": tag_type, "label": label, "color": color}
        order.append(tag_type)
    return meta, order


def build_alias_map(meta: Dict[str, dict]) -> Dict[str, str]:
    alias_map: Dict[str, str] = {}
    for tag, info in meta.items():
        canonical = normalize_tag(info.get("alias_to") or "") or tag
        alias_map[tag] = canonical
        for alias in info.get("aliases") or []:
            normalized = normalize_tag(alias)
            if normalized:
                alias_map[normalized] = canonical
    return alias_map


def build_parent_map(
    meta: Dict[str, dict],
    alias_map: Optional[Dict[str, str]] = None,
) -> Dict[str, List[str]]:
    alias_map = alias_map or build_alias_map(meta)
    parents: Dict[str, List[str]] = {}
    for tag, info in meta.items():
        if info.get("alias_to"):
            continue
        raw_parents = info.get("parents") or []
        resolved: List[str] = []
        for parent in raw_parents:
            normalized = normalize_tag(parent)
            canonical = alias_map.get(normalized) or normalized
            if not canonical or canonical == tag:
                continue
            if canonical not in resolved:
                resolved.append(canonical)
        parents[tag] = resolved
    return parents


def find_parent_cycles(parent_map: Dict[str, List[str]]) -> List[str]:
    visiting: set = set()
    visited: set = set()
    cycle: List[str] = []

    def visit(node: str, stack: List[str]) -> bool:
        if node in visiting:
            cycle.extend(stack[stack.index(node) :])
            return True
        if node in visited:
            return False
        visiting.add(node)
        stack.append(node)
        for parent in parent_map.get(node, []):
            if visit(parent, stack):
                return True
        visiting.remove(node)
        visited.add(node)
        stack.pop()
        return False

    for tag in parent_map:
        if visit(tag, []):
            break
    return cycle


def missing_parent_tags(
    tags: List[str], parent_map: Dict[str, List[str]]
) -> List[str]:
    missing: List[str] = []
    tag_set = set(tags)
    for tag in tags:
        for parent in parent_map.get(tag, []):
            if parent not in tag_set and parent not in missing:
                missing.append(parent)
    return missing


def apply_alias_map(
    tags: List[str],
    alias_map: Optional[Dict[str, str]] = None,
    *,
    drop_unknown: bool = False,
) -> List[str]:
    if not alias_map:
        return [] if drop_unknown else list(dict.fromkeys(tags))
    resolved: List[str] = []
    for tag in tags:
        normalized = normalize_tag(tag)
        canonical = alias_map.get(normalized)
        if not canonical:
            if drop_unknown:
                continue
            canonical = normalized
        if canonical and canonical not in resolved:
            resolved.append(canonical)
    return resolved


def parse_tags_input(
    raw: object,
    alias_map: Optional[Dict[str, str]] = None,
    *,
    require_known: bool = False,
    require_hash: bool = False,
) -> Tuple[Optional[List[str]], Optional[str]]:
    if raw is None:
        return [], None
    values: List[str] = []
    if isinstance(raw, str):
        raw_text = raw.strip()
        if not raw_text:
            return [], None
        if "#" in raw_text:
            chunks = raw_text.replace(",", " ").split("#")
            values = [v for v in (chunk.strip() for chunk in chunks) if v]
        else:
            if require_hash:
                return None, "标签必须以 # 开头"
            values = [v for v in re.split(r"[,\s|]+", raw_text) if v]
    elif isinstance(raw, list):
        values = [str(v) for v in raw if str(v).strip()]
    else:
        return None, "标签格式不正确"

    tags: List[str] = []
    for item in values:
        item = item.strip()
        if not item:
            continue
        if item.startswith("#"):
            name = item[1:].strip()
        else:
            if isinstance(raw, list) and require_hash:
                return None, "标签必须以 # 开头"
            name = item
        if not name:
            continue
        normalized = normalize_tag(name)
        if normalized not in tags:
            tags.append(normalized)

    if require_known:
        if not alias_map:
            return None, "标签尚未注册"
        unknown = [tag for tag in tags if normalize_tag(tag) not in alias_map]
        if unknown:
            return None, f"未注册标签: {unknown[0]}"

    tags = apply_alias_map(tags, alias_map, drop_unknown=require_known)
    return tags, None


def parse_tags_json(
    raw: Optional[str],
    alias_map: Optional[Dict[str, str]] = None,
    *,
    drop_unknown: bool = False,
) -> List[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if isinstance(data, list):
        normalized = [normalize_tag(tag) for tag in data if normalize_tag(tag)]
        return apply_alias_map(normalized, alias_map, drop_unknown=drop_unknown)
    return []
