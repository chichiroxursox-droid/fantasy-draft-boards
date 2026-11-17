#!/usr/bin/env python3
"""Local draft-day server: serves draft.html + data/, and accepts POST /state
(the board pushes full draft state after every pick -> data/state.json, so
Claude can read the live board during the draft).

Usage: python3 tools/serve.py   ->   http://localhost:8712/draft.html
"""
import http.server
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8712


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")  # morning re-fetch shows on plain reload
        super().end_headers()

    STATE_FILES = {"/state": "state.json", "/auction_state": "auction_state.json"}

    def do_POST(self):
        name = self.STATE_FILES.get(self.path)
        if not name:
            return self.send_error(404)
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            json.loads(body)
        except Exception:
            return self.send_error(400)
        (ROOT / "data").mkdir(exist_ok=True)
        tmp = ROOT / "data" / (name + ".tmp")   # atomic: a concurrent reader never sees a torn file
        tmp.write_bytes(body)
        tmp.replace(ROOT / "data" / name)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass  # keep the terminal quiet during the draft


def lan_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))          # no traffic sent; just picks the LAN interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


if __name__ == "__main__":
    print(f"Snake board   -> http://localhost:{PORT}/draft.html")
    print(f"Auction board -> http://localhost:{PORT}/auction.html")
    ip = lan_ip()
    if ip:
        print(f"Phone (same wifi/hotspot) -> http://{ip}:{PORT}/auction.html")
    print("(Ctrl-C to stop)")
    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
