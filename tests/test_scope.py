"""Unit tests for scope.py — the branchy, load-bearing logic the skill depends on.

Covers the pure functions (glob matching, structure detection, alternative
resolution) and scope_pages end-to-end with synthetic pages. The git/argparse/IO
shell in main() is left to the integration smoke run.
"""

from __future__ import annotations

from pathlib import Path

import scope

# --- glob helpers ---------------------------------------------------------


def test_expand_braces_single_group():
    assert scope.expand_braces("*.{ts,tsx}") == ["*.ts", "*.tsx"]


def test_expand_braces_no_group_is_identity():
    assert scope.expand_braces("**/*.py") == ["**/*.py"]


def test_detect_matches_doublestar_matches_root_and_nested():
    files = ["main.py", "pkg/sub/mod.py", "README.md"]
    assert scope.detect_matches("**/*.py", files) is True
    assert scope.detect_matches("**/*.py", ["only.md"]) is False


def test_detect_matches_brace_expansion():
    assert scope.detect_matches("**/*.{ts,tsx}", ["app/x.tsx"]) is True
    assert scope.detect_matches("**/*.{ts,tsx}", ["app/x.js"]) is False


def test_detect_matches_literal_path():
    assert scope.detect_matches(".gitlab-ci.yml", [".gitlab-ci.yml"]) is True
    assert scope.detect_matches(".gitlab-ci.yml", ["other.yml"]) is False


def test_target_present_file_dir_and_glob(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("x")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "workflows").mkdir()
    assert scope.target_present("pyproject.toml", tmp_path) is True
    assert scope.target_present(".github/workflows/", tmp_path) is True
    assert scope.target_present("missing.toml", tmp_path) is False
    assert scope.target_present(".github/*", tmp_path) is True


# --- as_list --------------------------------------------------------------


def test_as_list_coerces():
    assert scope.as_list(["a", "b"]) == ["a", "b"]
    assert scope.as_list("solo") == ["solo"]
    assert scope.as_list(None) == []
    assert scope.as_list("") == []


# --- structure detection --------------------------------------------------


def test_structure_single_project_root_manifest():
    s = scope.detect_structure(["pyproject.toml", "scripts/x.py"])
    assert s["verdict"] == "single_project"
    assert s["ambiguous"] is False


def test_structure_multi_component_sibling_manifests():
    s = scope.detect_structure(["api/pyproject.toml", "web/package.json"])
    assert s["verdict"] == "multi_component"
    assert s["ambiguous"] is False


def test_structure_nested_single_manifest_is_ambiguous():
    s = scope.detect_structure(["orchestrator/pyproject.toml"])
    assert s["verdict"] == "ambiguous"
    assert s["ambiguous"] is True


def test_structure_no_manifest_is_single():
    s = scope.detect_structure(["README.md", "docs/x.md"])
    assert s["verdict"] == "single_project"


# --- alternative resolution ----------------------------------------------


def test_dep_bot_gitlab_forces_renovate():
    assert scope._resolve_dep_bot("gitlab", set())[0] == "renovate"


def test_dep_bot_github_default_is_dependabot():
    assert scope._resolve_dep_bot("github", set())[0] == "dependabot"


def test_dep_bot_respects_configured_renovate():
    assert scope._resolve_dep_bot("github", {"renovate"})[0] == "renovate"


def test_release_github_single():
    out = scope._resolve_release("github", multi=False, is_py=False)
    assert out["chosen"] == "releases-github"
    assert "note" not in out


def test_release_github_monorepo_keeps_github_with_note():
    out = scope._resolve_release("github", multi=True, is_py=True)
    assert out["chosen"] == "releases-github"
    assert "note" in out  # the gitlab-only releases-monorepo page can't apply


def test_release_gitlab_monorepo_uses_monorepo_tool():
    out = scope._resolve_release("gitlab", multi=True, is_py=True)
    assert out["chosen"] == "releases-monorepo"


def test_release_gitlab_python_vs_plain():
    assert scope._resolve_release("gitlab", multi=False, is_py=True)["chosen"] == (
        "releases-python"
    )
    assert scope._resolve_release("gitlab", multi=False, is_py=False)["chosen"] == (
        "releases-gitlab"
    )


def test_release_unknown_platform_is_none():
    assert scope._resolve_release("unknown", multi=False, is_py=False)["chosen"] is None


def _row(tool, scope_, present=False):
    return {"tool": tool, "scope": scope_, "targets_present": ["x"] if present else []}


def test_resolve_alternatives_drops_losers():
    in_scope = [
        _row("dependabot", "universal"),
        _row("renovate", "universal"),
        _row("releases-github", "universal"),
    ]
    out = scope.resolve_alternatives(in_scope, "github", {"verdict": "single_project"})
    assert out["dep_updates"]["chosen"] == "dependabot"
    assert "renovate" in out["dropped"]
    assert out["releases"]["chosen"] == "releases-github"


# --- scope_pages end-to-end ----------------------------------------------


def _page(
    tool,
    scope_,
    *,
    tier="baseline",
    platform="",
    detect=None,
    detect_content=None,
    targets=None,
):
    return {
        "tool": tool,
        "_page": f"{scope_}/{tool}.md",
        "scope": scope_,
        "tier": tier,
        "platform": platform,
        "detect": detect or [],
        "detect_content": detect_content or [],
        "targets": targets or [],
    }


def test_scope_pages_platform_filter_and_detect(tmp_path: Path):
    pages = [
        _page("ruff", "python", detect=["**/*.py"], targets=["pyproject.toml"]),
        _page("biome", "node", detect=["package.json"]),
        _page("security", "universal", platform="github"),
        _page("gitlab-dedup", "universal", platform="gitlab"),
    ]
    (tmp_path / "pyproject.toml").write_text("x")
    tracked = ["scripts/x.py", "pyproject.toml"]
    out = scope.scope_pages(
        pages, tmp_path, tracked, "github", {"verdict": "single_project"}
    )
    tools = {r["tool"] for r in out["in_scope"]}
    assert "ruff" in tools  # detect matched + target present
    assert "security" in tools  # github page on github
    assert "biome" not in tools  # no package.json tracked
    assert "gitlab-dedup" not in tools  # gitlab page on github
    ruff = next(r for r in out["in_scope"] if r["tool"] == "ruff")
    assert ruff["targets_present"] == ["pyproject.toml"]


def test_detect_content_matches_yaml_body(tmp_path: Path):
    (tmp_path / "deploy.yaml").write_text("apiVersion: apps/v1\nkind: Deployment\n")
    (tmp_path / "values.yaml").write_text("replicas: 3\nimage: foo\n")
    tracked = ["deploy.yaml", "values.yaml", "README.md"]
    # matches the manifest, not the plain values file
    assert (
        scope.detect_content_matches([r"^kind:\s"], tmp_path, tracked)
        == r"content:^kind:\s"
    )


def test_detect_content_no_match_when_no_manifest(tmp_path: Path):
    (tmp_path / "values.yaml").write_text("replicas: 3\n")
    tracked = ["values.yaml"]
    assert scope.detect_content_matches([r"^kind:\s"], tmp_path, tracked) is None
    # empty patterns short-circuit
    assert scope.detect_content_matches([], tmp_path, tracked) is None


def test_scope_pages_content_detect_identifies_k8s_repo(tmp_path: Path):
    pages = [
        _page("kubeconform", "k8s", detect_content=[r"^kind:\s"]),
        _page("ruff", "python", detect=["**/*.py"]),
    ]
    (tmp_path / "svc.yaml").write_text("kind: Service\n")
    tracked = ["svc.yaml"]
    out = scope.scope_pages(
        pages, tmp_path, tracked, "gitlab", {"verdict": "single_project"}
    )
    tools = {r["tool"] for r in out["in_scope"]}
    assert "kubeconform" in tools  # content detect fired on the manifest
    assert "ruff" not in tools  # no .py files
    kc = next(r for r in out["in_scope"] if r["tool"] == "kubeconform")
    assert kc["matched_detect"] == r"content:^kind:\s"


def test_scope_pages_drops_monorepo_when_single_project(tmp_path: Path):
    pages = [_page("layout", "monorepo")]
    out = scope.scope_pages(
        pages, tmp_path, [], "github", {"verdict": "single_project"}
    )
    assert out["in_scope"] == []
    assert out["skipped"][0]["tool"] == "layout"


def test_scope_pages_platform_pending_when_unknown(tmp_path: Path):
    pages = [_page("security", "universal", platform="github")]
    out = scope.scope_pages(
        pages, tmp_path, [], "unknown", {"verdict": "single_project"}
    )
    assert out["in_scope"][0]["platform_pending"] is True
