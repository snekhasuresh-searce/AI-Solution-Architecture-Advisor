from advisor.catalogue import is_known, unknown_choices


def test_known_and_unknown():
    assert is_known("Next.js")
    assert is_known("React with Next.js")
    assert is_known("Cloud Run (min 1 instance)")
    assert not is_known("Reactor")
    assert unknown_choices(["PostgreSQL", "FooDB"]) == ["FooDB"]
