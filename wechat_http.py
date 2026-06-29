#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wechat_http.py — tiny local HTTP API for the WeChat (Weixin 4.x) sender, so ANY
agent / language / framework (OpenClaw, Hermes Agent, n8n, curl, scripts...) can
send a WeChat message — not just MCP clients. Pure Python standard library, zero deps.

本地 HTTP 接口:任何 agent / 语言 / 框架都能通过一个 HTTP 请求发微信(不限 MCP)。纯标准库,零依赖。

Run:
    python wechat_http.py                 # listens on 127.0.0.1:8765 (localhost only)
    set WX_API_HOST=0.0.0.0 & set WX_API_PORT=8800 & python wechat_http.py
    set WX_API_TOKEN=secret & python wechat_http.py   # then send header  X-Token: secret

Endpoints:
    GET  /health                 -> {"ok": true, ...}
    POST /send                   -> send (or preview) a message
         body (JSON): {"to": "...", "message": "...", "kind": "any|contact|group",
                       "dry_run": false, "confirm_title": true}
         returns the sender's result dict; HTTP 200 on ok, 422 on failure.

Example:
    curl -X POST http://127.0.0.1:8765/send -H "Content-Type: application/json" \
         -d "{\"to\":\"文件传输助手\",\"message\":\"hi\",\"dry_run\":true}"
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from wechat_send import send_message

HOST = os.environ.get("WX_API_HOST", "127.0.0.1")
PORT = int(os.environ.get("WX_API_PORT", "8765"))
TOKEN = os.environ.get("WX_API_TOKEN")  # optional shared secret; if set, require X-Token header


class Handler(BaseHTTPRequestHandler):
    server_version = "weixin-auto-send/1.0"

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self):
        if not TOKEN:
            return True
        return self.headers.get("X-Token") == TOKEN

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/health"):
            self._json(200, {"ok": True, "service": "weixin-auto-send", "endpoint": "POST /send"})
        else:
            self._json(404, {"ok": False, "reason": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") != "/send":
            self._json(404, {"ok": False, "reason": "not found"})
            return
        if not self._authed():
            self._json(401, {"ok": False, "reason": "unauthorized (bad or missing X-Token)"})
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            self._json(400, {"ok": False, "reason": f"bad json: {e}"})
            return

        to = data.get("to")
        msg = data.get("message", data.get("msg"))
        if not to or msg is None:
            self._json(400, {"ok": False, "reason": "'to' and 'message' are required"})
            return

        try:
            res = send_message(
                to=to,
                msg=str(msg),
                kind=data.get("kind", "any"),
                send=not bool(data.get("dry_run", False)),
                confirm_title=bool(data.get("confirm_title", True)),
                verbose=False,
            )
        except Exception as e:
            self._json(500, {"ok": False, "stage": "exception", "reason": str(e)})
            return
        self._json(200 if res.get("ok") else 422, res)

    def log_message(self, *args):
        pass  # keep stdout quiet


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"weixin-auto-send HTTP API -> http://{HOST}:{PORT}  (POST /send, GET /health)"
          + ("  [token required]" if TOKEN else ""))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
