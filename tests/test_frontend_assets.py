from pathlib import Path
import json
import re


BASE_DIR = Path(__file__).resolve().parents[1]


def read_text(rel_path: str) -> str:
    return (BASE_DIR / rel_path).read_text(encoding="utf-8")


def test_theme_toggle_after_brand():
    templates = [
        "static/templates/index.html.j2",
        "static/templates/detail.html.j2",
        "static/templates/search.html.j2",
        "static/templates/tags.html.j2",
        "static/templates/tag.html.j2",
        "static/templates/admin.html.j2",
        "static/templates/admin_tags.html.j2",
        "static/templates/pages/wiki.html.j2",
        "static/templates/pages/dmca.html.j2",
    ]
    for template in templates:
        content = read_text(template)
        brand_idx = content.find('class="brand')
        toggle_idx = content.find("data-theme-toggle")
        assert brand_idx != -1 and toggle_idx != -1, template
        assert brand_idx < toggle_idx, template


def test_controls_use_theme_panel_background():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.controls\s*\{[^}]*background:\s*linear-gradient\(180deg,\s*var\(--panel\),\s*var\(--panel-strong\)\)",
        css,
        re.S,
    )


def test_status_page_has_uptime_and_requests_cards():
    html = read_text("static/templates/status.html.j2")
    assert "page-status" in html
    assert "系统状态" in html
    assert "总览" in html
    assert 'id="uptime"' in html
    assert 'id="requests"' in html
    assert "服务器上次重启距今" in html
    assert "起始" not in html
    assert "status-raw" in html


def test_status_page_mobile_padding():
    html = read_text("static/templates/status.html.j2")
    assert re.search(
        r"@media \(max-width: 600px\)[\s\S]*?padding:\s*calc\(var\(--topbar-height\) \+ 18px\)\s+18px\s+40px;",
        html,
        re.S,
    )


def test_status_page_desktop_padding():
    html = read_text("static/templates/status.html.j2")
    assert "padding: calc(var(--topbar-height) + 32px) 80px 72px;" in html
    assert "padding: 12px 40px;" in html
    assert "justify-content: flex-start;" in html


def test_status_page_mobile_layout_overrides():
    html = read_text("static/templates/status.html.j2")
    assert re.search(
        r"@media \(max-width: 600px\)[\s\S]*--topbar-height:\s*calc\(44px\s*\+\s*env\(safe-area-inset-top\)\);",
        html,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 600px\)[\s\S]*min-height:\s*var\(--topbar-height\);",
        html,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 600px\)[\s\S]*padding:\s*calc\(6px\s*\+\s*env\(safe-area-inset-top\)\)\s+12px\s+6px;",
        html,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 600px\)[\s\S]*\.page-status\s+\.topbar-left[\s\S]*flex:\s*1 1 auto",
        html,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 600px\)[\s\S]*\.page-status\s+\.brand[\s\S]*margin-right:\s*auto",
        html,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 600px\)[\s\S]*status-grid[\s\S]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)",
        html,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 600px\)[\s\S]*status-meta-block[\s\S]*grid-template-columns:\s*repeat\(3, minmax\(0, 1fr\)\)",
        html,
        re.S,
    )


def test_error_pages_include_ui_js():
    templates = [
        "static/templates/404.html.j2",
        "static/templates/error.html.j2",
        "static/templates/maintenance.html.j2",
    ]
    for template in templates:
        html = read_text(template)
        assert '/static/js/ui.js?v={{ static_version }}' in html


def test_admin_tags_page_has_layout_class():
    html = read_text("static/templates/admin_tags.html.j2")
    assert "page-admin-tags" in html
    assert "tag-admin-guide" in html


def test_admin_tags_layout_structure_present():
    js = read_text("static/js/admin.js")
    assert "tag-admin-head" in js
    assert "tag-admin-fields" in js
    assert "tag-admin-actions" in js


def test_admin_tags_layout_responsive_grids():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.tag-admin-head\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s*auto",
        css,
        re.S,
    )
    assert re.search(r"\.tag-admin-fields\s*\{[^}]*auto-fit", css, re.S)


def test_admin_dashboard_layout_present():
    html = read_text("static/templates/admin_images.html.j2")
    assert "page-admin-dashboard" in html
    assert "admin-controls-card" in html


def test_admin_image_cards_default_open():
    js = read_text("static/js/admin.js")
    assert "admin-card-editor" in js
    assert "class=\"card-body\"" in js
    assert "class=\"meta\"" in js
    assert "class=\"tags\"" in js
    assert "admin-card-summary" not in js
    css = read_text("static/styles/gallery.css")
    assert ".admin-card-editor" in css


def test_admin_tag_editor_present():
    html = read_text("static/templates/admin_upload.html.j2")
    assert "data-tag-editor" in html
    assert "data-tag-chips" in html
    js = read_text("static/js/admin.js")
    assert "initTagEditors" in js
    css = read_text("static/styles/gallery.css")
    assert ".tag-editor" in css
    assert ".tag-chip" in css


def test_admin_home_navigation_cards():
    html = read_text("static/templates/admin.html.j2")
    assert "admin-home-grid" in html
    assert "admin-nav-card" in html
    assert "admin-home-section" in html
    assert 'href="/admin/images/"' in html
    assert 'href="/admin/upload/"' in html
    assert 'href="/admin/collections/"' in html
    assert 'href="/admin/auth/"' in html
    assert 'href="/admin/tags/"' in html
    assert 'href="/status/"' in html


def test_admin_dashboard_grid_styles_present():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.admin-dashboard\s*\{[^}]*grid-template-columns", css, re.S)
    assert re.search(r"\.admin-controls\.admin-controls-card\s*\{", css, re.S)


def test_admin_dashboard_stacks_panels():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.admin-dashboard\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)",
        css,
        re.S,
    )
    assert re.search(
        r"\.page-admin-dashboard\s+\.admin-side\s*\{[^}]*position:\s*static",
        css,
        re.S,
    )


def test_admin_and_auth_main_offset_topbar():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.admin-main\s*\{[^}]*padding:\s*calc\(24px\s*\+\s*var\(--topbar-height\)\)\s+18px\s+40px;",
        css,
        re.S,
    )
    assert re.search(
        r"\.auth-main\s*\{[^}]*padding:\s*calc\(24px\s*\+\s*var\(--topbar-height\)\)\s+18px\s+40px;",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.admin-main[\s\S]*?padding:\s*calc\(14px\s*\+\s*var\(--topbar-height\)\)\s+12px\s+32px;",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.auth-main[\s\S]*?padding:\s*calc\(14px\s*\+\s*var\(--topbar-height\)\)\s+12px\s+32px;",
        css,
        re.S,
    )


def test_primary_button_uses_theme_gradient():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.btn\.primary\s*\{[^}]*var\(--accent-2\)", css, re.S)


def test_gallery_pages_use_compact_card_tokens():
    css = read_text("static/styles/gallery.css")
    match = re.search(
        r"\.page-home[\s\S]*?\{[^}]*--card-thumb-max:\s*none[^}]*--card-desc-lines:\s*1",
        css,
        re.S,
    )
    assert match
    selector = match.group(0).split("{", 1)[0]
    assert ".page-search" in selector
    assert ".page-my" in selector
    assert ".page-admin" in selector
    assert re.search(r"\.thumb-shell\s*\{[^}]*max-height:\s*var\(--card-thumb-max\)", css, re.S)
    assert re.search(r"\.card-body\s*\{[^}]*padding:\s*var\(--card-body-pad\)", css, re.S)
    assert re.search(r"\.card-body\s*\{[^}]*gap:\s*var\(--card-body-gap\)", css, re.S)
    assert re.search(r"\.card-body\s+\.desc\s*\{[^}]*-webkit-line-clamp:\s*var\(--card-desc-lines\)", css, re.S)
    assert re.search(r"--card-thumb-max:\s*none", css, re.S)
    assert re.search(r"--card-desc-lines:\s*1", css, re.S)


def test_live2d_message_path_absolute():
    js = read_text("static/live2d/live2d/js/message.js")
    assert "var message_Path = '/static/live2d/live2d/';" in js


def test_masonry_relayout_uses_scrollheight():
    js = read_text("static/js/gallery.js")
    assert "scrollHeight" in js
    assert "requestAnimationFrame" in js
    assert "relayoutMasonry" in js


def test_masonry_relayout_resets_row_span_before_measure():
    js = read_text("static/js/gallery.js")
    assert "setProperty('--row-span', '1')" in js


def test_masonry_ready_class_applied_after_layout():
    js = read_text("static/js/gallery.js")
    assert "classList.add('masonry-ready')" in js


def test_masonry_ready_set_for_dynamic_pages():
    search_js = read_text("static/js/search.js")
    admin_js = read_text("static/js/admin.js")
    user_js = read_text("static/js/user.js")
    assert "masonry-ready" in search_js
    assert "masonry-ready" in admin_js
    assert "masonry-ready" in user_js


def test_masonry_helper_shared_across_pages():
    ui_js = read_text("static/js/ui.js")
    assert "GalleryMasonry" in ui_js
    search_js = read_text("static/js/search.js")
    admin_js = read_text("static/js/admin.js")
    user_js = read_text("static/js/user.js")
    assert "GalleryMasonry" in search_js
    assert "GalleryMasonry" in admin_js
    assert "GalleryMasonry" in user_js


def test_suggest_panels_have_styles():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.suggest-panel\s*\{", css)
    assert re.search(r"\.suggest-chip\s*\{", css)


def test_search_close_button_contrast():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.close-button\s*\{[^}]*color:\s*#fff", css, re.S)
    assert re.search(r"\.close-button\s*\{[^}]*background:\s*rgba", css, re.S)


def test_auth_avatar_url_uses_webp():
    data = json.loads(read_text("static/data/site.json"))
    assert data.get("auth_avatar_url", "").endswith(".webp")


def test_tag_suggest_helpers_present():
    js = read_text("static/js/ui.js")
    assert "GalleryTagSuggest" in js
    assert "initTagInputs" in js
    assert "initSearchInputs" in js


def test_tag_suggest_auto_fills_missing_parents():
    js = read_text("static/js/ui.js")
    assert "applyMissingParents" in js
    assert "findMissingParents" in js
    assert "addEventListener('blur'" in js or "addEventListener(\"blur\"" in js


def test_tag_suggest_replaces_last_token_on_click():
    js = read_text("static/js/ui.js")
    assert "endsWithDelimiter" in js
    assert "tags[tags.length - 1] = tag" in js


def test_tag_suggest_supports_alias_prefix():
    js = read_text("static/js/ui.js")
    assert "aliasMap.forEach" in js
    assert "alias.startsWith" in js
    assert "alias.includes" in js


def test_global_search_overlay_present_on_core_pages():
    templates = [
        "static/templates/pages/favorites.html.j2",
        "static/templates/pages/my.html.j2",
        "static/templates/admin.html.j2",
        "static/templates/admin_tags.html.j2",
        "static/templates/auth_login.html.j2",
        "static/templates/auth_register.html.j2",
    ]
    for template in templates:
        content = read_text(template)
        assert "data-search-open" in content, template
        assert "data-search-overlay" in content, template
        assert "data-search-input" in content, template


def test_admin_filter_search_supports_suggest():
    html = read_text("static/templates/admin_images.html.j2")
    assert re.search(r"data-admin-query[^>]*data-search-input", html) or re.search(
        r"data-search-input[^>]*data-admin-query", html
    )


def test_status_page_removes_search_and_theme_toggle():
    html = read_text("static/templates/status.html.j2")
    assert "data-search-open" not in html
    assert "data-search-overlay" not in html
    assert "data-search-input" not in html
    assert "data-theme-toggle" not in html


def test_search_syntax_parser_present():
    js = read_text("static/js/search.js")
    assert "parseQuery" in js
    assert "width" in js and "height" in js and "bytes" in js
    assert "sort" in js


def test_search_alias_prefix_maps_to_tag():
    js = read_text("static/js/search.js")
    assert "resolveTagPrefix" in js
    assert "aliasPrefixCache" in js
    assert "alias.startsWith" in js


def test_wiki_page_template_exists():
    html = read_text("static/templates/pages/wiki.html.j2")
    assert "page-wiki" in html
    assert "wiki-tree" in html
    assert "data-wiki-content" in html
    assert "wiki.js" in html


def test_wiki_page_uses_sidebar_layout():
    html = read_text("static/templates/pages/wiki.html.j2")
    assert "data-left-sidebar" in html
    assert "data-left-toggle" in html
    assert "data-sidebar-dim" in html
    assert "sidebar-close" in html


def test_masonry_ready_waits_for_images_or_timeout():
    js = read_text("static/js/gallery.js")
    assert "img.complete" in js
    assert "addEventListener('error'" in js
    assert "MASONRY_READY_TIMEOUT" in js


def test_favorites_page_template_exists():
    html = read_text("static/templates/pages/favorites.html.j2")
    assert "page-favorites" in html
    assert "我的收藏" in html
    assert "gallery.css" in html


def test_dmca_page_template_exists():
    html = read_text("static/templates/pages/dmca.html.j2")
    assert "page-dmca" in html
    assert "版权/侵权删除申请" in html
    assert "我保证以上提供的信息是真实准确的" in html
    assert "name=\"work_url\"" in html
    assert "name=\"full_name\"" in html
    assert "name=\"authority\"" in html
    assert "name=\"source_url\" required" in html
    assert "name=\"evidence\" required" in html
    assert "name=\"signature\"" not in html


def test_masonry_grid_hidden_until_ready():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.gallery\[data-masonry\]\s*\{[^}]*opacity:\s*0", css, re.S)
    assert re.search(r"\.gallery\[data-masonry\]\s*\{[^}]*translateY\(14px\)", css, re.S)
    assert re.search(r"\.gallery\[data-masonry\]\s*\{[^}]*transition:[^;]*0\.65s", css, re.S)
    assert re.search(r"\.gallery\[data-masonry\]\.masonry-ready\s*\{[^}]*opacity:\s*1", css, re.S)
    assert re.search(
        r"\.gallery\[data-masonry\]:not\(\.masonry-ready\)\s+\.illust-card\s*\{[^}]*grid-row-end:\s*span 1",
        css,
        re.S,
    )


def test_footer_present_on_homepage():
    html = read_text("static/templates/index.html.j2")
    assert "site-footer" in html


def test_homepage_layout_has_sidebars():
    html = read_text("static/templates/index.html.j2")
    assert "data-left-sidebar" in html
    assert "data-avatar-toggle" in html
    assert "avatar-caret" in html
    assert "data-live2d-toggle" in html
    assert "search-icon" in html


def test_homepage_sidebar_dimmer_present():
    html = read_text("static/templates/index.html.j2")
    assert "data-sidebar-dim" in html


def test_homepage_sidebar_has_copyright_notice():
    html = read_text("static/templates/index.html.j2")
    assert "site.copyright_year" in html
    assert "site.copyright_holder" in html
    assert "href=\"/dmca/\"" in html
    assert "侵权请" in html


def test_homepage_filter_summary_present():
    html = read_text("static/templates/index.html.j2")
    assert "data-filter-summary" in html
    assert "data-filter-summary-list" in html
    assert "data-filter-summary-clear" in html


def test_cards_have_click_targets():
    index_html = read_text("static/templates/index.html.j2")
    tag_html = read_text("static/templates/tag.html.j2")
    assert "data-card-link" in index_html
    assert "data-card-link" in tag_html


def test_homepage_live2d_toggle_before_wiki_heading():
    html = read_text("static/templates/index.html.j2")
    toggle_idx = html.find("data-live2d-toggle")
    wiki_idx = html.find("Wiki / status")
    assert toggle_idx != -1
    assert wiki_idx != -1
    assert toggle_idx < wiki_idx


def test_homepage_sidebar_tags_removed():
    html = read_text("static/templates/index.html.j2")
    assert "side-tags" not in html
    assert "side-tag" not in html


def test_homepage_tag_strip_has_all_tags_link():
    html = read_text("static/templates/index.html.j2")
    assert "tag-chip-more" in html
    assert "→全部标签" in html
    assert "top_tags[:6]" in html


def test_homepage_tag_strip_balance_styles():
    css = read_text("static/styles/gallery.css")
    assert "--shadow-soft" in css
    assert re.search(r":root\[data-theme=\"dark\"\][\s\S]*--shadow-soft", css, re.S)
    assert re.search(r"\.home-tag-strip\s*\{[^}]*padding:\s*10px 12px", css, re.S)
    assert re.search(r"\.home-tag-strip\s*\{[^}]*background:\s*linear-gradient", css, re.S)
    assert re.search(r"\.tag-strip-list\s*\{[^}]*padding:\s*4px 0", css, re.S)
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.tag-strip-list\s*\{[^}]*padding:\s*0",
        css,
        re.S,
    )
    assert re.search(r"\.controls\s*\{[^}]*box-shadow:\s*var\(--shadow-soft\)", css, re.S)


def test_homepage_top_tags_sorted_by_count():
    source = read_text("app/static_site.py")
    assert "top_tags = sorted" in source
    assert "item.get(\"count\")" in source


def test_homepage_sidebar_rules_present():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.home-layout\s*\{[^}]*grid-template-columns:\s*var\(--sidebar-width\)", css, re.S)
    assert re.search(r"body\.sidebar-collapsed\s+\.home-layout", css, re.S)
    assert re.search(r"body\.sidebar-collapsed\s+\.left-sidebar", css, re.S)
    assert re.search(r"\.side-toggle\[data-live2d-state=\"on\"\]::after", css, re.S)


def test_dark_theme_live2d_dot_uses_accent():
    css = read_text("static/styles/gallery.css")
    assert re.search(r":root\[data-theme=\"dark\"\][\s\S]*--live2d-dot:\s*var\(--accent\)", css, re.S)


def test_tablet_sidebar_width_matches_layout():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 1200px\)[\s\S]*--sidebar-width:\s*220px",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 1200px\)[\s\S]*\.home-layout\s*\{[^}]*grid-template-columns:\s*var\(--sidebar-width\)",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 900px\)[\s\S]*--sidebar-width:\s*200px",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 900px\)[\s\S]*\.home-layout\s*\{[^}]*grid-template-columns:\s*var\(--sidebar-width\)",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 900px\)[\s\S]*\.wiki-shell\s*\{[^}]*grid-template-columns:\s*var\(--sidebar-width\)",
        css,
        re.S,
    )


def test_mobile_sidebar_drawer_styles_present():
    css = read_text("static/styles/gallery.css")
    assert "--sidebar-close-color: #111111" in css
    assert re.search(r":root\[data-theme=\"dark\"\][\s\S]*--sidebar-close-color:\s*#ffffff", css, re.S)
    assert re.search(r"\.sidebar-dim\s*\{", css)
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*body\.page-home\.sidebar-open\s+\.sidebar-dim",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*html\.sidebar-open\s*\{",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*html\.sidebar-open\s+body\.page-home",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*body\.sidebar-collapsed\s+\.home-layout",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*body\.page-home\s+main[\s\S]*z-index:\s*auto",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.left-sidebar\s*\{[^}]*position:\s*fixed",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.sidebar-close\s*\{",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.sidebar-close\s*\{[^}]*color:\s*var\(--sidebar-close-color\)",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.sidebar-close\s*\{[^}]*left:\s*calc\(min\(86vw,\s*var\(--drawer-width\)\)\s*-\s*44px\)",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.sidebar-close::before[\s\S]*background:\s*var\(--sidebar-close-color\)",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.topbar\s*\{[^}]*flex-direction:\s*row",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*body\.page-home\.sidebar-open\s+\.left-sidebar",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*body\.page-home\.sidebar-open\s+\.sidebar-close",
        css,
        re.S,
    )


def test_topbar_stays_single_row_and_allows_search_shrink():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.topbar-center\s*\{[^}]*min-width:\s*0", css, re.S)
    assert re.search(r"\.top-search\s*\{[^}]*min-width:\s*0", css, re.S)
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.topbar\s*\{[^}]*flex-wrap:\s*nowrap",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.topbar-center\s*\{[^}]*order:\s*0",
        css,
        re.S,
    )


def test_homepage_sidebar_close_button_present():
    html = read_text("static/templates/index.html.j2")
    assert "sidebar-close" in html
    assert "aria-label=\"关闭侧栏\"" in html


def test_topbar_fixed_and_main_offset():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.topbar\s*\{[^}]*position:\s*fixed", css, re.S)
    assert re.search(
        r"main\s*\{[^}]*padding:\s*calc\(24px\s*\+\s*var\(--topbar-height\)\)",
        css,
        re.S,
    )
    assert re.search(
        r"\.page-home\s+main\s*\{[^}]*padding:\s*var\(--topbar-height\)",
        css,
        re.S,
    )


def test_tag_chip_hover_has_underline():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.tag-chip:hover", css)
    assert re.search(r"\.tag-chip:hover[\s\S]*text-decoration:\s*underline", css, re.S)


def test_card_focus_styles_present():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.illust-card:focus-within", css)
    assert re.search(r"\.illust-card:focus-visible", css)


def test_noise_texture_and_search_dim_present():
    css = read_text("static/styles/gallery.css")
    assert "--noise-texture" in css
    assert "var(--noise-texture)" in css
    assert re.search(r"\.search-dim\s*\{", css)


def test_suggest_panel_hint_styles_present():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.suggest-hint\s*\{", css)
    assert re.search(r"\.suggest-hint\s+\.hint-chip", css)


def test_ui_updates_topbar_height_variable():
    js = read_text("static/js/ui.js")
    assert "syncTopbarHeight" in js
    assert "setProperty('--topbar-height'" in js


def test_ui_mobile_sidebar_defaults_collapsed():
    js = read_text("static/js/ui.js")
    assert "matchMedia('(max-width: 640px)')" in js
    assert "data-sidebar-dim" in js
    assert "sidebar-open" in js
    assert "classList.remove('sidebar-collapsed')" in js
    assert "document.documentElement" in js
    assert "root.classList.toggle('sidebar-open'" in js


def test_ui_supports_search_shortcut():
    js = read_text("static/js/ui.js")
    assert "event.metaKey" in js or "event.ctrlKey" in js
    assert "event.key.toLowerCase() === 'k'" in js


def test_search_suggest_panel_shows_on_focus():
    js = read_text("static/js/ui.js")
    assert "document.activeElement === input" in js
    assert "panel.classList.toggle('is-empty', !isFocused)" in js


def test_search_suggest_requires_hash_prefix():
    js = read_text("static/js/ui.js")
    assert "startsWith('#')" in js
    assert "startsWith('-#')" in js or "startsWith(\"-#\")" in js


def test_wall_page_removed_everywhere():
    templates = [
        "static/templates/index.html.j2",
        "static/templates/detail.html.j2",
        "static/templates/search.html.j2",
        "static/templates/tags.html.j2",
        "static/templates/tag.html.j2",
        "static/templates/404.html.j2",
    ]
    for template in templates:
        content = read_text(template)
        assert "/wall.html" not in content
    assert not (BASE_DIR / "static" / "wall.html").exists()
    assert not (BASE_DIR / "static" / "js" / "wall.js").exists()
    assert not (BASE_DIR / "static" / "styles" / "wall.css").exists()


def test_auth_pages_have_static_links_and_https_flag():
    login_html = read_text("static/templates/auth_login.html.j2")
    register_html = read_text("static/templates/auth_register.html.j2")
    assert 'data-auth-require-https' in login_html
    assert 'data-auth-require-https' in register_html
    assert 'href="/auth/register/"' in login_html
    assert 'href="/auth/login/"' in register_html
    assert "data-auth-login-form" in login_html
    assert "data-auth-register-form" in register_html
    assert 'name="password_confirm"' in register_html


def test_error_pages_have_apology_and_figure():
    templates = [
        "static/templates/404.html.j2",
        "static/templates/error.html.j2",
        "static/templates/maintenance.html.j2",
    ]
    for template in templates:
        html = read_text(template)
        assert "error-figure" in html
        assert "/static/images/error-figure.webp" in html
        assert "很抱歉" in html
        assert "提示" in html


def test_404_page_has_retry_copy_and_stamp():
    html = read_text("static/templates/404.html.j2")
    assert "重新搜索" in html
    assert "page-404" in html


def test_404_error_code_uses_monospace_font():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.page-404\s*\.error-code\s*\{[^}]*JetBrains Mono", css, re.S)
    assert re.search(r"\.page-404\s*\.error-code\s*\{[^}]*Consolas", css, re.S)


def test_404_page_mobile_media_rules():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-404\s*\.error-figure\s*\{[^}]*display:\s*none",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-404\s*\.error-actions\s*\{[^}]*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-404\s*\.error-card\s*\{[^}]*padding:\s*18px 20px",
        css,
        re.S,
    )


def test_error_page_uses_scale_variable():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.page-error\s*\{[^}]*--error-scale:\s*1", css, re.S)
    assert re.search(r"\.page-error\s*\{[^}]*--error-shift:\s*0px", css, re.S)
    assert re.search(
        r"\.error-main\s*\{[^}]*transform:\s*translateY\(var\(--error-shift\)\)\s*scale\(var\(--error-scale\)\)",
        css,
        re.S,
    )
    assert re.search(r"@media \(min-width: 1200px\)[\s\S]*--error-scale:\s*1\.06", css, re.S)
    assert re.search(r"@media \(min-width: 1200px\)[\s\S]*--error-shift:\s*clamp\(10px,\s*1\.6vh,\s*20px\)", css, re.S)
    assert re.search(r"@media \(min-width: 1200px\)[\s\S]*\.page-error main\s*\{[^}]*justify-content:\s*center", css, re.S)
    assert re.search(r"@media \(min-width: 1200px\)[\s\S]*\.page-error main\s*\{[^}]*min-height:\s*calc\(100vh - var\(--topbar-height\) - 64px\)", css, re.S)
    assert re.search(r"@media \(min-width: 1200px\)[\s\S]*\.page-error \.error-main\s*\{[^}]*transform-origin:\s*top center", css, re.S)
    assert re.search(r"@media \(max-width: 360px\)[\s\S]*--error-scale:\s*0\.92", css, re.S)


def test_admin_links_present_in_topbars():
    templates = [
        "static/templates/index.html.j2",
        "static/templates/detail.html.j2",
        "static/templates/search.html.j2",
        "static/templates/tags.html.j2",
        "static/templates/tag.html.j2",
        "static/templates/auth_login.html.j2",
        "static/templates/auth_register.html.j2",
        "static/templates/pages/my.html.j2",
    ]
    for template in templates:
        content = read_text(template)
        assert 'href="/admin/"' in content
        assert 'href="/admin/tags/"' in content
        assert 'href="/status/"' in content
        assert "data-admin-entry" in content


def test_user_avatar_placeholder_in_topbars():
    templates = [
        "static/templates/index.html.j2",
        "static/templates/detail.html.j2",
        "static/templates/search.html.j2",
        "static/templates/tags.html.j2",
        "static/templates/tag.html.j2",
        "static/templates/auth_login.html.j2",
        "static/templates/auth_register.html.j2",
    ]
    for template in templates:
        content = read_text(template)
        assert "data-user-avatar" in content, template
        assert "data-user-avatar-img" in content, template
    index_html = read_text("static/templates/index.html.j2")
    assert "data-auth-login-link" in index_html
    assert "data-auth-register-link" in index_html
    assert "data-auth-user-link" in index_html


def test_hidden_attribute_overrides_display():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\[hidden\]\s*\{[^}]*display:\s*none", css, re.S)


def test_mobile_topnav_scrolls():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media\s*\(max-width:\s*640px\)[\s\S]*?\.topnav\s*\{[\s\S]*?overflow-x:\s*auto",
        css,
    )


def test_homepage_mobile_gallery_is_two_columns():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s+\.gallery\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s+\.gallery\s*\{[^}]*gap:\s*10px",
        css,
        re.S,
    )


def test_homepage_mobile_card_density_tokens():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s*\{[^}]*--card-thumb-max:\s*220px",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s*\{[^}]*--card-body-pad:\s*7px 8px 8px",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s*\{[^}]*--card-tags-max:\s*22px",
        css,
        re.S,
    )


def test_homepage_mobile_main_padding_has_left_right_gap():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s+main\s*\{[^}]*padding:\s*calc\(14px\s*\+\s*var\(--topbar-height\)\)\s+12px\s+32px",
        css,
        re.S,
    )


def test_homepage_filter_pills_wrapper_present():
    html = read_text("static/templates/index.html.j2")
    assert html.count('class="filter-pills"') >= 2


def test_tag_chip_base_style_is_borderless():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.tag-chip\s*\{[^}]*border:\s*none", css, re.S)
    assert re.search(r"\.tag-chip\s*\{[^}]*background:\s*transparent", css, re.S)


def test_admin_tag_chip_styles_scoped():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.page-admin-tags\s+\.tag-chip\s*\{[^}]*border:\s*1px\s+solid", css, re.S)
    assert re.search(r"\.page-admin-tags\s+\.tag-chip:hover\s*\{", css, re.S)


def test_homepage_mobile_filters_scrollable_row():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s+\.filters\s*\{[^}]*flex-direction:\s*column",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s+\.filter-group\s*\{[^}]*flex-wrap:\s*nowrap",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s+\.filter-pills\s*\{[^}]*overflow-x:\s*auto",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s+\.filter-pills\s*\{[^}]*flex-wrap:\s*nowrap",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s+\.filter-pills\s+\.pill\s*\{[^}]*padding:\s*0",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s+\.filter-pills\s+\.pill\s*\{[^}]*background:\s*transparent",
        css,
        re.S,
    )


def test_my_page_template_has_upload_and_gallery():
    html = read_text("static/templates/pages/my.html.j2")
    assert "data-user-upload-form" in html
    assert "data-user-gallery" in html


def test_detail_page_has_editor_panel():
    html = read_text("static/templates/detail.html.j2")
    assert "data-image-editor" in html
    assert "data-image-uuid" in html
