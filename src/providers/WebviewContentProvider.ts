import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export class WebviewContentProvider {
  constructor(private readonly extensionContext: vscode.ExtensionContext) {}

  getHtmlForWebview(webview: vscode.Webview): string {
    const htmlPath = path.join(
      this.extensionContext.extensionPath,
      'media',
      'index.html'
    );

    let html = fs.readFileSync(htmlPath, 'utf8');

    // 获取 CSS 和 JS 文件的 URI
    const cssUri = webview.asWebviewUri(
      vscode.Uri.file(
        path.join(this.extensionContext.extensionPath, 'media', 'webview.css')
      )
    );
    const jsUri = webview.asWebviewUri(
      vscode.Uri.file(
        path.join(this.extensionContext.extensionPath, 'media', 'webview.js')
      )
    );

    // 生成 nonce 用于 CSP
    const nonce = this.getNonce();

    // 构建正确的 CSP 策略
    const cspContent = [
      `default-src 'none'`,
      `img-src ${webview.cspSource} data: https:`,
      `style-src ${webview.cspSource} 'unsafe-inline'`,
      `script-src 'nonce-${nonce}'`,
      `connect-src http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*`,
      `font-src ${webview.cspSource}`
    ].join('; ') + ';';

    // 替换占位符
    html = html.replace(/\$\{nonce\}/g, nonce);
    html = html.replace('{{CSP_CONTENT}}', cspContent);
    html = html.replace('./webview.css', cssUri.toString());
    html = html.replace('./webview.js', jsUri.toString());

    return html;
  }

  private getNonce(): string {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
      text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
  }
}
