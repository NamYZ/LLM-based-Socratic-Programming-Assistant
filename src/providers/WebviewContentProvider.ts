import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export class WebviewContentProvider {
  constructor(private readonly extensionContext: vscode.ExtensionContext) {}

  getHtmlForWebview(webview: vscode.Webview): string {
    const htmlPath = path.join(
      this.extensionContext.extensionPath,
      'src',
      'webview',
      'index.html'
    );

    let html = fs.readFileSync(htmlPath, 'utf8');

    // 获取 CSS 和 JS 文件的 URI
    const cssUri = webview.asWebviewUri(
      vscode.Uri.file(
        path.join(this.extensionContext.extensionPath, 'src', 'webview', 'webview.css')
      )
    );
    const jsUri = webview.asWebviewUri(
      vscode.Uri.file(
        path.join(this.extensionContext.extensionPath, 'src', 'webview', 'webview.js')
      )
    );

    // 生成 nonce 用于 CSP
    const nonce = this.getNonce();

    // 替换占位符
    html = html.replace(/\$\{nonce\}/g, nonce);
    html = html.replace('./webview.css', cssUri.toString());
    html = html.replace('./webview.js', jsUri.toString());

    // 更新 CSP 策略以允许 webview URI 和 CDN
    html = html.replace(
      /content="default-src 'none'; style-src [^"]+"/,
      `content="default-src 'none'; img-src ${webview.cspSource} data: https:; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}' ${webview.cspSource} https://cdn.jsdelivr.net; connect-src http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*;"`
    );

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
