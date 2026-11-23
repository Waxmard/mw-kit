from __future__ import annotations

from pathlib import Path

import build_manifest


def _write_page(
    root: Path,
    *,
    scope: str = "universal",
    name: str = "tool.md",
    frontmatter: str | None = None,
    body: str = "\n# Tool\n",
    link_in_readme: bool = True,
) -> Path:
    scope_dir = root / scope
    scope_dir.mkdir(parents=True, exist_ok=True)
    readme = scope_dir / "README.md"
    if link_in_readme:
        readme.write_text(f"# {scope}\n\n- [{name}](./{name}) — desc\n")
    elif not readme.exists():
        readme.write_text(f"# {scope}\n")

    if frontmatter is None:
        frontmatter = (
            "---\n"
            "tool: tool\n"
            f"scope: {scope}\n"
            "tier: optional\n"
            'summary: "Example tool"\n'
            'targets: ["tool.toml"]\n'
            "---\n"
        )
    page = scope_dir / name
    page.write_text(frontmatter + body)
    return page


def test_live_playbook_is_valid() -> None:
    assert build_manifest.validate_playbook(build_manifest.PLAYBOOK) == []


def test_missing_frontmatter_key(tmp_path: Path) -> None:
    _write_page(
        tmp_path,
        frontmatter=(
            "---\ntool: tool\nscope: universal\ntier: optional\ntargets: []\n---\n"
        ),
    )
    errors = build_manifest.validate_playbook(tmp_path)
    assert any("summary" in e for e in errors)


def test_invalid_tier(tmp_path: Path) -> None:
    _write_page(
        tmp_path,
        frontmatter=(
            "---\n"
            "tool: tool\n"
            "scope: universal\n"
            "tier: experimental\n"
            'summary: "x"\n'
            'targets: ["a"]\n'
            "---\n"
        ),
    )
    errors = build_manifest.validate_playbook(tmp_path)
    assert any("tier" in e for e in errors)


def test_scope_mismatch_directory(tmp_path: Path) -> None:
    _write_page(
        tmp_path,
        scope="python",
        frontmatter=(
            "---\n"
            "tool: tool\n"
            "scope: node\n"
            "tier: optional\n"
            'summary: "x"\n'
            'targets: ["a"]\n'
            "---\n"
        ),
    )
    errors = build_manifest.validate_playbook(tmp_path)
    assert any("does not match dir" in e for e in errors)


def test_missing_from_scope_readme(tmp_path: Path) -> None:
    _write_page(tmp_path, link_in_readme=False)
    errors = build_manifest.validate_playbook(tmp_path)
    assert any("not linked in" in e for e in errors)


def test_broken_relative_link(tmp_path: Path) -> None:
    _write_page(tmp_path, body="\nSee [missing](./does-not-exist.md#sec).\n")
    errors = build_manifest.validate_playbook(tmp_path)
    assert any("broken relative link" in e for e in errors)


def test_fenced_semver_rules(tmp_path: Path) -> None:
    allowed_body = (
        "\n```yaml\n"
        'host = "127.0.0.1"\n'
        'version = "0.0.0"\n'
        'alt = "0.1.0"\n'
        "uses: actions/checkout@1.2.3\n"
        "pin = X.Y.Z  # v0.36.0\n"
        "```\n"
    )
    _write_page(tmp_path, body=allowed_body)
    assert build_manifest.validate_playbook(tmp_path) == []

    _write_page(tmp_path, body='\n```toml\nruff = "1.2.3"\n```\n')
    errors = build_manifest.validate_playbook(tmp_path)
    assert any("hardcoded semver '1.2.3'" in e for e in errors)
