# BOSS 简历筛选器 - 打包部署指南

## 跨平台支持

| 平台 | 输出格式 | 用途 |
|------|---------|------|
| Windows | `BOSS_ResumeFilter.exe` | 单文件可执行程序 |
| macOS | `BOSS_ResumeFilter.app` | 应用包 |
| macOS | `BOSS_ResumeFilter.dmg` | 安装包（用户拖拽安装） |
| macOS | `BOSS_ResumeFilter_mac.zip` | 自动更新用 |

`build.py` 自动检测当前平台，无需额外参数。

### 自动双平台发布（GitHub Actions）

推送 tag 后，GitHub Actions 自动在 Windows + macOS runner 上并行打包，产物上传到同一个 Release：

```bash
# 本地操作（Mac 或 Windows 均可）
python build.py --release --version 2.9   # 打包 → 打 tag → 推送
# GitHub Actions 自动补齐另一个平台的产物
```

Release 页面最终包含：
- `BOSS_ResumeFilter.exe` — Windows 用户
- `BOSS_ResumeFilter.dmg` — macOS 用户（手动安装）
- `BOSS_ResumeFilter_mac.zip` — macOS 自动更新用

配置文件：`.github/workflows/release.yml`

---

## 方案一：Windows 打包（单文件 EXE）

### 1. 环境准备

#### 开发机（打包用）
- Windows 10/11
- Python 3.9+（推荐 3.11）
- pip 包管理器

#### 目标机（运行用）
- Windows 10/11
- Chrome 浏览器（必需）
- 无需安装 Python

### 2. 打包步骤

#### 步骤 1：安装打包工具

```bash
# 进入项目目录
cd boss-resume-filter

# 安装打包工具
pip install pyinstaller

# 安装项目依赖
pip install -r requirements.txt
```

#### 步骤 2：执行打包

```bash
# 仅执行发布前检查：不打包、不提交、不推送
python build.py --check

# 使用自动打包脚本（推荐）
python build.py

# 一键发布：打包 → 提交 → 打 tag → 推送 → GitHub Release
python build.py --release

# 自动更新版本号 + 一键发布
python build.py --release --version 2.5

# 或手动打包（不推荐，缺少依赖检查和 PIL 完整收集）
pyinstaller --onefile --noconsole \
    --collect-all PIL \
    --collect-submodules tkinter \
    --hidden-import=tkinter \
    --hidden-import=tkinter.ttk \
    --hidden-import=tkinter.font \
    --hidden-import=tkinter.filedialog \
    --hidden-import=tkinter.messagebox \
    --name "BOSS_ResumeFilter" \
    gui_main.py
```

`--check` 会验证：

- 核心依赖可导入
- `.storage/` 未被 Git 跟踪
- `.env`、`candidates_all.json`、`candidates_all.xlsx` 未被 Git 跟踪
- `api_config.json` 不含明文 `api_key` / `api_key_ref`
- 核心源码可通过 `py_compile`
- `python tests/run_unit_tests.py` 通过
- `python tests/test_import.py` 通过
- 工作区干净

Release 模式不会再执行 `git add -A`。除 `--version` 自动修改 `gui_main.py` 外，其他变更必须先手工提交，否则发布脚本会中断。

Release 标题和说明必须先写在 `CHANGELOG.md` 对应版本段落中。`python build.py --release` 会自动提取该段落作为 GitHub Release 内容；如果缺少对应版本，或未按以下顺序分类，发布会直接中断：

- 新增功能
- 行为优化
- UI 改进
- Bug 修复
- 构建改进

如果打包环境来自 Anaconda，`build.py` 会自动定位并打包：

- `Lib/tkinter`
- `DLLs/_tkinter.pyd`
- `Library/lib/tcl8.6`
- `Library/lib/tk8.6`（打包到 EXE 内部的 `tcl/tk8.6`）
- `Library/bin/tcl86t.dll`
- `Library/bin/tk86t.dll`

不要绕过 `build.py` 直接手写 PyInstaller 命令，否则容易生成启动时报 `No module named 'tkinter'` 的 EXE。

#### 步骤 3：获取输出

打包完成后，`dist/` 目录下会生成：

```
dist/
├── BOSS_ResumeFilter.exe   <-- 主程序
├── job_config.json        <-- 岗位配置
├── selectors.json         <-- 页面选择器配置（DOM 变化时可直接编辑）
└── README.md             <-- 说明文档
```

CHANGELOG.md 通过 `--add-data` 嵌入 EXE 内部（PyInstaller 解压到 `_MEIPASS`），无需单独分发。

### 3. 部署到目标电脑

**注意：首次在新电脑部署需要重新配置 API Key。**
详细步骤见 [DEPLOYMENT.md](DEPLOYMENT.md)。

#### 方式 A：复制文件夹（推荐）

1. 将 `dist/` 目录复制到目标电脑任意位置
2. 双击 `BOSS_ResumeFilter.exe` 运行

#### 方式 B：创建快捷方式

```bash
# 在桌面创建快捷方式（手动操作）
1. 右键 BOSS_ResumeFilter.exe
2. 发送到 -> 桌面快捷方式
```

### 4. 首次运行配置

#### 步骤 1：配置岗位规则

编辑 `job_config.json`：

```json
{
    "job_requirements": {
        "高级 Java 工程师": {
            "min_exp": 5,
            "edu": "本科",
            "keywords": ["Java", "Spring Boot", "MySQL", "Redis"],
            "required_conditions": ["统招本科", {"type": "or", "items": ["activiti", "camunda"]}]
        }
    }
}
```

#### 步骤 2：配置 AI 模型（可选）

```
1. 打开程序 -> 系统设置
2. 选择服务商（qwen/deepseek/kimi 等）
3. 输入 API Key 和 Base URL
4. 测试连接 -> 保存配置
```

#### 步骤 3：开始使用

```
1. 确保 Chrome 浏览器已安装
2. 登录 BOSS 直聘网站
3. 导航到推荐页面
4. 在程序中选择岗位 -> 点击"开始"
```

### 5. 常见问题

#### Q1: 打包后 EXE 文件太大？

解决方案：使用 UPX 压缩

```bash
# 下载 UPX
# https://github.com/upx/upx/releases

# 使用 UPX 压缩
upx --best "dist/BOSS_ResumeFilter.exe"
```

#### Q2: 目标电脑提示缺少 DLL？

原因：某些依赖未正确打包

解决方案：

```bash
# 使用 --collect-all 指定完整收集
pyinstaller --onefile --noconsole \
    --collect-all PIL \
    --collect-submodules tkinter \
    --hidden-import=tkinter \
    --hidden-import=tkinter.ttk \
    --hidden-import=tkinter.font \
    --hidden-import=tkinter.filedialog \
    --hidden-import=tkinter.messagebox \
    --name "BOSS_ResumeFilter" \
    gui_main.py
```

#### Q3: 配置文件路径问题？

确保 `job_config.json` 与 EXE 在同一目录：

```
BOSS_ResumeFilter.exe
job_config.json
```

#### Q4: 如何更新到新版本？

```bash
# 1. 备份旧数据
cp candidates_all.json candidates_all.json.bak

# 2. 替换 EXE 文件
# 3. 保留 job_config.json 和 candidates_all.json
```

### 6. 高级选项

#### 打包带图标

```bash
pyinstaller --onefile --noconsole \
    --icon=app.ico \
    --name "BOSS_ResumeFilter" \
    gui_main.py
```

#### 打包调试版本（带控制台）

```bash
pyinstaller --onefile --console \
    --name "BOSS_ResumeFilter_debug" \
    gui_main.py
```

#### 多文件模式（启动更快）

```bash
pyinstaller --onedir --noconsole \
    --name "BOSS_ResumeFilter" \
    gui_main.py
```

### 7. 依赖清单

打包时会自动包含以下依赖：

| 依赖 | 用途 |
|------|------|
| tkinter | GUI 框架 |
| DrissionPage | 浏览器自动化 |
| requests | HTTP 请求 |
| pandas | Excel 导出 |
| openpyxl | Excel 格式 |
| Pillow | 图标绘制（PIL.ImageDraw） |
| keyring | API Key 加密存储 |
| python-dotenv | 环境变量管理 |

### 8. 最小化部署

如果目标电脑已有 Python，可以直接复制源码运行：

```bash
# 1. 复制源码到目标电脑
cp -r boss-resume-filter/ D:/

# 2. 安装依赖
cd D:/boss-resume-filter
pip install -r requirements.txt

# 3. 运行
python gui_main.py
```

---

## 方案二：macOS 打包（.app + DMG）

### 1. 环境准备

- macOS 10.15+
- Python 3.10+（推荐 Homebrew 安装）
- PyInstaller（`pip install pyinstaller`）

### 2. 打包步骤

```bash
# 创建虚拟环境（推荐）
python3 -m venv pack_venv
source pack_venv/bin/activate
pip install -r requirements.txt pyinstaller

# 执行打包（自动检测 macOS 平台）
python3 build.py

# 或一键发布
python3 build.py --release
```

### 3. 输出文件

```
dist/
├── BOSS_ResumeFilter.app         ← 应用包（双击运行）
├── BOSS_ResumeFilter.dmg         ← 安装包（拖拽到 Applications）
├── BOSS_ResumeFilter_mac.zip     ← 自动更新用
├── job_config.json
├── selectors.json
└── README.md
```

### 4. 分发方式

**方式 A：DMG 安装包（推荐用户安装）**
1. 用户下载 `BOSS_ResumeFilter.dmg`
2. 双击打开 DMG
3. 拖拽 .app 到 Applications 文件夹
4. 首次运行需右键 → 打开（绕过 Gatekeeper）

**方式 B：自动更新（已安装用户）**
- 程序启动时自动检查 GitHub Release
- 发现新版本后下载 ZIP 并自动替换 .app
- 替换完成后自动重启应用

### 5. macOS 特殊说明

- **Tcl/Tk 收集**：macOS 上 Homebrew Python 的 Tcl/Tk 由 PyInstaller 自动收集，无需手动指定
- **分隔符差异**：`--add-data` 参数在 macOS 使用 `:` 分隔，Windows 使用 `;`（`build.py` 已自动处理）
- **PyInstaller 模式**：macOS 使用 `--onedir --windowed`（生成 .app bundle），Windows 使用 `--onefile --noconsole`

### 6. Gatekeeper 与签名

未签名的 .app 首次运行时会被 macOS Gatekeeper 拦截：

**用户解决方法：**
1. 右键点击 .app → 选择「打开」
2. 在弹出的对话框中再次点击「打开」

**开发者签名（可选）：**
- 需要 Apple Developer 账号（$99/年）
- 使用 `codesign` 签名 + `notarize` 公证
- 签名后用户无需右键打开

---

**最后更新**: 2026-05-24
