import * as assert from 'assert';
// vscode 模块提供扩展测试中常用的 API（弹窗、命令、工作区等）。
import * as vscode from 'vscode';
// 如果需要做集成测试，可以在这里导入扩展入口并触发真实行为。

suite('Extension Test Suite', () => {
	vscode.window.showInformationMessage('Start all tests.');

	// 这是一个示例测试，用于演示断言写法。
	test('Sample test', () => {	
		assert.strictEqual(-1, [1, 2, 3].indexOf(5));
		assert.strictEqual(-1, [1, 2, 3].indexOf(0));
	});
});
