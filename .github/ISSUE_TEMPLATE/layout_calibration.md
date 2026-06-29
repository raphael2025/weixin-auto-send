---
name: Layout / resolution calibration / 布局·分辨率校准
about: Share working layout constants for your resolution/DPI, or report clicks landing off
title: "[layout] "
labels: layout
---

<!-- Help the tool work on more screens. 帮助工具适配更多屏幕。 -->

## Setup / 环境
- Screen resolution / 分辨率:
- Display scaling (DPI) / 缩放比例:
- WeChat window size & maximized? / 微信窗口大小、是否最大化:
- WeChat version / 微信版本:

## Symptom / 现象
<!-- e.g. click lands in chat area / title confirm fails / result not found
     如:点到了聊天区 / 标题确认失败 / 找不到结果 -->


## Working values (if you found them) / 调通的常量(若已找到)
<!-- from the top of wechat_send.py / 来自 wechat_send.py 顶部 -->
```python
SEARCH_BOX_DX, SEARCH_BOX_DY =
RESULTS_DX, RESULTS_W =
RESULTS_DY =
TITLE_DX, TITLE_DY, TITLE_W, TITLE_H =
INPUT_RX, INPUT_DY =
# OCR -Scale =
```

## Raw OCR (optional) / 原始 OCR(可选)
<!-- The `ocr` field from a failed dry-run helps a lot.
     失败 dry-run 返回的 `ocr` 字段很有帮助。 -->
```
(paste here)
```
