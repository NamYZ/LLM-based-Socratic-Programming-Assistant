import * as vscode from 'vscode';
import * as path from 'path';

export class SessionExporter {
  async exportSessionMarkdown(sessionId: number, apiBase: string): Promise<void> {
    try {
      const response = await fetch(`${apiBase}/api/sessions/${sessionId}/messages`);
      const data = await response.json() as {
        detail?: string;
        messages?: Array<{ role: 'user' | 'assistant'; content: string; time?: string }>;
        session?: { id: number; title: string; mode: string; created_at: string };
      };

      if (!response.ok || !data.session || !data.messages) {
        throw new Error(data.detail || '导出会话失败');
      }

      const defaultFolderUri = vscode.workspace.workspaceFolders?.[0]?.uri;
      const fileName = `${this.sanitizeFileName(data.session.title || `session-${sessionId}`)}.md`;
      const defaultUri = defaultFolderUri
        ? vscode.Uri.joinPath(defaultFolderUri, fileName)
        : undefined;

      const saveUri = await vscode.window.showSaveDialog({
        defaultUri,
        filters: {
          Markdown: ['md']
        },
        saveLabel: '导出 Markdown'
      });

      if (!saveUri) {
        return;
      }

      const markdown = this.buildSessionMarkdown(data.session, data.messages);
      await vscode.workspace.fs.writeFile(saveUri, Buffer.from(markdown, 'utf8'));

      vscode.window.showInformationMessage(`聊天记录已导出: ${path.basename(saveUri.fsPath)}`);
    } catch (error: any) {
      vscode.window.showErrorMessage(`导出聊天记录失败: ${error.message}`);
    }
  }

  private buildSessionMarkdown(
    session: { title: string; mode: string; created_at: string },
    messages: Array<{ role: 'user' | 'assistant'; content: string; time?: string }>
  ): string {
    const modeLabel = session.mode === 'guided'
      ? '引导式'
      : (session.mode === 'agent' ? 'Agent模式' : '答案式');

    const lines: string[] = [
      `# ${session.title || '聊天记录'}`,
      '',
      `- 模式: ${modeLabel}`,
      `- 创建时间: ${session.created_at || '未知'}`,
      `- 导出时间: ${new Date().toLocaleString('zh-CN', { hour12: false })}`,
      ''
    ];

    messages.forEach((message, index) => {
      lines.push('---', '');
      lines.push(`## ${message.role === 'user' ? '用户' : 'AI'} ${index + 1}`);
      if (message.time) {
        lines.push('', `时间: ${message.time}`);
      }
      lines.push('', message.content || '', '');
    });

    return lines.join('\n').trimEnd() + '\n';
  }

  private sanitizeFileName(fileName: string): string {
    const sanitized = fileName
      .replace(/[<>:"/\\|?*\u0000-\u001F]/g, '-')
      .replace(/\s+/g, ' ')
      .trim();

    return sanitized || 'chat-session';
  }
}
