"""Repository/generated-link boundary regressions using synthetic files only."""
import pytest
from scripts.check_documentation_links import classify_link, markdown_targets, GENERATED_OUTPUTS

@pytest.fixture
def public_root(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("# Public guide\n")
    (tmp_path / "docs/guide.md").write_text("# Reproduction\n")
    return tmp_path, {"README.md", "docs/guide.md"}

def test_real_committed_file_and_heading(public_root):
    root, files = public_root
    assert classify_link(root, "docs/guide.md", "../README.md#public-guide", files) == "repository"
    with pytest.raises(ValueError, match="Missing Markdown heading"):
        classify_link(root, "docs/guide.md", "../README.md#missing", files)

def test_only_documented_generated_names_are_optional(public_root):
    root, files = public_root
    assert len(GENERATED_OUTPUTS) == 13
    for name in GENERATED_OUTPUTS:
        assert classify_link(root, "README.md", "results/phase5/" + name, files) == "generated"
    with pytest.raises(ValueError, match="Unexpected generated"):
        classify_link(root, "README.md", "results/phase5/unreviewed.zip", files)

@pytest.mark.parametrize("target", [
    "../private.md", "docs/../../private.md", "/etc/passwd", "C:/private",
    "docs/%2e%2e/private", "docs\\private", "docs/guide.md?raw=1",
    "javascript:alert(1)", "//private.example/file", "docs/\x00private",
])
def test_unsafe_targets_fail(public_root, target):
    root, files = public_root
    with pytest.raises(ValueError):
        classify_link(root, "README.md", target, files)

def test_missing_or_unapproved_files_fail(public_root):
    root, files = public_root
    (root / "not-approved.md").write_text("# Unreviewed")
    for target in ("missing.md", "not-approved.md"):
        with pytest.raises(ValueError, match="Missing or unapproved"):
            classify_link(root, "README.md", target, files)

def test_symlinks_fail_even_for_generated_outputs(public_root, tmp_path):
    root, files = public_root
    (root / "alias.md").symlink_to(root / "README.md")
    with pytest.raises(ValueError, match="Symlink"):
        classify_link(root, "README.md", "alias.md", files | {"alias.md"})
    (root / "results").symlink_to(root / "docs", target_is_directory=True)
    with pytest.raises(ValueError, match="Symlink"):
        classify_link(root, "README.md", "results/phase5/report.md", files)

def test_fenced_examples_are_not_live_markdown_links():
    text = "~~~md\n[example](not-a-real-file)\n~~~\n[guide](README.md)\n"
    assert list(markdown_targets(text)) == ["README.md"]
