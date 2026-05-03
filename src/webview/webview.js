// 在浏览器开发者控制台输出消息
console.log('[Webview] Script loaded');

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function escapeHtmlAttribute(text) {
  return text.replace(/"/g, '&quot;');
}

function restoreTokens(text, tokenMap) {
  let output = text;
  tokenMap.forEach((html, token) => {
    output = output.split(token).join(html);
  });
  return output;
}

function parseInlineMarkdown(text) {
  if (!text) {
    return '';
  }

  const inlineTokens = new Map();
  let output = text.replace(/`([^`\n]+)`/g, (match, code) => {
    const token = `@@MDINLINE${inlineTokens.size}@@`;
    inlineTokens.set(token, `<code>${code}</code>`);
    return token;
  });

  output = output.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
    const token = `@@MDINLINE${inlineTokens.size}@@`;
    inlineTokens.set(
      token,
      `<img src="${escapeHtmlAttribute(url)}" alt="${escapeHtmlAttribute(alt)}" style="max-width: 100%; height: auto;">`
    );
    return token;
  });

  output = output.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, label, url) => {
    const token = `@@MDINLINE${inlineTokens.size}@@`;
    inlineTokens.set(
      token,
      `<a href="${escapeHtmlAttribute(url)}" target="_blank" rel="noopener noreferrer">${label}</a>`
    );
    return token;
  });
  output = output.replace(/~~(.+?)~~/g, '<del>$1</del>');
  output = output.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  output = output.replace(/__(.+?)__/g, '<strong>$1</strong>');
  output = output.replace(/(^|[^\*])\*([^\*\n]+?)\*(?=($|[^\*]))/gm, '$1<em>$2</em>');
  output = output.replace(/(^|[^_])_([^_\n]+?)_(?=($|[^_]))/gm, '$1<em>$2</em>');

  return restoreTokens(output, inlineTokens);
}

function parseTableBlock(block) {
  const lines = block.split('\n').map(line => line.trim()).filter(Boolean);
  if (lines.length < 3) {
    return null;
  }

  if (!lines.every(line => /^\|.*\|$/.test(line)) || !/^\|[\s|:-]+\|$/.test(lines[1])) {
    return null;
  }

  const parseCells = (line) => line
    .split('|')
    .slice(1, -1)
    .map(cell => parseInlineMarkdown(cell.trim()));

  const headers = parseCells(lines[0]);
  const rows = lines.slice(2).map(parseCells);

  if (headers.length === 0 || rows.some(row => row.length !== headers.length)) {
    return null;
  }

  const headerHtml = headers.map(cell => `<th>${cell}</th>`).join('');
  const bodyHtml = rows
    .map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`)
    .join('');

  return `<table class="markdown-table"><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>`;
}

function parseListBlock(block) {
  const lines = block.split('\n').map(line => line.trim()).filter(Boolean);
  if (lines.length === 0) {
    return null;
  }

  let listTag = null;
  const items = [];

  for (const line of lines) {
    let match = line.match(/^[\*\-\+]\s+(.+)$/);
    if (match) {
      if (listTag && listTag !== 'ul') {
        return null;
      }
      listTag = 'ul';
      items.push(match[1]);
      continue;
    }

    match = line.match(/^\d+\.\s+(.+)$/);
    if (match) {
      if (listTag && listTag !== 'ol') {
        return null;
      }
      listTag = 'ol';
      items.push(match[1]);
      continue;
    }

    return null;
  }

  return `<${listTag}>${items.map(item => `<li>${parseInlineMarkdown(item)}</li>`).join('')}</${listTag}>`;
}

function separateStandaloneBlocks(text) {
  const lines = text.split('\n');
  const separatedLines = [];

  const isStandaloneLine = (line) => {
    const trimmed = line.trim();
    return /^@@MDCODEBLOCK\d+@@$/.test(trimmed)
      || /^\s{0,3}#{1,6}\s+.+$/.test(line)
      || /^(-{3,}|\*{3,}|_{3,})$/.test(trimmed);
  };

  lines.forEach((line, index) => {
    if (!isStandaloneLine(line)) {
      separatedLines.push(line);
      return;
    }

    if (separatedLines.length > 0 && separatedLines[separatedLines.length - 1] !== '') {
      separatedLines.push('');
    }

    separatedLines.push(line);

    if (index < lines.length - 1 && lines[index + 1] !== '') {
      separatedLines.push('');
    }
  });

  return separatedLines.join('\n');
}

// 简单的 Markdown 解析器
function parseMarkdown(text) {
  if (!text) {
    return '';
  }

  const codeBlockTokens = new Map();
  let normalized = text.replace(/\r\n?/g, '\n');

  normalized = normalized.replace(/```([^\n`]*)?\n([\s\S]*?)```/g, (match, lang, code) => {
    const token = `@@MDCODEBLOCK${codeBlockTokens.size}@@`;
    const language = (lang || '').trim() || 'plaintext';
    const trimmedCode = code.replace(/\n$/, '');
    codeBlockTokens.set(
      token,
      `<pre><code class="language-${language}">${escapeHtml(trimmedCode)}</code></pre>`
    );
    return `\n\n${token}\n\n`;
  });

  normalized = escapeHtml(normalized).trim();
  if (!normalized) {
    return '';
  }

  normalized = separateStandaloneBlocks(normalized);

  const blocks = normalized.split(/\n{2,}/).map(block => block.trim()).filter(Boolean);
  const htmlBlocks = blocks.map(block => {
    const codeBlockMatch = block.match(/^@@MDCODEBLOCK(\d+)@@$/);
    if (codeBlockMatch) {
      return codeBlockTokens.get(codeBlockMatch[0]) || '';
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(block)) {
      return '<hr>';
    }

    const tableHtml = parseTableBlock(block);
    if (tableHtml) {
      return tableHtml;
    }

    const listHtml = parseListBlock(block);
    if (listHtml) {
      return listHtml;
    }

    const headingMatch = block.match(/^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/);
    if (headingMatch && !block.includes('\n')) {
      const level = headingMatch[1].length;
      return `<h${level}>${parseInlineMarkdown(headingMatch[2])}</h${level}>`;
    }

    const quoteLines = block.split('\n');
    if (quoteLines.every(line => /^&gt;\s?/.test(line))) {
      const quoteContent = quoteLines
        .map(line => line.replace(/^&gt;\s?/, ''))
        .join('<br>');
      return `<blockquote>${parseInlineMarkdown(quoteContent)}</blockquote>`;
    }

    return `<p>${parseInlineMarkdown(block).replace(/\n/g, '<br>')}</p>`;
  });

  return htmlBlocks.join('');
}

// 格式化时间显示
function formatTimeAgo(timestamp) {
  if (!timestamp) {
    return '';
  }

  const now = new Date();
  const past = new Date(timestamp);
  const diffMs = now - past;
  const diffMinutes = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMinutes < 1) {
    return '刚刚';
  } else if (diffMinutes < 60) {
    return `${diffMinutes}分钟前`;
  } else if (diffHours < 24) {
    return `${diffHours}小时前`;
  } else if (diffDays < 7) {
    return `${diffDays}天前`;
  } else {
    // 超过7天显示具体日期
    const year = past.getFullYear();
    const month = String(past.getMonth() + 1).padStart(2, '0');
    const day = String(past.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
}

// 向 VS Code 申请 WebView API
const vscode = acquireVsCodeApi();

// 状态管理
let currentSessionId = null;
let currentMode = 'answer';
let isStreaming = false;
let codeContexts = []; // 存储已添加的代码上下文
let editingConfigId = null;
let activeStreamingContentEl = null;
let streamingRenderFrameId = null;

// Assembly Guide 状态
let manualHintMode = false;
let currentHintLevel = 1;
const API_BASE = 'http://127.0.0.1:5500';

// 模型参数状态
let modelParams = {
  temperature: 0.7,
  temperatureEnabled: true,
  topP: 1,
  topPEnabled: true,
  frequencyPenalty: 0,
  frequencyPenaltyEnabled: true,
  presencePenalty: 0,
  presencePenaltyEnabled: true
};

// DOM 元素（给页面上的各个交互组件起名字，后续代码可以通过变量直接操作这些组件）

// 聊天消息展示区域 - 消息输入文本框 - 发送消息按钮
const messagesArea = document.getElementById('messages-area');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const attachBtn = document.getElementById('attach-btn');
const codeContextTags = document.getElementById('code-context-tags');

// 模式选择 - 按钮和面板
const modeSelectBtn = document.getElementById('mode-select-btn');
const modeSelectPanel = document.getElementById('mode-select-panel');
const modeLabelText = document.getElementById('mode-label-text');

// 新建聊天 - 历史记录 - 采样参数 - 设置 - 关闭 五个按钮
const btnNewChat = document.getElementById('btn-new-chat');
const btnProgress = document.getElementById('btn-progress');
const btnHistory = document.getElementById('btn-history');
const btnSamplingParams = document.getElementById('btn-sampling-params');
const btnSettings = document.getElementById('btn-settings');
const btnClose = document.getElementById('btn-close');

// 聊天主视图 - 历史记录视图 - 采样参数视图 - 设置视图 - 编辑配置视图
const viewChat = document.getElementById('view-chat');
const viewHistory = document.getElementById('view-history');
const viewSamplingParams = document.getElementById('view-sampling-params');
const viewSettings = document.getElementById('view-settings');
const viewEditConfig = document.getElementById('view-edit-config');

// 历史记录列表 - 清空历史按钮
const historyList = document.getElementById('history-list');
const clearAllBtn = document.getElementById('clear-all-btn');

// 配置相关输入框（添加新配置）
const configNameInput = document.getElementById('config-name-input');
const apiKeyInput = document.getElementById('api-key-input');
const modelInput = document.getElementById('model-input');
const providerInput = document.getElementById('provider-input');
const baseUrlInput = document.getElementById('base-url-input');
const setActiveCheckbox = document.getElementById('set-active-checkbox');
const saveSettingsBtn = document.getElementById('save-settings-btn');
const configList = document.getElementById('config-list');

// 编辑配置相关输入框（编辑页面）
const editConfigNameInput = document.getElementById('edit-config-name-input');
const editApiKeyInput = document.getElementById('edit-api-key-input');
const editModelInput = document.getElementById('edit-model-input');
const editProviderInput = document.getElementById('edit-provider-input');
const editBaseUrlInput = document.getElementById('edit-base-url-input');
const editSetActiveCheckbox = document.getElementById('edit-set-active-checkbox');
const saveEditConfigBtn = document.getElementById('save-edit-config-btn');
const editConfigBackBtn = document.getElementById('edit-config-back-btn');

// 模型配置按钮 - 模型配置面板（高级模型设置） - 模型状态文本标签 - 模型状态指示点（green or red）
const modelConfigBtn = document.getElementById('model-config-btn');
const modelConfigPanel = document.getElementById('model-config-panel');
const modelLabelText = document.getElementById('model-label-text');
const modelDot = document.getElementById('model-dot');

// 采样参数相关元素
const temperatureSlider = document.getElementById('temperature-slider');
const temperatureValue = document.getElementById('temperature-value');
const temperatureEnabled = document.getElementById('temperature-enabled');

const topPSlider = document.getElementById('top-p-slider');
const topPValue = document.getElementById('top-p-value');
const topPEnabled = document.getElementById('top-p-enabled');

const frequencyPenaltySlider = document.getElementById('frequency-penalty-slider');
const frequencyPenaltyValue = document.getElementById('frequency-penalty-value');
const frequencyPenaltyEnabled = document.getElementById('frequency-penalty-enabled');

const presencePenaltySlider = document.getElementById('presence-penalty-slider');
const presencePenaltyValue = document.getElementById('presence-penalty-value');
const presencePenaltyEnabled = document.getElementById('presence-penalty-enabled');

const presetAnswerBtn = document.getElementById('preset-answer');
const presetGuidedBtn = document.getElementById('preset-guided');
const presetResetBtn = document.getElementById('preset-reset');

function cancelStreamingRenderFrame() {
  if (streamingRenderFrameId !== null) {
    cancelAnimationFrame(streamingRenderFrameId);
    streamingRenderFrameId = null;
  }
}

function resetStreamingRenderState() {
  cancelStreamingRenderFrame();
  activeStreamingContentEl = null;
}

function setActiveStreamingMessage(messageElement) {
  activeStreamingContentEl = messageElement?.querySelector('.message-content') || null;
  if (activeStreamingContentEl) {
    activeStreamingContentEl.classList.add('streaming');
  }
}

function getActiveStreamingContentEl() {
  if (activeStreamingContentEl && document.body.contains(activeStreamingContentEl)) {
    return activeStreamingContentEl;
  }
  activeStreamingContentEl = messagesArea.querySelector('.message.assistant:last-child .message-content');
  return activeStreamingContentEl;
}

function getActiveStreamingMessageEl() {
  return getActiveStreamingContentEl()?.closest('.message') || null;
}

// 检查用户是否在消息区域底部附近(容差50px)
function isUserAtBottom() {
  const threshold = 50;
  return messagesArea.scrollHeight - messagesArea.scrollTop - messagesArea.clientHeight < threshold;
}

// 智能滚动:只有用户在底部时才自动滚动
function smartScrollToBottom() {
  if (isUserAtBottom()) {
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }
}

function scheduleStreamingTextRender(contentEl) {
  if (!contentEl || streamingRenderFrameId !== null) {
    return;
  }
  streamingRenderFrameId = requestAnimationFrame(() => {
    streamingRenderFrameId = null;
    if (!contentEl || !document.body.contains(contentEl)) {
      return;
    }
    // 流式渲染时也解析 Markdown，提升用户体验
    const rawContent = contentEl.dataset.rawContent || '';
    contentEl.innerHTML = parseMarkdown(rawContent);
    smartScrollToBottom();
  });
}

function finalizeStreamingMessage(contentEl) {
  if (!contentEl) {
    return;
  }
  cancelStreamingRenderFrame();
  const rawContent = contentEl.dataset.rawContent || '';
  contentEl.classList.remove('streaming');
  contentEl.innerHTML = parseMarkdown(rawContent);

  // 显示操作按钮
  const messageDiv = contentEl.closest('.message');
  if (messageDiv) {
    const actionsDiv = messageDiv.querySelector('.message-actions');
    if (actionsDiv) {
      actionsDiv.classList.remove('hidden');
    }
  }

  smartScrollToBottom();
}

function formatAgentStepContent(step) {
  const sections = [];

  if (step.title) {
    sections.push(`**${step.title}**`);
  }

  if (step.content) {
    sections.push(step.content);
  }

  return sections.join('\n\n');
}

function addAgentProcessMessage(step) {
  const insertBeforeNode = getActiveStreamingMessageEl();
  const msgDiv = addMessage(
    'agent-process',
    formatAgentStepContent(step),
    [],
    false,
    { insertBeforeNode }
  );

  if (step.status) {
    msgDiv.classList.add(step.status);
  }
}

// 检查 DOM 元素
console.log('[Webview] DOM elements:', {
  messagesArea: !!messagesArea,
  sendBtn: !!sendBtn,
  attachBtn: !!attachBtn,
  btnNewChat: !!btnNewChat,
  btnHistory: !!btnHistory,
  btnSettings: !!btnSettings
});

// 初始化
console.log('[Webview] Loading settings...');

loadSettings();
loadConfigs();

// 初始化模式选项的选中状态
modeSelectPanel.querySelector('.mode-option[data-value="answer"]').classList.add('active');

console.log('[Webview] Setting up event listeners...');

// 发送消息 - 点击逻辑（ addEventListener 只负责监听用户点击事件，不负责处理事件）
sendBtn.addEventListener('click', () => {
  console.log('[Webview] Send button clicked');

  // 如果正在流式传输，点击按钮表示停止
  if (isStreaming) {
    console.log('[Webview] Stop button clicked, stopping stream');
    stopStreaming();
    return;
  }

  sendMessage();
});

// 发送消息 - 回车键逻辑
messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    // 检查是否正在使用输入法输入（composing状态）
    if (e.isComposing) {
      console.log('[Webview] Enter key pressed but composing, ignoring');
      return;
    }
    console.log('[Webview] Enter key pressed');
    e.preventDefault();
    sendMessage();
  }
});

// 文件引用按钮逻辑
attachBtn.addEventListener('click', () => {
  console.log('[Webview] Attach button clicked');
  if (isStreaming) {
    console.log('[Webview] Attach blocked while streaming');
    return;
  }

  // 调用 vscode.postMessage 发送类型为 pickFileReference 的消息给 ChatViewProvider 处理
  vscode.postMessage({ type: 'pickFileReference' });
  // pickFileReference 为字符串，用于通知 ChatViewProvider 处理文件引用逻辑
});

// 模式选择按钮逻辑 - 切换面板显示
modeSelectBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  console.log('[Webview] Mode select button clicked');
  const isShowing = modeSelectPanel.classList.toggle('show');
  // 旋转图标
  const icon = modeSelectBtn.querySelector('.dropdown-icon');
  if (isShowing) {
    icon.style.transform = 'rotate(180deg)';
  } else {
    icon.style.transform = 'rotate(0deg)';
  }
  // 关闭模型配置面板
  modelConfigPanel.classList.remove('show');
  const modelIcon = modelConfigBtn.querySelector('.dropdown-icon');
  modelIcon.style.transform = 'rotate(0deg)';
});

// 模式选项点击逻辑
modeSelectPanel.addEventListener('click', (e) => {
  // 支持点击整个mode-option或其子元素
  const modeOption = e.target.closest('.mode-option');
  if (modeOption) {
    const value = modeOption.dataset.value;
    let text = '答案式';
    if (value === 'answer') {
      text = '答案式';
    } else if (value === 'guided') {
      text = '引导式';
    } else if (value === 'assembly_guide') {
      text = '需求引导';
    } else if (value === 'assembly_check') {
      text = '代码检查';
    }
    currentMode = value;
    modeLabelText.textContent = text;

    // 更新选中状态
    modeSelectPanel.querySelectorAll('.mode-option').forEach(opt => {
      opt.classList.remove('active');
    });
    modeOption.classList.add('active');

    modeSelectPanel.classList.remove('show');
    const modeIcon = modeSelectBtn.querySelector('.dropdown-icon');
    modeIcon.style.transform = 'rotate(0deg)';
    console.log('[Webview] Mode changed to:', currentMode);

    // 如果切换到 assembly_guide 模式且有当前会话，更新进度
    if (currentMode === 'assembly_guide' && currentSessionId) {
      updateProgress(currentSessionId);
    } else {
      document.getElementById('progress-container').style.display = 'none';
    }
  }
});

// 新建聊天按钮逻辑 - 清空当前会话，重置状态，切换到聊天视图
btnNewChat.addEventListener('click', () => {
  console.log('[Webview] New chat button clicked');
  currentSessionId = null;
  codeContexts = [];
  renderCodeContextTags();
  clearMessages();
  messageInput.focus();
});

// 任务进度按钮逻辑 - 切换到任务进度视图
btnProgress.addEventListener('click', () => {
  console.log('[Webview] Progress button clicked');
  switchView('progress');
  updateProgressView();
});

// 历史记录按钮逻辑 - 切换到历史记录视图，加载历史会话数据
btnHistory.addEventListener('click', () => {
  console.log('[Webview] History button clicked');
  switchView('history');
  loadSessions();
});

// 采样参数按钮逻辑 - 切换到采样参数视图
btnSamplingParams.addEventListener('click', () => {
  console.log('[Webview] Sampling params button clicked');
  switchView('sampling-params');
  loadSamplingParams();
});

// 设置按钮逻辑 - 切换到设置视图
btnSettings.addEventListener('click', () => {
  console.log('[Webview] Settings button clicked');
  switchView('settings');
  loadConfigList();
});

// 关闭按钮逻辑 - 关闭webview面板
btnClose.addEventListener('click', () => {
  console.log('[Webview] Close button clicked');
  vscode.postMessage({ type: 'closePanel' });
});

// 历史记录和设置视图的返回按钮逻辑 - 切换回聊天视图
document.getElementById('history-back-btn').addEventListener('click', () => {
  console.log('[Webview] History back button clicked');
  switchView('chat');
});

document.getElementById('sampling-params-back-btn').addEventListener('click', () => {
  console.log('[Webview] Sampling params back button clicked');
  saveSamplingParams();
  switchView('chat');
});

document.getElementById('settings-back-btn').addEventListener('click', () => {
  console.log('[Webview] Settings back button clicked');
  switchView('chat');
});

document.getElementById('progress-back-btn').addEventListener('click', () => {
  console.log('[Webview] Progress back button clicked');
  switchView('chat');
});

// 清空历史按钮逻辑 - 发送清空历史的消息到后端
clearAllBtn.addEventListener('click', () => {
  console.log('[Webview] Clear all button clicked');
  // 直接清空，不使用 confirm（webview 不支持）
  vscode.postMessage({ type: 'clearAll' });
});

// 保存设置按钮逻辑 - 添加新配置
saveSettingsBtn.addEventListener('click', () => {
  console.log('[Webview] Save settings button clicked');
  const configName = configNameInput.value.trim();
  const apiKey = apiKeyInput.value.trim();
  const modelName = modelInput.value.trim() || 'qwen3-max';
  const provider = providerInput.value.trim() || 'qwen';
  const baseUrl = baseUrlInput.value.trim() || 'https://dashscope.aliyuncs.com/compatible-mode/v1';
  const setActive = setActiveCheckbox.checked;

  if (!configName) {
    console.log('[Webview] Config name is empty');
    showNotification('请输入配置名称', 'error');
    return;
  }

  if (!apiKey) {
    console.log('[Webview] API Key is empty');
    showNotification('请输入 API Key', 'error');
    return;
  }

  const payload = {
    name: configName,
    api_key: apiKey,
    model_name: modelName,
    provider: provider,
    base_url: baseUrl,
    set_active: setActive
  };

  console.log('[Webview] Adding config:', { configName, modelName, provider, baseUrl, setActive });
  vscode.postMessage({
    type: 'addConfig',
    data: payload
  });
});

// 保存编辑配置按钮逻辑
saveEditConfigBtn.addEventListener('click', () => {
  console.log('[Webview] Save edit config button clicked');
  const configName = editConfigNameInput.value.trim();
  const apiKey = editApiKeyInput.value.trim();
  const modelName = editModelInput.value.trim() || 'qwen3-max';
  const provider = editProviderInput.value.trim() || 'qwen';
  const baseUrl = editBaseUrlInput.value.trim() || 'https://dashscope.aliyuncs.com/compatible-mode/v1';
  const setActive = editSetActiveCheckbox.checked;

  if (!configName) {
    console.log('[Webview] Config name is empty');
    showNotification('请输入配置名称', 'error');
    return;
  }

  if (!apiKey) {
    console.log('[Webview] API Key is empty');
    showNotification('请输入 API Key', 'error');
    return;
  }

  if (editingConfigId === null) {
    console.log('[Webview] No config is being edited');
    showNotification('没有正在编辑的配置', 'error');
    return;
  }

  const payload = {
    name: configName,
    api_key: apiKey,
    model_name: modelName,
    provider: provider,
    base_url: baseUrl,
    set_active: setActive
  };

  console.log('[Webview] Updating config:', { editingConfigId, configName, modelName, provider, baseUrl, setActive });
  vscode.postMessage({
    type: 'updateConfig',
    configId: editingConfigId,
    data: payload
  });
});

// 编辑配置返回按钮
editConfigBackBtn.addEventListener('click', () => {
  console.log('[Webview] Edit config back button clicked');
  editingConfigId = null;
  switchView('settings');
});

// 模型配置按钮逻辑 - 切换模型配置面板的显示状态
modelConfigBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  console.log('[Webview] Model config button clicked');
  const isShowing = modelConfigPanel.classList.toggle('show');
  // 旋转图标
  const icon = modelConfigBtn.querySelector('.dropdown-icon');
  if (isShowing) {
    icon.style.transform = 'rotate(180deg)';
  } else {
    icon.style.transform = 'rotate(0deg)';
  }
  // 关闭模式选择面板
  modeSelectPanel.classList.remove('show');
  const modeIcon = modeSelectBtn.querySelector('.dropdown-icon');
  modeIcon.style.transform = 'rotate(0deg)';
  console.log('[Webview] Model config panel visible:', modelConfigPanel.classList.contains('show'));
});

// 模型配置选项点击逻辑
modelConfigPanel.addEventListener('click', (e) => {
  if (e.target.classList.contains('model-config-option')) {
    const configId = e.target.dataset.configId;
    console.log('[Webview] Switching to config:', configId);
    vscode.postMessage({ type: 'activateConfig', configId: parseInt(configId) });

    // 更新选中状态
    modelConfigPanel.querySelectorAll('.model-config-option').forEach(opt => {
      opt.classList.remove('active');
    });
    e.target.classList.add('active');

    // 关闭面板
    modelConfigPanel.classList.remove('show');
    const modelIcon = modelConfigBtn.querySelector('.dropdown-icon');
    modelIcon.style.transform = 'rotate(0deg)';
  }
});

// 点击页面其他地方关闭下拉面板
document.addEventListener('click', (e) => {
  if (!modeSelectBtn.contains(e.target) && !modeSelectPanel.contains(e.target)) {
    modeSelectPanel.classList.remove('show');
    const modeIcon = modeSelectBtn.querySelector('.dropdown-icon');
    modeIcon.style.transform = 'rotate(0deg)';
  }
  if (!modelConfigBtn.contains(e.target) && !modelConfigPanel.contains(e.target)) {
    modelConfigPanel.classList.remove('show');
    const modelIcon = modelConfigBtn.querySelector('.dropdown-icon');
    modelIcon.style.transform = 'rotate(0deg)';
  }
});

// 设置消息监听器 - 监听来自后端的消息，根据消息类型更新 UI 或处理数据
console.log('[Webview] Setting up message listener...');
window.addEventListener('message', (event) => {
  const message = event.data;
  console.log('[Webview] Received message:', message.type, message);

  switch (message.type) {
    case 'settingsLoaded':
      console.log('[Webview] Settings loaded:', message.data);
      if (message.data.configured) {
        modelLabelText.textContent = message.data.model_name || '已配置';
        modelDot.className = 'model-dot active';
      } else {
        modelLabelText.textContent = '未配置';
        modelDot.className = 'model-dot';
      }
      break;

    case 'settingsSaved':
      console.log('[Webview] Settings saved:', message.success);
      if (message.success) {
        loadSettings();
        loadConfigs();
        setTimeout(() => {
          modelConfigPanel.classList.remove('show');
        }, 1000);
      }
      break;

    case 'configAdded':
      console.log('[Webview] Config added:', message.success);
      if (message.success) {
        // 清空添加表单
        configNameInput.value = '';
        apiKeyInput.value = '';
        modelInput.value = '';
        providerInput.value = 'qwen';
        baseUrlInput.value = '';
        setActiveCheckbox.checked = true;
        // 重新加载配置列表
        loadConfigList();
        loadSettings();
        loadConfigs();
      }
      break;

    case 'configUpdated':
      console.log('[Webview] Config updated:', message.success);
      if (message.success) {
        editingConfigId = null;
        loadConfigList();
        loadSettings();
        loadConfigs();
        switchView('settings');
      }
      break;

    case 'configsListLoaded':
      console.log('[Webview] Configs list loaded:', message.data);
      renderConfigList(message.data);
      break;

    case 'configDetailLoaded':
      console.log('[Webview] Config detail loaded:', message.data);
      populateConfigForm(message.data);
      break;

    case 'configDeleted':
      console.log('[Webview] Config deleted');
      if (message.success) {
        loadConfigList();
        loadSettings();
        loadConfigs();
      }
      break;

    case 'chatChunk':
      handleChatChunk(message.data);
      break;

    case 'chatError':
      console.log('[Webview] Chat error:', message.error);
      resetStreamingRenderState();
      isStreaming = false;
      updateSendButtonState(false);
      break;

    case 'sessionsLoaded':
      console.log('[Webview] Sessions loaded:', message.data.length);
      renderSessions(message.data);
      break;

    case 'sessionMessagesLoaded':
      console.log('[Webview] Session messages loaded');
      codeContexts = [];
      renderCodeContextTags();
      loadSessionIntoChat(message.data);
      break;

    case 'sessionDeleted':
      console.log('[Webview] Session deleted');
      loadSessions();
      break;

    case 'historyCleared':
      console.log('[Webview] History cleared');
      currentSessionId = null;
      clearMessages();
      loadSessions();
      break;

    case 'configsLoaded':
      console.log('[Webview] Configs loaded:', message.data);
      renderConfigSelect(message.data);
      break;

    case 'configActivated':
      console.log('[Webview] Config activated');
      if (message.success) {
        if (typeof message.configId === 'number') {
          markConfigAsActiveInSettings(message.configId);
        }
        loadSettings();
        loadConfigs();
        loadConfigList();
        modelConfigPanel.classList.remove('show');
      }
      break;

    case 'quickMessage':
      console.log('[Webview] Quick message received:', message.message);
      // 自动填充消息并发送
      messageInput.value = message.message;
      sendMessage();
      break;

    case 'newChat':
      console.log('[Webview] New chat message received');
      currentSessionId = null;
      codeContexts = [];
      renderCodeContextTags();
      clearMessages();
      switchView('chat');
      messageInput.focus();
      break;

    case 'openSettings':
      console.log('[Webview] Open settings message received');
      switchView('settings');
      loadConfigList();
      break;

    case 'codeContextAdded':
      console.log('[Webview] Code context added:', message.data);
      // 添加代码上下文到列表
      addCodeContext(message.data);
      break;

    case 'clearCodeContexts':
      console.log('[Webview] Clear code contexts');
      // 清空代码上下文
      codeContexts = [];
      renderCodeContextTags();
      break;
  }
});

// 向 VS Code 扩展主进程请求加载设置数据
function loadSettings() {
  console.log('[Webview] loadSettings() called');
  vscode.postMessage({ type: 'loadSettings' });
}

// 向 VS Code 扩展主进程请求加载配置列表
function loadConfigs() {
  console.log('[Webview] loadConfigs() called');
  vscode.postMessage({ type: 'loadConfigs' });
}

// 向 VS Code 扩展主进程请求加载完整配置列表（用于设置页面）
function loadConfigList() {
  console.log('[Webview] loadConfigList() called');
  vscode.postMessage({ type: 'loadConfigsList' });
}

function loadConfigDetail(configId) {
  console.log('[Webview] loadConfigDetail() called:', configId);
  vscode.postMessage({ type: 'loadConfigDetail', configId });
}

function markConfigAsActiveInSettings(configId) {
  console.log('[Webview] markConfigAsActiveInSettings() called:', configId);
  const targetConfigId = String(configId);

  configList.querySelectorAll('.config-item').forEach(item => {
    const isTarget = item.dataset.configId === targetConfigId;
    item.classList.toggle('active', isTarget);

    const nameDiv = item.querySelector('.config-item-name');
    const badge = nameDiv?.querySelector('.active-badge');

    if (isTarget && nameDiv && !badge) {
      nameDiv.insertAdjacentHTML('beforeend', '<span class="active-badge">当前</span>');
    }

    if (!isTarget && badge) {
      badge.remove();
    }

    const actions = item.querySelector('.config-item-actions');
    if (!actions) {
      return;
    }

    const deleteBtn = actions.querySelector('.delete-btn');
    if (isTarget) {
      if (deleteBtn) {
        deleteBtn.remove();
      }
    } else if (!deleteBtn) {
      actions.insertAdjacentHTML(
        'beforeend',
        `<button class="config-action-btn delete-btn" data-config-id="${item.dataset.configId}" title="删除此配置">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12"/>
          </svg>
        </button>`
      );
    }
  });

  if (editingConfigId !== null) {
    editSetActiveCheckbox.checked = editingConfigId === configId;
  }
}

function resetConfigForm() {
  console.log('[Webview] resetConfigForm() called');
  editingConfigId = null;
  apiKeyInput.type = 'password';
  configNameInput.value = '';
  apiKeyInput.value = '';
  modelInput.value = '';
  providerInput.value = 'qwen';
  baseUrlInput.value = '';
  setActiveCheckbox.checked = true;
}

function populateConfigForm(config) {
  console.log('[Webview] populateConfigForm() called:', config);
  editingConfigId = config.id;

  // 填充编辑页面的表单
  editConfigNameInput.value = config.name || '';
  editApiKeyInput.value = config.api_key || '';
  editModelInput.value = config.model_name || '';
  editProviderInput.value = config.provider || 'qwen';
  editBaseUrlInput.value = config.base_url || '';
  editSetActiveCheckbox.checked = !!config.is_active;

  // 切换到编辑页面
  switchView('edit-config');
  editConfigNameInput.focus();
}

// 渲染配置选择下拉框
function renderConfigSelect(configs) {
  console.log('[Webview] renderConfigSelect() called:', configs.length);
  if (configs.length === 0) {
    modelConfigPanel.innerHTML = '<div class="model-config-option" style="color: var(--text-muted); cursor: default;">暂无配置</div>';
    return;
  }

  modelConfigPanel.innerHTML = configs.map(c =>
    `<div class="model-config-option ${c.is_active ? 'active' : ''}" data-config-id="${c.id}">
      ${c.name} (${c.provider})
    </div>`
  ).join('');
}

// 渲染配置列表（设置页面）
function renderConfigList(configs) {
  console.log('[Webview] renderConfigList() called:', configs.length);
  if (configs.length === 0) {
    configList.innerHTML = '<div class="empty-config">暂无配置</div>';
    if (editingConfigId !== null) {
      editingConfigId = null;
    }
    return;
  }

  configList.innerHTML = configs.map(c => `
    <div class="config-item ${c.is_active ? 'active' : ''}" data-config-id="${c.id}">
      <div class="config-item-info">
        <div class="config-item-name">
          ${c.name}
          ${c.is_active ? '<span class="active-badge">当前</span>' : ''}
        </div>
        <div class="config-item-details">
          <span class="config-item-detail">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 12px; height: 12px;">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 6v6l4 2"/>
            </svg>
            ${c.provider}
          </span>
          <span class="config-item-detail">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 12px; height: 12px;">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
            </svg>
            ${c.model_name}
          </span>
          <span class="config-item-detail">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 12px; height: 12px;">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
            ${c.api_key}
          </span>
        </div>
      </div>
      <div class="config-item-actions">
        <button class="config-action-btn edit-btn" data-config-id="${c.id}" title="修改此配置">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 20h9"/>
            <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
          </svg>
        </button>
        ${!c.is_active ? `
          <button class="config-action-btn delete-btn" data-config-id="${c.id}" title="删除此配置">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        ` : ''}
      </div>
    </div>
  `).join('');

  // 绑定配置项点击事件
  configList.querySelectorAll('.config-item').forEach(item => {
    item.addEventListener('click', (e) => {
      const editBtn = e.target.closest('.edit-btn');
      if (editBtn) {
        e.stopPropagation();
        loadConfigDetail(parseInt(editBtn.dataset.configId, 10));
        return;
      }

      const deleteBtn = e.target.closest('.delete-btn');
      if (deleteBtn) {
        e.stopPropagation();
        const configId = deleteBtn.dataset.configId;
        console.log('[Webview] Deleting config:', configId);
        vscode.postMessage({ type: 'deleteConfig', configId: parseInt(configId, 10) });
        return;
      }

      const configId = item.dataset.configId;
      const isActive = item.classList.contains('active');

      // 如果已经是激活状态，不需要切换
      if (isActive) {
        return;
      }

      console.log('[Webview] Activating config:', configId);
      vscode.postMessage({ type: 'activateConfig', configId: parseInt(configId, 10) });
    });
  });
}

// 发送消息函数 - 包括输入验证、UI 更新、向后端发送消息等逻辑（调用 vscode.postMessage 发送消息给 ChatViewProvider 处理）
function sendMessage() {
  console.log('[Webview] sendMessage() called');

  // 获取用户输入的消息，并去除首尾空白
  const message = messageInput.value.trim();
  console.log('[Webview] Message:', message, 'isStreaming:', isStreaming);

  // 如果消息为空或者正在流式传输中，阻止发送并给出提示
  if (!message || isStreaming) {
    console.log('[Webview] Message blocked - empty or streaming');
    return;
  }

  // 设置流式传输状态，切换按钮为暂停状态 - 核心：防止重复发送
  isStreaming = true;
  updateSendButtonState(true);
  resetStreamingRenderState();

  // 保存当前的代码上下文（在清空之前）
  const currentCodeContexts = [...codeContexts];

  // UI 显示用户发送的消息到聊天界面（包含代码上下文预览）
  addMessage('user', message, currentCodeContexts);

  // 清空输入框 - 核心：发送后清空输入框，准备下一条消息
  messageInput.value = '';

  // 清空代码上下文标签
  codeContexts = [];
  renderCodeContextTags();

  // 创建 AI 消息占位符（避免 AI 响应速度慢时界面无反馈）
  const aiMsgDiv = addMessage('assistant', '正在思考...', [], true);
  setActiveStreamingMessage(aiMsgDiv);

  // 准备采样参数（只包含启用的参数）
  const samplingParams = {};
  if (modelParams.temperatureEnabled) {
    samplingParams.temperature = modelParams.temperature;
  }
  if (modelParams.topPEnabled) {
    samplingParams.top_p = modelParams.topP;
  }
  if (modelParams.frequencyPenaltyEnabled) {
    samplingParams.frequency_penalty = modelParams.frequencyPenalty;
  }
  if (modelParams.presencePenaltyEnabled) {
    samplingParams.presence_penalty = modelParams.presencePenalty;
  }

  console.log('[Webview] Sending message to backend:', { message, session_id: currentSessionId, mode: currentMode, codeContexts: currentCodeContexts, samplingParams });

  // 向后端发送消息，包含消息内容、当前会话 ID、对话模式和采样参数
  vscode.postMessage({
    type: 'sendMessage',
    data: {
      message,
      session_id: currentSessionId,
      mode: currentMode,
      codeContexts: currentCodeContexts,
      samplingParams: samplingParams
    }
  });
}

// 停止流式传输
function stopStreaming() {
  console.log('[Webview] stopStreaming() called');

  // 通知后端停止流式传输
  vscode.postMessage({
    type: 'stopStreaming'
  });

  // 重置状态
  const lastMsg = getActiveStreamingContentEl();
  if (lastMsg) {
    const currentContent = lastMsg.dataset.rawContent || '';
    if (currentContent) {
      lastMsg.dataset.rawContent = currentContent + '\n\n[已停止生成]';
    } else {
      lastMsg.dataset.rawContent = '[已停止生成]';
    }
    finalizeStreamingMessage(lastMsg);
  }

  resetStreamingRenderState();
  isStreaming = false;
  updateSendButtonState(false);
  messageInput.focus();
}

// 更新发送按钮状态（发送/暂停）
function updateSendButtonState(isStreaming) {
  const sendIcon = sendBtn.querySelector('.send-icon');
  const stopIcon = sendBtn.querySelector('.stop-icon');

  if (isStreaming) {
    // 切换为暂停按钮
    sendIcon.classList.add('hidden');
    stopIcon.classList.remove('hidden');
    sendBtn.title = '停止生成';
    sendBtn.disabled = false;
  } else {
    // 切换为发送按钮
    sendIcon.classList.remove('hidden');
    stopIcon.classList.add('hidden');
    sendBtn.title = '发送';
    sendBtn.disabled = false;
  }
}

// 处理后端发送的聊天流式数据
function handleChatChunk(data) {
  console.log('[Webview] handleChatChunk:', data);

  if (data.agent_step) {
    addAgentProcessMessage(data.agent_step);
    return;
  }

  // 处理状态更新
  if (data.status) {
    const lastMsg = getActiveStreamingContentEl();
    if (lastMsg) {
      // 将状态信息显示在正常的消息框中，而不是特殊的状态指示器
      let statusText = data.status;

      // 根据状态内容判断类型
      if (data.status === 'thinking') {
        statusText = '正在思考...';
      } else if (data.status === 'generating') {
        statusText = '正在生成回复...';
      }
      // 其他状态直接显示原文（如 "🔄 初始化会话状态..."）

      // 使用与正式回答相同的样式显示状态消息
      lastMsg.dataset.rawContent = statusText;
      lastMsg.classList.add('streaming');
      lastMsg.innerHTML = parseMarkdown(statusText);
    }
    return;
  }

  // 处理流式更新 AI 消息内容
  if (data.content) {
    // 找到当前 AI 消息的内容元素
    const lastMsg = getActiveStreamingContentEl();
    if (lastMsg) {
      // 累积原始文本内容
      if (!lastMsg.dataset.rawContent) {
        lastMsg.dataset.rawContent = '';
      }
      // 如果之前是状态消息，清空后再追加新内容
      const previousContent = lastMsg.dataset.rawContent;
      if (previousContent && (
        previousContent.includes('正在思考') ||
        previousContent.includes('正在生成') ||
        previousContent.includes('🔄') ||
        previousContent.includes('🤖') ||
        previousContent.includes('💭') ||
        previousContent.includes('🛠️') ||
        previousContent.includes('✅') ||
        previousContent.includes('⚠️') ||
        previousContent.includes('📌') ||
        previousContent.includes('📝')
      )) {
        lastMsg.dataset.rawContent = '';
      }
      lastMsg.dataset.rawContent += data.content;
      lastMsg.classList.add('streaming');
      scheduleStreamingTextRender(lastMsg);
    }
  }
  // 当流式传输完成时，重置状态并更新当前会话 ID（如果有的话）
  if (data.done) {
    console.log('[Webview] Chat stream done');
    const lastMsg = getActiveStreamingContentEl();
    finalizeStreamingMessage(lastMsg);
    resetStreamingRenderState();
    isStreaming = false;
    updateSendButtonState(false);
    if (data.session_id) {
      currentSessionId = data.session_id;
    }

    // 如果是 assembly_guide 模式，更新进度
    if (currentMode === 'assembly_guide' && currentSessionId) {
      updateProgress(currentSessionId);
    }

    // 检查是否任务完成，显示导出按钮
    if (data.completion_status === 'completed' && currentSessionId) {
      showExportButton(currentSessionId);
    }

    messageInput.focus();
  }
  // 处理错误情况，显示错误通知并重置状态
  if (data.error) {
    console.log('[Webview] Chat chunk error:', data.error);
    resetStreamingRenderState();
    isStreaming = false;
    updateSendButtonState(false);

    // 在聊天界面显示红色错误消息
    const lastMsg = messagesArea.querySelector('.message.assistant:last-child .message-content');
    if (lastMsg) {
      lastMsg.className = 'message-content error-message';
      lastMsg.innerHTML = `
        <div class="error-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
        </div>
        <div class="error-text">${data.error.replace(/\n/g, '<br>')}</div>
      `;
    }
  }
}

// 添加消息到聊天界面函数
function addMessage(role, content, contexts = [], isStreaming = false, options = {}) {
  console.log('[Webview] addMessage:', role, content);
  const insertBeforeNode = options.insertBeforeNode || null;

  // 一旦有消息，空状态提示就不再显示（重新获取元素以确保引用正确）
  const currentEmptyState = document.getElementById('empty-state');
  if (currentEmptyState) {
    currentEmptyState.remove();
  }

  // 区分用户消息和 AI 消息，创建不同样式的消息元素
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${role}`;

  // 单独拆分消息内容的 DOM 元素，方便后续更新（如流式更新 AI 消息）
  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';

  // 用户消息用纯文本，AI 消息用 Markdown 渲染
  if (role === 'user') {
    // 如果有代码上下文，先添加预览
    if (contexts && contexts.length > 0) {
      const previewDiv = document.createElement('div');
      previewDiv.className = 'code-context-preview';

      contexts.forEach(ctx => {
        const previewItem = document.createElement('div');
        previewItem.className = 'code-preview-item';

        const lineInfo = ctx.selection ? `:${ctx.selection.start + 1}-${ctx.selection.end + 1}` : '';
        const header = document.createElement('div');
        header.className = 'code-preview-header';
        header.textContent = `${ctx.fileName}${lineInfo}`;

        const codeBlock = document.createElement('pre');
        codeBlock.className = 'code-preview-content';
        const code = document.createElement('code');
        code.textContent = ctx.content;
        codeBlock.appendChild(code);

        previewItem.appendChild(header);
        previewItem.appendChild(codeBlock);
        previewDiv.appendChild(previewItem);
      });

      msgDiv.appendChild(previewDiv);
    }

    // 然后添加文本内容
    contentDiv.textContent = content;
    msgDiv.appendChild(contentDiv);
  } else {
    // AI 消息：存储原始内容并渲染 Markdown
    contentDiv.dataset.rawContent = content;
    contentDiv.innerHTML = content ? parseMarkdown(content) : '';
    msgDiv.appendChild(contentDiv);
  }

  // 如果是 AI 消息，添加操作按钮
  if (role === 'assistant') {
    const actionsDiv = document.createElement('div');
    // 如果正在流式传输，初始时隐藏按钮；否则显示按钮（历史消息）
    actionsDiv.className = isStreaming ? 'message-actions hidden' : 'message-actions';
    actionsDiv.innerHTML = `
      <button class="message-action-btn regenerate-btn" title="重新生成">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
      <button class="message-action-btn copy-btn" title="复制">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
      </button>
    `;
    msgDiv.appendChild(actionsDiv);

    // 绑定按钮事件
    const regenerateBtn = actionsDiv.querySelector('.regenerate-btn');
    const copyBtn = actionsDiv.querySelector('.copy-btn');

    regenerateBtn.addEventListener('click', () => {
      console.log('[Webview] Regenerate button clicked');
      regenerateLastMessage();
    });

    copyBtn.addEventListener('click', () => {
      console.log('[Webview] Copy button clicked');
      copyMessageContent(contentDiv.dataset.rawContent || contentDiv.textContent);
    });
  }

  if (insertBeforeNode && insertBeforeNode.parentNode === messagesArea) {
    messagesArea.insertBefore(msgDiv, insertBeforeNode);
  } else {
    messagesArea.appendChild(msgDiv);
  }

  // 每次添加消息后智能滚动到底部
  smartScrollToBottom();

  return msgDiv;
}

// 清空消息展示区域函数 - 包括重置状态和显示空状态提示
function clearMessages() {
  console.log('[Webview] clearMessages() called');
  resetStreamingRenderState();

  // 清空消息展示区域
  messagesArea.innerHTML = '';

  // 创建一个新的空状态提示元素
  const emptyDiv = document.createElement('div');
  emptyDiv.className = 'empty-state';
  emptyDiv.id = 'empty-state';

  // 填充空状态提示内容，包含一个 SVG 图标和一些文本，引导用户开始对话
  emptyDiv.innerHTML = `
    <svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
    <h3>开始新对话</h3>
    <p>向 AI 提问编程问题<br>支持多种教学模式</p>
  `;

  // 将 空状态提示 插入 消息展示区域
  messagesArea.appendChild(emptyDiv);
}

// 切换视图函数 - 根据传入的视图名称显示对应的视图
function switchView(viewName) {
  console.log('[Webview] switchView() called:', viewName);

  // 移除所有视图的 active 类，隐藏所有视图
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

  // 给目标视图添加 active 类，激活目标视图
  document.getElementById(`view-${viewName}`).classList.add('active');
}

// 向 VS Code 扩展主进程请求加载历史会话数据
function loadSessions() {
  console.log('[Webview] loadSessions() called');
  vscode.postMessage({ type: 'loadSessions' });
}

// 渲染历史会话列表函数
function renderSessions(sessions) {
  console.log('[Webview] renderSessions() called:', sessions.length);
  if (sessions.length === 0) {
    historyList.innerHTML = `
      <div class="empty-history">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" stroke-linecap="round"/>
        </svg>
        <span>暂无历史会话</span>
      </div>
    `;
    return;
  }

  historyList.innerHTML = sessions.map(s => {
    // 确定模式显示文本和样式类
    let modeText = '答案式';
    let modeClass = 'mode-answer';
    if (s.mode === 'guided') {
      modeText = '引导式';
      modeClass = 'mode-guided';
    } else if (s.mode === 'assembly_guide') {
      modeText = '需求引导';
      modeClass = 'mode-assembly-guide';
    } else if (s.mode === 'assembly_check') {
      modeText = '代码检查';
      modeClass = 'mode-assembly-check';
    }

    return `
    <div class="history-item" data-session-id="${s.id}">
      <div class="history-item-main">
        <div class="history-item-header">
          <span class="history-item-title">${s.title}</span>
        </div>
        <div class="history-item-meta">
          <span class="history-item-mode ${modeClass}">${modeText}</span>
          <span class="history-item-count">${s.msg_count} 条消息</span>
          <span class="history-item-time">${formatTimeAgo(s.updated_at)}</span>
        </div>
      </div>
      <div class="history-item-actions">
        <button class="history-item-action history-item-export" data-session-id="${s.id}" title="导出 Markdown">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 3v12"/>
            <path d="M7 10l5 5 5-5"/>
            <path d="M5 21h14"/>
          </svg>
        </button>
        <button class="history-item-action history-item-delete" data-session-id="${s.id}" title="删除会话">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </div>
  `;
  }).join('');

  // 绑定点击事件
  historyList.querySelectorAll('.history-item').forEach(item => {
    item.addEventListener('click', (e) => {
      console.log('[Webview] History item clicked');
      const exportBtn = e.target.closest('.history-item-export');
      if (exportBtn) {
        e.stopPropagation();
        const sessionId = exportBtn.dataset.sessionId;
        vscode.postMessage({ type: 'exportSessionMarkdown', sessionId: parseInt(sessionId, 10) });
        return;
      }

      const deleteBtn = e.target.closest('.history-item-delete');
      if (deleteBtn) {
        e.stopPropagation();
        const sessionId = deleteBtn.dataset.sessionId;
        // 直接删除，不使用 confirm（webview 不支持）
        vscode.postMessage({ type: 'deleteSession', sessionId: parseInt(sessionId, 10) });
      } else {
        const sessionId = item.dataset.sessionId;
        console.log('[Webview] Loading session:', sessionId);
        vscode.postMessage({ type: 'loadSessionMessages', sessionId: parseInt(sessionId, 10) });
      }
    });
  });
}

// 加载会话消息到聊天界面
function loadSessionIntoChat(data) {
  console.log('[Webview] loadSessionIntoChat() called:', data);
  resetStreamingRenderState();

  // 设置当前会话 ID 和模式，更新模式选择按钮的值
  currentSessionId = data.session?.id || null;
  currentMode = data.session.mode;

  // 更新模式按钮显示
  let modeText = '答案式';
  if (currentMode === 'guided') {
    modeText = '引导式';
  } else if (currentMode === 'assembly_guide') {
    modeText = '需求引导';
  } else if (currentMode === 'assembly_check') {
    modeText = '代码检查';
  }
  modeLabelText.textContent = modeText;

  // 更新模式选项的选中状态
  modeSelectPanel.querySelectorAll('.mode-option').forEach(opt => {
    if (opt.dataset.value === currentMode) {
      opt.classList.add('active');
    } else {
      opt.classList.remove('active');
    }
  });

  // 清空当前聊天消息
  messagesArea.innerHTML = '';

  // 遍历会话消息，逐条添加到聊天界面
  data.messages.forEach(msg => {
    addMessage(msg.role, msg.content);
  });

  // 切换回聊天视图
  switchView('chat');
}

// 显示通知函数 - 在页面上显示一个临时的通知消息
function showNotification(message, type = 'info') {
  console.log('[Webview] showNotification:', message, type);
  const notification = document.getElementById('notification');

  // 设置通知文本和样式，根据类型（成功、错误、信息）应用不同的样式
  notification.textContent = message;

  // 设置不同类型的通知样式
  notification.className = `notification show ${type}`;

  // 3秒后自动隐藏通知
  setTimeout(() => {
    notification.classList.remove('show');
  }, 3000);
}

// 重新生成最后一条消息
function regenerateLastMessage() {
  console.log('[Webview] regenerateLastMessage() called');

  if (isStreaming) {
    console.log('[Webview] Cannot regenerate while streaming');
    return;
  }

  // 找到最后一条用户消息
  const messages = messagesArea.querySelectorAll('.message.user');
  if (messages.length === 0) {
    console.log('[Webview] No user messages to regenerate');
    return;
  }

  const lastUserMessage = messages[messages.length - 1];
  const messageContent = lastUserMessage.querySelector('.message-content').textContent;

  // 删除最后一轮响应中的所有非用户消息（包括 Agent 过程消息）
  let nextSibling = lastUserMessage.nextElementSibling;
  while (nextSibling) {
    const currentNode = nextSibling;
    nextSibling = nextSibling.nextElementSibling;
    currentNode.remove();
  }

  // 重新发送消息
  isStreaming = true;
  updateSendButtonState(true);
  resetStreamingRenderState();

  // 创建 AI 消息占位符
  const aiMsgDiv = addMessage('assistant', '正在思考...', [], true);
  setActiveStreamingMessage(aiMsgDiv);

  console.log('[Webview] Regenerating message:', { message: messageContent, session_id: currentSessionId, mode: currentMode });

  // 向后端发送消息
  vscode.postMessage({
    type: 'sendMessage',
    data: {
      message: messageContent,
      session_id: currentSessionId,
      mode: currentMode,
      codeContexts: codeContexts
    }
  });
}

// 复制消息内容
function copyMessageContent(content) {
  console.log('[Webview] copyMessageContent() called');

  // 使用 Clipboard API 复制文本
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(content).then(() => {
      console.log('[Webview] Content copied to clipboard');
    }).catch(err => {
      console.error('[Webview] Failed to copy:', err);
    });
  } else {
    // 降级方案：使用 execCommand
    const textarea = document.createElement('textarea');
    textarea.value = content;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
      console.log('[Webview] Content copied to clipboard (fallback)');
    } catch (err) {
      console.error('[Webview] Failed to copy (fallback):', err);
    }
    document.body.removeChild(textarea);
  }
}

// 添加代码上下文到 UI
function addCodeContext(context) {
  console.log('[Webview] addCodeContext() called:', context);

  // 相同文件/相同行范围的引用只保留一份，避免重复标签
  const existingIndex = codeContexts.findIndex((ctx) => {
    const sameFile = ctx.filePath === context.filePath;
    const bothFullFile = !ctx.selection && !context.selection;
    const sameSelection = ctx.selection && context.selection &&
      ctx.selection.start === context.selection.start &&
      ctx.selection.end === context.selection.end;

    return sameFile && (bothFullFile || sameSelection);
  });

  if (existingIndex >= 0) {
    codeContexts[existingIndex] = context;
  } else {
    codeContexts.push(context);
  }

  // 渲染标签
  renderCodeContextTags();
}

// 移除代码上下文
function removeCodeContext(index) {
  console.log('[Webview] removeCodeContext() called:', index);

  // 从数组中移除
  codeContexts.splice(index, 1);

  // 重新渲染标签
  renderCodeContextTags();
}

// 渲染代码上下文标签
function renderCodeContextTags() {
  console.log('[Webview] renderCodeContextTags() called:', codeContexts.length);

  if (codeContexts.length === 0) {
    codeContextTags.innerHTML = '';
    codeContextTags.style.display = 'none';
    return;
  }

  codeContextTags.style.display = 'flex';
  codeContextTags.innerHTML = codeContexts.map((ctx, index) => {
    const lineInfo = ctx.selection ? `:${ctx.selection.start + 1}-${ctx.selection.end + 1}` : '';
    return `
      <div class="code-context-tag">
        <span class="code-context-tag-text">${ctx.fileName}${lineInfo}</span>
        <button class="code-context-tag-remove" data-index="${index}" title="移除">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    `;
  }).join('');

  // 绑定移除按钮事件
  codeContextTags.querySelectorAll('.code-context-tag-remove').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const index = parseInt(btn.dataset.index);
      removeCodeContext(index);
    });
  });
}

// ===== 采样参数设置相关函数 =====

// 加载采样参数
function loadSamplingParams() {
  console.log('[Webview] loadSamplingParams() called');

  // 从 localStorage 加载保存的参数
  const saved = localStorage.getItem('samplingParams');
  if (saved) {
    try {
      modelParams = JSON.parse(saved);
    } catch (e) {
      console.error('[Webview] Failed to parse saved sampling params:', e);
    }
  }

  // 更新UI
  updateParamUI('temperature', modelParams.temperature, modelParams.temperatureEnabled);
  updateParamUI('top-p', modelParams.topP, modelParams.topPEnabled);
  updateParamUI('frequency-penalty', modelParams.frequencyPenalty, modelParams.frequencyPenaltyEnabled);
  updateParamUI('presence-penalty', modelParams.presencePenalty, modelParams.presencePenaltyEnabled);
}

// 保存采样参数
function saveSamplingParams() {
  console.log('[Webview] saveSamplingParams() called');
  localStorage.setItem('samplingParams', JSON.stringify(modelParams));
}

// 更新参数UI
function updateParamUI(paramName, value, enabled) {
  const slider = document.getElementById(`${paramName}-slider`);
  const valueDisplay = document.getElementById(`${paramName}-value`);
  const enabledCheckbox = document.getElementById(`${paramName}-enabled`);

  if (slider) {
    slider.value = value;
    // 更新滑块进度条颜色
    updateSliderProgress(slider);
  }
  if (valueDisplay) {
    valueDisplay.textContent = value;
  }
  if (enabledCheckbox) {
    enabledCheckbox.checked = enabled;
  }
}

// 更新滑块进度条
function updateSliderProgress(slider) {
  const min = parseFloat(slider.min);
  const max = parseFloat(slider.max);
  const value = parseFloat(slider.value);
  const percentage = ((value - min) / (max - min)) * 100;
  slider.style.setProperty('--slider-progress', `${percentage}%`);
}

// Temperature 滑块事件
if (temperatureSlider) {
  temperatureSlider.addEventListener('input', (e) => {
    const value = parseFloat(e.target.value);
    modelParams.temperature = value;
    temperatureValue.textContent = value;
    updateSliderProgress(e.target);
  });
}

if (temperatureEnabled) {
  temperatureEnabled.addEventListener('change', (e) => {
    modelParams.temperatureEnabled = e.target.checked;
  });
}

// Top P 滑块事件
if (topPSlider) {
  topPSlider.addEventListener('input', (e) => {
    const value = parseFloat(e.target.value);
    modelParams.topP = value;
    topPValue.textContent = value;
    updateSliderProgress(e.target);
  });
}

if (topPEnabled) {
  topPEnabled.addEventListener('change', (e) => {
    modelParams.topPEnabled = e.target.checked;
  });
}

// Frequency Penalty 滑块事件
if (frequencyPenaltySlider) {
  frequencyPenaltySlider.addEventListener('input', (e) => {
    const value = parseFloat(e.target.value);
    modelParams.frequencyPenalty = value;
    frequencyPenaltyValue.textContent = value;
    updateSliderProgress(e.target);
  });
}

if (frequencyPenaltyEnabled) {
  frequencyPenaltyEnabled.addEventListener('change', (e) => {
    modelParams.frequencyPenaltyEnabled = e.target.checked;
  });
}

// Presence Penalty 滑块事件
if (presencePenaltySlider) {
  presencePenaltySlider.addEventListener('input', (e) => {
    const value = parseFloat(e.target.value);
    modelParams.presencePenalty = value;
    presencePenaltyValue.textContent = value;
    updateSliderProgress(e.target);
  });
}

if (presencePenaltyEnabled) {
  presencePenaltyEnabled.addEventListener('change', (e) => {
    modelParams.presencePenaltyEnabled = e.target.checked;
  });
}

// 预设按钮事件
if (presetAnswerBtn) {
  presetAnswerBtn.addEventListener('click', () => {
    console.log('[Webview] Preset answer clicked');
    applyPreset({
      temperature: 0.7,
      topP: 1,
      frequencyPenalty: 0,
      presencePenalty: 0
    });
    showNotification('已应用答案式预设');
  });
}

if (presetGuidedBtn) {
  presetGuidedBtn.addEventListener('click', () => {
    console.log('[Webview] Preset guided clicked');
    applyPreset({
      temperature: 0.9,
      topP: 0.95,
      frequencyPenalty: 0.1,
      presencePenalty: 0.1
    });
    showNotification('已应用引导式预设');
  });
}

if (presetResetBtn) {
  presetResetBtn.addEventListener('click', () => {
    console.log('[Webview] Preset reset clicked');
    applyPreset({
      temperature: 0.7,
      topP: 1,
      frequencyPenalty: 0,
      presencePenalty: 0
    });
    // 重置所有开关为开启状态
    modelParams.temperatureEnabled = true;
    modelParams.topPEnabled = true;
    modelParams.frequencyPenaltyEnabled = true;
    modelParams.presencePenaltyEnabled = true;

    updateParamUI('temperature', modelParams.temperature, modelParams.temperatureEnabled);
    updateParamUI('top-p', modelParams.topP, modelParams.topPEnabled);
    updateParamUI('frequency-penalty', modelParams.frequencyPenalty, modelParams.frequencyPenaltyEnabled);
    updateParamUI('presence-penalty', modelParams.presencePenalty, modelParams.presencePenaltyEnabled);

    showNotification('已恢复默认设置');
  });
}

// 应用预设参数
function applyPreset(preset) {
  modelParams.temperature = preset.temperature;
  modelParams.topP = preset.topP;
  modelParams.frequencyPenalty = preset.frequencyPenalty;
  modelParams.presencePenalty = preset.presencePenalty;

  updateParamUI('temperature', preset.temperature, modelParams.temperatureEnabled);
  updateParamUI('top-p', preset.topP, modelParams.topPEnabled);
  updateParamUI('frequency-penalty', preset.frequencyPenalty, modelParams.frequencyPenaltyEnabled);
  updateParamUI('presence-penalty', preset.presencePenalty, modelParams.presencePenaltyEnabled);
}

// ===== ASSEMBLY GUIDE 功能 =====

// 更新进度显示
async function updateProgress(sessionId) {
  if (!sessionId || currentMode !== 'assembly_guide') {
    document.getElementById('progress-container').style.display = 'none';
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/assembly/progress/${sessionId}`);
    const progressData = await response.json();

    const container = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const stepsContainer = document.getElementById('progress-steps');

    if (!progressData || progressData.total_steps === 0) {
      container.style.display = 'none';
      return;
    }

    container.style.display = 'block';
    const percentage = progressData.total_steps > 0
      ? (progressData.current_step / progressData.total_steps) * 100
      : 0;
    progressBar.style.width = percentage + '%';
    progressText.textContent = `步骤 ${progressData.current_step}/${progressData.total_steps}`;

    // 渲染步骤徽章
    stepsContainer.innerHTML = progressData.task_steps.map((step, idx) => {
      const status = idx < progressData.current_step ? 'completed' :
                    idx === progressData.current_step ? 'current' : '';
      return `<div class="step-badge ${status}">${idx + 1}. ${step}</div>`;
    }).join('');

    // 更新提示等级显示
    currentHintLevel = progressData.hint_level;
    manualHintMode = progressData.manual_mode;
    document.getElementById('manual-hint-toggle').checked = manualHintMode;
    document.getElementById('hint-level-slider').style.display = manualHintMode ? 'flex' : 'none';

    // 更新提示按钮状态
    document.querySelectorAll('.hint-btn').forEach(btn => {
      btn.classList.toggle('active', parseInt(btn.dataset.level) === currentHintLevel);
    });

  } catch (error) {
    console.error('获取进度失败:', error);
  }
}

// 更新进度页面视图
async function updateProgressView() {
  if (!currentSessionId || currentMode !== 'assembly_guide') {
    document.getElementById('progress-empty-view').style.display = 'flex';
    document.getElementById('progress-container-full').querySelector('.progress-section').style.display = 'none';
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/assembly/progress/${currentSessionId}`);
    const progressData = await response.json();

    const emptyView = document.getElementById('progress-empty-view');
    const progressSections = document.querySelectorAll('#progress-container-full .progress-section');
    const progressBarView = document.getElementById('progress-bar-view');
    const progressTextView = document.getElementById('progress-text-view');
    const stepsContainerView = document.getElementById('progress-steps-view');
    const currentHintLevelSpan = document.getElementById('current-hint-level');

    if (!progressData || progressData.total_steps === 0) {
      emptyView.style.display = 'flex';
      progressSections.forEach(section => section.style.display = 'none');
      return;
    }

    emptyView.style.display = 'none';
    progressSections.forEach(section => section.style.display = 'block');

    const percentage = progressData.total_steps > 0
      ? (progressData.current_step / progressData.total_steps) * 100
      : 0;
    progressBarView.style.width = percentage + '%';
    progressTextView.textContent = `步骤 ${progressData.current_step}/${progressData.total_steps}`;

    // 渲染步骤徽章
    stepsContainerView.innerHTML = progressData.task_steps.map((step, idx) => {
      const status = idx < progressData.current_step ? 'completed' :
                    idx === progressData.current_step ? 'current' : '';
      return `<div class="step-badge ${status}">${idx + 1}. ${step}</div>`;
    }).join('');

    // 更新提示等级显示
    currentHintLevel = progressData.hint_level;
    manualHintMode = progressData.manual_mode;
    currentHintLevelSpan.textContent = currentHintLevel;
    document.getElementById('manual-hint-toggle-view').checked = manualHintMode;
    document.getElementById('hint-level-slider-view').style.display = manualHintMode ? 'flex' : 'none';

    // 更新提示按钮状态
    document.querySelectorAll('#hint-level-slider-view .hint-btn').forEach(btn => {
      btn.classList.toggle('active', parseInt(btn.dataset.level) === currentHintLevel);
    });

  } catch (error) {
    console.error('获取进度失败:', error);
  }
}

// 手动提示模式切换（进度页面）
document.getElementById('manual-hint-toggle-view').addEventListener('change', async (e) => {
  manualHintMode = e.target.checked;
  document.getElementById('hint-level-slider-view').style.display = manualHintMode ? 'flex' : 'none';

  if (!currentSessionId) return;

  try {
    await fetch(`${API_BASE}/api/assembly/hint-level`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        session_id: currentSessionId,
        hint_level: currentHintLevel,
        manual_mode: manualHintMode
      })
    });
  } catch (error) {
    console.error('设置提示模式失败:', error);
  }
});

// 手动提示等级按钮（进度页面）
document.querySelectorAll('#hint-level-slider-view .hint-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    if (!manualHintMode || !currentSessionId) return;

    const level = parseInt(btn.dataset.level);
    currentHintLevel = level;

    document.querySelectorAll('#hint-level-slider-view .hint-btn').forEach(b => {
      b.classList.remove('active');
    });
    btn.classList.add('active');
    document.getElementById('current-hint-level').textContent = level;

    try {
      await fetch(`${API_BASE}/api/assembly/hint-level`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          session_id: currentSessionId,
          hint_level: level,
          manual_mode: true
        })
      });
    } catch (error) {
      console.error('设置提示等级失败:', error);
    }
  });
});

// 手动提示模式切换
document.getElementById('manual-hint-toggle').addEventListener('change', async (e) => {
  manualHintMode = e.target.checked;
  document.getElementById('hint-level-slider').style.display = manualHintMode ? 'flex' : 'none';

  if (!currentSessionId) return;

  try {
    await fetch(`${API_BASE}/api/assembly/hint-level`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        session_id: currentSessionId,
        manual_mode: manualHintMode,
        hint_level: currentHintLevel
      })
    });
    showNotification(manualHintMode ? '已启用手动调整模式' : '已关闭手动调整模式');
  } catch (error) {
    console.error('设置手动模式失败:', error);
    showNotification('设置失败', 'error');
  }
});

// 提示等级按钮点击
document.querySelectorAll('.hint-btn').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    if (!manualHintMode || !currentSessionId) return;

    currentHintLevel = parseInt(e.target.dataset.level);
    document.querySelectorAll('.hint-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');

    try {
      await fetch(`${API_BASE}/api/assembly/hint-level`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          session_id: currentSessionId,
          manual_mode: true,
          hint_level: currentHintLevel
        })
      });
      showNotification(`提示等级已设置为 ${currentHintLevel}`);
    } catch (error) {
      console.error('设置提示等级失败:', error);
      showNotification('设置失败', 'error');
    }
  });
});

// 导出学习报告
async function exportReport(sessionId, format = 'json') {
  try {
    const response = await fetch(`${API_BASE}/api/assembly/report/${sessionId}/export?format=${format}`);
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `learning_report_${sessionId}_${Date.now()}.${format}`;
    a.click();
    window.URL.revokeObjectURL(url);
    showNotification('报告已导出');
  } catch (error) {
    console.error('导出报告失败:', error);
    showNotification('导出失败', 'error');
  }
}

// 显示导出按钮
function showExportButton(sessionId) {
  // 在消息区域添加导出按钮
  const exportBtn = document.createElement('button');
  exportBtn.className = 'export-report-btn';
  exportBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
    </svg>
    导出学习报告
  `;
  exportBtn.onclick = () => exportReport(sessionId);

  // 添加到消息区域底部
  const messagesArea = document.getElementById('messages-area');
  const existingBtn = messagesArea.querySelector('.export-report-btn');
  if (existingBtn) {
    existingBtn.remove();
  }
  messagesArea.appendChild(exportBtn);
  exportBtn.style.display = 'inline-flex';
}

// 加载用户画像
async function loadUserProfile() {
  try {
    const [profileRes, errorBankRes] = await Promise.all([
      fetch(`${API_BASE}/api/assembly/profile`),
      fetch(`${API_BASE}/api/assembly/error-bank`)
    ]);

    const profile = await profileRes.json();
    const errorBankData = await errorBankRes.json();

    // 更新统计数据
    document.getElementById('total-sessions').textContent = profile.total_sessions || 0;
    document.getElementById('completed-tasks').textContent = profile.completed_tasks || 0;
    document.getElementById('total-errors').textContent = profile.total_errors || 0;
    document.getElementById('avg-hint-level').textContent = (profile.avg_hint_level || 1.0).toFixed(1);

    // 渲染擅长领域
    const strongAreasEl = document.getElementById('strong-areas');
    if (profile.strong_areas && profile.strong_areas.length > 0) {
      strongAreasEl.innerHTML = profile.strong_areas.map(area =>
        `<span class="area-tag">${area}</span>`
      ).join('');
    } else {
      strongAreasEl.innerHTML = '<span class="area-tag">暂无数据</span>';
    }

    // 渲染薄弱环节
    const weakAreasEl = document.getElementById('weak-areas');
    if (profile.weak_areas && profile.weak_areas.length > 0) {
      weakAreasEl.innerHTML = profile.weak_areas.map(area =>
        `<span class="area-tag weak">${area}</span>`
      ).join('');
    } else {
      weakAreasEl.innerHTML = '<span class="area-tag weak">暂无数据</span>';
    }

    // 渲染错题库
    const errorListEl = document.getElementById('error-bank-list');
    if (errorBankData.errors && errorBankData.errors.length > 0) {
      errorListEl.innerHTML = errorBankData.errors.map(error => `
        <div class="error-item">
          <div class="error-item-header">
            <span class="error-category">${error.category}</span>
            <span class="error-count">出现 ${error.count} 次</span>
          </div>
          <div class="error-description">${error.description || '无描述'}</div>
          <div class="error-knowledge">知识点: ${error.knowledge_point}</div>
        </div>
      `).join('');
    } else {
      errorListEl.innerHTML = '<div class="empty-message">暂无错误记录</div>';
    }

  } catch (error) {
    console.error('加载用户画像失败:', error);
    showNotification('加载失败', 'error');
  }
}

// 个人画像按钮点击
document.getElementById('btn-profile').addEventListener('click', async () => {
  switchView('profile');
  await loadUserProfile();
});

// 个人画像返回按钮
document.getElementById('profile-back-btn').addEventListener('click', () => {
  switchView('chat');
});

console.log('[Webview] Script initialization complete');
