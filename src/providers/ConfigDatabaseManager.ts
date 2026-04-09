import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export class ConfigDatabaseManager {
  private _sqlJsPromise?: Promise<any>;

  async loadConfigDetail(configId: number): Promise<any> {
    const db = await this.openLocalConfigDb();

    try {
      const stmt = db.prepare(`
        SELECT id, name, provider, base_url, api_key, model_name, is_active, created_at
        FROM model_configs_vscode
        WHERE id = ?
      `);
      stmt.bind([configId]);

      if (!stmt.step()) {
        stmt.free();
        throw new Error('配置不存在');
      }

      const row = stmt.getAsObject();
      stmt.free();

      return {
        id: Number(row.id),
        name: String(row.name ?? ''),
        provider: String(row.provider ?? 'qwen'),
        base_url: String(row.base_url ?? ''),
        api_key: String(row.api_key ?? ''),
        model_name: String(row.model_name ?? ''),
        is_active: Number(row.is_active ?? 0) === 1,
        created_at: String(row.created_at ?? '')
      };
    } finally {
      db.close();
    }
  }

  async updateConfig(configId: number, data: any): Promise<void> {
    if (!data?.name) {
      throw new Error('配置名称不能为空');
    }
    if (!data?.api_key) {
      throw new Error('API Key 不能为空');
    }
    if (!data?.base_url) {
      throw new Error('Base URL 不能为空');
    }

    const db = await this.openLocalConfigDb();

    try {
      const existingStmt = db.prepare('SELECT is_active FROM model_configs_vscode WHERE id = ?');
      existingStmt.bind([configId]);
      if (!existingStmt.step()) {
        existingStmt.free();
        throw new Error('配置不存在');
      }
      const existingRow = existingStmt.getAsObject();
      existingStmt.free();

      const duplicateStmt = db.prepare('SELECT id FROM model_configs_vscode WHERE name = ? AND id != ?');
      duplicateStmt.bind([data.name, configId]);
      const hasDuplicate = duplicateStmt.step();
      duplicateStmt.free();

      if (hasDuplicate) {
        throw new Error('配置名称已存在');
      }

      const existingIsActive = Number(existingRow.is_active ?? 0) === 1;
      const targetIsActive = data.set_active || existingIsActive ? 1 : 0;

      db.run('BEGIN TRANSACTION');

      if (data.set_active) {
        db.run('UPDATE model_configs_vscode SET is_active = 0');
      }

      db.run(
        `UPDATE model_configs_vscode
         SET name = ?, provider = ?, base_url = ?, api_key = ?, model_name = ?, is_active = ?, updated_at = ?
         WHERE id = ?`,
        [
          data.name,
          data.provider || 'qwen',
          data.base_url,
          data.api_key,
          data.model_name || 'qwen3-max',
          targetIsActive,
          this.getLocalTimestamp(),
          configId
        ]
      );

      db.run('COMMIT');
      this.saveLocalConfigDb(db);
    } catch (error) {
      try {
        db.run('ROLLBACK');
      } catch {
        // 忽略回滚失败，保留原始错误
      }
      throw error;
    } finally {
      db.close();
    }
  }

  private async openLocalConfigDb() {
    const SQL = await this.getSqlJs();
    const dbPath = this.getDbPath();

    if (!fs.existsSync(dbPath)) {
      throw new Error(`数据库不存在: ${dbPath}`);
    }

    const fileBuffer = fs.readFileSync(dbPath);
    return new SQL.Database(fileBuffer);
  }

  private saveLocalConfigDb(db: any) {
    const exported = db.export();
    fs.writeFileSync(this.getDbPath(), Buffer.from(exported));
  }

  private async getSqlJs() {
    if (!this._sqlJsPromise) {
      const initSqlJsModule = require('sql.js');
      const initSqlJs = initSqlJsModule.default ?? initSqlJsModule;
      this._sqlJsPromise = initSqlJs({
        locateFile: (file: string) => require.resolve(`sql.js/dist/${file}`)
      });
    }

    return this._sqlJsPromise;
  }

  private getDbPath() {
    return path.join(os.homedir(), 'vscode_chat.db');
  }

  private getLocalTimestamp() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  }
}
