"""Operator-controlled shell strings are assigned as text."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "psyfi_api" / "static" / "app.js"
PLAYER = ROOT / "psyfi_api" / "static" / "viz" / "experiencePlayer.js"


def test_operator_strings_are_not_interpolated_into_html() -> None:
    app = APP.read_text(encoding="utf-8")
    player = PLAYER.read_text(encoding="utf-8")
    for needle in (
        "${body.planner_text}",
        "${record.planner.planner_text}",
        "${record.title",
        "${data.note",
    ):
        assert needle not in app
    assert "createTextNode(` · ${record.preset || 'no preset'}`)" in app
    assert "textEl('strong', '', record.title || record.substance || 'journey')" in app
    assert "textEl('span', 'preset-name', preset.name)" in app
    assert "provenanceEl.innerHTML" not in app
    assert "this.provenanceEl.innerHTML" not in player
    assert "textEl('div', 'muted', body.planner_text)" in app
    assert "textEl('div', 'muted', record.planner.planner_text)" in app
    assert "Not medical advice." in player
    assert "parameters INFERRED" in player


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_text_helper_keeps_a_tag_as_characters() -> None:
    app = APP.read_text(encoding="utf-8")
    helper = app.split("function textEl", 1)[1].split("async function refreshHistory", 1)[0]
    script = """
const document = {
  createElement(tag) {
    return {
      tag,
      className: '',
      textContent: '',
      children: [],
      append(...nodes) { this.children.push(...nodes); },
    };
  },
  createTextNode(text) { return { text: String(text) }; },
};
""" + "function textEl" + helper + """
const note = textEl('div', 'muted', '<img src=x onerror=alert(1)>');
if (note.textContent !== '<img src=x onerror=alert(1)>') {
  throw new Error('tag was not kept as text: ' + note.textContent);
}
const line = provenanceLabeled('Experience', '<b>name</b>');
const shown = line.children.map((node) => node.textContent || node.text || '').join('');
if (shown !== 'Experience <b>name</b>') {
  throw new Error('provenance swallowed a tag: ' + shown);
}
"""
    completed = subprocess.run(
        ["node", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    for path in (APP, PLAYER):
        one = subprocess.run(
            ["node", "--check", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert one.returncode == 0, one.stderr
