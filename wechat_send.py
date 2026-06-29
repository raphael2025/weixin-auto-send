#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wechat_send.py — 微信(Weixin 4.x)自动发消息小工具 / 纯标准库, 零 pip 安装

原理: 激活微信 -> 点搜索框 -> 粘贴名字(微信自带模糊搜索) -> OCR 结果列表选中正确目标
      -> 打开聊天 -> OCR 顶部标题二次确认 -> 粘贴消息并回车发送。
依赖: 同目录 wx_helper.ps1 (用 Windows 自带中文 OCR 做"看"的部分)。

用法示例:
  # 预览(dry-run, 默认): 只搜索/定位/确认, 不真的发送
  python wechat_send.py --to "工作群" --msg "服务器 #3 离线" --type group
  # 真的发送:
  python wechat_send.py --to "工作群" --msg "服务器 #3 离线" --type group --send
  # 作为模块调用见文件末尾 send_message()
"""
import argparse
import ctypes
import json
import subprocess
import sys
import time
from ctypes import wintypes
from difflib import SequenceMatcher
from pathlib import Path

HELPER = str(Path(__file__).with_name("wx_helper.ps1"))

# ---- 可调参数(布局/时序) ----
# 自适应模型: 左侧列表栏是「固定逻辑像素」(不随窗口变宽), 故下列偏移按【逻辑像素】给,
# 运行时统一乘以窗口 DPI 缩放(win["dpi"])换算成物理像素; 聊天区/输入框则按窗口尺寸。
# 这些基准值在 100% 缩放、列表栏默认宽度下标定。
SEARCH_BOX_DX, SEARCH_BOX_DY = 160, 55      # 搜索框点击点(逻辑像素, 相对窗口左上)
RESULTS_DX, RESULTS_W = 100, 250            # OCR 结果列文字区(逻辑像素, 跳过头像列)
RESULTS_DY = 78                             # 结果区顶部(逻辑像素); 高度运行时动态算到窗口底部
TITLE_DX, TITLE_DY, TITLE_W, TITLE_H = 345, 8, 460, 44  # 聊天标题区(逻辑像素)
INPUT_RX, INPUT_DY = 0.55, 60               # 输入框: x=窗口宽*0.55(落在聊天区), y=底部上方逻辑像素
T_AFTER_SEARCH = 1.2                         # 输入后等下拉框
T_AFTER_OPEN = 1.0                           # 点开聊天后等加载
MATCH_THRESHOLD = 0.45                       # 模糊匹配阈值
TITLE_THRESHOLD = 0.45                       # 标题确认阈值

# 结果下拉框里的「区块标题」
SECTION_HEADERS = {"最常使用", "联系人", "群聊", "聊天记录", "聊天文件",
                   "功能", "公众号", "小程序", "朋友圈", "群公告"}
# 默认只在这些区块里找可点开的目标(避开"聊天记录/功能"等)
ALLOWED_DEFAULT = {"最常使用", "联系人", "群聊"}

# ---------- win32 (ctypes) ----------
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                               wintypes.DWORD, ctypes.POINTER(ctypes.c_ulong)]
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD,
                               ctypes.POINTER(ctypes.c_ulong)]

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL, VK_RETURN, VK_ESCAPE = 0x11, 0x0D, 0x1B
VK_A, VK_V = 0x41, 0x56


def click(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.08)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, None)
    time.sleep(0.04)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, None)


def _key(vk, up=False):
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP if up else 0, None)


def hotkey_ctrl(vk):
    _key(VK_CONTROL); time.sleep(0.02); _key(vk); time.sleep(0.02)
    _key(vk, True); time.sleep(0.02); _key(VK_CONTROL, True)


def press(vk):
    _key(vk); time.sleep(0.03); _key(vk, True)


# ---------- 剪贴板 (Unicode, 64位安全) ----------
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
user32.SetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
user32.OpenClipboard.argtypes = [wintypes.HWND]


def set_clipboard(text: str):
    data = text.encode("utf-16-le") + b"\x00\x00"
    if not user32.OpenClipboard(None):
        raise OSError("OpenClipboard 失败")
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        ptr = kernel32.GlobalLock(h)
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(h)
        if not user32.SetClipboardData(CF_UNICODETEXT, h):
            raise OSError("SetClipboardData 失败")
    finally:
        user32.CloseClipboard()


# ---------- 调用 PowerShell 助手 ----------
def _ps(args):
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", HELPER] + args
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"助手失败: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def find_window(activate=True):
    out = _ps(["-Action", "find"] + (["-Activate"] if activate else []))
    return json.loads(out)


def release_window():
    try:
        _ps(["-Action", "release"])
    except Exception:
        pass


def shotocr(L, T, W, H, scale=3.0):
    out = _ps(["-Action", "shotocr", "-L", str(int(L)), "-T", str(int(T)),
               "-W", str(int(W)), "-H", str(int(H)), "-Scale", str(scale)])
    if not out:
        return []
    data = json.loads(out)
    if isinstance(data, dict):
        data = [data]
    return [r for r in data if isinstance(r, dict) and "y" in r and "cy" in r]


# ---------- 模糊匹配 ----------
def norm(s: str) -> str:
    return "".join(ch for ch in s if not ch.isspace())


BAD_SECTIONS = {"聊天记录", "聊天文件", "功能", "公众号", "小程序", "朋友圈", "群公告"}


def score(target: str, text: str) -> float:
    """长度感知: 短名字精确包含 > 长句子里碰巧包含。"""
    t, x = norm(target), norm(text)
    if not t or not x:
        return 0.0
    ratio = SequenceMatcher(None, t, x).ratio()
    overlap = sum(1 for ch in set(t) if ch in x) / len(set(t))   # 目标字覆盖率(抗OCR错字)
    if t in x:                       # 被包含: 候选越长(多余越多)分越低
        ratio = max(ratio, 0.6 + 0.4 * ratio)
    return max(ratio, overlap * 0.6)


def is_noise(text: str) -> bool:
    x = norm(text)
    if not x:
        return True
    if x.startswith("查看全部") or x.startswith("搜索"):
        return True
    if "相关聊天记录" in x or (x.startswith("共") and "条" in x):
        return True
    return False


def chat_record_zones(lines):
    """'共N条相关聊天记录' 标志一条聊天记录条目, 其上方约45px(标题+预览)整块跳过。"""
    zones = []
    for r in lines:
        if "相关聊天记录" in norm(r["text"]):
            zones.append((r["y"] - 48, r["y"] + r["h"] + 4))
    return zones


def in_zones(y, zones):
    return any(a <= y <= b for a, b in zones)


def pick_target(lines, target, allowed):
    """跟踪区块标题; 跳过坏区块/聊天记录块/噪声行; 长度感知评分取最高。"""
    lines = sorted(lines, key=lambda r: r["y"])
    zones = chat_record_zones(lines)
    saw_good_section = any(norm(r["text"]) in (allowed | {"最常使用"}) for r in lines)
    section = None
    best, best_s = None, 0.0
    for r in lines:
        x = norm(r["text"])
        if x in SECTION_HEADERS:
            section = x
            continue
        if section in BAD_SECTIONS and section not in allowed:   # 坏区块(除非显式允许, 如文件传输助手的「功能」)
            continue
        if saw_good_section and section is not None and section not in allowed:
            continue                          # 有分区时, 只在允许分区里找
        if is_noise(r["text"]) or in_zones(r["cy"], zones):
            continue
        s = score(target, r["text"])
        if s > best_s:
            best_s, best = s, r
    return best, best_s


# ---------- 主流程 ----------
def send_message(to: str, msg: str, kind="any", send=False, confirm_title=True, verbose=True):
    """返回 dict 结果。send=False 为预览(dry-run)。"""
    def log(*a):
        if verbose:
            print(*a, flush=True)

    if norm(to) in ("文件传输助手", "filehelper"):
        allowed = {"功能", "最常使用"}      # 文件传输助手是「功能」项, 单击即开聊天
    elif kind == "contact":
        allowed = {"联系人", "最常使用"}
    elif kind == "group":
        allowed = {"群聊", "最常使用"}
    else:
        allowed = ALLOWED_DEFAULT

    win = find_window(activate=True)   # 激活并临时置顶
    L, T, W, H = win["left"], win["top"], win["w"], win["h"]
    sc = float(win.get("dpi", 1.0)) or 1.0     # DPI 缩放: 逻辑像素 -> 物理像素
    px = lambda v: int(round(v * sc))          # 把逻辑像素换算成物理像素
    log(f"[1] 微信窗口: {W}x{H} @ ({L},{T}), DPI×{sc}")

    try:
        # 搜索
        click(L + px(SEARCH_BOX_DX), T + px(SEARCH_BOX_DY))
        time.sleep(0.35)
        hotkey_ctrl(VK_A)
        time.sleep(0.1)
        set_clipboard(to)
        time.sleep(0.12)
        hotkey_ctrl(VK_V)
        log(f"[2] 已搜索: 「{to}」(模糊)")
        time.sleep(T_AFTER_SEARCH)

        # OCR 结果列表(高度动态: 从结果区顶部一直到窗口底部)
        res_h = H - px(RESULTS_DY) - px(20)
        lines = shotocr(L + px(RESULTS_DX), T + px(RESULTS_DY), px(RESULTS_W), res_h)
        target, s = pick_target(lines, to, allowed)
        if target is None:
            press(VK_ESCAPE); press(VK_ESCAPE)
            return {"ok": False, "stage": "match", "reason": "未在结果中找到匹配目标",
                    "ocr": [r["text"] for r in lines]}
        log(f"[3] 命中结果: 「{target['text']}」 (相似度 {s:.2f})")
        if s < MATCH_THRESHOLD:
            press(VK_ESCAPE); press(VK_ESCAPE)
            return {"ok": False, "stage": "match", "reason": f"最佳匹配相似度过低 {s:.2f}",
                    "best": target["text"], "ocr": [r["text"] for r in lines]}

        # 点开聊天: 直接点 OCR 命中行的真实坐标(天然自适应, 无需硬编码 X)
        click(target["cx"], target["cy"])
        time.sleep(T_AFTER_OPEN)

        # 标题二次确认
        title_text = ""
        if confirm_title:
            tlines = shotocr(L + px(TITLE_DX), T + px(TITLE_DY), px(TITLE_W), px(TITLE_H))
            title_text = norm(" ".join(r["text"] for r in tlines))
            ts = score(to, title_text) if title_text else 0.0
            log(f"[4] 聊天标题: 「{title_text}」 (与目标相似度 {ts:.2f})")
            if ts < TITLE_THRESHOLD:
                press(VK_ESCAPE); press(VK_ESCAPE)
                return {"ok": False, "stage": "confirm",
                        "reason": f"标题确认失败(相似度 {ts:.2f}), 已中止以防发错", "title": title_text}

        # 发送
        if not send:
            log(f"[5] [DRY-RUN] 未发送。将发给「{title_text or target['text']}」内容: {msg}")
            return {"ok": True, "dry_run": True, "target": title_text or target["text"], "msg": msg}

        click(L + int(W * INPUT_RX), T + H - px(INPUT_DY))   # 聚焦底部输入框(聊天区)
        time.sleep(0.3)
        set_clipboard(msg)
        time.sleep(0.15)
        hotkey_ctrl(VK_V)
        time.sleep(0.35)
        press(VK_RETURN)
        time.sleep(0.4)
        log(f"[5] 已发送给「{title_text or target['text']}」: {msg}")
        return {"ok": True, "dry_run": False, "target": title_text or target["text"], "msg": msg}
    finally:
        release_window()   # 释放置顶, 恢复普通层级


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="微信(4.x)自动发消息 — 默认 dry-run, 加 --send 才真发")
    ap.add_argument("--to", required=True, help="联系人/群名(支持模糊)")
    ap.add_argument("--msg", required=True, help="消息内容")
    ap.add_argument("--type", choices=["any", "contact", "group"], default="any", help="目标类型(缩小匹配范围)")
    ap.add_argument("--send", action="store_true", help="真正发送(不加=预览)")
    ap.add_argument("--no-confirm-title", action="store_true", help="跳过打开后标题二次确认(不推荐)")
    a = ap.parse_args()
    res = send_message(a.to, a.msg, kind=a.type, send=a.send,
                       confirm_title=not a.no_confirm_title)
    print("\n结果:", json.dumps(res, ensure_ascii=False))
    sys.exit(0 if res.get("ok") else 2)


if __name__ == "__main__":
    main()
