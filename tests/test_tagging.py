from app.tagging import normalize_aliases, normalize_parents, normalize_tag, safe_tag_slug


def test_normalize_aliases_splits_fullwidth_delimiters():
    raw = "Flandre，フランドール、Alice;Bob|Carol"
    assert normalize_aliases(raw) == ["flandre", "フランドール", "alice", "bob", "carol"]


def test_normalize_parents_splits_fullwidth_delimiters():
    raw = "ParentA，ParentB、ParentC;ParentD|ParentE"
    assert normalize_parents(raw) == [
        "parenta",
        "parentb",
        "parentc",
        "parentd",
        "parente",
    ]


def test_normalize_tag_treats_underscore_as_space():
    assert normalize_tag("ai_work") == "ai work"
    assert normalize_tag("ai  work") == "ai work"


def test_safe_tag_slug_replaces_spaces_with_underscore():
    assert safe_tag_slug("ai work") == "ai_work"
