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


# --- incremental-sync memory ----------------------------------------------


def _scoped_row(tool, page=None):
    return {"tool": tool, "page": page or f"python/{tool}.md"}


def test_load_state_absent_is_none(tmp_path: Path):
    assert scope.load_state(tmp_path) is None


def test_load_state_corrupt_is_none(tmp_path: Path):
    (tmp_path / scope.STATE_FILE).write_text("{not json")
    assert scope.load_state(tmp_path) is None


def test_load_state_wrong_schema_is_none(tmp_path: Path):
    (tmp_path / scope.STATE_FILE).write_text('{"schema": 99, "tools": {}}')
    assert scope.load_state(tmp_path) is None


def test_load_state_valid_round_trips(tmp_path: Path):
    (tmp_path / scope.STATE_FILE).write_text(
        '{"schema": 1, "playbook_commit": "abc", "tools": {}}'
    )
    state = scope.load_state(tmp_path)
    assert state is not None
    assert state["playbook_commit"] == "abc"


def test_annotate_state_no_state_marks_all_new():
    rows = [_scoped_row("ruff"), _scoped_row("mypy")]
    summary = scope.annotate_state(rows, None, "HEAD", changed_fn=lambda c, p: False)
    assert summary["present"] is False
    assert summary["new_tools"] == ["mypy", "ruff"]
    assert summary["all_settled"] is False
    assert rows[0]["state"] == {"decision": "new"}


def test_annotate_state_same_commit_is_settled_without_git():
    # decided at the current HEAD → page provably unchanged, changed_fn never called
    rows = [_scoped_row("ruff")]
    state = {
        "playbook_commit": "HEAD",
        "tools": {"ruff": {"decision": "synced", "playbook_commit": "HEAD"}},
    }

    def boom(commit, page):  # must not be consulted when commit == head
        raise AssertionError("changed_fn called for same-commit row")

    summary = scope.annotate_state(rows, state, "HEAD", changed_fn=boom)
    assert rows[0]["state"]["settled"] is True
    assert summary["settled_tools"] == ["ruff"]
    assert summary["all_settled"] is True
    assert summary["playbook_unchanged"] is True


def test_annotate_state_changed_page_is_stale():
    rows = [_scoped_row("lefthook", "universal/lefthook.md")]
    state = {
        "playbook_commit": "old",
        "tools": {"lefthook": {"decision": "synced", "playbook_commit": "old"}},
    }
    summary = scope.annotate_state(rows, state, "new", changed_fn=lambda c, p: True)
    assert rows[0]["state"]["settled"] is False
    assert rows[0]["state"]["page_changed_since_decision"] is True
    assert summary["stale_tools"] == ["lefthook"]


def test_annotate_state_declined_unchanged_stays_suppressed():
    # the decline-until-page-changes rule: declined + page unchanged → settled
    rows = [_scoped_row("tach", "optional/tach.md")]
    state = {
        "playbook_commit": "c",
        "tools": {
            "tach": {"decision": "declined", "playbook_commit": "c", "reason": "flat"}
        },
    }
    summary = scope.annotate_state(rows, state, "c", changed_fn=lambda c, p: False)
    assert rows[0]["state"]["settled"] is True
    assert rows[0]["state"]["reason"] == "flat"
    assert summary["settled_tools"] == ["tach"]


def test_annotate_state_missing_commit_assumes_changed():
    rows = [_scoped_row("uv")]
    state = {"tools": {"uv": {"decision": "override"}}}  # no playbook_commit recorded

    def boom(commit, page):  # changed_fn needs a commit to diff; must be skipped
        raise AssertionError("changed_fn called without a recorded commit")

    scope.annotate_state(rows, state, "HEAD", changed_fn=boom)
    assert rows[0]["state"]["settled"] is False
    assert rows[0]["state"]["page_changed_since_decision"] is True


def test_annotate_state_unknown_decision_never_settles():
    rows = [_scoped_row("ruff")]
    state = {
        "playbook_commit": "c",
        "tools": {"ruff": {"decision": "wat", "playbook_commit": "c"}},
    }
    scope.annotate_state(rows, state, "c", changed_fn=lambda c, p: False)
    assert rows[0]["state"]["settled"] is False  # only synced/declined/override settle
