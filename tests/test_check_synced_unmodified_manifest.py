"""check_synced_unmodified.py reads two lists from the HUB's live manifest (W-5feb6e9c).

Every project copy of the check reads `/opt/fabrik/scripts/fabrik_synced_manifest.py` — no project
holds a copy — so a hub rename of either symbol reaches every project gate at once (51 copies
under /opt, 2026-10-18). The old `from fabrik_synced_manifest import X` / `except ImportError` read
a MISSING SYMBOL exactly like a missing module (both raise ImportError, both with
`name == 'fabrik_synced_manifest'`) and ran the check with empty lists: reds blamed on the project,
with no word about the hub. These tests drive `main()` in-process against a fake hub and a fake
project; the last one loads THIS tree's manifest through the check's own loader.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import runpy
import sys
import types
from pathlib import Path

import pytest

_CHECK = Path(__file__).resolve().parents[1] / "scripts/enforcement/check_synced_unmodified.py"

_FULL_MANIFEST = (
    'SEEDED_NOT_ENFORCED = {"PORTS.md"}\nRETIRED_VENDORED_DIRS = ["libs/retired_mod"]\n'
)
_HUB_WORDS = "the HUB's defect, not this project's"
_PROJECT_BLAME = "You edited a synced copy"


def _load_check():
    spec = importlib.util.spec_from_file_location("check_synced_unmodified_under_test", _CHECK)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _md5(text: str) -> str:
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


def _run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    manifest: str | None,
    files: dict[str, str],
    lock: dict[str, str],
    *,
    hub_exists: bool = True,
) -> int:
    """Run the check with a fake hub (`manifest` None = no manifest file; `hub_exists` False = no
    hub directory at all, the VPS case) and a fake project."""
    hub = tmp_path / "hub"
    if hub_exists:
        (hub / "scripts").mkdir(parents=True)
    if manifest is not None:
        (hub / "scripts" / "fabrik_synced_manifest.py").write_text(manifest, encoding="utf-8")
    project = tmp_path / "project"
    (project / ".fabrik").mkdir(parents=True)
    for rel, text in files.items():
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_text(text, encoding="utf-8")
    (project / ".fabrik" / "synced.lock").write_text(json.dumps(lock), encoding="utf-8")

    check = _load_check()
    monkeypatch.setattr(check, "FABRIK_ROOT", hub)
    monkeypatch.setattr(sys, "argv", ["check", "--project-root", str(project)])
    return check.main()


@pytest.mark.parametrize("missing", ["SEEDED_NOT_ENFORCED", "RETIRED_VENDORED_DIRS"])
def test_a_manifest_missing_a_symbol_fails_red_naming_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    missing: str,
) -> None:
    manifest = "".join(
        line + "\n" for line in _FULL_MANIFEST.splitlines() if not line.startswith(missing)
    )
    # PORTS.md is edited: under the old swallow a seeded rename flagged it as the PROJECT's edit.
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    rc = _run(monkeypatch, tmp_path, manifest, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, f"a manifest without {missing} must red the check, not degrade it:\n{out}"
    assert missing in out, out
    assert _HUB_WORDS in out, out
    assert _PROJECT_BLAME not in out, f"the red must name the hub, not blame the project:\n{out}"
    # The check's own refusal passes as raised, never re-wrapped as a load failure of itself.
    assert "failed to load" not in out, out


def test_a_manifest_that_fails_to_load_fails_red(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = "import a_module_that_does_not_exist_w5feb6e9c\n" + _FULL_MANIFEST
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    rc = _run(monkeypatch, tmp_path, manifest, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "a_module_that_does_not_exist_w5feb6e9c" in out, out
    assert _HUB_WORDS in out, out
    assert _PROJECT_BLAME not in out, out


def test_an_absent_manifest_file_degrades_and_names_the_hub_beside_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    rc = _run(monkeypatch, tmp_path, None, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out  # empty lists: the edited seeded file reads as drift, as before
    assert "PORTS.md" in out, out
    assert "hub manifest" in out and "is missing" in out, out


def test_an_absent_hub_degrades_with_no_hub_note(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No `/opt/fabrik` at all (a VPS): empty lists, drift reported plainly, no hub note."""
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    rc = _run(monkeypatch, tmp_path, None, files, lock, hub_exists=False)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "PORTS.md" in out, out
    assert "hub manifest" not in out, out


@pytest.mark.skipif(os.geteuid() == 0, reason="root traverses a mode-000 directory")
def test_a_hub_this_user_cannot_enter_degrades_like_an_absent_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`Path.is_file()` RAISES PermissionError (it swallows only ENOENT-class errors): a hub
    another uid owns must read as absent, never crash the check with a bare traceback."""
    hub_scripts = tmp_path / "hub" / "scripts"
    hub_scripts.mkdir(parents=True)
    (hub_scripts / "fabrik_synced_manifest.py").write_text(_FULL_MANIFEST, encoding="utf-8")
    rc = None
    try:
        hub_scripts.chmod(0)
        files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
        rc = _run(monkeypatch, tmp_path, None, files, lock, hub_exists=False)
    finally:
        hub_scripts.chmod(0o755)
    out = capsys.readouterr().out
    assert rc == 1, out  # empty lists: PORTS.md reads as drift, as with no hub
    assert "PORTS.md" in out, out
    assert "hub manifest" not in out, out  # unreadable is "cannot tell", never "missing"


@pytest.mark.parametrize(
    ("seeded", "retired"),
    [("None", "[]"), ("set()", '"libs/x"'), ("set()", "[1]"), ("{5}", "[]"), ("set()", "[()]")],
    ids=["seeded-None", "retired-a-string", "retired-an-int-entry", "seeded-an-int", "empty-tuple"],
)
def test_a_wrongly_typed_list_fails_red_naming_the_hub(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    seeded: str,
    retired: str,
) -> None:
    """A present symbol of the wrong shape is a guessed list too: `set(None)` crashed with a bare
    TypeError, and a string was exploded into one-character prefixes that exempt nothing."""
    manifest = f"SEEDED_NOT_ENFORCED = {seeded}\nRETIRED_VENDORED_DIRS = {retired}\n"
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    rc = _run(monkeypatch, tmp_path, manifest, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert _HUB_WORDS in out, out
    assert _PROJECT_BLAME not in out, out


@pytest.mark.parametrize("code", [0, 3])
def test_a_manifest_that_exits_while_loading_fails_red(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], code: int
) -> None:
    """`SystemExit` is no `Exception`: a manifest calling `sys.exit(0)` ended the check GREEN."""
    manifest = f"import sys\nsys.exit({code})\n" + _FULL_MANIFEST
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    rc = _run(monkeypatch, tmp_path, manifest, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "SystemExit" in out and _HUB_WORDS in out, out


@pytest.mark.parametrize(
    ("raise_line", "named"),
    [
        ('raise GeneratorExit("gen")', "GeneratorExit"),
        ('raise BaseExceptionGroup("g", [GeneratorExit()])', "BaseExceptionGroup"),
        ('raise BaseExceptionGroup("g", [KeyboardInterrupt()])', "BaseExceptionGroup"),
        (
            "class SubclassOfKeyboardInterrupt(KeyboardInterrupt):\n    pass\n"
            "raise SubclassOfKeyboardInterrupt",
            "failed to load or answer: SubclassOfKeyboardInterrupt:",
        ),
        (
            "class X(Exception):\n    def __str__(self):\n        raise KI\n"
            "class KI(KeyboardInterrupt):\n    pass\nraise X",
            "<its message raised too>",
        ),
    ],
    ids=[
        "GeneratorExit",
        "BaseExceptionGroup",
        "group-holding-a-KeyboardInterrupt",
        "KeyboardInterrupt-subclass",
        "KeyboardInterrupt-subclass-from-the-message",
    ],
)
def test_any_base_exception_but_keyboardinterrupt_fails_red_naming_the_hub(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    raise_line: str,
    named: str,
) -> None:
    """W-3d6a6236: `except (Exception, SystemExit)` let any other BaseException escape as a bare
    traceback — still rc 1, but with no word about the hub. Only a bare KeyboardInterrupt, the
    operator's, is let through: a group holding one, or a subclass of it, is the manifest's
    construct and is named (a group names only itself, never its members)."""
    manifest = raise_line + "\n" + _FULL_MANIFEST
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    try:
        rc = _run(monkeypatch, tmp_path, manifest, files, lock)
    except KeyboardInterrupt:  # escaped as the operator's: fail this param, not the session
        pytest.fail("the manifest's KeyboardInterrupt construct escaped as the operator's")
    out = capsys.readouterr().out
    assert rc == 1, out
    assert _HUB_WORDS in out and named in out, out
    assert _PROJECT_BLAME not in out, out


_EXIT0 = "def _exit0(*a, **k):\n    raise SystemExit(0)\n"
# The refusal each post-load param's OWN guard produces, by param id (W-73044efc). The last two
# have no guard of their own: the exit fires inside the check's own read (a `__name__` while the
# entry refusal's message is built, the `a not in names` lookup), so the wide catch IS what turns
# it red, and they pin that. That the dict is taken BEFORE the load is pinned by
# test_a_manifest_that_swaps_its_module_class_cannot_answer_through_it, not here.
_POST_LOAD_REFUSAL = {
    "module-getattr": "has no SEEDED_NOT_ENFORCED, RETIRED_VENDORED_DIRS",
    "list-iter": "SEEDED_NOT_ENFORCED is a L, not a collection of paths",
    "str-str": "SEEDED_NOT_ENFORCED holds a S, not a path",
    "str-rstrip": "RETIRED_VENDORED_DIRS holds a S, not a path",
    "class-property": "RETIRED_VENDORED_DIRS holds a P, not a path",
    "tuple-getitem": "RETIRED_VENDORED_DIRS holds a T, not a path",
    "repr": "SEEDED_NOT_ENFORCED holds a R, not a path",
    "exc-str": "failed to load or answer: X: <its message raised too>",
    "manifesterror-subclass": "failed to load or answer: F: <its message raised too>",
    "list-iterates-differently": "RETIRED_VENDORED_DIRS is a L, not a collection of paths",
    "metaclass-eq": "SEEDED_NOT_ENFORCED is a C, not a collection of paths",
    "metaclass-eq-true": "RETIRED_VENDORED_DIRS is a C, not a collection of paths",
    "metaclass-eq-entry": "RETIRED_VENDORED_DIRS holds a C, not a path",
    "metaclass-name": "failed to load or answer: SystemExit: 0",
    "colliding-dict-key": "failed to load or answer: SystemExit: 0",
    "exc-type-name": "failed to load or answer: <its type name could not be read>: x",
    "exc-type-name-generatorexit": "failed to load or answer: <its type name could not be read>: x",
    "exc-name-str-subclass": "failed to load or answer: <its type name could not be read>: x",
    "exc-str-str-subclass": "failed to load or answer: E: <its message raised too>",
    "manifesterror-hostile-arg": "failed to load or answer: ManifestError: <its message raised too>",
}


@pytest.mark.parametrize(
    "manifest",
    [
        _EXIT0 + "__getattr__ = _exit0\n",
        _EXIT0 + "class L(list):\n    __iter__ = _exit0\n"
        'SEEDED_NOT_ENFORCED = L(["PORTS.md"])\nRETIRED_VENDORED_DIRS = []\n',
        _EXIT0 + "class S(str):\n    __str__ = _exit0\n"
        'SEEDED_NOT_ENFORCED = {S("PORTS.md")}\nRETIRED_VENDORED_DIRS = []\n',
        _EXIT0 + "class S(str):\n    rstrip = _exit0\n"
        'SEEDED_NOT_ENFORCED = set()\nRETIRED_VENDORED_DIRS = [S("libs/x")]\n',
        _EXIT0 + "class P:\n    __class__ = property(_exit0)\n"
        "SEEDED_NOT_ENFORCED = set()\nRETIRED_VENDORED_DIRS = [P()]\n",
        # An isinstance shape check would index it clean once and let `main()` index it again into
        # the exit; the exact-type check refuses the tuple subclass before indexing it.
        _EXIT0 + "class T(tuple):\n    calls = 0\n    def __getitem__(self, i):\n"
        "        T.calls += 1\n        return 'libs/x' if T.calls == 1 else _exit0()\n"
        'SEEDED_NOT_ENFORCED = set()\nRETIRED_VENDORED_DIRS = [T(("libs/x",))]\n',
        _EXIT0 + "class R:\n    __repr__ = _exit0\n"
        "SEEDED_NOT_ENFORCED = [R()]\nRETIRED_VENDORED_DIRS = []\n",
        _EXIT0 + "class X(BaseException):\n    __str__ = _exit0\nraise X\n",
        # The LIVE check's ManifestError, from the frame running `_manifest_lists`.
        _EXIT0 + "import sys\nf = sys._getframe()\n"
        "while '_manifest_lists' not in f.f_globals:\n    f = f.f_back\n"
        "class F(f.f_globals['ManifestError']):\n    __str__ = _exit0\nraise F('x')\n",
        # An isinstance shape check would admit the list subclass; the check copies it in ONE
        # iteration (`_path_list`), which yields clean, so the run ends as drift blamed on the
        # project — only a check that iterated it again would reach the `rstrip` exit. The identity
        # test refuses the subclass before iterating it.
        _EXIT0 + "class S(str):\n    rstrip = _exit0\nclass L(list):\n    calls = 0\n"
        "    def __iter__(self):\n        L.calls += 1\n"
        "        return iter(['libs/x'] if L.calls == 1 else [S('libs/x')])\n"
        "SEEDED_NOT_ENFORCED = set()\nRETIRED_VENDORED_DIRS = L(['libs/x'])\n",
        _EXIT0 + "class Meta(type):\n    __eq__ = _exit0\n    __hash__ = type.__hash__\n"
        "class C(metaclass=Meta):\n    pass\n"
        "SEEDED_NOT_ENFORCED = C()\nRETIRED_VENDORED_DIRS = []\n",
        # A metaclass that answers `==` True for any class passes an `in`/`==` type test; copied in
        # one iteration it yields clean, so the run ends as drift blamed on the project (a second
        # iteration would reach the `rstrip` exit). The identity test (`type(x) is T`) refuses the
        # class before iterating it.
        _EXIT0 + "class S(str):\n    rstrip = _exit0\n"
        "class Meta(type):\n    __eq__ = lambda c, o: True\n    __hash__ = type.__hash__\n"
        "class C(list, metaclass=Meta):\n    calls = 0\n    def __iter__(self):\n"
        "        C.calls += 1\n        return iter(['libs/x'] if C.calls == 1 else [S('libs/x')])\n"
        "SEEDED_NOT_ENFORCED = set()\nRETIRED_VENDORED_DIRS = C(['libs/x'])\n",
        # The same metaclass on an ENTRY: an `==`/`!=` entry test (`!=` falls back to the inverted
        # `__eq__`) admits it, and `main()` calls its `rstrip` outside the catch.
        _EXIT0 + "class Meta(type):\n    __eq__ = lambda c, o: True\n    __hash__ = type.__hash__\n"
        "class C(metaclass=Meta):\n    rstrip = _exit0\n"
        "SEEDED_NOT_ENFORCED = set()\nRETIRED_VENDORED_DIRS = [C()]\n",
        _EXIT0 + "class Meta(type):\n    __name__ = property(_exit0)\n"
        "class C(metaclass=Meta):\n    pass\n"
        "SEEDED_NOT_ENFORCED = [C()]\nRETIRED_VENDORED_DIRS = []\n",
        # The key takes the name's primary slot BEFORE the list is bound, so the list probes past it
        # and every later lookup compares against it; its `__eq__` is armed only once the body is
        # done, so the first armed comparison is the check's own lookup.
        _EXIT0 + "class K:\n    armed = False\n"
        "    def __hash__(self):\n        return hash('SEEDED_NOT_ENFORCED')\n"
        "    def __eq__(self, other):\n        if K.armed:\n            _exit0()\n"
        "        return False\nglobals()[K()] = 1\n" + _FULL_MANIFEST + "K.armed = True\n",
        # The raised exception's TYPE name, read while the failure's message is built (W-deb8eb0f):
        # outside the inner guard it escaped `main()` as SystemExit(0), GREEN.
        _EXIT0 + "class Meta(type):\n    __name__ = property(_exit0)\n"
        "class E(Exception, metaclass=Meta):\n    pass\nraise E('x')\n",
        # Any other BaseException from the name read is named the same way, never let through.
        "def _gen_exit(*a, **k):\n    raise GeneratorExit\n"
        "class Meta(type):\n    __name__ = property(_gen_exit)\n"
        "class E(Exception, metaclass=Meta):\n    pass\nraise E('x')\n",
        # Either half returned as a str SUBCLASS: its `__format__` would run in the f-string.
        _EXIT0 + "class S(str):\n    __format__ = _exit0\n"
        "class Meta(type):\n    __name__ = property(lambda c: S('E'))\n"
        "class E(Exception, metaclass=Meta):\n    pass\nraise E('x')\n",
        _EXIT0 + "class S(str):\n    __format__ = _exit0\n"
        "class E(Exception):\n    def __str__(self):\n        return S('x')\nraise E('x')\n",
        # The LIVE check's own exact ManifestError, raised with a hostile argument: passed through
        # as the check's own refusal, `main()` printing it ran the argument's `__str__`.
        _EXIT0 + "import sys\nf = sys._getframe()\n"
        "while '_manifest_lists' not in f.f_globals:\n    f = f.f_back\n"
        "class H:\n    __str__ = _exit0\nraise f.f_globals['ManifestError'](H())\n",
    ],
    ids=[
        "module-getattr",
        "list-iter",
        "str-str",
        "str-rstrip",
        "class-property",
        "tuple-getitem",
        "repr",
        "exc-str",
        "manifesterror-subclass",
        "list-iterates-differently",
        "metaclass-eq",
        "metaclass-eq-true",
        "metaclass-eq-entry",
        "metaclass-name",
        "colliding-dict-key",
        "exc-type-name",
        "exc-type-name-generatorexit",
        "exc-name-str-subclass",
        "exc-str-str-subclass",
        "manifesterror-hostile-arg",
    ],
)
def test_manifest_code_run_after_the_load_still_fails_red_naming_the_hub(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    request: pytest.FixtureRequest,
    manifest: str,
) -> None:
    """W-3d6a6236 (Opus critique, review pass 1): the load's catch closed when `exec_module`
    returned, yet a module `__getattr__`, a list, str or tuple subclass, a `__class__` property, an
    entry's `__repr__`, the raised exception's own `__str__`, a ManifestError subclass the
    manifest raises, a metaclass `__eq__` or `__name__`, or a globals key whose hash collides with a
    list's name runs the manifest's code later — each one a
    `sys.exit(0)` that ended the check GREEN over a drifted file. The check reads the module dict it
    took before the load, inside the catch, and takes only exact built-in types.

    Each param with a guard of its own asserts the refusal THAT guard produces (W-73044efc; see
    `_POST_LOAD_REFUSAL` for the two that have none). A guard that regressed to
    `getattr`/`isinstance`/`==` ends some other way — the wide catch's "failed to load or answer:
    SystemExit", a SystemExit escaping `main()`, or drift blamed on the project — never with the
    guard's own words.

    An escaped SystemExit is failed HERE, by its plain code and outside the `except`, because
    pytest formatting the hostile exception (W-deb8eb0f) re-runs its code and ends the whole
    session at rc 0 — a regression that reads as a green suite."""
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    escaped: object = None
    try:
        rc = _run(monkeypatch, tmp_path, manifest, files, lock)
    except SystemExit as exc:
        escaped = repr(exc.code) if type(exc.code) in (int, type(None)) else "<non-int code>"
    if escaped is not None:
        pytest.fail(f"SystemExit({escaped}) escaped main(): GREEN in a real process", pytrace=False)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert _HUB_WORDS in out, out
    assert _PROJECT_BLAME not in out, out
    assert _POST_LOAD_REFUSAL[request.node.callspec.id] in out, out


@pytest.mark.parametrize(
    "raise_code",
    [
        "raise KeyboardInterrupt\n",
        "class X(Exception):\n    def __str__(self):\n        raise KeyboardInterrupt\nraise X\n",
        "def _ki(*a, **k):\n    raise KeyboardInterrupt\n"
        "class Meta(type):\n    __name__ = property(_ki)\n"
        "class X(Exception, metaclass=Meta):\n    pass\nraise X\n",
    ],
    ids=["at-load", "while-the-message-is-built", "while-the-type-name-is-read"],
)
def test_a_keyboardinterrupt_while_loading_is_the_operators_never_named_the_hubs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raise_code: str
) -> None:
    """Ctrl-C during the load reaches the operator unchanged (a CONTROL, true before and after),
    and so does one that lands while the handler builds the failure's message."""
    manifest = raise_code + _FULL_MANIFEST
    with pytest.raises(KeyboardInterrupt):
        _run(monkeypatch, tmp_path, manifest, {"a.txt": "x"}, {"a.txt": _md5("x")})


def test_an_absent_manifest_file_with_a_clean_lock_stays_green(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A CONTROL (green before and after the fix): an absent manifest alone never reds."""
    rc = _run(monkeypatch, tmp_path, None, {"a.txt": "x"}, {"a.txt": _md5("x")})
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "match what was distributed" in out, out


def test_a_complete_manifest_applies_both_lists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both lists apply, with a STALE module cached under the manifest's name: the hub's FILE must
    answer, never `sys.modules` (red on the old import path, which the cache answered)."""
    stale = types.ModuleType("fabrik_synced_manifest")
    stale.SEEDED_NOT_ENFORCED = set()  # type: ignore[attr-defined]
    stale.RETIRED_VENDORED_DIRS = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik_synced_manifest", stale)
    files = {"PORTS.md": "edited", "libs/retired_mod/a.py": "edited", "synced.py": "edited"}
    lock = {
        "PORTS.md": _md5("orig"),
        "libs/retired_mod/a.py": _md5("orig"),
        "synced.py": _md5("orig"),
    }
    rc = _run(monkeypatch, tmp_path, _FULL_MANIFEST, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out  # an edited non-exempt file is still drift
    assert "synced.py" in out, out
    assert "PORTS.md" not in out, out
    assert "libs/retired_mod" not in out, out
    # W-85e4e5e4: the drift message is read by a PROJECT agent, who has no sync script to run —
    # it names the hub as the distributor and never tells the reader to re-sync.
    assert "re-sync" not in out, out
    assert "the hub distributes it" in out, out


def test_a_manifest_that_swaps_its_module_class_cannot_answer_through_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W-3d6a6236 review pass 1: a manifest can reach its own module object (gc) and swap its class
    for one with a `__dict__` property, so `vars(man)` after the load ran a `sys.exit(0)` and ended
    the check GREEN. The dict taken before the load answers instead: the lists apply and the
    drifted file is reported."""
    manifest = (
        _EXIT0 + "import gc, types\nclass M(types.ModuleType):\n    __dict__ = property(_exit0)\n"
        "me = [o for o in gc.get_referrers(globals()) if isinstance(o, types.ModuleType)][0]\n"
        "me.__class__ = M\nSEEDED_NOT_ENFORCED = set()\nRETIRED_VENDORED_DIRS = []\n"
    )
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    rc = _run(monkeypatch, tmp_path, manifest, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "PORTS.md" in out and _HUB_WORDS not in out, out


def test_a_tuple_entry_is_a_retired_dirs_convention_never_a_seeded_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`RETIRED_VENDORED_DIRS` accepts an exact `(path, …)` tuple entry by convention and exempts
    its path; `SEEDED_NOT_ENFORCED` takes plain strings only, so a tuple there is the hub's."""
    files = {"libs/retired_mod/a.py": "edited"}
    lock = {"libs/retired_mod/a.py": _md5("orig")}
    manifest = (
        'SEEDED_NOT_ENFORCED = set()\nRETIRED_VENDORED_DIRS = [("libs/retired_mod", "why")]\n'
    )
    rc = _run(monkeypatch, tmp_path / "retired", manifest, files, lock)
    out = capsys.readouterr().out
    assert rc == 0, out
    manifest = 'SEEDED_NOT_ENFORCED = {("PORTS.md",)}\nRETIRED_VENDORED_DIRS = []\n'
    rc = _run(monkeypatch, tmp_path / "seeded", manifest, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert _HUB_WORDS in out, out
    # A tuple entry whose head is no path names the HEAD's type, never the tuple's.
    manifest = 'SEEDED_NOT_ENFORCED = set()\nRETIRED_VENDORED_DIRS = [(1, "why")]\n'
    rc = _run(monkeypatch, tmp_path / "head", manifest, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "holds a int, not a path" in out, out


def test_the_repo_manifest_answers_the_checks_own_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    """The renaming worktree reds HERE, before the sync carries a rename to every project.

    The check reads the live `/opt/fabrik` manifest, so no other hub test sees a rename made on a
    branch; loading THIS tree's manifest through the check's own loader does, and its lists must
    equal what an independent run of the file defines.
    """
    root = _CHECK.parents[2]
    check = _load_check()
    monkeypatch.setattr(check, "FABRIK_ROOT", root)
    seeded, retired = check._manifest_lists()
    defined = runpy.run_path(str(root / check.MANIFEST_REL))
    assert seeded == set(defined["SEEDED_NOT_ENFORCED"]), seeded
    assert retired == tuple(defined["RETIRED_VENDORED_DIRS"]), retired


def test_the_repo_manifest_imports_only_the_stdlib() -> None:
    """Every project's check loads the HUB's manifest under the project's own interpreter, where a
    third-party package the hub venv happens to have (`yaml`) may be absent — and a hub sibling
    script is never importable (no `sys.path` entry). So the manifest imports the stdlib only."""
    tree = ast.parse((_CHECK.parents[2] / "scripts/fabrik_synced_manifest.py").read_text())
    names = {
        (alias.name if isinstance(node, ast.Import) else node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert names, "no imports parsed — the walk read nothing"
    foreign = sorted(n for n in names if n not in sys.stdlib_module_names and n != "__future__")
    assert not foreign, f"the hub manifest imports non-stdlib modules: {foreign}"
