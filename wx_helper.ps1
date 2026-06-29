<#
  wx_helper.ps1 — 微信自动化「感知」助手 (供 wechat_send.py 调用)
  动作:
    -Action find                          定位微信主窗口(可选 -Activate 恢复并置前),输出 JSON {handle,left,top,right,bottom,w,h}
    -Action shotocr -L -T -W -H [-Scale 3] 截取屏幕指定矩形 -> 放大 -> Windows自带中文OCR
                                          输出 JSON 行数组,坐标已换算回「绝对屏幕坐标」: {text,x,y,w,h,cx,cy}
  说明: 仅做「看」,不做「点/打字」(那些在 Python 里用 ctypes 完成)。
#>
param(
  [Parameter(Mandatory=$true)][ValidateSet('find','shotocr','release')][string]$Action,
  [int]$L, [int]$T, [int]$W, [int]$H,
  [double]$Scale = 3.0,
  [switch]$Activate
)
$ErrorActionPreference='Stop'
# 确保把 UTF-8 写到 stdout, 供 Python 以 utf-8 抓取(中文 JSON 不乱码)
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch {}

# ---------- DPI 感知(必须在任何窗口/GDI 调用之前) ----------
Add-Type @'
using System;using System.Runtime.InteropServices;
public class DpiAware {
  [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
  [DllImport("shcore.dll")] public static extern int SetProcessDpiAwareness(int v);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  public static void Enable(){
    try{ if(SetProcessDpiAwarenessContext(new IntPtr(-4))) return; }catch{} // PER_MONITOR_AWARE_V2
    try{ SetProcessDpiAwareness(2); return; }catch{}                        // PROCESS_PER_MONITOR_DPI_AWARE
    try{ SetProcessDPIAware(); }catch{}                                     // 旧系统兜底
  }
}
'@
try { [DpiAware]::Enable() } catch {}

# ---------- win32 ----------
Add-Type @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class Win32 {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte sc, uint f, UIntPtr e);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr h);
  [StructLayout(LayoutKind.Sequential)] public struct RECT{public int Left,Top,Right,Bottom;}
  static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
  static readonly IntPtr HWND_NOTOPMOST = new IntPtr(-2);
  const uint SWP = 0x0001 | 0x0002 | 0x0040; // NOSIZE|NOMOVE|SHOWWINDOW
  // 绕过前台锁定: Alt 轻点解锁 + 把本线程输入挂到当前前台线程 + 强制置前 + 临时置顶(盖过别的置顶窗口)。
  public static void ForceForeground(IntPtr hwnd){
    if(IsIconic(hwnd)){ ShowWindow(hwnd, 9); System.Threading.Thread.Sleep(250); } // SW_RESTORE
    IntPtr fore = GetForegroundWindow();
    uint dummy; uint foreThread = GetWindowThreadProcessId(fore, out dummy);
    uint thisThread = GetCurrentThreadId();
    keybd_event(0x12,0,0,UIntPtr.Zero); keybd_event(0x12,0,2,UIntPtr.Zero);     // Alt down/up
    bool attached=false;
    if(foreThread != thisThread){ attached = AttachThreadInput(thisThread, foreThread, true); }
    ShowWindow(hwnd, 5); BringWindowToTop(hwnd); SetForegroundWindow(hwnd);     // SW_SHOW
    SetWindowPos(hwnd, HWND_TOPMOST, 0,0,0,0, SWP);                              // 置顶, 盖过前台锁定/置顶窗口
    if(attached){ AttachThreadInput(thisThread, foreThread, false); }
  }
  // 释放置顶, 让微信恢复普通层级。
  public static void Release(IntPtr hwnd){ SetWindowPos(hwnd, HWND_NOTOPMOST, 0,0,0,0, SWP); }
  // 注意: 微信4.x 最小化=隐藏窗口(IsWindowVisible=False 且非 iconic),所以这里不按可见性过滤。
  // 主窗口特征: 类名精确匹配 ^Qt\d+QWindowIcon$ (排除 ToolSaveBits 气泡、WxTrayIcon 托盘消息窗等)。
  public static List<IntPtr> Find(string procName){
    var found=new List<IntPtr>();
    var rx=new System.Text.RegularExpressions.Regex(@"^Qt\d+QWindowIcon$");
    EnumWindows((h,l)=>{
      uint pid; GetWindowThreadProcessId(h, out pid);
      try{ var p=System.Diagnostics.Process.GetProcessById((int)pid);
        if(!string.Equals(p.ProcessName, procName, StringComparison.OrdinalIgnoreCase)) return true;
      }catch{ return true; }
      var cn=new StringBuilder(256); GetClassName(h,cn,256);
      if(!rx.IsMatch(cn.ToString())) return true;
      found.Add(h);
      return true;
    }, IntPtr.Zero);
    return found;
  }
}
'@

function Get-MainWindow {
  $cands = [Win32]::Find('Weixin')
  if($cands.Count -eq 0){ throw '未找到微信窗口,请确认微信(Weixin 4.x)已登录并在运行。' }
  # 收集每个候选窗口的尺寸/最小化状态/标题
  $info = foreach($h in $cands){
    $r=New-Object Win32+RECT; [Win32]::GetWindowRect($h,[ref]$r)|Out-Null
    $sb=New-Object System.Text.StringBuilder 256; [Win32]::GetWindowText($h,$sb,256)|Out-Null
    [pscustomobject]@{ h=$h; w=($r.Right-$r.Left); ht=($r.Bottom-$r.Top);
                       iconic=[Win32]::IsIconic($h); title=$sb.ToString() }
  }
  # 主窗口特征: 标题为「微信」, 或处于最小化(iconic, 尺寸会塌缩), 或本身够大(>=600x400)。
  # 排除那些既不大也非最小化的小弹窗(标题多为 'Weixin')。
  $main = $info | Where-Object { $_.iconic -or ($_.w -ge 600 -and $_.ht -ge 400) }
  if(-not $main){ $main = $info }
  $best = $main | Sort-Object `
            @{Expression={$_.title -eq '微信'}; Descending=$true}, `
            @{Expression={$_.iconic};           Descending=$true}, `
            @{Expression={$_.w * $_.ht};         Descending=$true} |
          Select-Object -First 1
  return $best.h
}

if($Action -eq 'find'){
  $h = Get-MainWindow
  if($Activate){
    [Win32]::ForceForeground($h)
    Start-Sleep -Milliseconds 500
  }
  $r=New-Object Win32+RECT; [Win32]::GetWindowRect($h,[ref]$r)|Out-Null
  $dpi=96; try{ $d=[Win32]::GetDpiForWindow($h); if($d -gt 0){ $dpi=$d } }catch{}
  [pscustomobject]@{
    handle=[int64]$h; left=$r.Left; top=$r.Top; right=$r.Right; bottom=$r.Bottom;
    w=($r.Right-$r.Left); h=($r.Bottom-$r.Top); dpi=[math]::Round($dpi/96.0,3)
  } | ConvertTo-Json -Compress
  exit 0
}

if($Action -eq 'release'){
  $h = Get-MainWindow
  [Win32]::Release($h)
  "released"
  exit 0
}

if($Action -eq 'shotocr'){
  Add-Type -AssemblyName System.Drawing
  Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
  # 1) 截图指定屏幕矩形
  $bmp=New-Object System.Drawing.Bitmap($W,$H)
  $g=[System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($L,$T,0,0,(New-Object System.Drawing.Size($W,$H)))
  $g.Dispose()
  # 2) 放大(小字 OCR 关键)
  $sw=[int]($W*$Scale); $sh=[int]($H*$Scale)
  $big=New-Object System.Drawing.Bitmap($sw,$sh)
  $gb=[System.Drawing.Graphics]::FromImage($big)
  $gb.InterpolationMode=[System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $gb.DrawImage($bmp,0,0,$sw,$sh); $gb.Dispose(); $bmp.Dispose()
  $tmp=[System.IO.Path]::Combine($env:TEMP, "wx_shotocr_$PID.png")
  $big.Save($tmp,[System.Drawing.Imaging.ImageFormat]::Png); $big.Dispose()

  # 3) WinRT OCR
  $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
  function Await($op,$rt){ $t=$asTaskGeneric.MakeGenericMethod($rt).Invoke($null,@($op)); $t.Wait(-1)|Out-Null; $t.Result }
  [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
  [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
  [Windows.Media.Ocr.OcrEngine,Windows.Media,ContentType=WindowsRuntime] | Out-Null
  [Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime] | Out-Null
  $file    = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($tmp)) ([Windows.Storage.StorageFile])
  $stream  = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $sbmp    = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $lang=New-Object Windows.Globalization.Language("zh-Hans-CN")
  $engine=[Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
  if($null -eq $engine){ $engine=[Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
  $res = Await ($engine.RecognizeAsync($sbmp)) ([Windows.Media.Ocr.OcrResult])

  $lines=@()
  foreach($line in $res.Lines){
    $minX=1e9;$minY=1e9;$maxX=0;$maxY=0
    foreach($wd in $line.Words){ $b=$wd.BoundingRect
      if($b.X -lt $minX){$minX=$b.X}; if($b.Y -lt $minY){$minY=$b.Y}
      if(($b.X+$b.Width) -gt $maxX){$maxX=$b.X+$b.Width}; if(($b.Y+$b.Height) -gt $maxY){$maxY=$b.Y+$b.Height} }
    # 放大空间坐标 -> 绝对屏幕坐标
    $ax=$L + ($minX/$Scale); $ay=$T + ($minY/$Scale)
    $aw=($maxX-$minX)/$Scale; $ah=($maxY-$minY)/$Scale
    $lines += [pscustomobject]@{
      text=($line.Text -replace '\s','')   # 去掉 OCR 在汉字间插入的空格
      x=[int]$ax; y=[int]$ay; w=[int]$aw; h=[int]$ah
      cx=[int]($ax+$aw/2); cy=[int]($ay+$ah/2)
    }
  }
  Remove-Item $tmp -ErrorAction SilentlyContinue
  $lines | ConvertTo-Json -Depth 4 -Compress
  exit 0
}
