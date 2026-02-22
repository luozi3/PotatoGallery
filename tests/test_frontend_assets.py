from pathlib import Path
import json
import re
import pytest


BASE_DIR = Path(__file__).resolve().parents[1]
INCLUDE_RE = re.compile(r"{%\s*include\s+\"([^\"]+)\"\s*%}")


def _expand_includes(content: str, *, hide_search: bool) -> str:
    def replace(match: re.Match) -> str:
        include_path = match.group(1)
        include_file = BASE_DIR / "static" / "templates" / include_path
        if not include_file.exists():
            return ""
        include_content = include_file.read_text(encoding="utf-8")
        if hide_search and include_path == "partials/topbar.html.j2":
            include_content = re.sub(
                r"{%\s*if\s+show_search\s*%}[\s\S]*?{%\s*endif\s*%}",
                "",
                include_content,
            )
        return include_content

    for _ in range(3):
        updated = INCLUDE_RE.sub(replace, content)
        if updated == content:
            break
        content = updated
    return content


def read_text(rel_path: str) -> str:
    content = (BASE_DIR / rel_path).read_text(encoding="utf-8")
    if rel_path.endswith(".html.j2"):
        hide_search = "show_search = false" in content
        content = _expand_includes(content, hide_search=hide_search)
    return content


def test_theme_toggle_after_brand():
    topbar = read_text("static/templates/partials/topbar.html.j2")
    brand_idx = topbar.find('class="brand')
    toggle_idx = topbar.find("data-theme-toggle")
    assert brand_idx != -1 and toggle_idx != -1
    assert brand_idx < toggle_idx
    templates = [
        "static/templates/index.html.j2",
        "static/templates/detail.html.j2",
        "static/templates/search.html.j2",
        "static/templates/tags.html.j2",
        "static/templates/tag.html.j2",
        "static/templates/admin.html.j2",
        "static/templates/admin_dmca.html.j2",
        "static/templates/admin_tags.html.j2",
        "static/templates/pages/wiki.html.j2",
        "static/templates/pages/dmca.html.j2",
        "static/templates/pages/profile.html.j2",
    ]
    for template in templates:
        content = read_text(template)
        brand_idx = content.find('class="brand')
        toggle_idx = content.find("data-theme-toggle")
        assert brand_idx != -1 and toggle_idx != -1, template
        assert brand_idx < toggle_idx, template


def test_theme_init_inline_script_present():
    templates = []
    for path in (BASE_DIR / "static" / "templates").rglob("*.html.j2"):
        if "partials" in path.parts:
            continue
        templates.append(str(path.relative_to(BASE_DIR)))
    assert templates
    for template in templates:
        html = read_text(template)
        assert "data-theme-init" in html, template


def test_auth_hint_css_hides_login_links():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"html\.auth-hint-logged-in\s*\[data-auth-login-link\]", css)
    assert re.search(r"html\.auth-hint-logged-in\s*\[data-auth-register-link\]", css)


def test_avatar_menu_hover_has_fade_and_delay():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.avatar-dropdown\s*\{[^}]*opacity:\s*0", css, re.S)
    assert re.search(r"\.avatar-dropdown\s*\{[^}]*transition:\s*opacity\s*0\.14s", css, re.S)
    assert re.search(r"\.avatar-menu\.is-open\s+\.avatar-dropdown\s*\{[^}]*opacity:\s*1", css, re.S)
    js = read_text("static/js/ui.js")
    assert re.search(r"const\s+AVATAR_MENU_CLOSE_DELAY\s*=\s*160", js)
    assert re.search(r"const\s+AVATAR_MENU_ANIM_MS\s*=\s*140", js)
    assert re.search(r"setTimeout\([^,]+,\s*AVATAR_MENU_CLOSE_DELAY", js)


def test_avatar_dropdown_compact_width():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.avatar-dropdown\s*\{[^}]*min-width:\s*150px", css, re.S)
    assert re.search(r"\.avatar-dropdown\s*\{[^}]*padding:\s*6px", css, re.S)


def test_avatar_dropdown_logout_icon_style():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.dropdown-item\s*\{[^}]*width:\s*100%", css, re.S)
    assert re.search(r"\.dropdown-item\s*\{[^}]*font:\s*inherit", css, re.S)
    assert re.search(r"\.dropdown-icon\s*\{[^}]*width:\s*14px", css, re.S)
    assert re.search(r"\.dropdown-icon\s*\{[^}]*height:\s*14px", css, re.S)
    assert re.search(r"\.dropdown-icon\s*\{[^}]*margin-left:\s*auto", css, re.S)


def test_avatar_dropdown_logout_items():
    topbar = read_text("static/templates/partials/topbar.html.j2")
    assert "data-admin-logout" not in topbar
    assert re.search(r"data-avatar-dropdown[\s\S]*data-user-logout", topbar)
    assert re.search(r"data-user-logout[^>]*\bhidden\b", topbar)
    assert "dropdown-icon" in topbar
    user_idx = topbar.find("data-user-logout")
    user_end = topbar.find("</button>", user_idx)
    if user_idx != -1 and user_end != -1:
        user_segment = topbar[user_idx:user_end]
        assert user_segment.find("退出账号") < user_segment.find("<svg")
    js = read_text("static/js/ui.js")
    assert "data-user-logout" in js
    assert "/auth/logout" in js


def test_tag_suggest_underscore_mapping():
    js = read_text("static/js/ui.js")
    assert re.search(r"replace\(/_/g,\s*' '\)", js)
    assert re.search(r"replace\(/ /g,\s*'_'\)", js)
    assert "formatTagForLabel" in js
    assert "formatTagForInput" in js
    assert "formatTagForLabel" in js


def test_admin_home_status_and_side_panels_have_compact_pills():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.admin-status-strip\s*\{[^}]*gap:\s*8px", css, re.S)
    assert re.search(r"\.admin-status-strip\s*\{[^}]*border-radius:\s*12px", css, re.S)
    assert re.search(r"\.admin-status-item\s*\{[^}]*border-radius:\s*10px", css, re.S)
    assert re.search(r"\.admin-status-item\s*\{[^}]*padding:\s*6px 12px", css, re.S)
    assert re.search(r"\.admin-status-item\s*\{[^}]*background:\s*var\(--panel-strong\)", css, re.S)
    assert re.search(r"\.admin-side-list\s*\{[^}]*border:\s*1px solid var\(--border\)", css, re.S)
    assert re.search(r"\.admin-side-row\s*\{[^}]*padding:\s*10px 12px", css, re.S)
    assert re.search(r"\.admin-side-links\s*\{[^}]*background:\s*var\(--border\)", css, re.S)


def test_admin_home_flow_notes_removed():
    html = read_text("static/templates/admin.html.j2")
    assert "流程提醒" not in html
    assert "admin-side-notes" not in html


def test_profile_page_html_structure():
    html = read_text("static/templates/pages/profile.html.j2")
    assert 'data-profile-page' in html
    assert 'class="profile-account-line"' in html
    assert 'data-profile-tab="basic"' in html
    assert 'data-profile-tab="security"' in html
    assert "profile-section-overview" in html
    assert "profile-section-avatar" in html
    assert "profile-section-form" in html


def test_profile_css_supports_dense_layout():
    css = read_text("static/styles/gallery.css")
    assert ".profile-shell" in css
    assert ".profile-header-meta" in css
    assert ".profile-account-line" in css
    assert ".profile-account-value" in css
    assert ".profile-tab.is-active" in css


def test_profile_header_panel_style():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.profile-header\s*\{[^}]*border-radius:\s*12px", css, re.S)
    assert re.search(r"\.profile-header\s*\{[^}]*background:\s*linear-gradient", css, re.S)
    assert re.search(r"\.profile-avatar\s*\{[^}]*box-shadow:\s*0 6px 14px", css, re.S)


def test_profile_avatar_modal_layout():
    html = read_text("static/templates/pages/profile.html.j2")
    assert "data-avatar-modal" in html
    assert "data-avatar-open" in html
    assert "data-avatar-current" in html
    assert "data-avatar-size" in html
    assert "data-avatar-frame" in html
    assert "data-avatar-handle" in html
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.profile-avatar-modal\s*\{[^}]*position:\s*fixed", css, re.S)
    assert re.search(r"\.profile-avatar-row\s*\{[^}]*grid-template-columns", css, re.S)
    assert re.search(r"\.profile-crop-frame\s*\{[^}]*box-shadow", css, re.S)
    assert ".profile-crop-handle" in css


def test_profile_avatar_picker_resets_and_locks_preview():
    js = read_text("static/js/profile.js")
    assert "previewLocked" in js
    assert "loadToken" in js
    assert "!cropState.previewLocked" in js
    assert "avatarInput.value = ''" in js


def test_admin_login_section_hidden_by_default():
    templates = [
        "static/templates/admin.html.j2",
        "static/templates/admin_auth.html.j2",
        "static/templates/admin_collections.html.j2",
        "static/templates/admin_dmca.html.j2",
        "static/templates/admin_images.html.j2",
        "static/templates/admin_tags.html.j2",
        "static/templates/admin_upload.html.j2",
    ]
    for template in templates:
        html = read_text(template)
        assert re.search(r"data-admin-login[^>]*\bhidden\b", html), template


def test_html_sidebar_collapsed_support():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"html\.sidebar-collapsed\s+body\s+\.left-sidebar", css)
    assert re.search(r"html\.sidebar-collapsed\s+body\s+\.detail-shell", css)


def test_profile_shell_left_padding():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.page-profile\s+\.profile-shell\s*\{[^}]*padding-left:\s*18px",
        css,
        re.S,
    )


def test_right_sidebar_background_and_sticky_inner():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.detail-shell\s*\{[^}]*--detail-sidebar-offset:\s*var\(--sidebar-width\)", css, re.S)
    assert re.search(r"\.detail-shell\s*\{[^}]*background:\s*linear-gradient", css, re.S)


def test_detail_hint_visibility_controls():
    html = read_text("static/templates/detail.html.j2")
    assert "data-detail-overlay" in html
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.detail-overlay\.hint-managed\s*\{[^}]*opacity:\s*0", css, re.S)
    assert re.search(r"\.detail-overlay\.hint-managed\.is-visible\s*\{[^}]*opacity:\s*1", css, re.S)
    js = read_text("static/js/ui.js")
    assert re.search(r"HINT_STARTUP_MS\s*=\s*5000", js)
    assert re.search(r"HINT_HOVER_HIDE_MS\s*=\s*3000", js)
    assert re.search(r"HINT_TOGGLE_SHOW_MS\s*=\s*3000", js)
    assert "showHintFor(HINT_TOGGLE_SHOW_MS)" in js
    assert re.search(r"\.detail-shell::before\s*\{[^}]*left:\s*var\(--detail-sidebar-offset\)", css, re.S)
    assert re.search(r"\.detail-shell::after\s*\{[^}]*left:\s*calc\(var\(--detail-sidebar-offset\)", css, re.S)
    assert re.search(r"\.detail-static-sidebar\s*\{[^}]*align-self:\s*stretch", css, re.S)
    assert re.search(r"\.detail-static-sidebar\s*\{[^}]*position:\s*relative", css, re.S)
    assert re.search(r"\.detail-static-sidebar\s*\{[^}]*background:\s*var\(--sidebar-bg\)", css, re.S)
    assert re.search(r"\.detail-static-sidebar\s*\{[^}]*padding-bottom:\s*48px", css, re.S)
    assert re.search(r"\.detail-static-sidebar\s+\.left-sidebar-inner\s*\{[^}]*position:\s*sticky", css, re.S)
    assert re.search(
        r"body\.page-detail\.with-sidebar\s+main\s*\{[^}]*padding:\s*var\(--topbar-height\)\s+18px\s+0\s+0",
        css,
        re.S,
    )
    assert re.search(r"\.detail-main\s*\{[^}]*padding:\s*12px\s+0\s+48px\s+24px", css, re.S)
    assert re.search(r"\.wiki-static-sidebar\s*\{[^}]*align-self:\s*stretch", css, re.S)
    assert re.search(r"\.wiki-static-sidebar\s*\{[^}]*background:\s*transparent", css, re.S)
    assert re.search(r"\.wiki-static-sidebar\s*\{[^}]*padding:\s*0", css, re.S)
    assert re.search(r"\.wiki-toc-panel\s*\{[^}]*position:\s*sticky", css, re.S)
    assert re.search(r"\.wiki-toc-panel\s*\{[^}]*background:\s*var\(--glass\)", css, re.S)
    assert re.search(
        r"body\.page-wiki\.with-sidebar\s+main\s*\{[^}]*padding:\s*var\(--topbar-height\)\s+18px\s+0\s+0",
        css,
        re.S,
    )
    assert re.search(r"\.wiki-main\s*\{[^}]*padding:\s*12px\s+0\s+48px\s+24px", css, re.S)


def test_detail_shell_relative_for_layers():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.detail-shell\s*\{[^}]*position:\s*relative", css, re.S)


def test_live2d_html_hidden_rule():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"html\.live2d-hidden\s+#landlord", css)
    assert re.search(r"\.live2d-root\.live2d-hidden\s*\{", css)
    assert not re.search(
        r"(^|\n)\s*\.live2d-hidden\s*\{\s*display\s*:\s*none",
        css,
        re.M,
    )


def test_live2d_hidden_on_narrow_and_toggle_hidden():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.live2d-root\s*\{[^}]*display:\s*none",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.side-toggle\[data-live2d-toggle\]\s*\{[^}]*display:\s*none",
        css,
        re.S,
    )
    assert re.search(
        r"html\.live2d-narrow\s+\.side-toggle\[data-live2d-toggle\]\s*\{[^}]*display:\s*none",
        css,
        re.S,
    )


def test_live2d_forced_off_on_narrow():
    js = read_text("static/js/ui.js")
    assert "matchMedia('(max-width: 640px)')" in js
    assert re.search(
        r"applyLive2dState\(\s*live2dMedia\s*&&\s*live2dMedia\.matches\s*\)",
        js,
        re.S,
    )
    assert "live2d-narrow" in js
    assert "classList.add('live2d-hidden')" in js
    assert "classList.remove('live2d-hidden')" in js


def test_live2d_lazy_load_on_narrow():
    html = read_text("static/templates/partials/live2d_block.html.j2")
    assert "matchMedia('(max-width: 640px)')" in html
    assert "id=\"landlord\"" in html
    assert re.search(
        r"live2dMedia\s*&&\s*live2dMedia\.matches[\s\S]*return",
        html,
        re.S,
    )
    assert "loadlive2d" in html
    assert re.search(
        r"live2dMedia\.addEventListener\('change'|live2dMedia\.addListener\(",
        html,
        re.S,
    )


def test_sidebar_restore_back_forward_hook():
    js = read_text("static/js/ui.js")
    assert "sidebar-restore-open" in js
    assert "pagehide" in js
    assert "pageshow" in js


def test_mobile_sidebar_clears_root_collapse():
    js = read_text("static/js/ui.js")
    assert "root.classList.remove('sidebar-collapsed')" in js


def test_default_theme_is_light():
    js = read_text("static/js/ui.js")
    assert re.search(r"const initialTheme\s*=\s*savedTheme\s*\|\|\s*'light'", js)


def test_admin_stress_controls_have_stop_retry():
    html = read_text("static/templates/admin_upload.html.j2")
    assert "data-admin-stress-stop" in html
    assert "data-admin-stress-retry" in html


def test_upload_progress_supports_retry_pause():
    js = read_text("static/js/ui.js")
    assert "retrying" in js
    assert "paused" in js
    assert "stopped" in js


def test_admin_stress_retry_abortable_requests():
    js = read_text("static/js/admin.js")
    assert "AbortController" in js
    assert "REQUEST_TIMEOUT_MS" in js


def test_admin_invite_panel_has_controls():
    html = read_text("static/templates/admin_auth.html.j2")
    assert "data-admin-invite-create" in html
    assert "data-admin-invite-list" in html
    assert "data-admin-invite-archive-list" in html
    assert "data-admin-invite-archive-toggle" in html
    assert "data-admin-invite-dialog" in html
    assert "data-admin-invite-dialog-disable" in html
    assert "data-admin-invite-dialog-delete" in html
    assert "btn danger" in html
    assert re.search(
        r"<input[^>]*data-admin-invite-expires-at[^>]*type=\"date\"|<input[^>]*type=\"date\"[^>]*data-admin-invite-expires-at",
        html,
    )
    assert "data-admin-invite-expires-at" in html
    assert "data-admin-invite-max-uses" in html


def test_admin_dialog_has_animation_styles():
    css = read_text("static/styles/gallery.css")
    assert ".admin-dialog.is-open" in css
    assert "transition: opacity 0.18s var(--ease), visibility 0s linear 0s" in css
    assert ".admin-dialog.is-open .admin-dialog-backdrop" in css


def test_controls_use_theme_panel_background():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.controls\s*\{[^}]*background:\s*linear-gradient\(180deg,\s*var\(--panel\),\s*var\(--panel-strong\)\)",
        css,
        re.S,
    )


def test_primary_button_gradient_alignment():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.btn\.primary\s*\{[^}]*background-size:\s*120% 120%", css, re.S)
    assert re.search(r"\.btn\.primary\s*\{[^}]*background-position:\s*60% 50%", css, re.S)


def test_tags_page_density_rules():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.tag-grid\s*\{[^}]*gap:\s*0", css, re.S)
    assert re.search(
        r"\.tag-grid\.tags-two-column\s*\{[^}]*repeat\(2,\s*minmax\(0,\s*1fr\)\)",
        css,
        re.S,
    )
    assert re.search(r"\.tag-card\s*\{[^}]*border-radius:\s*0", css, re.S)
    assert re.search(r"\.tag-card\s*\{[^}]*box-shadow:\s*none", css, re.S)
    assert re.search(
        r"@media\s*\(max-width:\s*720px\)[\s\S]*?\.tag-grid\s*\{[^}]*grid-template-columns:\s*1fr",
        css,
    )


def test_tags_page_filters_present():
    html = read_text("static/templates/tags.html.j2")
    assert "data-tags-search" in html
    assert "data-tags-type" in html
    assert "data-tags-grid" in html
    assert "/static/js/tags.js" in html


def test_tags_toolbar_compact_style():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.tags-toolbar\s*\{[^}]*border-bottom:\s*1px", css, re.S)
    assert re.search(r"\.tags-filter input[\s\S]*border-bottom:\s*1px", css)
    assert re.search(r"\.tags-filter input[\s\S]*border-radius:\s*0", css)


def test_tags_filter_script_hooks():
    js = read_text("static/js/tags.js")
    assert "data-tags-search" in js
    assert "data-tags-type" in js
    assert "data-tags-grid" in js
    assert "data-tags-empty" in js
    assert "tags-two-column" in js


def test_wiki_mobile_density_rules():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media\s*\(max-width:\s*980px\)[\s\S]*?\.wiki-header\s*\{[^}]*flex-direction:\s*column",
        css,
    )
    assert re.search(
        r"@media\s*\(max-width:\s*640px\)[\s\S]*?\.wiki-header-actions\s+\.btn\s*\{[^}]*font-size:\s*12px",
        css,
    )
    assert re.search(
        r"@media\s*\(max-width:\s*640px\)[\s\S]*?\.wiki-article\s+h2\s*\{[^}]*font-size:\s*19px",
        css,
    )


def test_wiki_narrow_no_card_background():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.wiki-main\s*\{[^}]*background:\s*transparent", css, re.S)
    assert re.search(
        r"@media\s*\(max-width:\s*900px\)[\s\S]*?body\.page-wiki\s+main\s*\{[^}]*padding-left:\s*0[^}]*padding-right:\s*0",
        css,
        re.S,
    )
    assert re.search(
        r"@media\s*\(max-width:\s*900px\)[\s\S]*?body\.page-wiki\s+\.wiki-main\s*\{[^}]*padding:\s*20px\s+16px\s+48px",
        css,
        re.S,
    )
    assert re.search(
        r"@media\s*\(max-width:\s*900px\)[\s\S]*?\.wiki-shell\s*\{[^}]*grid-template-columns:\s*var\(--sidebar-width\)\s+minmax\(0,\s*1fr\)",
        css,
        re.S,
    )
    assert re.search(
        r"@media\s*\(max-width:\s*900px\)[\s\S]*?body\.page-wiki\s+\.wiki-static-sidebar\s*\{[^}]*position:\s*fixed",
        css,
        re.S,
    )


def test_error_card_overlay_layering():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.error-card\s*\{[^}]*z-index:\s*0", css, re.S)
    assert re.search(r"\.error-card::before\s*\{[^}]*z-index:\s*0", css, re.S)
    assert re.search(r"\.error-card\s*>\s*\*\s*\{[^}]*z-index:\s*1", css, re.S)
    assert re.search(r"\.error-card::before\s*\{[^}]*inset:\s*0", css, re.S)
    assert re.search(r"\.error-card::before\s*\{[^}]*linear-gradient", css, re.S)


def test_admin_gallery_auto_rows_override():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.page-admin\s+\.admin-gallery\s*\{[^}]*grid-auto-rows:\s*auto",
        css,
        re.S,
    )


def test_admin_narrow_padding_removed():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"body\.page-admin\s+main\s*\{[^}]*padding-left:\s*0[^}]*padding-right:\s*0",
        css,
        re.S,
    )
    assert re.search(
        r"body\.page-admin\s+\.admin-main\s*\{[^}]*padding-left:\s*0[^}]*padding-right:\s*0",
        css,
        re.S,
    )


def test_admin_narrow_outer_panel_removed():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"body\.page-admin\s+\.admin-panel\.admin-surface,\s*body\.page-admin\s+\.admin-auth\.admin-surface\s*\{[^}]*padding:\s*0",
        css,
        re.S,
    )
    assert re.search(
        r"body\.page-admin\s+\.admin-panel\.admin-surface,\s*body\.page-admin\s+\.admin-auth\.admin-surface\s*\{[^}]*border:\s*none",
        css,
        re.S,
    )
    assert re.search(
        r"body\.page-admin\s+\.admin-panel\.admin-surface,\s*body\.page-admin\s+\.admin-auth\.admin-surface\s*\{[^}]*background:\s*transparent",
        css,
        re.S,
    )


def test_admin_trash_view_skips_editor():
    js = read_text("static/js/admin.js")
    assert "const showEditor = !showTrash;" in js
    assert "const editorHtml = showEditor" in js
    assert "if (!showTrash) {" in js


def test_admin_trash_purge_buttons_present():
    html = read_text("static/templates/admin_images.html.j2")
    assert "data-admin-trash-page" in html
    assert "data-admin-trash-all" in html
    css = read_text("static/styles/gallery.css")
    assert ".btn.danger" in css


def test_admin_tags_filters_persisted():
    js = read_text("static/js/admin.js")
    assert "admin-tags-filters-v1" in js
    assert "persistTagFilterPrefs" in js


def test_system_font_stack_used():
    css = read_text("static/styles/gallery.css")
    assert "fonts.googleapis.com" not in css
    assert "--font-sans:" in css
    assert re.search(r"body\s*\{[^}]*font-family:\s*var\(--font-sans\)", css, re.S)
    assert "Shippori" not in css
    assert "Zen Kaku" not in css
    assert "Noto Sans" not in css
    assert "Noto Serif" not in css


def test_favorites_flag_icons_present():
    html = read_text("static/templates/pages/favorites.html.j2")
    assert 'data-fav-flag="pick"' in html
    assert 'data-fav-flag="reject"' in html
    assert "⚑" in html
    assert "⚐" in html
    js = read_text("static/js/favorites.js")
    assert 'data-fav-flag="pick"' in js
    assert 'data-fav-flag="reject"' in js
    assert "⚑" in js
    assert "⚐" in js


def test_favorites_pagination_controls_present():
    html = read_text("static/templates/pages/favorites.html.j2")
    assert html.count("data-fav-pagination") >= 2
    assert "data-fav-pagination-top" in html
    assert "data-fav-page-prev" in html
    assert "data-fav-page-next" in html
    assert "data-fav-page-list" in html
    assert "data-fav-page-input" in html
    assert "data-fav-page-jump" in html
    js = read_text("static/js/favorites.js")
    assert re.search(r"pageSize\s*=\s*25", js)


def test_favorites_facets_flat_style():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.facet-card\s*\{[^}]*background:\s*var\(--panel\)", css, re.S)
    assert re.search(r"\.facet-card\s*\{[^}]*border:\s*1px solid", css, re.S)
    assert re.search(r"\.facet-item\s*\{[^}]*border-bottom:\s*1px solid", css, re.S)


def test_favorites_narrow_list_above_facets():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.favorites-layout\s*\{[^}]*grid-template-areas:\s*\"facets list\"",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 980px\)[\s\S]*?\.favorites-layout\s*\{[^}]*grid-template-areas:\s*\"list\"\s*\"facets\"",
        css,
        re.S,
    )


def test_favorites_narrow_thumb_portrait():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 980px\)[\s\S]*?\.favorites-row\s*\{[^}]*grid-template-columns:\s*minmax\(110px,\s*32%\)\s*minmax\(0,\s*1fr\)",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 980px\)[\s\S]*?\.favorites-thumb\s*\{[^}]*aspect-ratio:\s*3\s*/\s*4",
        css,
        re.S,
    )
    js = read_text("static/js/favorites.js")
    assert "favorites-summary" in js


def test_favorites_narrow_hide_list_head():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 980px\)[\s\S]*?\.favorites-list-head\s*\{[^}]*display:\s*none",
        css,
        re.S,
    )


def test_mobile_topbar_compact_layout():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.topbar-left[\s\S]*?flex:\s*0 1 auto",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.topbar-center[\s\S]*?flex:\s*1 1 0",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.brand-text strong[\s\S]*?font-size:\s*13px",
        css,
        re.S,
    )
    assert ".brand.brand-compact .brand-text strong" not in css


def test_mobile_home_gallery_cover_and_width():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.page-home\s+\.gallery[\s\S]*?grid-template-columns:\s*repeat\(auto-fill,\s*minmax\(156px,\s*1fr\)\)",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.page-home\s+\.thumb[\s\S]*?object-fit:\s*cover",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.page-home\s*\{[^}]*--card-thumb-max:\s*260px",
        css,
        re.S,
    )


def test_detail_page_dual_sidebar_layout_present():
    html = read_text("static/templates/detail.html.j2")
    assert "data-left-sidebar" in html
    assert "detail-static-sidebar" in html
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.detail-shell\s*\{[^}]*grid-template-columns:\s*var\(--sidebar-width\)\s+var\(--detail-sidebar-width\)\s+minmax\(0,\s*1fr\)",
        css,
        re.S,
    )
    assert ".detail-static-sidebar" in css


def test_detail_image_fit_rules_present():
    html = read_text("static/templates/detail.html.j2")
    assert "data-thumb-width" in html
    assert "data-full-width" in html
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.detail-media\s*\{[^}]*--detail-fit-width", css, re.S)
    assert re.search(r"\.detail-frame\s*\{[^}]*width:\s*var\(--detail-fit-width", css, re.S)
    assert re.search(r'\.detail-media\[data-image-mode="full"\]\s+\.detail-frame\s*\{[^}]*max-width:\s*none', css, re.S)
    js = read_text("static/js/ui.js")
    assert "--detail-fit-width" in js
    assert "--detail-fit-height" in js
    assert "applyDetailImageFit" in js


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


def test_status_page_canvas_styles_scoped():
    html = read_text("static/templates/status.html.j2")
    assert ".status-chart canvas" in html
    assert not re.search(r"\n\s*canvas\s*\{", html)


def test_status_page_mobile_padding():
    html = read_text("static/templates/status.html.j2")
    assert re.search(
        r"@media \(max-width: 600px\)[\s\S]*?padding:\s*18px\s+18px\s+40px;",
        html,
        re.S,
    )


def test_status_page_desktop_padding():
    html = read_text("static/templates/status.html.j2")
    assert "padding: 32px 80px 72px;" in html


def test_status_page_mobile_layout_overrides():
    html = read_text("static/templates/status.html.j2")
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
    assert "data-admin-tag-candidate" in html
    assert "data-admin-tag-suggest-list" in html
    assert "admin-subnav-link" not in html


def test_admin_tags_layout_structure_present():
    js = read_text("static/js/admin.js")
    assert "tag-admin-head" in js
    assert "tag-admin-fields" in js
    assert "tag-admin-actions" in js
    assert "tag-admin-tree" in js


def test_admin_tags_parent_tag_suggest_hooked():
    js = read_text("static/js/admin.js")
    assert re.search(r"data-tag-field=\"parents\"[^>]*data-tag-input", js)


def test_admin_tags_parent_tag_suggest_init_on_editor():
    js = read_text("static/js/admin.js")
    assert "initTagSuggest(tagEditorTagPanel)" in js


def test_admin_tags_layout_responsive_grids():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.tag-admin-head\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s*auto",
        css,
        re.S,
    )
    assert re.search(r"\.tag-admin-fields\s*\{[^}]*auto-fit", css, re.S)
    assert ".tag-admin-tree" in css


def test_admin_dashboard_layout_present():
    html = read_text("static/templates/admin_images.html.j2")
    assert "page-admin-dashboard" in html
    assert "admin-controls-card" in html
    assert "data-admin-pagination" in html
    assert "data-admin-page-prev" in html
    assert "data-admin-page-next" in html
    assert "data-admin-page-summary" in html
    assert "data-admin-page-input" in html
    assert "data-admin-page-jump" in html
    assert "data-admin-grid data-masonry" not in html


def test_admin_images_top_pagination_present():
    html = read_text("static/templates/admin_images.html.j2")
    assert "data-admin-pagination-top" in html
    assert html.count("data-admin-page-jump") >= 2
    js = read_text("static/js/admin.js")
    assert "data-admin-pagination-top" in js


def test_admin_image_cards_default_open():
    js = read_text("static/js/admin.js")
    assert "admin-card-editor" in js
    assert "class=\"card-body\"" in js
    assert "class=\"meta\"" in js
    assert "data-masonry-item" in js
    assert "class=\"tags\"" in js
    assert "admin-card-summary" not in js
    css = read_text("static/styles/gallery.css")
    assert ".admin-card-editor" in css


def test_admin_images_pagination_jump_present():
    js = read_text("static/js/admin.js")
    assert "data-admin-page-input" in js
    assert "jumpToPage" in js


def test_admin_tag_editor_present():
    html = read_text("static/templates/admin_upload.html.j2")
    assert "data-tag-editor" in html
    assert "data-tag-chips" in html
    js = read_text("static/js/admin.js")
    assert "initTagEditors" in js
    css = read_text("static/styles/gallery.css")
    assert ".tag-editor" in css
    assert ".tag-chip" in css


def test_admin_upload_tag_quick_panel_present():
    html = read_text("static/templates/admin_upload.html.j2")
    assert "admin-tag-quick-panel" in html
    assert "data-admin-tag-add" in html
    assert "data-admin-tags-hint" in html
    assert "data-admin-editor" in html
    assert "data-editor-mode=\"compact\"" in html


def test_admin_upload_tag_quick_styles_present():
    css = read_text("static/styles/gallery.css")
    assert ".admin-tag-quick-panel" in css
    assert ".tag-admin-row-compact" in css
    assert ".tag-quick-attach" in css
    assert ".tag-admin-shell-compact" in css


def test_admin_upload_tag_quick_attach_hook():
    js = read_text("static/js/admin.js")
    assert "data-tag-attach" in js
    assert "appendTagToUploadInput" in js


def test_admin_upload_tag_quick_mobile_density_rules():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media\s*\(max-width:\s*900px\)[\s\S]*admin-tag-quick-panel\.admin-surface[\s\S]*background:\s*transparent",
        css,
        re.S,
    )
    assert re.search(
        r"@media\s*\(max-width:\s*900px\)[\s\S]*admin-tag-quick-panel[\s\S]*tag-admin-row[\s\S]*border:\s*none",
        css,
        re.S,
    )


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
    assert 'href="/admin/dmca/"' in html


def test_admin_dmca_page_structure_present():
    html = read_text("static/templates/admin_dmca.html.j2")
    assert "page-admin-dmca" in html
    assert "data-admin-dmca-list" in html
    assert "data-admin-dmca-filter" in html
    assert "data-admin-dmca-refresh" in html
    assert 'href="/admin/dmca/"' in html
    assert 'href="/status/"' in html


def test_admin_home_status_strip_present():
    html = read_text("static/templates/admin.html.j2")
    assert "data-admin-status-bar" in html
    assert 'data-admin-status="images.total"' in html
    assert 'data-admin-status="disk"' in html
    assert 'data-admin-status="request_counts.api"' in html
    assert 'data-admin-status="request_counts.pages"' in html
    assert "data-admin-status-flag" in html
    assert "data-admin-user" in html
    assert "status-hide-xxl" in html
    assert "status-hide-xl" in html
    assert "status-hide-lg" in html
    assert "status-hide-md" in html
    assert "status-hide-sm" in html
    assert "status-hide-xs" in html


def test_admin_memory_status_uses_used_percent():
    js = read_text("static/js/admin.js")
    assert "formatMemory" in js
    assert "已用" in js
    assert "memory.available" in js
    assert re.search(r"used\s*=\s*Math\.max\(memory\.total\s*-\s*available", js)
    assert re.search(r"\(\$\{pct\}%\)", js)


def test_admin_home_status_styles_present():
    css = read_text("static/styles/gallery.css")
    assert ".admin-status-strip" in css
    assert ".admin-home-layout" in css
    assert ".admin-side-panel" in css
    assert re.search(r"\.admin-status-strip\s*\{[^}]*flex-wrap:\s*nowrap", css, re.S)
    assert re.search(r"\.admin-status-item\s*\{[^}]*min-width:\s*150px", css, re.S)


def test_admin_status_strip_fade_hint():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.admin-status-strip::after\s*\{[^}]*linear-gradient\(\s*90deg", css, re.S)
    assert re.search(r"\.admin-status-strip::after\s*\{[^}]*pointer-events:\s*none", css, re.S)
    assert re.search(
        r"@media\s*\(max-width:\s*1360px\)[\s\S]*?\.admin-status-strip::after\s*\{[^}]*opacity:\s*1",
        css,
        re.S,
    )


def test_admin_status_loader_present():
    js = read_text("static/js/admin.js")
    assert "loadAdminStatus" in js
    assert "/static/status.json" in js


def test_admin_disk_status_uses_free_space():
    js = read_text("static/js/admin.js")
    assert re.search(r"disk\.free", js)
    assert "剩余" in js


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
        r"body\.with-sidebar\s+\.admin-main\s*\{[^}]*padding:\s*24px\s+18px\s+40px;",
        css,
        re.S,
    )
    assert re.search(
        r"body\.with-sidebar\s+\.auth-main\s*\{[^}]*padding:\s*24px\s+18px\s+40px;",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.with-sidebar\s+\.admin-main[\s\S]*?padding:\s*14px\s+12px\s+32px;",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.with-sidebar\s+\.auth-main[\s\S]*?padding:\s*14px\s+12px\s+32px;",
        css,
        re.S,
    )


def test_admin_mobile_top_padding_compact():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.page-admin\s+main\s*\{[^}]*padding:\s*var\(--topbar-height\)\s+12px\s+32px;",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.page-admin\s+\.home-main\s*\{[^}]*padding-top:\s*0",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.page-admin\s+\.admin-main\s*\{[^}]*padding-top:\s*0",
        css,
        re.S,
    )


def test_admin_mobile_hero_stack():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.page-admin\s+\.admin-hero\s*\{[^}]*flex-direction:\s*column",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.page-admin\s+\.admin-hero\s*\{[^}]*align-items:\s*flex-start",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.page-admin\s+\.admin-hero-meta\s*\{[^}]*width:\s*100%",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.page-admin\s+\.admin-hero-meta\s*\{[^}]*text-align:\s*left",
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
    assert ".page-profile" in selector
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
    js = read_text("static/js/ui.js")
    assert "scrollHeight" in js
    assert "requestAnimationFrame" in js
    assert "relayoutGrid" in js


def test_masonry_relayout_resets_row_span_before_measure():
    js = read_text("static/js/ui.js")
    assert "setProperty('--row-span', '1')" in js


def test_masonry_ready_class_applied_after_layout():
    js = read_text("static/js/ui.js")
    assert "classList.add('masonry-ready')" in js


def test_masonry_ready_set_for_dynamic_pages():
    search_js = read_text("static/js/search.js")
    user_js = read_text("static/js/user.js")
    assert "masonry-ready" in search_js
    assert "masonry-ready" in user_js


def test_masonry_helper_shared_across_pages():
    ui_js = read_text("static/js/ui.js")
    assert "GalleryMasonry" in ui_js
    gallery_js = read_text("static/js/gallery.js")
    assert "GalleryMasonry" in gallery_js
    search_js = read_text("static/js/search.js")
    admin_js = read_text("static/js/admin.js")
    user_js = read_text("static/js/user.js")
    assert "GalleryMasonry" in search_js
    assert "GalleryMasonry" in admin_js
    assert "GalleryMasonry" in user_js


def test_tag_page_masonry_init():
    js = read_text("static/js/ui.js")
    assert "initTagPageMasonry" in js
    assert "page-tag" in js
    assert "data-masonry" in js


def test_tag_page_pagination_hooks_in_script():
    js = read_text("static/js/tag.js")
    assert "data-tag-page-prev" in js
    assert "data-tag-page-next" in js
    assert "data-tag-page-list" in js
    assert "data-tag-page-input" in js
    assert "data-tag-page-jump" in js
    assert "data-tag-gallery" in js


def test_tag_editor_toggle_hooked():
    js = read_text("static/js/ui.js")
    assert "data-tag-editor-toggle" in js


def test_masonry_refresh_supports_soft_items():
    js = read_text("static/js/ui.js")
    assert "opts.soft" in js
    assert "opts.items" in js
    assert "allowSoft" in js


def test_homepage_masonry_soft_refresh_on_append():
    js = read_text("static/js/gallery.js")
    assert "masonry.refresh({ soft: true" in js or "masonry.refresh({soft: true" in js


def test_back_to_top_button_present():
    js = read_text("static/js/ui.js")
    assert "back-to-top" in js
    assert "scrollTo({ top: 0" in js


def test_back_to_top_uses_upload_offset():
    css = read_text("static/styles/gallery.css")
    assert ".back-to-top" in css
    assert "var(--upload-progress-offset" in css
    js = read_text("static/js/ui.js")
    assert "--upload-progress-offset" in js


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
    assert "tags[tags.length - 1] = normalizedTag" in js


def test_tag_suggest_supports_alias_match_key():
    js = read_text("static/js/ui.js")
    assert "normalizeTagMatch" in js
    assert "aliasEntries" in js
    assert "matchKey.startsWith" in js
    assert "matchKey.includes" in js


def test_global_search_bar_present_on_core_pages():
    templates = [
        "static/templates/index.html.j2",
        "static/templates/detail.html.j2",
        "static/templates/search.html.j2",
        "static/templates/tags.html.j2",
        "static/templates/tag.html.j2",
        "static/templates/pages/favorites.html.j2",
        "static/templates/pages/my.html.j2",
        "static/templates/pages/profile.html.j2",
        "static/templates/pages/wiki.html.j2",
        "static/templates/pages/dmca.html.j2",
        "static/templates/legal.html.j2",
        "static/templates/status.html.j2",
        "static/templates/error.html.j2",
        "static/templates/maintenance.html.j2",
        "static/templates/404.html.j2",
    ]
    for template in templates:
        content = read_text(template)
        has_search = "data-search-host" in content or "data-search-open" in content
        assert has_search, template


def test_global_search_bar_hidden_on_auth_and_admin():
    templates = [
        "static/templates/admin.html.j2",
        "static/templates/admin_auth.html.j2",
        "static/templates/admin_collections.html.j2",
        "static/templates/admin_images.html.j2",
        "static/templates/admin_tags.html.j2",
        "static/templates/admin_upload.html.j2",
        "static/templates/auth_login.html.j2",
        "static/templates/auth_register.html.j2",
    ]
    for template in templates:
        content = read_text(template)
        has_search = "data-search-host" in content or "data-search-open" in content
        assert not has_search, template


def test_admin_filter_search_supports_suggest():
    html = read_text("static/templates/admin_images.html.j2")
    assert re.search(r"data-admin-query[^>]*data-search-input", html) or re.search(
        r"data-search-input[^>]*data-admin-query", html
    )


def test_status_page_uses_global_topbar():
    html = read_text("static/templates/status.html.j2")
    assert "data-theme-toggle" in html
    has_search = "data-search-host" in html or "data-search-open" in html
    assert has_search


def test_search_syntax_parser_present():
    js = read_text("static/js/search.js")
    assert "parseQuery" in js
    assert "width" in js and "height" in js and "bytes" in js
    assert "sort" in js


def test_search_alias_prefix_maps_to_tag():
    js = read_text("static/js/search.js")
    assert "resolveTagPrefix" in js
    assert "aliasPrefixCache" in js
    assert "normalizeTagMatch" in js
    assert "aliasKey.startsWith" in js


def test_wiki_page_template_exists():
    html = read_text("static/templates/pages/wiki.html.j2")
    assert "page-wiki" in html
    assert "wiki-tree" in html
    assert "data-wiki-content" in html
    assert "data-wiki-aside" in html
    assert "wiki.js" in html
    assert "data-wiki-toc-toggle" in html
    assert "data-wiki-toc-close" in html


def test_live2d_assets_in_shared_partials():
    theme = read_text("static/templates/partials/theme_init.html.j2")
    sidebar = read_text("static/templates/partials/sidebar_default.html.j2")
    assert "live2d/css/live2d.css" in theme
    assert "id=\"landlord\"" in sidebar


def test_wiki_page_uses_sidebar_layout():
    html = read_text("static/templates/pages/wiki.html.j2")
    assert "data-left-sidebar" in html
    assert "wiki-static-sidebar" in html


def test_wiki_mobile_toc_styles():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.page-wiki\s+\.wiki-static-sidebar[\s\S]*position:\s*fixed",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.wiki-shell\s*\{[^}]*grid-template-columns:\s*1fr",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.sidebar-collapsed\s+\.wiki-shell[\s\S]*grid-template-columns:\s*1fr",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.page-wiki\.wiki-toc-open\s+\.wiki-static-sidebar",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.page-wiki\s+\.wiki-toc-fab",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.page-wiki\s+\.back-to-top[\s\S]*bottom:\s*calc\(",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.page-wiki\s+\.back-to-top[\s\S]*right:\s*16px",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.page-wiki\s+\.back-to-top[\s\S]*width:\s*44px",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.page-wiki\s+\.wiki-toc-dim",
        css,
        re.S,
    )


def test_wiki_medium_toc_styles():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 900px\)[\s\S]*?\.wiki-shell\s*\{[^}]*grid-template-columns:\s*var\(--sidebar-width\)\s+minmax\(0,\s*1fr\)",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 900px\)[\s\S]*?body\.page-wiki\s+\.wiki-static-sidebar[\s\S]*position:\s*fixed",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 900px\)[\s\S]*?body\.page-wiki\s+\.wiki-toc-fab",
        css,
        re.S,
    )


def test_wiki_mobile_toc_script():
    js = read_text("static/js/wiki.js")
    assert "wiki-toc-open" in js
    assert "data-wiki-toc-toggle" in js


def test_wiki_two_sidebar_layout_styles():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.wiki-shell\s*\{[^}]*grid-template-columns:\s*var\(--sidebar-width\)\s+var\(--detail-sidebar-width\)\s+minmax\(0,\s*1fr\)",
        css,
        re.S,
    )
    assert re.search(
        r"\.wiki-static-sidebar\s*\{[^}]*align-self:\s*stretch",
        css,
        re.S,
    )
    assert re.search(
        r"\.wiki-static-sidebar\s*\{[^}]*position:\s*fixed",
        css,
        re.S,
    )
    assert re.search(
        r"\.wiki-static-sidebar\s*\{[^}]*top:\s*var\(--topbar-height\)",
        css,
        re.S,
    )
    assert re.search(
        r"\.wiki-static-sidebar\s*\{[^}]*left:\s*var\(--sidebar-width\)",
        css,
        re.S,
    )
    assert re.search(
        r"\.wiki-static-sidebar\s*\{[^}]*height:\s*calc\(100vh\s*-\s*var\(--topbar-height\)\)",
        css,
        re.S,
    )
    assert re.search(
        r"body\.sidebar-collapsed\s+\.wiki-static-sidebar[\s\S]*left:\s*18px",
        css,
        re.S,
    )
    assert re.search(
        r"\.wiki-toc-panel\s*\{[^}]*position:\s*sticky",
        css,
        re.S,
    )


def test_wiki_heading_anchor_offset():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.wiki-article\s+h1[\s\S]*scroll-margin-top:\s*calc\(var\(--topbar-height\)\s*\+\s*12px\)",
        css,
        re.S,
    )


def test_masonry_ready_waits_for_images_or_timeout():
    js = read_text("static/js/ui.js")
    assert "img.complete" in js
    assert "addEventListener('error'" in js
    assert "MASONRY_READY_TIMEOUT" in js


def test_detail_favorite_loading_state_present():
    js = read_text("static/js/user.js")
    assert "is-loading" in js
    assert "加载中" in js


def test_detail_favorite_loading_style():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.detail-action-toggle\.is-loading\s*\{[^}]*cursor:\s*progress", css, re.S)


def test_favorites_page_template_exists():
    html = read_text("static/templates/pages/favorites.html.j2")
    assert "page-favorites" in html
    assert "我的收藏" in html
    assert "gallery.css" in html


def test_profile_page_template_exists():
    html = read_text("static/templates/pages/profile.html.j2")
    assert "page-profile" in html
    assert "data-profile-page" in html
    assert "/static/js/profile.js" in html


def test_profile_js_wires_avatar_cropper():
    js = read_text("static/js/profile.js")
    assert "data-avatar-cropper" in js
    assert "data-avatar-handle" in js
    assert "readAsDataURL" in js
    assert "/api/user/profile" in js
    assert "/api/user/avatar" in js


def test_profile_dense_layout_present():
    html = read_text("static/templates/pages/profile.html.j2")
    assert "profile-board" in html
    assert "profile-name-line" in html
    assert "profile-tabs" in html
    assert "profile-flow" in html
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.profile-tabs\s*\{[^}]*border-bottom", css, re.S)
    assert re.search(r"\.profile-flow\s*\{[^}]*display:\s*grid", css, re.S)
    assert re.search(r"\.profile-field\s*\{[^}]*grid-template-columns:\s*80px", css, re.S)


def test_profile_header_links_removed():
    html = read_text("static/templates/pages/profile.html.j2")
    assert "profile-header-links" not in html
    assert "profile-header-main" in html
    assert "profile-header-stats" in html


def test_profile_header_main_grid_rule():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.profile-header-main\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(0,\s*220px\)",
        css,
        re.S,
    )


def test_dmca_page_template_exists():
    html = read_text("static/templates/pages/dmca.html.j2")
    assert "page-dmca" in html
    assert "版权/侵权删除申请" in html
    assert "我保证以上提供的信息是真实准确的" in html
    assert "每次仅受理一张作品" in html
    assert "多张链接不予处理" in html
    assert "action=\"/api/dmca\"" in html
    assert "data-dmca-status" in html
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


def test_gallery_auto_rows_only_for_masonry():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.gallery\[data-masonry\]\s*\{[^}]*grid-auto-rows:\s*8px", css, re.S)
    assert not re.search(r"\.gallery\s*\{[^}]*grid-auto-rows", css, re.S)


def test_mobile_gallery_non_masonry_spacing():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.gallery:not\(\[data-masonry\]\)\s*\{[^}]*margin-top:\s*10px",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?body\.sidebar-collapsed\s+\.home-main[\s\S]*padding-left:\s*0",
        css,
        re.S,
    )


def test_mobile_detail_orders_media_before_meta():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.detail-main\s*\{[^}]*order:\s*0",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.detail-static-sidebar\s*\{[^}]*order:\s*1",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*?\.detail-static-sidebar\s*\{[^}]*border-top:\s*1px",
        css,
        re.S,
    )


def test_footer_present_on_homepage():
    html = read_text("static/templates/index.html.j2")
    assert "site-footer" in html


def test_homepage_layout_has_sidebars():
    index = read_text("static/templates/index.html.j2")
    topbar = read_text("static/templates/partials/topbar.html.j2")
    sidebar = read_text("static/templates/partials/sidebar_default.html.j2")
    assert "page-home with-sidebar" in index
    assert "data-left-sidebar" in index
    assert "data-left-sidebar" in sidebar
    assert "data-avatar-toggle" in topbar
    assert "avatar-caret" in topbar
    assert "data-live2d-toggle" in sidebar
    assert "search-icon" in topbar


def test_homepage_sidebar_dimmer_present():
    topbar = read_text("static/templates/partials/topbar.html.j2")
    assert "data-sidebar-dim" in topbar


def test_homepage_sidebar_has_copyright_notice():
    sidebar = read_text("static/templates/partials/sidebar_default.html.j2")
    assert "site.copyright_year" in sidebar
    assert "site.copyright_holder" in sidebar
    assert "href=\"/dmca/\"" in sidebar
    assert "侵权请" in sidebar


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


def test_tag_page_editor_toggle_present():
    html = read_text("static/templates/tag.html.j2")
    assert "data-tag-editor-toggle" in html
    assert "id=\"tag-editor-panel\"" in html
    assert "data-tag-editor" in html


def test_tag_page_pagination_markup_present():
    html = read_text("static/templates/tag.html.j2")
    assert "data-tag-pagination-top" in html
    assert "data-tag-pagination" in html
    assert "data-tag-page-prev" in html
    assert "data-tag-page-next" in html
    assert "data-tag-page-list" in html
    assert "data-tag-page-summary" in html
    assert "data-tag-page-input" in html
    assert "data-tag-page-jump" in html


def test_tag_page_pagination_script_loaded():
    html = read_text("static/templates/tag.html.j2")
    assert "/static/js/tag.js" in html
    assert "/static/js/gallery.js" not in html


def test_tag_page_has_masonry_marker():
    html = read_text("static/templates/tag.html.j2")
    assert "data-masonry" in html
    assert "image.tags[:1]" in html


def test_tag_page_js_limits_tags():
    js = read_text("static/js/tag.js")
    assert "slice(0, 1)" in js


def test_tag_page_orientation_size_labels_literal():
    html = read_text("static/templates/tag.html.j2")
    assert '"portrait": "竖屏"' in html
    assert '"landscape": "横屏"' in html
    assert '"square": "方形"' in html
    assert '"ultra": "超清"' in html
    assert '"large": "高清"' in html
    assert '"medium": "中等"' in html
    assert '"compact": "轻量"' in html


def test_tag_page_tags_not_clamped():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.page-tag\s+\.tags\s*\{[^}]*max-height:\s*none", css, re.S)


def test_homepage_live2d_toggle_before_wiki_heading():
    sidebar = read_text("static/templates/partials/sidebar_default.html.j2")
    toggle_idx = sidebar.find("data-live2d-toggle")
    wiki_idx = sidebar.find("Wiki / status")
    assert toggle_idx != -1
    assert wiki_idx != -1
    assert toggle_idx < wiki_idx


def test_homepage_sidebar_tags_removed():
    sidebar = read_text("static/templates/partials/sidebar_default.html.j2")
    assert "side-tags" not in sidebar
    assert "side-tag" not in sidebar


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
        r"@media \(max-width: 900px\)[\s\S]*\.wiki-shell\s*\{[^}]*grid-template-columns:\s*1fr",
        css,
        re.S,
    )


def test_mobile_sidebar_drawer_styles_present():
    css = read_text("static/styles/gallery.css")
    assert "--sidebar-close-color: #111111" in css
    assert re.search(r":root\[data-theme=\"dark\"\][\s\S]*--sidebar-close-color:\s*#ffffff", css, re.S)
    assert re.search(r"\.sidebar-dim\s*\{", css)
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*body\.sidebar-open\s+\.sidebar-dim",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*html\.sidebar-open\s*\{",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*html\.sidebar-open\s+body\.sidebar-open",
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
        r"@media \(max-width: 640px\)[\s\S]*body\.with-sidebar\s+main[\s\S]*z-index:\s*auto",
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
        r"@media \(max-width: 640px\)[\s\S]*body\.sidebar-open\s+\.left-sidebar",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*body\.sidebar-open\s+\.sidebar-close",
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
    topbar = read_text("static/templates/partials/topbar.html.j2")
    assert "sidebar-close" in topbar
    assert "aria-label=\"关闭侧栏\"" in topbar


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


def test_search_suggest_renders_alias_hint():
    js = read_text("static/js/ui.js")
    assert "alias && alias !== tag" in js
    assert "->" in js


def test_search_suggest_accepts_plain_tokens():
    js = read_text("static/js/ui.js")
    assert "parseSearchSuggestToken" in js
    assert "buildTagSuggestions" in js
    assert "includeAlias: true" in js


def test_detail_full_mode_clamps_to_available_width():
    js = read_text("static/js/ui.js")
    assert "fitWidth > availableWidth" in js
    assert "fitWidth = availableWidth" in js


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
    assert 'name="remember_device"' in login_html
    assert 'data-auth-remember' in login_html
    assert 'name="session_days"' in login_html
    assert "记住本设备登录状态" in login_html
    assert "用户协议" in login_html
    assert "隐私政策" in login_html
    for value in ("1", "7", "30", "60"):
        assert f'value="{value}"' in login_html


def test_auth_login_js_supports_session_days():
    js = read_text("static/js/auth.js")
    assert "session_days" in js
    assert "remember_device" in js
    assert "/auth/login" in js


def test_legal_page_has_tos_and_privacy_sections():
    html = read_text("static/templates/legal.html.j2")
    assert 'id="tos"' in html
    assert 'id="privacy"' in html
    assert "用户协议" in html
    assert "隐私政策" in html
    assert "版权通知" in html


def test_error_pages_have_apology_and_figure():
    templates = [
        "static/templates/404.html.j2",
        "static/templates/error.html.j2",
        "static/templates/maintenance.html.j2",
    ]
    for template in templates:
        html = read_text(template)
        assert "error-figure" in html
        assert "/static/images/error-figure.jpg" in html
        assert "很抱歉" in html
        assert "提示" in html


def test_error_figure_asset_exists():
    assert (BASE_DIR / "static" / "images" / "error-figure.jpg").exists()


def test_error_page_scale_excludes_sidebar_layout():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.page-error\.with-sidebar\s*\{[^}]*--error-scale:\s*1", css, re.S)
    assert re.search(
        r"@media \(min-width: 1200px\)[\s\S]*\.page-error:not\(\.with-sidebar\)\s*\{",
        css,
        re.S,
    )


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
    sidebar = read_text("static/templates/partials/sidebar_default.html.j2")
    assert 'href="/admin/"' in sidebar
    assert 'href="/admin/tags/"' in sidebar
    assert 'href="/status/"' in sidebar
    assert "data-admin-entry" in sidebar
    templates = [
        "static/templates/index.html.j2",
        "static/templates/search.html.j2",
        "static/templates/tags.html.j2",
        "static/templates/tag.html.j2",
        "static/templates/auth_login.html.j2",
        "static/templates/auth_register.html.j2",
        "static/templates/pages/my.html.j2",
    ]
    for template in templates:
        content = read_text(template)
        assert "data-admin-entry" in content


def test_admin_tags_filters_present():
    content = read_text("static/templates/admin_tags.html.j2")
    assert "data-admin-tag-search" in content
    assert "data-admin-tag-type-filter" in content
    assert "data-admin-tag-sort" in content
    assert "data-admin-tag-show-empty" in content
    assert "data-admin-tag-page-size" in content
    assert "data-admin-tag-page-info" in content
    assert "data-admin-tag-shell" in content
    assert "data-admin-editor" in content
    assert "data-admin-editor-back" in content
    assert "data-admin-type-toggle" in content


def test_user_avatar_placeholder_in_topbars():
    topbar = read_text("static/templates/partials/topbar.html.j2")
    assert "data-user-avatar" in topbar
    assert "data-user-avatar-img" in topbar
    assert "data-auth-login-link" in topbar
    assert "data-auth-register-link" in topbar
    assert "data-auth-user-link" in topbar
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


def test_hidden_attribute_overrides_display():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\[hidden\]\s*\{[^}]*display:\s*none", css, re.S)


def test_mobile_topnav_scrolls():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media\s*\(max-width:\s*640px\)[\s\S]*?\.topnav\s*\{[\s\S]*?overflow-x:\s*auto",
        css,
    )


def test_homepage_mobile_gallery_is_auto_fill():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s+\.gallery\s*\{[^}]*grid-template-columns:\s*repeat\(auto-fill,\s*minmax\(156px,\s*1fr\)\)",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s+\.gallery\s*\{[^}]*gap:\s*12px",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s+\.gallery\s*\{[^}]*padding:\s*0\s+6px",
        css,
        re.S,
    )


def test_homepage_mobile_card_density_tokens():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"@media \(max-width: 640px\)[\s\S]*\.page-home\s*\{[^}]*--card-thumb-max:\s*260px",
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


def test_homepage_tag_strip_has_data_hook():
    html = read_text("static/templates/index.html.j2")
    assert "data-tag-strip-list" in html


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


def test_homepage_filters_scale_smoothly():
    css = read_text("static/styles/gallery.css")
    assert re.search(
        r"\.page-home\s+\.controls\s*\{[^}]*--home-filter-font:\s*clamp",
        css,
        re.S,
    )
    assert re.search(
        r"\.page-home\s+\.controls\s*\{[^}]*--home-filter-pill-font:\s*clamp",
        css,
        re.S,
    )
    assert re.search(
        r"\.page-home\s+\.tab\s*\{[^}]*font-size:\s*var\(--home-filter-font\)",
        css,
        re.S,
    )
    assert re.search(
        r"\.page-home\s+\.filter-group\s+\.label\s*\{[^}]*font-size:\s*var\(--home-filter-font\)",
        css,
        re.S,
    )
    assert re.search(
        r"\.page-home\s+\.filter-pills\s+\.pill\s*\{[^}]*font-size:\s*var\(--home-filter-pill-font\)",
        css,
        re.S,
    )
    assert re.search(
        r"\.page-home\s+\.filter-pills\s+\.pill\s*\{[^}]*padding:\s*var\(--home-filter-pill-pad-y\)\s+var\(--home-filter-pill-pad-x\)",
        css,
        re.S,
    )


def test_homepage_tag_strip_label_no_wrap():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.tag-strip-label\s*\{[^}]*white-space:\s*nowrap", css, re.S)


def test_ui_handles_tag_strip_overflow():
    js = read_text("static/js/ui.js")
    assert "data-tag-strip-list" in js
    assert "tag-chip-more" in js
    assert "scrollWidth" in js


def test_upload_progress_styles():
    css = read_text("static/styles/gallery.css")
    assert ".upload-progress" in css
    assert ".upload-progress-fill" in css


def test_my_page_template_has_gallery_only():
    html = read_text("static/templates/pages/my.html.j2")
    assert "data-user-upload-form" not in html
    assert "data-user-gallery" in html


def test_upload_page_template_has_upload_form():
    upload_page = BASE_DIR / "static" / "templates" / "pages" / "upload.html.j2"
    if not upload_page.exists():
        pytest.skip("upload page template removed to avoid reserved path conflict")
    html = read_text("static/templates/pages/upload.html.j2")
    assert "data-user-upload-page" in html
    assert "data-user-upload-form" in html


def test_avatar_dropdown_has_user_upload_link():
    topbar = read_text("static/templates/partials/topbar.html.j2")
    upload_idx = topbar.find('href="/upload/"')
    my_idx = topbar.find('href="/my/"')
    assert upload_idx != -1
    assert my_idx != -1
    assert upload_idx < my_idx


def test_detail_page_has_editor_panel():
    html = read_text("static/templates/detail.html.j2")
    assert "data-image-editor" in html
    assert "data-image-uuid" in html
    assert "data-image-edit-toggle" in html
    assert "data-image-edit-close" in html
    assert re.search(r"<button[^>]*data-image-edit-toggle[^>]*detail-action-toggle", html) or re.search(
        r"<button[^>]*detail-action-toggle[^>]*data-image-edit-toggle", html
    )


def test_detail_page_has_tag_tree_panel():
    html = read_text("static/templates/detail.html.j2")
    assert "tag-groups" in html
    assert "tag-flat-list" in html
    assert "detail-static-sidebar" in html
    assert "data-left-sidebar" in html
    assert 'data-sidebar-default="collapsed"' in html
    assert "回到首页" not in html


def test_detail_page_uses_thumbnail_toggle():
    html = read_text("static/templates/detail.html.j2")
    assert "{% set thumb_src" in html
    assert "data-detail-image" in html
    assert "data-thumb-src" in html
    assert "data-full-src" in html
    assert "data-image-status" in html


def test_ui_supports_detail_image_toggle():
    js = read_text("static/js/ui.js")
    assert "data-detail-media" in js
    assert "data-detail-image" in js
    assert "data-image-status" in js
    assert "data-sidebar-default" in js


def test_tag_page_has_tree_toggle():
    html = read_text("static/templates/tag.html.j2")
    assert "data-tag-tree-toggle" in html
    assert "data-tag-tree-panel" in html


def test_ui_supports_tag_tree_toggle():
    js = read_text("static/js/ui.js")
    assert "data-tag-tree-toggle" in js
    assert "data-tag-tree-panel" in js


def test_tag_gallery_uses_masonry_grid():
    html = read_text("static/templates/tag.html.j2")
    assert 'class="gallery" data-masonry data-gallery-grid' in html
    assert "data-masonry-item" in html


def test_tag_js_initializes_gallery_masonry():
    js = read_text("static/js/tag.js")
    assert "window.GalleryMasonry ? window.GalleryMasonry.init(gallery)" in js
