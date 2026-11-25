import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from playlistkit import __version__, updates
from playlistkit.util import PlaylistKitError

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("PLAYLISTKIT_HOME", str(tmp_path / "home"))
    updates.PROGRESS.update(phase="idle", progress=0.0, error="")
    return tmp_path


def fake_release(tmp_path, monkeypatch, version="99.0.0", payload=b"installer bytes", good_hash=True, body="- Shiny"):
    name = f"PlaylistKit-Setup-{version}.exe"
    exe = tmp_path / name
    exe.write_bytes(payload)
    digest = hashlib.sha256(payload if good_hash else b"other").hexdigest()
    sums = tmp_path / "SHA256SUMS.txt"
    sums.write_text(f"{digest}  {name}\n", encoding="ascii")
    rel = {"tag_name": f"v{version}", "body": body, "html_url": "https://example.invalid/rel",
           "assets": [{"name": name, "browser_download_url": exe.as_uri()},
                      {"name": "SHA256SUMS.txt", "browser_download_url": sums.as_uri()}]}
    path = tmp_path / "latest.json"
    path.write_text(json.dumps(rel), encoding="utf-8")
    monkeypatch.setenv("PLAYLISTKIT_UPDATE_URL", path.as_uri())
    return name


def test_parse_version():
    assert updates.parse_version("v0.10.2") > updates.parse_version("0.9.9")
    assert updates.parse_version("1.2") == (1, 2, 0)
    assert updates.parse_version("0.3.0-beta") == (0, 3, 0)


def test_release_notes_section():
    spec = importlib.util.spec_from_file_location("release_notes", ROOT / "scripts" / "release_notes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = mod.section(text, f"v{__version__}")
    assert notes and "## " not in notes
    assert mod.section(text, "0.0.0") == ""


def test_check_reports_newer_release(tmp_path, monkeypatch):
    fake_release(tmp_path, monkeypatch)
    updates.check(force=True)
    st = updates.status()
    assert st["newer"] and st["latest"] == "99.0.0" and st["notes"] == "- Shiny"
    assert st["mode"] == "python" and not st["can_install"]  # tests run from source, not the installer build


def test_whats_new_after_update(tmp_path, monkeypatch):
    fake_release(tmp_path, monkeypatch, version=__version__, body="- New stuff")
    updates.check(force=True)
    assert updates.status()["whats_new"] is None  # first run: nothing to announce
    state = updates._load()
    state["seen_version"] = "0.0.1"  # pretend an older version ran before
    updates._save(state)
    updates.check()  # cached answer is fresh, but What's new is still prepared
    assert updates.status()["whats_new"] == {"version": __version__, "notes": "- New stuff"}
    updates.mark_seen()
    assert updates.status()["whats_new"] is None


def test_install_verifies_and_launches(tmp_path, monkeypatch):
    name = fake_release(tmp_path, monkeypatch)
    updates.check(force=True)
    monkeypatch.setattr(updates, "install_mode", lambda: "installer")
    launched = []
    monkeypatch.setattr(updates.subprocess, "Popen", lambda args, **kw: launched.append(args))
    done = []
    updates.download_and_install(lambda: done.append(True))
    assert launched and launched[0][0].endswith(name) and "/RELAUNCH=1" in launched[0] and done
    assert updates.PROGRESS["phase"] == "restarting"


def test_install_rejects_bad_checksum(tmp_path, monkeypatch):
    fake_release(tmp_path, monkeypatch, good_hash=False)
    updates.check(force=True)
    monkeypatch.setattr(updates, "install_mode", lambda: "installer")
    monkeypatch.setattr(updates.subprocess, "Popen", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(PlaylistKitError, match="SHA-256"):
        updates.download_and_install(lambda: None)
    assert updates.PROGRESS["phase"] == "error"
    assert not list((Path(updates.app_home()) / "updates").glob("*.exe"))
