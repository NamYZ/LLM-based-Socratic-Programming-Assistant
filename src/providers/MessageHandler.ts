import * as vscode from 'vscode';
import * as path from 'path';
import { FileReferenceParser } from '../fileReferenceParser';

export class MessageHandler {
  private lastCodeContent: string = '';
  private lastFilePath: string = '';
  private abortController: AbortController | null = null;

  stopCurrentStream() {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  async handleSendMessage(
    message: any,
    view: vscode.WebviewView | undefined,
    apiBase: string
  ): Promise<void> {
    try {
      // 创建新的 AbortController
      this.abortController = new AbortController();

      const userMessage = message.data.message;
      let finalMessage = userMessage;
      let contextParts: string[] = [];

      console.log('[ChatViewProvider] Received codeContexts:', message.data.codeContexts);

      // 1. 解析 @文件引用
      const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      const { cleanMessage, references } = await FileReferenceParser.parseFileReferences(
        userMessage,
        workspaceRoot
      );
      finalMessage = cleanMessage;

      // 添加@文件引用的内容
      if (references.length > 0) {
        contextParts.push(FileReferenceParser.formatReferences(references));
      }

      // 2. 添加手动引用的代码上下文（从 webview 传来的）
      if (message.data.codeContexts && message.data.codeContexts.length > 0) {
        let manualContext = '\n\n[手动添加的代码上下文]\n';
        for (const ctx of message.data.codeContexts) {
          const lineInfo = ctx.selection ? `行 ${ctx.selection.start + 1}-${ctx.selection.end + 1}` : '完整文件';
          manualContext += `\n文件: ${ctx.fileName} (${lineInfo})\n路径: ${ctx.filePath}\n语言: ${ctx.language}\n\`\`\`${ctx.language}\n${ctx.content}\n\`\`\`\n`;
        }
        contextParts.push(manualContext);
        console.log('[ChatViewProvider] Added manual context:', manualContext);
      }

      // 3. 每次发送都直接附带当前编辑器文件代码
      let currentCode = '';
      const editor = vscode.window.activeTextEditor;
      if (editor) {
        const document = editor.document;
        const selection = editor.selection;

        // 如果有选中内容，只获取选中部分；否则获取全部
        const content = selection.isEmpty
          ? document.getText()
          : document.getText(selection);

        currentCode = content; // 保存当前代码用于 Agent

        const currentFilePath = document.fileName;
        const hasChanged = this.lastFilePath === currentFilePath && this.lastCodeContent !== content;

        // 更新缓存
        this.lastFilePath = currentFilePath;
        this.lastCodeContent = content;

        // 构建上下文信息，如果代码发生变更则添加提示
        const changeNotice = hasChanged ? '代码已变更，内容如下:\n' : '';
        const contextInfo = `\n\n[当前编辑器文件]\n${changeNotice}文件: ${path.basename(document.fileName)}\n路径: ${document.fileName}\n语言: ${document.languageId}\n${selection.isEmpty ? '完整代码' : '选中代码'}:\n\`\`\`${document.languageId}\n${content}\n\`\`\``;
        contextParts.push(contextInfo);
      }

      // 4. 组合最终消息
      const messageWithContext = finalMessage + contextParts.join('');

      // 5. Agent 模式由前端模式选择显式控制
      const useAgent = message.data.mode === 'agent';

      const response = await fetch(`${apiBase}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...message.data,
          message: messageWithContext,
          current_code: currentCode,  // 传递当前代码
          use_agent: useAgent          // 启用 Agent
        }),
        signal: this.abortController.signal
      });

      if (!response.ok) {
        const errorData = await response.json() as { detail?: string };
        throw new Error(errorData.detail || '请求失败');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('无法读取响应流');
      }

      let sseBuffer = '';

      const processSseChunk = async (rawChunk: string, shouldFlushTail = false) => {
        sseBuffer += rawChunk;
        const lines = sseBuffer.split('\n');
        if (!shouldFlushTail) {
          sseBuffer = lines.pop() ?? '';
        } else {
          sseBuffer = '';
        }

        for (const rawLine of lines) {
          const line = rawLine.trim();
          if (!line.startsWith('data: ')) {
            continue;
          }

          const payload = line.slice(6).trim();
          if (!payload) {
            continue;
          }

          let data: any;
          try {
            data = JSON.parse(payload);
          } catch (error) {
            console.warn('[ChatViewProvider] Skip malformed SSE payload:', payload, error);
            continue;
          }

          await view?.webview.postMessage({
            type: 'chatChunk',
            data
          });
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        await processSseChunk(decoder.decode(value, { stream: true }));
      }

      // 刷新 decoder / SSE 缓冲区尾部
      await processSseChunk(decoder.decode(), true);

      // 发送完成后通知 webview 清空代码上下文
      view?.webview.postMessage({
        type: 'clearCodeContexts'
      });

      // 清理 AbortController
      this.abortController = null;
    } catch (error: any) {
      // 如果是用户主动取消，不显示错误
      if (error.name === 'AbortError') {
        console.log('[MessageHandler] Stream aborted by user');
        this.abortController = null;
        return;
      }

      view?.webview.postMessage({
        type: 'chatError',
        error: error.message
      });
      vscode.window.showErrorMessage(`对话失败: ${error.message}`);
      this.abortController = null;
    }
  }
}
