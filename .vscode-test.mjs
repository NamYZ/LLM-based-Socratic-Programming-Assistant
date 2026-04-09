import { defineConfig } from '@vscode/test-cli';

export default defineConfig({
	files: 'out/test/**/*.test.js',
});

// 定义了测试文件的位置 在 out 文件夹中