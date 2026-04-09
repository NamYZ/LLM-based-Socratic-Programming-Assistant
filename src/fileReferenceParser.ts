// 文件引用解析器：解析@文件名并读取文件内容

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export interface FileReference {
  fileName: string;
  filePath: string;
  content: string;
  language: string;
}

export class FileReferenceParser {
  /**
   * 解析用户消息中的@文件引用
   * @param message 用户输入的消息
   * @param workspaceRoot 工作区根目录
   * @returns 解析出的文件引用列表和清理后的消息
   */
  public static async parseFileReferences(
    message: string,
    workspaceRoot?: string
  ): Promise<{ cleanMessage: string; references: FileReference[] }> {
    // 匹配 @文件名 或 @路径/文件名
    const filePattern = /@([\w\-\.\/\\]+\.\w+)/g;
    const matches = Array.from(message.matchAll(filePattern));

    if (matches.length === 0) {
      return { cleanMessage: message, references: [] };
    }

    const references: FileReference[] = [];
    let cleanMessage = message;

    for (const match of matches) {
      const fileName = match[1];
      const fileRef = await this.resolveFile(fileName, workspaceRoot);

      if (fileRef) {
        references.push(fileRef);
        // 从消息中移除@文件名
        cleanMessage = cleanMessage.replace(match[0], '');
      }
    }

    return { cleanMessage: cleanMessage.trim(), references };
  }

  /**
   * 解析文件路径并读取内容
   */
  private static async resolveFile(
    fileName: string,
    workspaceRoot?: string
  ): Promise<FileReference | null> {
    try {
      let filePath: string;

      // 如果是绝对路径
      if (path.isAbsolute(fileName)) {
        filePath = fileName;
      } else if (workspaceRoot) {
        // 相对路径，基于工作区根目录
        filePath = path.join(workspaceRoot, fileName);
      } else {
        // 尝试在当前工作区查找
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
          return null;
        }
        filePath = path.join(workspaceFolders[0].uri.fsPath, fileName);
      }

      // 检查文件是否存在
      if (!fs.existsSync(filePath)) {
        // 尝试模糊搜索
        const foundPath = await this.fuzzySearchFile(fileName, workspaceRoot);
        if (!foundPath) {
          vscode.window.showWarningMessage(`文件未找到: ${fileName}`);
          return null;
        }
        filePath = foundPath;
      }

      // 读取文件内容
      const content = fs.readFileSync(filePath, 'utf8');
      const ext = path.extname(filePath).slice(1);
      const language = this.getLanguageId(ext);

      return {
        fileName: path.basename(filePath),
        filePath,
        content,
        language
      };
    } catch (error) {
      console.error(`读取文件失败: ${fileName}`, error);
      return null;
    }
  }

  /**
   * 模糊搜索文件（在工作区中查找匹配的文件）
   */
  private static async fuzzySearchFile(
    fileName: string,
    workspaceRoot?: string
  ): Promise<string | null> {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
      return null;
    }

    const root = workspaceRoot || workspaceFolders[0].uri.fsPath;
    const files = await vscode.workspace.findFiles(
      `**/${fileName}`,
      '**/node_modules/**',
      1
    );

    return files.length > 0 ? files[0].fsPath : null;
  }

  /**
   * 根据文件扩展名获取语言ID
   */
  private static getLanguageId(ext: string): string {
    const languageMap: { [key: string]: string } = {
      'js': 'javascript',
      'ts': 'typescript',
      'jsx': 'javascriptreact',
      'tsx': 'typescriptreact',
      'py': 'python',
      'java': 'java',
      'cpp': 'cpp',
      'c': 'c',
      'cs': 'csharp',
      'go': 'go',
      'rs': 'rust',
      'php': 'php',
      'rb': 'ruby',
      'swift': 'swift',
      'kt': 'kotlin',
      'html': 'html',
      'css': 'css',
      'scss': 'scss',
      'json': 'json',
      'xml': 'xml',
      'yaml': 'yaml',
      'yml': 'yaml',
      'md': 'markdown',
      'sh': 'shell',
      'sql': 'sql'
    };

    return languageMap[ext.toLowerCase()] || ext;
  }

  /**
   * 格式化文件引用为Markdown代码块
   */
  public static formatReferences(references: FileReference[]): string {
    if (references.length === 0) {
      return '';
    }

    let formatted = '\n\n[引用的文件]\n';
    for (const ref of references) {
      formatted += `\n文件: ${ref.fileName}\n路径: ${ref.filePath}\n\`\`\`${ref.language}\n${ref.content}\n\`\`\`\n`;
    }

    return formatted;
  }
}
