import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { ChildProcess, spawn } from 'child_process';

const API_BASE = 'http://127.0.0.1:5500';

export class BackendManager implements vscode.Disposable {
  private backendProcess?: ChildProcess;
  private startPromise?: Promise<string>;
  private readonly outputChannel = vscode.window.createOutputChannel('AI Coding Tool Backend');

  constructor(private readonly extensionContext: vscode.ExtensionContext) {}

  async ensureBackendRunning(): Promise<string> {
    if (await this.isHealthy()) {
      return API_BASE;
    }

    if (!this.startPromise) {
      this.startPromise = this.startBackend().finally(() => {
        this.startPromise = undefined;
      });
    }

    return this.startPromise;
  }

  dispose(): void {
    if (this.backendProcess && this.backendProcess.exitCode === null) {
      this.backendProcess.kill();
    }
    this.outputChannel.dispose();
  }

  private async startBackend(): Promise<string> {
    if (await this.isHealthy()) {
      return API_BASE;
    }

    // 检测是开发模式还是生产模式
    const isDevelopment = this.isDevelopmentMode();

    if (isDevelopment) {
      return this.startDevelopmentBackend();
    } else {
      return this.startProductionBackend();
    }
  }

  private isDevelopmentMode(): boolean {
    // 如果存在 backend/app_fastapi.py，则为开发模式
    const scriptPath = path.join(this.extensionContext.extensionPath, 'backend', 'app_fastapi.py');
    return fs.existsSync(scriptPath);
  }

  private async startDevelopmentBackend(): Promise<string> {
    this.outputChannel.appendLine('[模式] 开发模式 - 运行 Python 脚本');

    const scriptPath = path.join(this.extensionContext.extensionPath, 'backend', 'app_fastapi.py');
    const backendDir = path.dirname(scriptPath);

    const candidates = process.platform === 'win32'
      ? [
          { command: 'py', args: ['-3', '-u', scriptPath] },
          { command: 'python', args: ['-u', scriptPath] },
          { command: 'python3', args: ['-u', scriptPath] }
        ]
      : [
          { command: 'python3', args: ['-u', scriptPath] },
          { command: 'python', args: ['-u', scriptPath] }
        ];

    let lastError: Error | undefined;
    for (const candidate of candidates) {
      try {
        const processHandle = await this.spawnProcess(candidate.command, candidate.args, backendDir);
        this.backendProcess = processHandle;
        try {
          await this.waitForHealthy(processHandle);
          return API_BASE;
        } catch (error: any) {
          this.killBackendProcess();
          throw error;
        }
      } catch (error: any) {
        lastError = error instanceof Error ? error : new Error(String(error));
      }
    }

    throw lastError || new Error('无法启动后端服务');
  }

  private async startProductionBackend(): Promise<string> {
    this.outputChannel.appendLine('[模式] 生产模式 - 运行打包的可执行文件');

    const binaryName = process.platform === 'win32' ? 'backend.exe' : 'backend';
    const binaryPath = path.join(this.extensionContext.extensionPath, 'backend-bin', binaryName);

    if (!fs.existsSync(binaryPath)) {
      throw new Error(`后端可执行文件不存在: ${binaryPath}\n请先运行打包脚本生成后端可执行文件`);
    }

    const binaryDir = path.dirname(binaryPath);

    try {
      const processHandle = await this.spawnProcess(binaryPath, [], binaryDir);
      this.backendProcess = processHandle;

      try {
        await this.waitForHealthy(processHandle);
        return API_BASE;
      } catch (error: any) {
        this.killBackendProcess();
        throw error;
      }
    } catch (error: any) {
      throw error instanceof Error ? error : new Error(String(error));
    }
  }

  private async spawnProcess(
    command: string,
    args: string[],
    cwd: string
  ): Promise<ChildProcess> {
    return await new Promise((resolve, reject) => {
      const processHandle = spawn(command, args, {
        cwd,
        env: {
          ...process.env,
          PYTHONDONTWRITEBYTECODE: '1'
        },
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true
      });

      let settled = false;
      const settle = (fn: () => void) => {
        if (settled) {
          return;
        }
        settled = true;
        fn();
      };

      processHandle.once('spawn', () => {
        this.outputChannel.appendLine(`[spawn] ${command} ${args.join(' ')}`);
        processHandle.stdout?.on('data', (chunk) => {
          this.outputChannel.appendLine(String(chunk).trimEnd());
        });
        processHandle.stderr?.on('data', (chunk) => {
          this.outputChannel.appendLine(String(chunk).trimEnd());
        });
        processHandle.once('exit', (code, signal) => {
          this.outputChannel.appendLine(`[exit] code=${code ?? 'null'} signal=${signal ?? 'null'}`);
        });
        settle(() => resolve(processHandle));
      });

      processHandle.once('error', (error) => {
        settle(() => reject(error));
      });
    });
  }

  private async waitForHealthy(processHandle: ChildProcess): Promise<void> {
    const deadline = Date.now() + 20000;

    while (Date.now() < deadline) {
      if (await this.isHealthy()) {
        return;
      }

      if (processHandle.exitCode !== null) {
        throw new Error(`后端进程已退出，退出码: ${processHandle.exitCode}`);
      }

      await new Promise((resolve) => setTimeout(resolve, 500));
    }

    throw new Error('后端启动超时，请确认 Python 和依赖已安装');
  }

  private async isHealthy(): Promise<boolean> {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 1000);
      const response = await fetch(`${API_BASE}/health`, { signal: controller.signal });
      clearTimeout(timer);
      return response.ok;
    } catch {
      return false;
    }
  }

  private killBackendProcess(): void {
    if (this.backendProcess && this.backendProcess.exitCode === null) {
      this.backendProcess.kill();
    }
    this.backendProcess = undefined;
  }
}
