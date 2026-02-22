from pathlib import Path


def test_release_ignore_has_critical_excludes():
    root = Path(__file__).resolve().parents[1]
    ignore = (root / "deploy" / ".releaseignore").read_text(encoding="utf-8")
    required = [
        "*.local.json",
        "storage/",
        "static/images/*.jpg",
        "static/images/*.png",
        "static/live2d/",
    ]
    for pattern in required:
        assert pattern in ignore


def test_deploy_templates_exist_and_have_placeholders():
    root = Path(__file__).resolve().parents[1]
    templates = [
        root / "deploy" / "nginx" / "potato_gallery.conf",
        root / "deploy" / "systemd" / "gallery-upload.service",
        root / "deploy" / "systemd" / "gallery-worker.service",
        root / "deploy" / "env" / "gallery_root.env",
        root / "deploy" / "cron" / "potato_gallery_maintenance",
        root / "deploy" / "cron" / "potato_gallery_requests",
    ]
    for path in templates:
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "__GALLERY_ROOT__" in text

    daily = (root / "deploy" / "cron" / "potato_gallery_maintenance").read_text(encoding="utf-8")
    assert "__CRON_DAILY__" in daily
    assert "__CRON_DAILY_USER__" in daily

    stats = (root / "deploy" / "cron" / "potato_gallery_requests").read_text(encoding="utf-8")
    assert "__CRON_STATS__" in stats
    assert "__CRON_STATS_USER__" in stats


def test_install_script_exists():
    root = Path(__file__).resolve().parents[1]
    install = root / "install.sh"
    assert install.exists()
    text = install.read_text(encoding="utf-8")
    assert "deploy_auto.sh" in text
