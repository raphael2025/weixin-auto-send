# Contributing / 贡献指南

[English](#english) · [简体中文](#简体中文)

## English

Thanks for helping improve **weixin-auto-send**! This project drives the WeChat 4.x
desktop client via simulated input + Windows OCR, so most improvements are about
**robustness across machines**.

### High-value contributions

- **Layout constants for other resolutions / DPI** — report your screen resolution,
  DPI scaling, window size, and the values that worked (`SEARCH_BOX_*`, `RESULTS_*`,
  `TITLE_*`, `INPUT_*`).
- **OCR-anchor auto-calibration** — locate the search box / list column / title by
  detecting text & features instead of relying on baseline constants.
- **WeChat version compatibility** — note the exact version (`Weixin.exe` ProductVersion)
  you tested and anything that differed.
- **i18n** — English-locale WeChat (title "Weixin" vs "微信"), other OCR languages.

### Dev notes

- `wechat_send.py` is pure Python stdlib (`ctypes`) — please keep **zero pip deps**.
- `wx_helper.ps1` must be saved as **UTF-8 with BOM** (Windows PowerShell 5.1 reads
  `.ps1` as the local ANSI code page otherwise — Chinese will break parsing).
- Keep "perception" (screenshot/OCR) in the PowerShell helper and "control/logic"
  (window/mouse/keyboard/matching) in Python.
- **Always test with dry-run first** (no `--send`). For a real send, target
  `文件传输助手` (File Transfer, i.e. yourself) so you don't message anyone.
- Include a short before/after note and, if relevant, the failure-JSON `ocr` lines.

### Reporting bugs

Open an issue with: WeChat version, Windows version, resolution + DPI scaling,
the exact command, the full console output (including the `ocr` field on failure),
and what you expected.

---

## 简体中文

感谢帮助改进 **weixin-auto-send**!本项目用"模拟输入 + Windows OCR"驱动微信 4.x 桌面端,
所以大多数改进都围绕**跨机器的鲁棒性**。

### 高价值贡献

- **其他分辨率/DPI 的布局常量** —— 反馈你的屏幕分辨率、DPI 缩放、窗口大小,以及调通的值
  (`SEARCH_BOX_*`、`RESULTS_*`、`TITLE_*`、`INPUT_*`)。
- **OCR 锚点自动校准** —— 靠识别文字/特征定位搜索框/列表栏/标题,不再依赖基准常量。
- **微信版本兼容** —— 注明你测试的确切版本(`Weixin.exe` 的 ProductVersion)及差异。
- **国际化** —— 英文版微信(标题 "Weixin" 而非 "微信")、其他 OCR 语言。

### 开发约定

- `wechat_send.py` 是纯 Python 标准库(`ctypes`)—— 请保持**零 pip 依赖**。
- `wx_helper.ps1` 必须存为 **UTF-8 带 BOM**(否则 PowerShell 5.1 按本地 ANSI 读 `.ps1`,中文会解析失败)。
- 「看」(截图/OCR)放 PowerShell 助手,「控制/逻辑」(窗口/鼠标/键盘/匹配)放 Python。
- **务必先用 dry-run 测试**(不加 `--send`)。真发请发给 `文件传输助手`(即自己),别打扰别人。
- 附上简短的前后对比;如相关,贴上失败 JSON 里的 `ocr` 行。

### 反馈 Bug

提 Issue 时请附:微信版本、Windows 版本、分辨率+DPI 缩放、完整命令、完整控制台输出
(失败时含 `ocr` 字段)、以及你期望的行为。
