"""Session API. Run in the PC desktop: python -m agent.server --token-file PATH.

Use --dry RUN_DIR on the Mac for real recorded pixels and a fake pad. No shell or
raw input endpoint; the policy and range guards remain inside Rivals Agent.
"""
import argparse
import hmac
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .session import Session


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, session, token):
        if len(token) < 32:
            raise ValueError("control token must be at least 32 characters")
        self.session, self.token = session, token
        self.share = None
        self.share_lock = threading.Lock()
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Watch URLs contain read-only credentials.

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def reply(self, code, body, content_type="application/json"):
        payload = json.dumps(body).encode() if content_type == "application/json" else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def authorized(self):
        return hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + self.server.token)

    def do_GET(self):
        url = urlsplit(self.path)
        try:
            if url.path in ("/watch", "/frame.png"):
                query = parse_qs(url.query)
                key = query.get("key", [""])[0]
                with self.server.share_lock:
                    share = self.server.share
                if not share or not hmac.compare_digest(key, share["key"]):
                    return self.reply(401, {"error": "watch_authentication_required"})
                session_id = share["sessionId"]
                with self.server.session.lock:
                    self.server.session._current(session_id)
                if url.path == "/frame.png":
                    return self.reply(200, self.server.session.png(session_id), "image/png")
                html = b'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Clankie plays Spider-Man</title>
<style>body{margin:0;background:#111;color:#eee;font:18px system-ui;text-align:center}img{max-width:100%;max-height:85vh}p{margin:1rem}</style>
<p id="status" role="status">Connecting to Clankie's game...</p><img id="game" alt="Clankie's Spider-Man gameplay"><script>
const game=document.getElementById('game'), status=document.getElementById('status');
async function tick(){try{const r=await fetch('/frame.png'+location.search,{cache:'no-store'});if(!r.ok)throw Error();
const url=URL.createObjectURL(await r.blob());const old=game.src;game.src=url;if(old.startsWith('blob:'))URL.revokeObjectURL(old);status.textContent='Clankie plays Spider-Man';
}catch{game.removeAttribute('src');status.textContent='No live game frame available';}setTimeout(tick,200);}tick();</script></html>'''
                return self.reply(200, html, "text/html; charset=utf-8")
            if not self.authorized():
                return self.reply(401, {"error": "authentication_required"})
            if url.path == "/v1/status":
                return self.reply(200, self.server.session.status())
            if url.path == "/v1/frame":
                session_id = parse_qs(url.query).get("sessionId", [""])[0]
                return self.reply(200, self.server.session.png(session_id), "image/png")
            self.reply(404, {"error": "not_found"})
        except (ValueError, RuntimeError) as error:
            self.reply(409, {"error": str(error)})
        except Exception:
            self.reply(500, {"error": "session_read_failed"})

    def do_POST(self):
        if not self.authorized():
            return self.reply(401, {"error": "authentication_required"})
        if self.headers.get("Origin") is not None:
            return self.reply(403, {"error": "browser_control_refused"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 8192 or self.headers.get("Transfer-Encoding"):
                return self.reply(413, {"error": "invalid_body_size"})
            data = json.loads(self.rfile.read(length))
            action = self.path
            if action == "/v1/start":
                result = self.server.session.start(data)
            elif action == "/v1/objective":
                result = self.server.session.steer(data)
            elif action == "/v1/stop":
                result = self.server.session.stop(data)
                with self.server.share_lock:
                    self.server.share = None
            elif action == "/v1/share":
                if not isinstance(data, dict) or set(data) != {"sessionId"}:
                    raise ValueError("sessionId required")
                self.server.session.png(data["sessionId"])
                with self.server.session.lock:
                    self.server.session._current(data["sessionId"])
                    with self.server.share_lock:
                        if not self.server.share or self.server.share["sessionId"] != data["sessionId"]:
                            self.server.share = {"sessionId": data["sessionId"], "key": secrets.token_urlsafe(32)}
                        key = self.server.share["key"]
                result = {"watchPath": "/watch?key=" + key, "framePath": "/frame.png?key=" + key}
            else:
                return self.reply(404, {"error": "not_found"})
            self.reply(200, result)
        except (ValueError, TypeError, KeyError):
            self.reply(400, {"error": "invalid_request"})
        except RuntimeError as error:
            self.reply(409, {"error": str(error)})
        except Exception:
            self.reply(500, {"error": "session_command_failed"})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4330)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--init-token", action="store_true")
    parser.add_argument("--dry", type=Path)
    parser.add_argument("--runs", type=Path, default=Path("data/clankie"))
    parser.add_argument("--cooldowns", choices=("off", "normal"),
                        help="required to serve: Practice Settings No Ability Cooldown ON = off, OFF = normal")
    args = parser.parse_args(argv)
    if args.init_token:
        import os
        with os.fdopen(os.open(args.token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
            out.write(secrets.token_urlsafe(32))
        return
    if args.cooldowns is None:
        parser.error("--cooldowns off|normal is required (no default)")
    session = Session(args.runs, args.dry, cooldowns=args.cooldowns)
    server = Server((args.host, args.port), session, args.token_file.read_text().strip())
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        session.cancel.set()
        if session.thread:
            session.thread.join(timeout=5)
        server.server_close()


if __name__ == "__main__":
    main()
