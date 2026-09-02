from app.main import resolve_within


def test_resolve_within_allows_a_normal_file(tmp_path):
    base = tmp_path / "dist"
    base.mkdir()
    (base / "index.html").write_text("ok")

    assert resolve_within(base, "index.html") == (base / "index.html").resolve()


def test_resolve_within_allows_a_nested_file(tmp_path):
    base = tmp_path / "dist"
    (base / "_nuxt").mkdir(parents=True)
    (base / "_nuxt" / "app.js").write_text("ok")

    assert resolve_within(base, "_nuxt/app.js") == (base / "_nuxt" / "app.js").resolve()


def test_resolve_within_blocks_dot_dot_traversal(tmp_path):
    base = tmp_path / "dist"
    base.mkdir()
    secret = tmp_path / ".env"
    secret.write_text("SECRET_KEY=nope")

    assert resolve_within(base, "../.env") is None
    assert resolve_within(base, "../../../.env") is None


def test_resolve_within_blocks_absolute_path_escape(tmp_path):
    base = tmp_path / "dist"
    base.mkdir()

    # pathlib treats an absolute operand to `/` as replacing the base entirely — this must
    # still be caught by the containment check, not silently served.
    assert resolve_within(base, str(tmp_path / ".env")) is None
