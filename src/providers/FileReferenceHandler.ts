import * as vscode from 'vscode';
import * as path from 'path';
import { CodeContext } from '../types';

export class FileReferenceHandler {
  async pickFileReferences(
    view: vscode.WebviewView | undefined,
    createCodeContextFromUri: (fileUri: vscode.Uri) => Promise<CodeContext | null>
  ): Promise<void> {
    const defaultUri = vscode.window.activeTextEditor?.document.uri
      || vscode.workspace.workspaceFolders?.[0]?.uri;

    const selectedFiles = await vscode.window.showOpenDialog({
      canSelectFiles: true,
      canSelectFolders: false,
      canSelectMany: true,
      defaultUri,
      openLabel: '引用文件'
    });

    if (!selectedFiles || selectedFiles.length === 0) {
      return;
    }

    let addedCount = 0;

    for (const fileUri of selectedFiles) {
      const codeContext = await createCodeContextFromUri(fileUri);
      if (!codeContext) {
        continue;
      }

      view?.webview.postMessage({
        type: 'codeContextAdded',
        data: codeContext
      });
      addedCount += 1;
    }

    if (addedCount === 0) {
      vscode.window.showWarningMessage('未能读取所选文件');
      return;
    }

    const message = addedCount === 1
      ? `已引用文件: ${path.basename(selectedFiles[0].fsPath)}`
      : `已引用 ${addedCount} 个文件`;

    vscode.window.showInformationMessage(message);
  }

  async createCodeContextFromUri(fileUri: vscode.Uri): Promise<CodeContext | null> {
    try {
      const document = await vscode.workspace.openTextDocument(fileUri);

      return {
        fileName: path.basename(document.fileName),
        filePath: document.fileName,
        language: document.languageId,
        content: document.getText()
      };
    } catch (error: any) {
      vscode.window.showWarningMessage(
        `读取文件失败: ${path.basename(fileUri.fsPath)}${error?.message ? ` (${error.message})` : ''}`
      );
      return null;
    }
  }
}
