# 打包脚本说明

本文件夹包含 AI Coding Tool 的打包脚本。

## 脚本列表

### 完整打包脚本（推荐）

这些脚本会自动完成后端打包 + TypeScript 编译 + VSCode 插件打包的全部流程：

- **`package-all-mac.sh`** - Mac 完整打包脚本
- **`package-all-win.bat`** - Windows 完整打包脚本

### 仅后端打包脚本

如果只需要重新打包后端，可以使用这些脚本：

- **`build-backend-mac.sh`** - Mac 后端打包脚本
- **`build-backend-win.bat`** - Windows 后端打包脚本

## 使用方法

### Mac 用户

#### 方式 1：使用 npm 脚本（推荐）

```bash
# 完整打包（后端 + 插件）
npm run package:mac

# 仅打包后端
npm run build:backend-mac
```

#### 方式 2：直接运行脚本

```bash
# 从项目根目录运行
bash scripts/package-all-mac.sh

# 或者进入 scripts 目录运行（脚本会自动切换到项目根目录）
cd scripts
./package-all-mac.sh

# 仅打包后端
bash scripts/build-backend-mac.sh
```

### Windows 用户

#### 方式 1：使用 npm 脚本（推荐）

```cmd
# 完整打包（后端 + 插件）
npm run package:win

# 仅打包后端
npm run build:backend-win
```

#### 方式 2：直接运行脚本

```cmd
# 从项目根目录运行
scripts\package-all-win.bat

# 或者进入 scripts 目录运行（脚本会自动切换到项目根目录）
cd scripts
package-all-win.bat

# 仅打包后端
scripts\build-backend-win.bat
```

## 前置要求

### 所有平台

1. **Node.js** - 用于编译 TypeScript 和打包插件
2. **npm** - Node.js 包管理器
3. **vsce** - VSCode 插件打包工具
   ```bash
   npm install -g @vscode/vsce
   ```
4. **uv** - Python 包管理器（用于运行 PyInstaller）
   ```bash
   # Mac
   brew install uv
   
   # Windows
   pip install uv
   ```

### Mac 特定

- 确保脚本有执行权限（已自动设置）

### Windows 特定

- 使用 CMD 或 PowerShell 运行 .bat 文件

## 输出文件

打包完成后会生成以下文件：

- **`backend-bin/backend`** (Mac) 或 **`backend-bin/backend.exe`** (Windows) - 后端可执行文件
- **`*.vsix`** - VSCode 插件安装包（仅完整打包脚本生成）

## 安装插件

打包完成后，使用以下命令安装插件：

```bash
code --install-extension *.vsix
```

或者在 VSCode 中：
1. 打开扩展面板（Ctrl+Shift+X / Cmd+Shift+X）
2. 点击右上角的 "..." 菜单
3. 选择 "从 VSIX 安装..."
4. 选择生成的 .vsix 文件

## 故障排除

### 错误：找不到 uv 命令

确保已安装 uv：
```bash
# Mac
brew install uv

# Windows
pip install uv
```

### 错误：找不到 vsce 命令

安装 vsce：
```bash
npm install -g @vscode/vsce
```

### 错误：权限被拒绝（Mac）

设置脚本执行权限：
```bash
chmod +x scripts/*.sh
```

### 错误：后端打包失败

1. 检查 Python 环境是否正确配置
2. 确保 `backend.spec` 文件存在于项目根目录
3. 查看错误日志，确认缺少的依赖

## 开发流程

1. **开发阶段**：修改代码
2. **测试阶段**：运行 `npm run compile` 编译 TypeScript
3. **打包阶段**：运行完整打包脚本
4. **发布阶段**：安装并测试生成的 .vsix 文件

## 注意事项

- 打包前会自动清理旧的 `build/`、`dist/` 和 `backend-bin/` 目录
- 完整打包脚本会自动删除旧的 .vsix 文件
- 打包过程中的临时文件会自动清理
- **脚本会自动切换到项目根目录**，可以从任何位置运行
- 所有生成的文件都会放在项目根目录下
