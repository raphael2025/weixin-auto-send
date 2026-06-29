# weixin-auto-send

[English](README.md) | **简体中文**

控制本机**已登录的微信(Weixin 4.x)桌面客户端**:按联系人/群名**模糊搜索**并自动发送消息。**零 pip 依赖**,中文 OCR 用 Windows 自带能力,**离线免费**。

> 为什么要有它:新版微信 4.x 是 **Qt** 重写的,界面整个画在一块画布上,对 UIAutomation 几乎不可见 —— 为老微信 3.9.x 写的 `wxauto` 在它上面**用不了**。本工具用"**模拟人操作 + 截图 OCR**"驱动微信,不需要付费的 `wxautox`。

---

## 特性

- 🎯 按联系人/群名模糊搜索(微信自带模糊 + OCR 模糊评分)
- 🆓 免费离线 —— 用系统自带 `Windows.Media.Ocr`(简体中文),不依赖第三方 OCR
- 📦 零安装 —— 纯 Python 标准库(`ctypes`)+ 一个 PowerShell 助手
- 🛡️ **防发错人**:区块过滤 + 长度感知匹配 + 发送前 **OCR 标题二次确认**
- 👀 默认 dry-run 预览;加 `--send` 才真发
- 🔍 自适应分辨率与 DPI 缩放(DPI 感知;直接点 OCR 命中坐标)
- 🪟 微信最小化到托盘也能唤醒,并强制置顶(绕过前台锁定)

## 工作原理

```
定位并唤醒微信窗口(含托盘隐藏)→ 强制置顶
  → 点搜索框 → 粘贴名字(微信自带模糊匹配)
  → 截图结果 → Windows OCR 读出每行文字+坐标
  → 选中正确目标 → 点击打开聊天
  → 再 OCR 一次顶部标题做二次确认(防发错人)
  → 粘贴消息 + 回车
```

| 文件 | 作用 |
|---|---|
| [`wechat_send.py`](wechat_send.py) | 主程序:窗口控制、鼠标/键盘、剪贴板、匹配、流程(`ctypes`,标准库) |
| [`wx_helper.ps1`](wx_helper.ps1) | 「看」的助手:截图 + Windows `Windows.Media.Ocr`,返回带绝对屏幕坐标的文字行 JSON |

## 环境要求

- **Windows 10/11**,装有**简体中文 OCR 语言组件**(中文系统默认带;自检:`Get-WindowsCapability -Online | ? Name -like "*OCR*Hans*"`)。
- **微信 Weixin 4.x** 已安装、已登录、保持**运行**(可最小化/托盘,会被唤醒;别完全退出)。
- **Python 3.x**,无需第三方库。
- 运行时不要锁屏;它会短暂接管鼠标键盘 —— **别同时动鼠标**。

## 快速开始

```bash
# 预览(dry-run,默认):打开聊天+确认标题,但【不发送】
python wechat_send.py --to "工作群" --msg "服务器 #3 离线" --type group

# 真正发送:加 --send
python wechat_send.py --to "工作群" --msg "服务器 #3 离线,请检查" --type group --send

# 最安全的真发测试 —— 发给自己(文件传输助手):
python wechat_send.py --to "文件传输助手" --msg "测试" --send
```

输出示例:

```
[1] 微信窗口: 1669x1075 @ (806,50), DPI×1.0
[2] 已搜索: 「工作群」(模糊)
[3] 命中结果: 「项目协作工作群」 (相似度 0.80)
[4] 聊天标题: 「项目协作工作群(25)」 (与目标相似度 0.62)
[5] 已发送给「项目协作工作群(25)」: 服务器 #3 离线,请检查
```

## 命令行参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `--to` | 是 | 联系人/群名(支持模糊) |
| `--msg` | 是 | 消息内容(任意字符,走剪贴板粘贴) |
| `--type` | 否 | `any`(默认)/ `contact` / `group` —— 缩小匹配范围 |
| `--send` | 否 | **加上才真发**;不加=dry-run 预览 |
| `--no-confirm-title` | 否 | 跳过打开后标题二次确认(**不推荐**) |

退出码:`0`=成功,`2`=失败(未匹配/相似度过低/标题确认失败)。

## 作为模块调用

```python
import sys; sys.path.insert(0, r"path/to/weixin-auto-send")
from wechat_send import send_message

res = send_message(
    to="工作群",           # 模糊名
    msg="⚠️ 服务器 web-3 离线",
    kind="group",          # any / contact / group
    send=True,             # False=预览
    confirm_title=True,    # 保持标题二次确认
    verbose=False,
)
if not res["ok"]:
    print("发送失败:", res.get("reason"))
```

见 [`examples/alert_example.py`](examples/alert_example.py)。

## 作为 MCP server 使用(多 AI 接入)

把"发微信"暴露成 **MCP 工具**,任何支持 MCP 的 AI(Claude Desktop、Claude Code、Cursor、各类 agent…)都能调用。封装见 [`wechat_mcp.py`](wechat_mcp.py)。

1. 装 SDK(核心工具仍零依赖):
   ```bash
   pip install mcp
   ```
2. 让你的 MCP 客户端启动 `wechat_mcp.py`。

**Claude Desktop** —— `claude_desktop_config.json`:
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

暴露的工具:**`wechat_send_message(to, message, kind="any", dry_run=True)`**。
`dry_run` 默认 **True**(只预览:找到目标并报告"将发给谁",不真发)。AI 必须显式传 `dry_run=False` 才真正发送 —— 多个 agent 都能调用时这是更安全的默认。

## 从任意 agent 调用(HTTP API / CLI)

对于**不是 MCP 客户端**的框架(OpenClaw、Hermes Agent、n8n、shell 脚本、任意语言),起一个零依赖的本地 **HTTP 服务**(同样纯标准库):

```bash
python wechat_http.py        # http://127.0.0.1:8765  (仅本机)
```

之后任何能发 HTTP 请求的东西都能发消息:
```bash
curl -X POST http://127.0.0.1:8765/send \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"to":"工作群","message":"hi","kind":"group","dry_run":false}'
# GET /health 做存活检查
```

- 请求体:`to`(必填)、`message`(必填)、`kind`(`any`/`contact`/`group`)、`dry_run`(默认 `false`)、`confirm_title`(默认 `true`)。
- 返回与 CLI/MCP 相同的结果 dict。成功 HTTP `200`,失败 `422`。
- 可选鉴权:设环境变量 `WX_API_TOKEN`,请求带 `X-Token: <token>` 头。改监听地址用 `WX_API_HOST` / `WX_API_PORT`。

或者,任何能跑命令的 agent 直接调 CLI:
```bash
python wechat_send.py --to "工作群" --msg "hi" --type group --send
```

## 防发错人机制

1. **区块过滤** —— 微信把结果分「最常使用/联系人/群聊/聊天记录/聊天文件/功能…」。工具只在前三类匹配,跳过「聊天记录/聊天文件/功能」(后者正是把"文件传输助手"开成特殊弹窗的陷阱)。
2. **长度感知模糊评分** —— 短的精确名 > 含关键词的长句子;整块「共 N 条相关聊天记录」直接跳过。
3. **标题二次确认** —— 打开聊天后 OCR 顶部标题(大字更准),**对不上就中止**。

> dry-run 会完整走到第 3 步并打印将要发送的对象与内容,只是不按回车。上线前务必先 dry-run。

## 自适应与调参

工具已做 **DPI 感知**,可适配不同分辨率:

- 列表栏 UI(搜索框、结果行)用**固定逻辑像素 × DPI 缩放**(列表栏宽度是固定的,不随窗口变宽成比例)。
- 结果行点击使用 **OCR 返回的真实坐标**,天然自适应。
- 聊天区/输入框按**窗口尺寸**定位。

基准常量(在 100% 缩放、默认列表栏宽度下标定)在 [`wechat_send.py`](wechat_send.py) 顶部。若你的布局不同(如拖动过列表分隔线、或窗口尺寸异常),可调 `SEARCH_BOX_*`、`RESULTS_*`、`TITLE_*`、`INPUT_*` 或 OCR 的 `-Scale`。失败时返回的 JSON 含原始 `ocr` 行,便于校准。

## 常见问题

- **"未找到微信窗口"** —— 微信没开/没登录。最小化或托盘没关系。
- **匹配不到/相似度过低** —— 名字太通用 → 更具体;加 `--type`;调大 OCR `-Scale` 或调低 `MATCH_THRESHOLD`;看输出的 `ocr` 字段。
- **标题确认失败** —— 调 `TITLE_*` 对准标题;或(不推荐)`--no-confirm-title`。
- **点偏了** —— 多半是窗口大小/DPI 不符,复查基准常量。
- **`.ps1` 中文解析报错** —— `wx_helper.ps1` 必须存为 **UTF-8 带 BOM**(否则 PowerShell 5.1 按本地 ANSI 代码页读)。

## 已知限制

- 依赖**屏幕坐标 + OCR**,本质比官方 API 脆;微信改版或异常布局可能要重新校准。
- 会抢占前台焦点并模拟输入,运行时别用电脑。
- **封号风险**:UI 模拟比协议机器人安全得多(等同你手动点),但**高频群发**仍可能触发风控。建议仅用于**低频告警/通知**,不要刷屏。
- 仅在 **Weixin 4.1.10.31 / Windows 11** 实测过;其他环境请先 dry-run 校准。

## 贡献

欢迎 Issue / PR —— 尤其是其他分辨率/DPI 的布局常量,以及 OCR 锚点自动校准模式。见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

[MIT](LICENSE)

## 免责声明

仅供个人自动化/便利使用。请自行遵守微信服务条款及适用法律。作者不对账号限制或任何其他后果负责。
