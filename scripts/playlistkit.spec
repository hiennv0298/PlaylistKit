# PyInstaller spec: two programs sharing one folder (dist\PlaylistKit).
#   playlistkit.exe     command line, runs in a console
#   PlaylistKitApp.exe  opens the app window, no console window
# The remix engine (engine/remix_engine.py) is shipped as a plain file: it runs in the
# separate AI Python (torch + demucs) that the app installs on first use.
# Build with: python -m PyInstaller --noconfirm --clean --distpath dist --workpath build scripts\playlistkit.spec
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("playlistkit", include_py_files=False)
datas += [(os.path.join(SPECPATH, "..", "src", "playlistkit", "engine", "remix_engine.py"), "playlistkit/engine")]
hidden = ["playlistkit.gui"] + collect_submodules("playlistkit") + collect_submodules("yt_dlp")

ICON = os.path.join(SPECPATH, "..", "src", "playlistkit", "webui", "playlistkit.ico")
a = Analysis([os.path.join(SPECPATH, "playlistkit_entry.py")], datas=datas, hiddenimports=hidden,
             pathex=[os.path.join(SPECPATH, "..", "src")])
pyz = PYZ(a.pure)
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="playlistkit", console=True, icon=ICON)
app = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PlaylistKitApp", console=False, icon=ICON)
coll = COLLECT(cli, app, a.binaries, a.datas, name="PlaylistKit")
