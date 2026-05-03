import * as vscode from 'vscode';
import * as path from 'path';
import { ChatViewProvider } from './providers/ChatViewProvider';
import { BackendManager } from './providers/BackendManager';
import { CodeContext } from './types';

// VS Code 插件的 “总开关 / 入口”。

// 插件一激活，就跑这个 activate() 函数，注册 Webview 界面和命令（比如新建聊天、打开设置等）
export function activate(context: vscode.ExtensionContext) {

  console.log('AI Coding Tool is now active!');

  const backendManager = new BackendManager(context);
  context.subscriptions.push(backendManager);
  void backendManager.ensureBackendRunning().catch((error: any) => {
    console.warn(`[AI Coding Tool] 后端预启动失败: ${error.message}`);
  });

  // 创建 ChatViewProvider 实例，注册 Webview 界面和命令
  const provider = new ChatViewProvider(context, backendManager);

  // 告诉 VS Code 注册 Webview 界面
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      // 视图 ID，前端 HTML 里会用这个 ID 来请求显示这个界面
      ChatViewProvider.viewType,
      // 页面提供者实例，负责管理这个界面的显示和交互
      provider,
      { webviewOptions: { retainContextWhenHidden: true } }
    )
  );

  // 注册命令：新建对话
  context.subscriptions.push(
    vscode.commands.registerCommand('aiCodingTool.newChat', () => {
      provider.newChat();
    })
  );

  // 注册命令：打开设置
  context.subscriptions.push(
    vscode.commands.registerCommand('aiCodingTool.openSettings', () => {
      provider.openSettings();
    })
  );

  // 注册命令：添加选中代码到AI上下文
  context.subscriptions.push(
    vscode.commands.registerCommand('aiCodingTool.addToContext', () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage('没有打开的编辑器');
        return;
      }

      const document = editor.document;
      const selection = editor.selection;

      // 如果没有选中内容，提示用户
      if (selection.isEmpty) {
        vscode.window.showWarningMessage('请先选中要添加的代码');
        return;
      }

      const selectedText = document.getText(selection);
      const codeContext: CodeContext = {
        fileName: path.basename(document.fileName),
        filePath: document.fileName,
        language: document.languageId,
        content: selectedText,
        selection: {
          start: selection.start.line,
          end: selection.end.line
        }
      };

      provider.addCodeToContext(codeContext);
      vscode.window.showInformationMessage(`已添加 ${codeContext.fileName} 的选中代码到上下文`);
    })
  );

  // 注册命令：切换 AI 面板显示/隐藏
  context.subscriptions.push(
    vscode.commands.registerCommand('aiCodingTool.togglePanel', () => {
      // 尝试聚焦到 AI 面板，如果已经可见则会隐藏
      vscode.commands.executeCommand('workbench.view.extension.ai-coding-tool');
    })
  );

  // 注册命令：快速输入发送给 AI
  let quickInputDisposable: vscode.Disposable | undefined;
  context.subscriptions.push(
    vscode.commands.registerCommand('aiCodingTool.quickInput', async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage('没有打开的编辑器');
        return;
      }

      const document = editor.document;
      const position = editor.selection.active;

      // 在当前光标位置插入空行
      const lineEnd = document.lineAt(position.line).range.end;
      await editor.edit(editBuilder => {
        editBuilder.insert(lineEnd, '\n');
      });

      // 移动光标到新行
      const newPosition = new vscode.Position(position.line + 1, 0);
      editor.selection = new vscode.Selection(newPosition, newPosition);
      editor.revealRange(new vscode.Range(newPosition, newPosition));

      // 记录插入的行号
      const insertedLine = position.line + 1;

      // 清理之前的监听器
      if (quickInputDisposable) {
        quickInputDisposable.dispose();
      }

      // 监听文档变化，检测回车键
      quickInputDisposable = vscode.workspace.onDidChangeTextDocument(async (event) => {
        if (event.document !== document) {
          return;
        }

        // 检查是否在插入的行上按了回车（添加了新行）
        for (const change of event.contentChanges) {
          if (change.text.includes('\n') && change.range.start.line === insertedLine) {
            // 获取插入行的内容（去除换行符）
            const lineText = document.lineAt(insertedLine).text.trim();

            if (lineText) {
              // 发送消息给 AI
              provider.sendQuickMessage(lineText);

              // 删除插入的行和新添加的空行
              await editor.edit(editBuilder => {
                const lineToDelete = document.lineAt(insertedLine);
                const deleteRange = new vscode.Range(
                  insertedLine,
                  0,
                  insertedLine + 2,
                  0
                );
                editBuilder.delete(deleteRange);
              });
            } else {
              // 如果是空行，只删除这一行
              await editor.edit(editBuilder => {
                const lineToDelete = document.lineAt(insertedLine);
                const deleteRange = new vscode.Range(
                  insertedLine,
                  0,
                  insertedLine + 1,
                  0
                );
                editBuilder.delete(deleteRange);
              });
            }

            // 清理监听器
            if (quickInputDisposable) {
              quickInputDisposable.dispose();
              quickInputDisposable = undefined;
            }

            return;
          }
        }
      });

      // 5秒后自动清理监听器（防止内存泄漏）
      setTimeout(() => {
        if (quickInputDisposable) {
          quickInputDisposable.dispose();
          quickInputDisposable = undefined;
        }
      }, 30000);
    })
  );
}

// 插件停用时执行的函数，通常用来清理资源等（这里暂时不需要做什么）
export function deactivate() {}
