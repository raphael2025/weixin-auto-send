#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example: push an alert to a WeChat group/contact.
示例:把一条告警推送到微信群/联系人(例如服务器/设备监控告警)。

Run from the repo root:  python examples/alert_example.py
"""
import sys
from pathlib import Path

# Make wechat_send importable when running from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wechat_send import send_message  # noqa: E402


def notify(target: str, text: str, kind: str = "any", send: bool = False) -> bool:
    """Send `text` to `target`. Returns True on success.

    send=False (default) only previews (dry-run) — nothing is actually sent.
    Set send=True to really deliver. Always keeps the title double-check on.
    """
    res = send_message(target, text, kind=kind, send=send,
                       confirm_title=True, verbose=True)
    if not res["ok"]:
        print("发送失败 / send failed:", res.get("reason"))
        # TODO: fall back to your existing alert channel (email / webhook / ...)
    return res["ok"]


if __name__ == "__main__":
    # Dry-run by default so the example is safe to run as-is.
    notify(
        target="文件传输助手",      # group or contact name (fuzzy)
        text="⚠️ Demo alert: server #3 is offline",
        kind="any",                  # "any" | "contact" | "group"
        send=False,                  # change to True to actually send
    )
