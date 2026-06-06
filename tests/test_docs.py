from pathlib import Path


def test_deploy_docs_exist():
    root = Path(__file__).resolve().parents[1]
    manual = root / "docs" / "deploy_manual.md"
    auto = root / "docs" / "deploy_auto.md"
    assert manual.exists()
    assert auto.exists()
    assert manual.read_text(encoding="utf-8").strip()
    assert auto.read_text(encoding="utf-8").strip()


def test_readme_mentions_deploy_docs():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "docs/deploy_manual.md" in readme
    assert "docs/deploy_auto.md" in readme
    # 域名已从 README 中移除（安全审计）
    # assert "https://luozi.de5.net/" in readme
    assert readme.find("docs/deploy_auto.md") < readme.find("docs/deploy_manual.md")


def test_auto_deploy_doc_mentions_scripts():
    root = Path(__file__).resolve().parents[1]
    text = (root / "docs" / "deploy_auto.md").read_text(encoding="utf-8")
    assert "bin/build_release.sh" in text
    assert "bin/deploy_auto.sh" in text
    assert "./install.sh" in text


def test_manual_deploy_marked_not_recommended():
    root = Path(__file__).resolve().parents[1]
    text = (root / "docs" / "deploy_manual.md").read_text(encoding="utf-8")
    assert "不推荐" in text
