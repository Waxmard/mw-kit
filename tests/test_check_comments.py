from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

PAGE = Path(__file__).resolve().parents[1] / "playbook/universal/no-comments.md"


@pytest.fixture(scope="module")
def checker(tmp_path_factory: pytest.TempPathFactory) -> ModuleType:
    block = re.search(r"```python\n(.*?)\n```", PAGE.read_text(encoding="utf-8"), re.S)
    assert block is not None
    script = tmp_path_factory.mktemp("page") / "check_comments.py"
    script.write_text(block.group(1) + "\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("check_comments", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_regex_literals_are_not_comments(checker: ModuleType) -> None:
    scan = checker.scan_js_comments
    assert scan("const a = /^x\\//i.test(b) ? 1 : 2; // real\n") == [(1, "// real")]
    assert scan("x = [/[/]\\/\\//, 1]; // c\n") == [(1, "// c")]
    assert scan("return /a\\/\\/b/.test(s);\n") == []
    assert scan('v.map((s) =>\n  /[",]/.test(s) ? `"${s}"` : s);\nf("//x");\n') == []


def test_division_and_strings_are_not_regex(checker: ModuleType) -> None:
    scan = checker.scan_js_comments
    assert scan("const r = a / b / c; /* k */\n") == [(1, "/* k */")]
    assert scan("const u = 'https://x.y'; const v = `a // b`;\n") == []


def test_svelte_script_style_and_markup(checker: ModuleType) -> None:
    source = (
        '<script lang="ts" generics="T extends Map<string, number>">\n'
        "  // one\n"
        "  const r = /\\/\\//;\n"
        "</script>\n"
        "\n"
        "<!-- two -->\n"
        "<p>don't // flag</p>\n"
        "<style>\n"
        "  /* three */\n"
        "  a { background: url(https://x.y/z.png); }\n"
        "</style>\n"
    )
    assert [line for line, _ in checker.scan_svelte_comments(source)] == [2, 6, 9]


def test_keep_list(checker: ModuleType) -> None:
    kept = checker.is_kept
    assert kept("// ponytail: flat guess; price per species if totals mislead")
    assert kept("<!-- prettier-ignore -->")
    assert kept("// biome-ignore format: table")
    assert kept("#!/usr/bin/env python3")
    assert not kept("// note")
    assert not kept("<!-- svelte-ignore a11y_click_events_have_key_events -->")
    assert not kept("// biome-ignore lint/style/noNonNullAssertion: x")
    assert not kept("// eslint-disable-next-line no-empty")
