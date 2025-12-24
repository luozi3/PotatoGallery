from pathlib import Path
import re


BASE_DIR = Path("/opt/PotatoGallery")


def read_text(rel_path: str) -> str:
    return (BASE_DIR / rel_path).read_text(encoding="utf-8")


def test_theme_toggle_after_brand():
    templates = [
        "static/templates/index.html.j2",
        "static/templates/detail.html.j2",
        "static/templates/search.html.j2",
        "static/templates/tags.html.j2",
        "static/templates/tag.html.j2",
        "static/templates/status.html.j2",
        "static/templates/admin.html.j2",
        "static/templates/admin_tags.html.j2",
    ]
    for template in templates:
        content = read_text(template)
        brand_idx = content.find('class="brand"')
        toggle_idx = content.find("data-theme-toggle")
        assert brand_idx != -1 and toggle_idx != -1, template
        assert brand_idx < toggle_idx, template


def test_controls_use_theme_panel_background():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.controls\s*\{[^}]*background:\s*var\(--panel\)", css, re.S)


def test_primary_button_uses_theme_gradient():
    css = read_text("static/styles/gallery.css")
    assert re.search(r"\.btn\.primary\s*\{[^}]*var\(--accent-2\)", css, re.S)


def test_live2d_message_path_absolute():
    js = read_text("static/live2d/live2d/js/message.js")
    assert "var message_Path = '/static/live2d/live2d/';" in js


def test_masonry_relayout_uses_scrollheight():
    js = read_text("static/js/gallery.js")
    assert "scrollHeight" in js
    assert "requestAnimationFrame(relayoutMasonry)" in js


def test_footer_present_on_homepage():
    html = read_text("static/templates/index.html.j2")
    assert "site-footer" in html
