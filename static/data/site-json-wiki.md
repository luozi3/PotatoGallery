# site.json / site.local.json 配置说明

> 适用于 `/opt/PotatoGallery/static/data/site.json` 与 `/opt/PotatoGallery/static/data/site.local.json`。
> 用于说明字段含义、引用位置与支持的用法。

## 位置与优先级

- 默认配置：`/opt/PotatoGallery/static/data/site.json`
- 本地覆盖：`/opt/PotatoGallery/static/data/site.local.json`（优先级更高，不参与 git push）
- 读取路径：`/opt/PotatoGallery/app/config.py`（`SITE_CONFIG_PATH` / `SITE_CONFIG_LOCAL_PATH`）
- 合并逻辑：`/opt/PotatoGallery/app/static_site.py` → `load_site_config()`
  - 先读 `site.json` 再读 `site.local.json`，深度合并字典，后者覆盖前者。
  - `site_url` 会自动去掉末尾 `/`。
  - `seo.default_og_image` 以 `/` 开头且 `site_url` 已设置时，会自动补成绝对 URL。

## 修改与生效

1) 修改 `site.local.json`（推荐，避免提交）
2) 执行 `/opt/PotatoGallery/bin/refresh_static.sh` 重新生成静态站点

## 字段说明（含引用位置与用法）

### 基础信息

- `site_name`（字符串）：站点主标题。
  - 引用：`static/templates/index.html.j2`、`static/templates/detail.html.j2`、`static/templates/tag.html.j2` 等标题/OG；`static/templates/partials/topbar.html.j2` 顶栏品牌；`app/static_site.py` 生成 JSON-LD。
  - 用法：任意字符串；为空时会回退到默认值。
- `site_description`（字符串）：页面描述与 OG 描述。
  - 引用：`static/templates/index.html.j2`、`static/templates/search.html.j2`、`static/templates/tags.html.j2`、`static/templates/status.html.j2` 等；`app/static_site.py` JSON-LD。
  - 用法：建议 60-120 字符左右的站点简介。
- `site_url`（字符串）：站点基础 URL。
  - 引用：`app/static_site.py`（生成 `sitemap.xml`/`robots.txt`/JSON-LD），`static/templates/*.j2`（canonical 与 og:url），`static/templates/pages/dmca.html.j2`（表单占位）。
  - 用法：`https://example.com`（不要带末尾 `/`）；为空时会使用相对 URL。

### SEO

- `seo.title_separator`（字符串）：标题分隔符。
  - 引用：`static/templates/*.j2` 标题与 OG title（如 `index.html.j2`、`detail.html.j2`、`tag.html.j2`）。
  - 用法：`"｜"`、`"|"` 等。
- `seo.twitter_card`（字符串）：Twitter 卡片类型。
  - 引用：`static/templates/index.html.j2`、`detail.html.j2`、`tag.html.j2`、`tags.html.j2`、`search.html.j2`、`status.html.j2`。
  - 用法：`summary` 或 `summary_large_image`。
- `seo.default_og_image`（字符串）：OG 图片兜底。
  - 引用：`static/templates/index.html.j2`、`detail.html.j2`、`tag.html.j2`、`tags.html.j2`、`search.html.j2`、`status.html.j2`。
  - 用法：可填绝对 URL 或站内路径（如 `/static/images/og.png`）；若是站内路径且 `site_url` 设置了，会自动变成绝对 URL。

### 品牌与版权

- `brand_name`（字符串）：顶栏品牌名。
  - 引用：`static/templates/partials/topbar.html.j2`。
  - 用法：留空时会自动回退为 `site_name`。
- `brand_tagline`（字符串）：品牌副标题。
  - 引用：`static/templates/partials/topbar.html.j2`、`static/templates/index.html.j2`（首页标题后缀）。
  - 用法：简短英文或定位语。
- `copyright_year`（数字）：版权年份。
  - 引用：`static/templates/partials/sidebar_default.html.j2`。
  - 用法：留空或非法值会自动回退为当前年份。
- `copyright_holder`（字符串）：版权主体。
  - 引用：`static/templates/partials/sidebar_default.html.j2`。
  - 用法：留空时会回退 `brand_name` 或 `site_name`。

### 主题与语言

- `theme_color`（字符串）：`<meta name="theme-color">` 使用的主题色。
  - 引用：`static/templates/*.j2`。
  - 用法：任意 CSS 颜色值，如 `#4c7cff`。
- `locale`（字符串）：OG 语言区域。
  - 引用：`static/templates/index.html.j2`、`detail.html.j2`、`tag.html.j2`、`tags.html.j2`、`search.html.j2`、`status.html.j2`。
  - 用法：`zh_CN`、`en_US` 等。

### Live2D

- `live2d.enabled`（布尔）：是否启用 Live2D。
  - 引用：`static/templates/index.html.j2`、`detail.html.j2`、`auth_login.html.j2`、`auth_register.html.j2`、`partials/sidebar_default.html.j2`。
  - 用法：`true/false`。
- `live2d.base_url`（字符串）：Live2D 资源根路径。
  - 引用：`static/templates/index.html.j2`、`detail.html.j2`、`auth_login.html.j2`、`auth_register.html.j2`。
  - 用法：如 `/static/live2d`。
- `live2d.model`（字符串）：模型 JSON 路径。
  - 引用：`static/templates/index.html.j2`、`detail.html.j2`（初始化脚本）。
  - 用法：如 `/static/live2d/assets/Pio/Pio.model.json`。
- `live2d.canvas_id`（字符串）：Canvas ID。
  - 引用：`static/templates/index.html.j2`、`detail.html.j2`。
  - 用法：保持唯一，如 `live2dcanvas`。
- `live2d.width` / `live2d.height`（数字）：Canvas 尺寸。
  - 引用：`static/templates/index.html.j2`、`detail.html.j2`。
  - 用法：整数像素，未设置则使用默认 `300x336`。

### 访问计数器

- `counter.enabled`（布尔）：是否展示访问统计图。
  - 引用：`static/templates/index.html.j2`、`detail.html.j2`。
  - 用法：`true/false`。
- `counter.img_url`（字符串）：统计图地址。
  - 引用：`static/templates/index.html.j2`、`detail.html.j2`。
  - 用法：可用站内或第三方 URL。

### 头像与收藏图标

- `auth_avatar_url`（字符串）：默认头像地址。
  - 引用：`static/templates/partials/topbar.html.j2`、`static/templates/pages/profile.html.j2`。
  - 用法：站内 `/thumb/...` 或绝对 URL。
- `favorites_icon_url`（字符串）：收藏页标题图标。
  - 引用：`static/templates/pages/favorites.html.j2`。
  - 用法：为空则不展示图标。

### 预留字段

- `thumb_bg_color`（字符串）：缩略图背景色。
  - 引用：当前模板未使用（预留字段）。
  - 用法：任意 CSS 颜色值，未来可用于卡片/缩略图背景。

## 示例（最小覆盖）

```json
{
  "site_url": "https://example.com",
  "site_name": "luozi_sama 的展馆",
  "seo": {
    "title_separator": "｜",
    "twitter_card": "summary_large_image",
    "default_og_image": "/static/images/og.png"
  },
  "live2d": {
    "enabled": true
  }
}
```
