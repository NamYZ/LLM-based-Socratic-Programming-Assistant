# AI Coding Tool - 打包指南

本指南说明如何将 AI Coding Tool 打包成可分发的 VSCode 插件（.vsix 文件）。

## 架构说明

本插件采用前后端分离架构：
- **前端**：VSCode 插件（TypeScript）
- **后端**：Python FastAPI 服务（使用 PyInstaller 打包成独立可执行文件）

## 打包流程

### 1. 准备环境

确保已安装以下工具：

- **Node.js** (>= 16.x)
- **npm** 或 **yarn**
- **uv** (Python 包管理工具)
  - Mac: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
- **vsce** (VSCode 插件打包工具)
  ```bash
  npm install -g @vscode/vsce
  ```

### 2. 安装依赖

```bash
# 安装 Node.js 依赖
npm install

# 安装 Python 依赖（使用 uv）
uv pip install -r requirements.txt
uv pip install pyinstaller
```

### 3. 打包后端

根据你的操作系统选择对应的打包脚本：

#### Mac 用户

```bash
npm run build:backend-mac
```

或直接运行：
```bash
bash build-backend-mac.sh
```

#### Windows 用户

```bash
npm run build:backend-win
```

或直接运行：
```cmd
build-backend-win.bat
```

打包完成后，会在 `backend-bin/` 目录下生成可执行文件：
- Mac: `backend-bin/backend`
- Windows: `backend-bin/backend.exe`

### 4. 打包 VSCode 插件

```bash
vsce package
```

这会生成一个 `.vsix` 文件，例如 `ai-coding-tool-0.0.1.vsix`。

**注意**：`vsce package` 会自动运行 `npm run vscode:prepublish`，它会检查后端可执行文件是否存在。如果未找到，打包会失败并提示你先运行后端打包脚本。

## 开发模式 vs 生产模式

插件会自动检测运行模式：

### 开发模式
- **触发条件**：存在 `backend/app_fastapi.py` 文件
- **行为**：直接运行 Python 脚本
- **适用场景**：本地开发和调试

### 生产模式
- **触发条件**：存在 `backend-bin/backend` 或 `backend-bin/backend.exe`
- **行为**：运行打包好的可执行文件
- **适用场景**：分发给最终用户

## 跨平台打包

如果你需要同时支持 Mac 和 Windows 用户，需要在两个平台上分别打包：

1. **在 Mac 上**：
   ```bash
   npm run build:backend-mac
   vsce package
   ```
   生成 `ai-coding-tool-0.0.1-mac.vsix`

2. **在 Windows 上**：
   ```bash
   npm run build:backend-win
   vsce package
   ```
   生成 `ai-coding-tool-0.0.1-win.vsix`

或者，你可以使用 GitHub Actions 等 CI/CD 工具自动在两个平台上打包。

## 安装打包好的插件

用户可以通过以下方式安装 `.vsix` 文件：

1. **通过 VSCode 界面**：
   - 打开 VSCode
   - 进入扩展面板（Ctrl+Shift+X 或 Cmd+Shift+X）
   - 点击右上角的 `...` 菜单
   - 选择 "从 VSIX 安装..."
   - 选择对应平台的 `.vsix` 文件

2. **通过命令行**：
   ```bash
   code --install-extension ai-coding-tool-0.0.1.vsix
   ```

## 常见问题

### Q: 打包后的文件太大怎么办？

A: PyInstaller 打包的文件会包含 Python 运行时和所有依赖，通常会比较大（50-100MB）。可以通过以下方式优化：
- 使用 `--exclude-module` 排除不需要的模块
- 使用 UPX 压缩（已在 backend.spec 中启用）

### Q: 用户安装后提示"后端启动失败"？

A: 检查以下几点：
1. 确保打包时包含了 `backend-bin/` 目录
2. 确保可执行文件有执行权限（Mac/Linux）
3. 查看 "AI Coding Tool Backend" 输出面板的日志

### Q: 如何在开发时测试生产模式？

A: 临时重命名 `backend/` 目录，插件会自动切换到生产模式：
```bash
mv backend backend.bak
# 测试插件
mv backend.bak backend
```

## 文件结构

```
ai-coding-tool/
├── backend/              # Python 源码（开发模式使用）
├── backend-bin/          # 打包的可执行文件（生产模式使用）
│   ├── backend          # Mac 可执行文件
│   └── backend.exe      # Windows 可执行文件
├── src/                 # TypeScript 源码
├── out/                 # 编译后的 JavaScript
├── backend.spec         # PyInstaller 配置
├── build-backend-mac.sh # Mac 打包脚本
├── build-backend-win.bat # Windows 打包脚本
└── package.json         # 插件配置
```

## 技术细节

- **后端端口**：5500
- **数据库位置**：`~/vscode_chat.db`（用户主目录）
- **日志输出**：VSCode 输出面板 "AI Coding Tool Backend"
