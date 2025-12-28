from pathlib import Path

from test_pipeline import seed_test_root, setup_env


def test_extra_pages_auto_discovery(tmp_path: Path):
    seed_test_root(tmp_path)
    pages_tpl_dir = tmp_path / "static" / "templates" / "pages"
    pages_tpl_dir.mkdir(parents=True, exist_ok=True)
    (pages_tpl_dir / "about.html.j2").write_text(
        "<!doctype html><title>{{ site_name }}</title>",
        encoding="utf-8",
    )
    help_dir = pages_tpl_dir / "help"
    help_dir.mkdir(parents=True, exist_ok=True)
    (help_dir / "index.html.j2").write_text(
        "<!doctype html><title>Help</title>",
        encoding="utf-8",
    )

    pages_raw_dir = tmp_path / "static" / "pages"
    pages_raw_dir.mkdir(parents=True, exist_ok=True)
    (pages_raw_dir / "faq.html").write_text("<!doctype html>FAQ", encoding="utf-8")
    docs_dir = pages_raw_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "intro.html").write_text("<!doctype html>Intro", encoding="utf-8")

    modules = setup_env(tmp_path)
    static_site = modules["app.static_site"]

    staging_dir = static_site.build_site([])
    assert (staging_dir / "about" / "index.html").exists()
    assert (staging_dir / "help" / "index.html").exists()
    assert (staging_dir / "faq.html").exists()
    assert (staging_dir / "docs" / "intro.html").exists()

    sitemap = (staging_dir / "sitemap.xml").read_text(encoding="utf-8")
    assert "/about/" in sitemap
    assert "/help/" in sitemap
    assert "/faq.html" in sitemap
    assert "/docs/intro.html" in sitemap
