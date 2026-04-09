# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Coding Tool is a VS Code extension for teaching 8086 assembly language programming using Socratic teaching methods. It features a TypeScript frontend (VS Code extension) and a Python backend (FastAPI + LangChain) with DOSBox integration for assembly code execution and tracing.

## Development Commands

### Frontend (TypeScript/VS Code Extension)

```bash
# Install dependencies
npm install

# Compile TypeScript (one-time)
npm run compile

# Watch mode (auto-recompile on changes)
npm run watch

# Lint code
npm run lint

# Debug extension
# Press F5 in VS Code to launch Extension Development Host
```

### Backend (Python/FastAPI)

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Start backend server (port 5500)
./start-backend.sh

# Or manually
cd backend
python3 app_fastapi.py

# Backend will be available at http://localhost:5500
```

### DOSBox (Optional - for assembly execution)

```bash
# Build modified DOSBox with trace support
./build_dosbox.sh

# Test DOSBox
./test_dosbox.sh
```

## Architecture

### Frontend Structure

- **Entry point**: `src/extension.ts` - Registers commands and webview provider
- **Main controller**: `src/providers/ChatViewProvider.ts` - Manages chat UI and backend communication
- **Message handling**: `src/providers/MessageHandler.ts` - Processes messages between webview and backend
- **Webview UI**: `src/webview/` - HTML/CSS/JS for chat interface
- **Database**: `src/providers/ConfigDatabaseManager.ts` - Local SQLite for settings (sql.js)

**Key commands registered:**
- `aiCodingTool.newChat` - Start new conversation
- `aiCodingTool.openSettings` - Configure API keys and models
- `aiCodingTool.addToContext` - Add selected code to chat context
- `aiCodingTool.togglePanel` - Show/hide AI panel (Ctrl+I)
- `aiCodingTool.quickInput` - Quick input from editor (Cmd+Y)

### Backend Structure

- **Entry point**: `backend/app_fastapi.py` - FastAPI app running on port 5500
- **Database**: SQLite at `~/vscode_chat.db` (initialized by `backend/database.py`)
- **Routers**:
  - `routers/config_router.py` - API key and model configuration
  - `routers/session_router.py` - Chat session management
  - `routers/chat_router.py` - Main chat endpoint with streaming responses

**Three interaction modes:**

1. **Answer Mode** (`ask_prompts/ANSWER_SYSTEM_PROMPT`): Direct answers with code examples
2. **Guided Mode** (`ask_prompts/GUIDED_SYSTEM_PROMPT`): Socratic questioning to guide learning
3. **Agent Mode** (in development): ReAct-based autonomous agent with tools

### Agent System (ReAct Architecture)

Located in `backend/agent_core.py` and supporting modules:

**Core components:**
- `agent_core.py` - Main agent class using LangChain's ReAct framework
- `agent_prompts/` - Prompt templates for system, modes, tasks, and tools
- `agent_tools/` - Five specialized tools for teaching assembly

**Five agent tools:**
1. `student_tree.py` - Track student learning progress
2. `code_analyzer.py` - Static analysis of assembly code
3. `code_executor.py` - Execute code in DOSBox with trace recording
4. `step_explainer.py` - Explain execution steps from trace data
5. `hint_generator.py` - Generate Socratic hints at different difficulty levels

**Agent workflow:**
1. Receive user question + code context
2. Get student progress from student_tree
3. ReAct loop: Reason → Act (call tools) → Observe → Repeat
4. Generate Socratic response (questions, not direct answers)
5. Update student progress
6. Stream response to frontend

### DOSBox Integration

The `dosbox-code-0-r4494-dosbox-trunk/` directory contains modified DOSBox source code that outputs JSON trace data during assembly program execution. This enables the agent to:
- Record register states before/after each instruction
- Track flag changes and memory writes
- Provide step-by-step execution explanations

## Important Implementation Details

### Backend Port Configuration

The backend runs on **port 5500**, not 8000. This is hardcoded in:
- `backend/app_fastapi.py` (line 43)
- Frontend likely expects this port for API calls

### Database Locations

- **Backend database**: `~/vscode_chat.db` (chat history, sessions, traces)
- **Frontend database**: Managed by sql.js in-memory (API keys, settings)

### Prompt System Organization

Two separate prompt systems exist:
1. **Basic modes** (`backend/ask_prompts/`): For answer and guided modes
2. **Agent mode** (`backend/agent_prompts/`): For ReAct agent with tool descriptions

When modifying prompts, ensure you're editing the correct system.

### Message Flow

1. User types in webview → `webview.js` sends message
2. `ChatViewProvider.ts` receives via `postMessage`
3. `MessageHandler.ts` processes and calls backend API
4. Backend streams response chunks
5. Frontend displays incrementally in chat UI

### Code Context Handling

When users select code and use "Add to Context":
1. `extension.ts` captures selection with file path and language
2. Creates `CodeContext` object with metadata
3. Passes to `ChatViewProvider.addCodeToContext()`
4. Included in next message to backend as context

## Common Development Tasks

### Adding a New Command

1. Define command in `package.json` under `contributes.commands`
2. Register handler in `src/extension.ts` using `vscode.commands.registerCommand`
3. Add to `context.subscriptions` for proper cleanup

### Adding a New Agent Tool

1. Create tool file in `backend/agent_tools/`
2. Define function with clear docstring (used by LLM)
3. Import and register in `agent_core.py` tools list
4. Add description to `agent_prompts/tool_prompt.py`

### Modifying Chat Behavior

- **Answer/Guided modes**: Edit `backend/ask_prompts/__init__.py`
- **Agent mode**: Edit `backend/agent_prompts/system_prompt.py`
- **Streaming logic**: Modify `backend/routers/chat_router.py`

### Testing the Extension

1. Run `npm run watch` in terminal 1
2. Run `./start-backend.sh` in terminal 2
3. Press F5 in VS Code to launch Extension Development Host
4. Open AI Coding Tool panel in new window
5. Test chat functionality

## Code Style Notes

- Frontend uses Chinese comments in some files (e.g., `extension.ts`)
- Backend uses Chinese docstrings and comments
- Agent system emphasizes Socratic teaching: never give direct answers or complete code
- Tool call limit: Maximum 5 tool calls per agent iteration (middleware in `agent_core.py`)

## Dependencies

### Frontend
- TypeScript 5.x
- VS Code Extension API 1.85.0+
- sql.js for local storage

### Backend
- Python 3.8+
- FastAPI + Uvicorn
- LangChain + LangChain-OpenAI
- Pydantic for data validation

### System (for DOSBox)
- SDL libraries (sdl, sdl2_net, sdl2_sound)
- automake, autoconf, gcc
- Install via: `brew install sdl sdl2_net sdl2_sound automake autoconf gcc`
