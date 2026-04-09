import * as vscode from 'vscode';
import { SessionExporter } from './SessionExporter';
import { FileReferenceHandler } from './FileReferenceHandler';
import { ConfigDatabaseManager } from './ConfigDatabaseManager';
import { MessageHandler } from './MessageHandler';
import { WebviewContentProvider } from './WebviewContentProvider';
import { CodeContext } from '../types';

export class ChatViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'aiCodingTool.chatView';
  private _view?: vscode.WebviewView;
  private _manualCodeContexts: CodeContext[] = [];

  private sessionExporter: SessionExporter;
  private fileReferenceHandler: FileReferenceHandler;
  private configDbManager: ConfigDatabaseManager;
  private messageHandler: MessageHandler;
  private webviewContentProvider: WebviewContentProvider;

  constructor(private readonly _extensionContext: vscode.ExtensionContext) {
    this.sessionExporter = new SessionExporter();
    this.fileReferenceHandler = new FileReferenceHandler();
    this.configDbManager = new ConfigDatabaseManager();
    this.messageHandler = new MessageHandler();
    this.webviewContentProvider = new WebviewContentProvider(_extensionContext);
  }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [
        vscode.Uri.file(this._extensionContext.extensionPath + '/src/webview')
      ]
    };

    webviewView.webview.html = this.webviewContentProvider.getHtmlForWebview(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(
      async (message) => {
        await this._handleMessage(message);
      },
      undefined,
      this._extensionContext.subscriptions
    );
  }

  private async _handleMessage(message: any) {
    const API_BASE = 'http://localhost:5500';

    switch (message.type) {
      case 'pickFileReference':
        await this.fileReferenceHandler.pickFileReferences(
          this._view,
          this.fileReferenceHandler.createCodeContextFromUri.bind(this.fileReferenceHandler)
        );
        break;

      case 'saveSettings':
        try {
          const response = await fetch(`${API_BASE}/api/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(message.data)
          });
          const result = await response.json() as { success?: boolean; detail?: string };

          if (response.ok) {
            this._view?.webview.postMessage({
              type: 'settingsSaved',
              success: true
            });
            vscode.window.showInformationMessage('API Key 已保存');
          } else {
            throw new Error(result.detail || '保存失败');
          }
        } catch (error: any) {
          this._view?.webview.postMessage({
            type: 'settingsSaved',
            success: false,
            error: error.message
          });
          vscode.window.showErrorMessage(`保存失败: ${error.message}`);
        }
        break;

      case 'loadSettings':
        try {
          const response = await fetch(`${API_BASE}/api/settings`);
          const settings = await response.json();
          this._view?.webview.postMessage({
            type: 'settingsLoaded',
            data: settings
          });
        } catch (error: any) {
          vscode.window.showErrorMessage(`加载设置失败: ${error.message}`);
        }
        break;

      case 'sendMessage':
        await this.messageHandler.handleSendMessage(message, this._view, API_BASE);
        break;

      case 'stopStreaming':
        this.messageHandler.stopCurrentStream();
        break;

      case 'loadSessions':
        try {
          const response = await fetch(`${API_BASE}/api/sessions`);
          const data = await response.json() as { sessions: any[] };
          this._view?.webview.postMessage({
            type: 'sessionsLoaded',
            data: data.sessions
          });
        } catch (error: any) {
          vscode.window.showErrorMessage(`加载会话列表失败: ${error.message}`);
        }
        break;

      case 'loadSessionMessages':
        try {
          const response = await fetch(`${API_BASE}/api/sessions/${message.sessionId}/messages`);
          const data = await response.json() as {
            messages?: Array<{ role: string; content: string; time?: string }>;
            session?: { id?: number; title?: string; mode?: string; created_at?: string };
          };
          if (data?.session && !data.session.id) {
            data.session.id = message.sessionId;
          }
          this._view?.webview.postMessage({
            type: 'sessionMessagesLoaded',
            data
          });
        } catch (error: any) {
          vscode.window.showErrorMessage(`加载会话消息失败: ${error.message}`);
        }
        break;

      case 'deleteSession':
        try {
          const response = await fetch(`${API_BASE}/api/sessions/${message.sessionId}`, {
            method: 'DELETE'
          });

          if (response.ok) {
            this._view?.webview.postMessage({
              type: 'sessionDeleted',
              sessionId: message.sessionId
            });
          }
        } catch (error: any) {
          vscode.window.showErrorMessage(`删除会话失败: ${error.message}`);
        }
        break;

      case 'exportSessionMarkdown':
        await this.sessionExporter.exportSessionMarkdown(message.sessionId, API_BASE);
        break;

      case 'clearAll':
        try {
          const response = await fetch(`${API_BASE}/api/history`, {
            method: 'DELETE'
          });

          if (response.ok) {
            this._view?.webview.postMessage({
              type: 'historyCleared'
            });
            vscode.window.showInformationMessage('所有会话已清空');
          }
        } catch (error: any) {
          vscode.window.showErrorMessage(`清空失败: ${error.message}`);
        }
        break;

      case 'loadConfigs':
        try {
          const response = await fetch(`${API_BASE}/api/configs`);
          const data = await response.json() as { configs: any[] };
          this._view?.webview.postMessage({
            type: 'configsLoaded',
            data: data.configs
          });
        } catch (error: any) {
          vscode.window.showErrorMessage(`加载配置列表失败: ${error.message}`);
        }
        break;

      case 'activateConfig':
        try {
          const response = await fetch(`${API_BASE}/api/configs/${message.configId}/activate`, {
            method: 'POST'
          });

          if (response.ok) {
            this._view?.webview.postMessage({
              type: 'configActivated',
              success: true,
              configId: message.configId
            });
            vscode.window.showInformationMessage('配置已切换');
          }
        } catch (error: any) {
          vscode.window.showErrorMessage(`切换配置失败: ${error.message}`);
        }
        break;

      case 'loadConfigsList':
        try {
          const response = await fetch(`${API_BASE}/api/configs`);
          const data = await response.json() as { configs: any[] };
          this._view?.webview.postMessage({
            type: 'configsListLoaded',
            data: data.configs
          });
        } catch (error: any) {
          vscode.window.showErrorMessage(`加载配置列表失败: ${error.message}`);
        }
        break;

      case 'loadConfigDetail':
        try {
          const response = await fetch(`${API_BASE}/api/configs/${message.configId}`);
          if (response.ok) {
            const data = await response.json() as { config?: any; detail?: string };

            if (!data.config) {
              throw new Error(data.detail || '加载配置详情失败');
            }

            this._view?.webview.postMessage({
              type: 'configDetailLoaded',
              data: data.config
            });
            break;
          }

          if (response.status !== 404 && response.status !== 405) {
            const data = await response.json() as { detail?: string };
            throw new Error(data.detail || '加载配置详情失败');
          }

          const config = await this.configDbManager.loadConfigDetail(message.configId);
          this._view?.webview.postMessage({
            type: 'configDetailLoaded',
            data: config
          });
        } catch (error: any) {
          try {
            const config = await this.configDbManager.loadConfigDetail(message.configId);
            this._view?.webview.postMessage({
              type: 'configDetailLoaded',
              data: config
            });
          } catch (fallbackError: any) {
            vscode.window.showErrorMessage(`加载配置详情失败: ${fallbackError.message || error.message}`);
          }
        }
        break;

      case 'addConfig':
        try {
          const response = await fetch(`${API_BASE}/api/configs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(message.data)
          });
          const result = await response.json() as { success?: boolean; detail?: string };

          if (response.ok) {
            this._view?.webview.postMessage({
              type: 'configAdded',
              success: true
            });
            vscode.window.showInformationMessage('配置已添加');
          } else {
            throw new Error(result.detail || '添加失败');
          }
        } catch (error: any) {
          this._view?.webview.postMessage({
            type: 'configAdded',
            success: false,
            error: error.message
          });
          vscode.window.showErrorMessage(`添加配置失败: ${error.message}`);
        }
        break;

      case 'updateConfig':
        try {
          const response = await fetch(`${API_BASE}/api/configs/${message.configId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(message.data)
          });

          if (response.ok) {
            const result = await response.json() as { success?: boolean; detail?: string };
            this._view?.webview.postMessage({
              type: 'configUpdated',
              success: true
            });
            vscode.window.showInformationMessage('配置已更新');
            break;
          }

          if (response.status !== 404 && response.status !== 405) {
            const result = await response.json() as { success?: boolean; detail?: string };
            throw new Error(result.detail || '更新失败');
          }

          await this.configDbManager.updateConfig(message.configId, message.data);
          this._view?.webview.postMessage({
            type: 'configUpdated',
            success: true
          });
          vscode.window.showInformationMessage('配置已更新');
        } catch (error: any) {
          try {
            await this.configDbManager.updateConfig(message.configId, message.data);
            this._view?.webview.postMessage({
              type: 'configUpdated',
              success: true
            });
            vscode.window.showInformationMessage('配置已更新');
          } catch (fallbackError: any) {
            this._view?.webview.postMessage({
              type: 'configUpdated',
              success: false,
              error: fallbackError.message || error.message
            });
            vscode.window.showErrorMessage(`更新配置失败: ${fallbackError.message || error.message}`);
          }
        }
        break;

      case 'deleteConfig':
        try {
          const response = await fetch(`${API_BASE}/api/configs/${message.configId}`, {
            method: 'DELETE'
          });

          if (response.ok) {
            this._view?.webview.postMessage({
              type: 'configDeleted',
              success: true
            });
            vscode.window.showInformationMessage('配置已删除');
          } else {
            const result = await response.json() as { detail?: string };
            throw new Error(result.detail || '删除失败');
          }
        } catch (error: any) {
          vscode.window.showErrorMessage(`删除配置失败: ${error.message}`);
        }
        break;

      case 'addCodeContext':
        if (message.data) {
          this._manualCodeContexts.push(message.data);
          vscode.window.showInformationMessage(`已添加代码到上下文: ${message.data.fileName}`);
        }
        break;

      case 'closePanel':
        if (this._view) {
          vscode.commands.executeCommand('workbench.action.closeSidebar');
        }
        break;
    }
  }

  public newChat() {
    this._view?.webview.postMessage({ type: 'newChat' });
  }

  public openSettings() {
    this._view?.webview.postMessage({ type: 'openSettings' });
  }

  public addCodeToContext(codeContext: CodeContext) {
    this._manualCodeContexts.push(codeContext);
    this._view?.webview.postMessage({
      type: 'codeContextAdded',
      data: codeContext
    });
  }

  public sendQuickMessage(message: string) {
    this._view?.webview.postMessage({
      type: 'quickMessage',
      message: message
    });
  }
}
