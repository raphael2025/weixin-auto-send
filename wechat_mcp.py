#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wechat_mcp.py — MCP server exposing the WeChat (Weixin 4.x) sender as tools,
so any MCP-capable AI (Claude Desktop / Claude Code / Cursor / agents ...) can
fuzzy-search a contact or group and send a message.

MCP 服务器:把"发微信"暴露成 MCP 工具,任何支持 MCP 的 AI 都能调用。

Requires the MCP SDK (the core sender itself has zero deps):
    pip install mcp
Run (usually launched by the MCP client, stdio transport):
    python wechat_mcp.py
"""
from typing import Literal

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "缺少 MCP SDK / MCP SDK not installed. Run:  pip install mcp"
    ) from e

from wechat_send import send_message

mcp = FastMCP("weixin-auto-send")


@mcp.tool()
def wechat_send_message(
    to: str,
    message: str,
    kind: Literal["any", "contact", "group"] = "any",
    dry_run: bool = True,
) -> dict:
    """Send a message on the local, already-logged-in WeChat (Weixin 4.x) desktop app.

    It activates WeChat, fuzzy-searches `to` (a contact or group name), opens the
    best match, re-confirms the opened chat's title by OCR to avoid sending to the
    wrong recipient, then sends `message`.

    SAFETY: `dry_run` defaults to True — it only previews (finds the target and
    reports who it WOULD send to) without sending anything. To actually deliver,
    call again with dry_run=False. Prefer previewing first when unsure.

    Args:
        to: Contact or group name (fuzzy match; the app's own search is fuzzy too).
        message: The text to send (any characters supported).
        kind: Narrow the match — "contact", "group", or "any" (default).
        dry_run: If True (default), preview only and DO NOT send.

    Returns:
        A result dict. On success: {"ok": true, "dry_run": bool, "target": <chat title>, "msg": ...}.
        On failure: {"ok": false, "stage": ..., "reason": ...} (and "ocr" lines when matching failed).
        Always check "ok"; when dry_run is True nothing was sent regardless.
    """
    return send_message(
        to=to,
        msg=message,
        kind=kind,
        send=not dry_run,
        confirm_title=True,
        verbose=False,
    )


if __name__ == "__main__":
    mcp.run()  # stdio transport by default
