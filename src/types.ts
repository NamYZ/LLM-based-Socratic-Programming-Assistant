// 给前端代码做 “说明书 / 规范”，规定前后端通信的数据格式（API相应类型定义）

// 规定前端接收 “AI 配置” 时的格式
export interface ApiSettings {
  api_key?: string;
  model_name?: string;
  provider?: string;
  base_url?: string;
  configured: boolean;
}

// 规定前端接收 “会话列表” 时的格式
export interface Message {
  role: 'user' | 'assistant';
  content: string;
  time?: string;
}

// 规定前端接收 “会话列表项” 时的格式
export interface Session {
  id: number;
  title: string;
  mode: 'answer' | 'guided' | 'agent';
  created_at: string;
  updated_at: string;
  msg_count: number;
}

// 规定前端接收 “会话详情（消息 + 标题）” 时的格式
export interface SessionDetail {
  messages: Message[];
  session: {
    id: number;
    title: string;
    mode: string;
    created_at: string;
  };
}

// 规定前端接收 “AI 模型配置（多配置用）” 时的格式
export interface ModelConfig {
  id: number;
  name: string;
  provider: string;
  base_url: string;
  api_key: string;
  model_name: string;
  is_active: boolean;
  created_at: string;
}

// 规定前端发送 “消息” 给后端时的格式
export interface WebviewMessage {
  type: 'saveSettings' | 'loadSettings' | 'sendMessage' | 'loadSessions' |
        'loadSessionMessages' | 'deleteSession' | 'clearAll' | 'newChat' |
        'addCodeContext' | 'pickFileReference' | 'loadConfigs' |
        'loadConfigsList' | 'activateConfig' | 'addConfig' | 'deleteConfig' |
        'loadConfigDetail' | 'updateConfig' | 'exportSessionMarkdown';
  data?: any;
}

// 代码上下文信息
export interface CodeContext {
  fileName: string;
  filePath: string;
  language: string;
  content: string;
  selection?: {
    start: number;
    end: number;
  };
}
