# weixin-auto-send

**English** | [简体中文](README.zh-CN.md)

Automate the **already-logged-in WeChat (Weixin 4.x) desktop client on Windows**: fuzzy-search a contact or group by name and send a message — with **zero pip dependencies** and **offline Chinese OCR** built into Windows.

> Why this exists: WeChat 4.x is a full **Qt** rewrite whose UI is painted onto a single canvas, so it exposes almost nothing to UIAutomation — the popular `wxauto` library (built for the old 3.9.x client) does **not** work on it. This tool drives WeChat the way a human does: **simulated input + screen OCR**, no paid `wxautox` required.

---

## Features

- 🎯 Fuzzy search by contact / group name (WeChat's own fuzzy search + OCR fuzzy scoring)
- 🆓 Free & offline — uses the built-in `Windows.Media.Ocr` (Simplified Chinese), no third-party OCR
- 📦 Zero install — pure Python standard library (`ctypes`) + one PowerShell helper
- 🛡️ **Anti-misfire**: section filtering + length-aware matching + **OCR title re-confirmation** before sending
- 👀 Dry-run by default; `--send` to actually deliver
- 🔍 Auto-adapts to resolution & DPI scaling (DPI-aware; clicks the OCR'd coordinates directly)
- 🪟 Wakes WeChat even when minimized to tray, and forces it to the front (beats foreground-lock)

## How it works

```
find & wake the WeChat window (incl. tray-hidden) and force it on top
  → click search box → paste name (WeChat fuzzy-matches)
  → screenshot results → Windows OCR reads each row's text + coordinates
  → pick the correct target → click it to open the chat
  → OCR the chat title once more to confirm (prevents wrong-recipient)
  → paste the message + Enter
```

| File | Role |
|---|---|
| [`wechat_send.py`](wechat_send.py) | Main program: window control, mouse/keyboard, clipboard, matching, flow (`ctypes`, stdlib) |
| [`wx_helper.ps1`](wx_helper.ps1) | "Perception" helper: screenshot + Windows `Windows.Media.Ocr`, returns text lines with absolute screen coordinates as JSON |

## Requirements

- **Windows 10/11** with the **Simplified Chinese OCR** language component (default on a Chinese-language Windows; check with `Get-WindowsCapability -Online | ? Name -like "*OCR*Hans*"`).
- **WeChat (Weixin 4.x)** installed, **logged in**, and **running** (may be minimized / in tray — it will be woken; do not fully quit it).
- **Python 3.x**. No third-party packages.
- Do not lock the screen while it runs; it takes over the mouse/keyboard briefly — **don't use the mouse at the same time**.

## Quick start

```bash
# Preview (dry-run, default): opens the chat & confirms the title, but does NOT send
python wechat_send.py --to "Team Group" --msg "Server #3 is down" --type group

# Actually send: add --send
python wechat_send.py --to "Team Group" --msg "Server #3 is down, please check" --type group --send

# Safest live test — send to yourself (File Transfer):
python wechat_send.py --to "文件传输助手" --msg "test" --send
```

Example output:

```
[1] WeChat window: 1669x1075 @ (806,50), DPI x1.0
[2] Searched: "Team Group" (fuzzy)
[3] Matched: "Project Team Group" (score 0.80)
[4] Chat title: "Project Team Group (25)" (score vs target 0.62)
[5] Sent to "Project Team Group (25)": Server #3 is down, please check
```

## CLI

| Flag | Required | Description |
|---|---|---|
| `--to` | yes | Contact or group name (fuzzy) |
| `--msg` | yes | Message text (any characters; pasted via clipboard) |
| `--type` | no | `any` (default) / `contact` / `group` — narrows the match |
| `--send` | no | **Required to actually send**; without it = dry-run preview |
| `--no-confirm-title` | no | Skip the post-open title re-confirmation (**not recommended**) |

Exit code: `0` = success, `2` = failure (no match / low score / title check failed).

## Use as a module

```python
import sys; sys.path.insert(0, r"path/to/weixin-auto-send")
from wechat_send import send_message

res = send_message(
    to="Team Group",       # fuzzy name
    msg="⚠️ Server web-3 is down",
    kind="group",          # any / contact / group
    send=True,             # False = preview
    confirm_title=True,    # keep the title double-check on
    verbose=False,
)
if not res["ok"]:
    print("failed:", res.get("reason"))
```

See [`examples/alert_example.py`](examples/alert_example.py).

## Use as an MCP server (multi-AI)

Expose sending as an **MCP tool** so any MCP-capable AI (Claude Desktop, Claude Code, Cursor, agents…) can use it. [`wechat_mcp.py`](wechat_mcp.py) wraps the sender.

1. Install the SDK (the core sender stays zero-dep):
   ```bash
   pip install mcp
   ```
2. Point your MCP client at `wechat_mcp.py`.

**Claude Desktop** — `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "weixin": {
      "command": "C:\\path\\to\\weixin-auto-send\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\weixin-auto-send\\wechat_mcp.py"]
    }
  }
}
```

**Claude Code**:
```bash
claude mcp add weixin -- C:\path\to\weixin-auto-send\.venv\Scripts\python.exe C:\path\to\weixin-auto-send\wechat_mcp.py
```

Exposed tool: **`wechat_send_message(to, message, kind="any", dry_run=True)`**.
`dry_run` defaults to **True** (preview only — finds the target and reports who it *would* send to, without sending). The AI must pass `dry_run=False` to actually deliver — a safe default when multiple agents can call it.

## Use from any agent (HTTP API / CLI)

For agents/frameworks that are **not** MCP clients (OpenClaw, Hermes Agent, n8n, shell scripts, any language), run the tiny local **HTTP API** — also zero-dependency (stdlib only):

```bash
python wechat_http.py        # http://127.0.0.1:8765  (localhost only)
```

Then anything that can make an HTTP request can send:
```bash
curl -X POST http://127.0.0.1:8765/send \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"to":"Team Group","message":"hi","kind":"group","dry_run":false}'
# GET /health for a liveness check
```

- Body: `to` (required), `message` (required), `kind` (`any`/`contact`/`group`), `dry_run` (default `false`), `confirm_title` (default `true`).
- Returns the same result dict as the CLI/MCP. HTTP `200` on `ok`, `422` on failure.
- Optional auth: set env `WX_API_TOKEN` and send header `X-Token: <token>`. Change bind with `WX_API_HOST` / `WX_API_PORT`.

Or, for any agent that can run a shell command, call the CLI directly:
```bash
python wechat_send.py --to "Team Group" --msg "hi" --type group --send
```

## Anti-misfire (why it rarely sends to the wrong person)

1. **Section filtering** — WeChat groups results into *Frequently used / Contacts / Groups / Chat history / Files / Functions…*. The tool only matches the first three, skipping *Chat history / Files / Functions* (the last is what turns "File Transfer" into a special popup).
2. **Length-aware fuzzy scoring** — a short exact name beats a long sentence that merely contains the keyword; whole "N related chat records" blocks are skipped.
3. **Title re-confirmation** — after opening the chat, it OCRs the header title (larger font, more reliable) and **aborts if it doesn't match** the target.

> Dry-run runs all the way through step 3 and prints what *would* be sent — it just doesn't press Enter. Always dry-run first.

## Adaptivity & tuning

The tool is **DPI-aware** and adapts to different resolutions:

- List-column UI (search box, result rows) uses **fixed logical pixels × DPI scale** (the list column width is fixed, not proportional to window width).
- The result row is clicked at its **actual OCR coordinates** — inherently adaptive.
- Chat area / input box are positioned **relative to the window size**.

Baseline constants (calibrated at 100% scaling, default list-column width) live at the top of [`wechat_send.py`](wechat_send.py). If your layout differs (e.g. you dragged the list divider, or an unusual window size), tune `SEARCH_BOX_*`, `RESULTS_*`, `TITLE_*`, `INPUT_*` or the OCR `-Scale`. The failure JSON includes the raw `ocr` lines to help you calibrate.

## Troubleshooting

- **"WeChat window not found"** — WeChat isn't running / logged in. Minimized or tray is fine.
- **No match / score too low** — name too generic → be more specific; add `--type`; raise OCR `-Scale` or lower `MATCH_THRESHOLD`; inspect the `ocr` field in the output.
- **Title confirmation failed** — adjust `TITLE_*` to frame the title, or (not recommended) `--no-confirm-title`.
- **Clicks land in the wrong place** — usually a window-size/DPI mismatch; re-check the baseline constants.
- **`.ps1` Chinese parse error** — `wx_helper.ps1` must be saved as **UTF-8 with BOM** (Windows PowerShell 5.1 otherwise reads it as the local ANSI code page).

## Limitations & notes

- Relies on **screen coordinates + OCR** — inherently more fragile than an official API; a WeChat redesign or unusual layout may need recalibration.
- It grabs foreground focus and simulates input — don't use the computer while it runs.
- **Account-ban risk**: UI automation is much safer than protocol bots (it's literally clicking for you), but **high-frequency bulk sending** can still trip risk control. Use it for **low-frequency alerts/notifications**, not spam.
- Verified on **Weixin 4.1.10.31 / Windows 11**. On other setups, dry-run first to calibrate.

## Contributing

Issues and PRs welcome — especially layout constants for other resolutions/DPI, and an OCR-anchor auto-calibration mode. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)

## Disclaimer

For personal automation/convenience only. You are responsible for complying with WeChat's Terms of Service and applicable laws. The authors are not liable for account restrictions or any other consequences.
