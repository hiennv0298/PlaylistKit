"""Entry point used by PyInstaller to build playlistkit.exe and PlaylistKitApp.exe."""
import sys

from playlistkit.cli import main

if __name__ == "__main__":
    sys.exit(main())
