# magicallyEncircle for Windows

在 Windows 10/11 上用 **Alt + 鼠标左键** 或 **鼠标中键** 画图案来触发快捷键、圈选复制文本/截图的小工具。

这是 macOS 版 [magicallyEncircle](../magicallyEncircle) 的 Windows 复刻版，核心识别算法、模板、阈值和交互逻辑保持一致；平台相关部分（全局钩子、透明覆盖层、快捷键发送、托盘、设置窗口）用 Windows / Python 重新实现。

---

## 功能

- Alt + 左键 / 鼠标中键绘制发光魔法线条（可切换）
- 内置图案：撤销、复制、粘贴、新建标签页、后退、前进、任务视图、锁定屏幕、删除、关闭、左右切换虚拟桌面
- 自定义图案：录制、重命名、删除、绑定快捷键、绑定 App、播放演示
- 多笔画：Alt 双击 / 单击模式；中键模式按空闲时间自动识别
- 闭环：快速松开复制圈内文本（Windows OCR）；按住 1 秒截图到剪贴板
- 识别结果 HUD、视觉风格、导入/导出、开机自启动
- 与 macOS 版互相导入/导出图案（导出文件带 `platform` / `coordinateSystem`）

---

## 开发运行

推荐使用项目指定的 Python 3.11：

```powershell
D:\work\env\miniconda\envs\p3.11\python.exe -m pip install -r requirements.txt
D:\work\env\miniconda\envs\p3.11\python.exe run_app.py
```

无控制台运行：

```powershell
D:\work\env\miniconda\envs\p3.11\pythonw.exe run_app.py
```

调试日志：

```powershell
D:\work\env\miniconda\envs\p3.11\python.exe run_app.py --debug
```

日志与配置默认在 `%APPDATA%\magicallyEncircle`。把 `portable.flag` 放在 exe 同目录（或加 `--portable`）会改用同目录 `data/`。

常用调试参数：

```powershell
python run_app.py --debug       # 控制台输出日志
python run_app.py --settings    # 启动时直接打开设置窗口
python run_app.py --self-test   # 检查显示器枚举与 Windows OCR 后退出
```

数据目录可以用环境变量临时覆盖（测试用）：

```powershell
$env:MAGICALLY_ENCIRCLE_DATA_DIR = "C:\Temp\me-test"
```

---

## 打包

### 便携版

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

产物：

- `dist\MagicallyEncircle\MagicallyEncircle.exe`（目录版，推荐）
- `dist\MagicallyEncircle-portable.zip`（带 `portable.flag`，解压即用）

> 使用 `--onedir` 而不是 `--onefile`：启动更快、杀毒软件误报更少，也方便替换图标/资源。
>
> 本项目当前用 conda p3.11 构建。conda 把 `ffi.dll` / `libssl` 等运行库放在
> `envs\p3.11\Library\bin`，`packaging/app.spec` 已显式把这些 DLL 打进去；
> 如果换用 python.org 的 venv，可以删掉 spec 里的 `conda_bin` 循环（保留也不会出错）。

### 安装包（可选）

安装 [Inno Setup 6](https://jrsoftware.org/isinfo.php) 后运行：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Installer
```

生成 `dist\MagicallyEncircle-Setup.exe`，按当前用户安装到 `%LOCALAPPDATA%\Programs\magicallyEncircle`，不需要管理员权限。

---

## 与 macOS 版互导

导出的 JSON 结构：

```json
{
  "version": 2,
  "platform": "windows",
  "coordinateSystem": "appkit-y-up",
  "gestures": [ ... ],
  "builtInOverrides": { ... }
}
```

- 坐标统一导出为 AppKit 风格（y 向上），Windows 导入时自动翻回屏幕坐标。
- `platform` 用来判断快捷键/App 绑定是否可用：
  - macOS 导入 Windows 文件：保留图案，清空 Windows 键码/App 路径，提示重新绑定。
  - Windows 导入 macOS 文件：保留图案，清空 macOS 键码/Bundle ID，提示重新绑定。
- 旧版 macOS 文件没有 `platform` 字段时按 `macos` + `appkit-y-up` 处理。
- macOS 端对应改动在 `GesturePackage.swift` 与 `MagicController.importGestures()`。

---

## 已知限制

- **没有代码签名**：首次运行可能出现 SmartScreen 提示；带全局钩子的程序也可能被个别杀毒软件误报。
- 普通权限进程无法向管理员权限窗口发送输入，也无法钩到 UAC/锁屏安全桌面。
- Alt 键在 Windows 上兼有“激活菜单栏”的语义；个别程序可能在松开 Alt 时闪一下菜单。遇到这种情况可在「通用设置」切换为鼠标中键。
- “共享”功能未实现（Windows 没有 macOS 那样统一的文件共享菜单）。
- “窗口速览”在 Windows 上映射为任务视图（Win+Tab）；“显示桌面”映射为 Win+D。
- “拖文件到屏幕边缘切换桌面”未实现（Windows 的文件拖拽检测与 macOS 差异很大）。
- 虚拟桌面切换后，置顶覆盖层可能不会自动跟随；当前在每次开始绘制时会重新置顶。若遇到不可见，重启应用即可。
- 圈选 OCR 使用系统自带的 Windows OCR；需要安装对应语言包（中文 Windows 通常已包含）。
- Windows 版的更新源（`version-win.json`）尚未发布，因此「启动时检查更新」默认关闭；手动检查会提示无法获取版本信息。
- 微信/支付宝赞赏码没有包含在 Windows 版设置里。

---

## 目录结构

```text
magically_encircle/
├─ app.py                  # 入口、单实例、托盘
├─ controller.py           # 核心协调器（对应 MagicController.swift）
├─ playback.py             # 图案回放
├─ config.py               # 路径、设置
├─ constants.py            # Win32 常量、阈值
├─ gesture/                # 几何、识别器、内置模板与动作
├─ model/gestures.py       # 数据模型、JSON 持久化
├─ platform_support/       # 钩子、覆盖层、SendInput、截图、OCR、自启动、更新
└─ ui/                     # 托盘、设置、画布、HUD、主题
```

---

## 测试

```powershell
D:\work\env\miniconda\envs\p3.11\python.exe -m unittest discover -s tests -v
```

识别器测试使用从 macOS Swift 源码提取的模板，覆盖自识别、反向绘制、±10° 旋转、多笔叉号、直线滑动与闭环判断。
