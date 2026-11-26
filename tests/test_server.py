import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from playlistkit import gui


def test_window_opens_at_its_own_host():
    # Edge names an app window's taskbar ID after the host: 127.0.0.1 would share it with every local app
    assert gui.app_url(8765) == "http://playlistkit.localhost:8765/"


def test_a_second_server_cannot_take_the_port():
    first = gui.AppServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    try:
        port = first.server_address[1]
        with pytest.raises(OSError):
            gui.AppServer(("127.0.0.1", port), BaseHTTPRequestHandler)
        if os.name == "nt":  # an old version's plain server (SO_REUSEADDR) cannot sneak in either
            with pytest.raises(OSError):
                ThreadingHTTPServer(("127.0.0.1", port), BaseHTTPRequestHandler)
    finally:
        first.server_close()


def test_port_is_free_again_after_close():
    first = gui.AppServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = first.server_address[1]
    first.server_close()
    again = gui.AppServer(("127.0.0.1", port), BaseHTTPRequestHandler)  # the relaunch after an update
    again.server_close()
