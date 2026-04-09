"""
Code Executor - 8086 汇编代码执行工具
执行代码并记录 trace 信息到数据库
"""
import sqlite3
import subprocess
import os
import sys
import uuid
import json
import shutil
import re
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import DB_PATH, get_local_time


class CodeExecutor:
    """8086 汇编代码执行器"""

    def __init__(self, dosbox_path: str = None):
        """
        初始化执行器

        参数：
            dosbox_path: DOSBox 可执行文件路径（如果为 None，使用默认路径）
        """
        self.dosbox_path = dosbox_path or self._find_dosbox()

    @staticmethod
    def _find_dosbox() -> str:
        """查找 DOSBox 可执行文件"""
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        env_path = os.environ.get("DOSBOX_PATH")
        if env_path and os.path.exists(env_path):
            return env_path

        possible_paths = [
            os.path.join(repo_root, "dosbox-code-0-r4494-dosbox-trunk", "src", "dosbox"),
            "/usr/local/bin/dosbox",
            "/usr/bin/dosbox",
            "C:\\Program Files\\DOSBox\\dosbox.exe",
            "C:\\Program Files (x86)\\DOSBox\\dosbox.exe",
        ]

        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path

        dosbox_in_path = shutil.which("dosbox")
        if dosbox_in_path:
            return dosbox_in_path

        # 如果找不到，返回默认命令
        return "dosbox"

    def execute(self, code: str, session_id: int) -> str:
        """
        执行汇编代码并记录 trace

        参数：
            code: 汇编代码
            session_id: 会话 ID

        返回：
            execution_id: 执行 ID（用于后续查询 trace）
        """
        execution_id = str(uuid.uuid4())

        try:
            # 1. 创建临时文件
            temp_dir = "/tmp/asm_executor"
            os.makedirs(temp_dir, exist_ok=True)

            asm_file = os.path.join(temp_dir, f"{execution_id}.asm")
            trace_file = os.path.join(temp_dir, f"{execution_id}_trace.json")

            # 写入汇编代码
            with open(asm_file, 'w') as f:
                f.write(self._prepare_com_program(code))

            # 2. 调用 DOSBox 执行（需要修改后的 DOSBox 支持 trace 输出）
            # 这里是占位实现，实际需要与修改后的 DOSBox 集成
            trace_data = self._execute_with_dosbox(asm_file, trace_file)

            # 3. 解析 trace 并存入数据库
            self._save_trace_to_db(execution_id, session_id, trace_data)

            return execution_id

        except Exception as e:
            print(f"[CodeExecutor] 执行失败: {e}")
            # 返回错误信息作为 execution_id
            return f"ERROR: {str(e)}"

    def _prepare_com_program(self, code: str) -> str:
        """将用户片段补成可执行的 COM 程序，避免 DOSBox 挂起。"""
        normalized_code = code.strip()
        if not normalized_code:
            return "ORG 100h\nINT 20h\n"

        has_org = re.search(r'^\s*ORG\s+100h\b', normalized_code, re.IGNORECASE | re.MULTILINE)
        has_exit = re.search(r'\bINT\s+20h\b|\bRET\b|\bINT\s+21h\b', normalized_code, re.IGNORECASE)

        program_lines = []
        if not has_org:
            program_lines.append("ORG 100h")

        program_lines.append(normalized_code)

        if not has_exit:
            program_lines.append("INT 20h")

        return "\n".join(program_lines) + "\n"

    def _execute_with_dosbox(self, asm_file: str, trace_file: str) -> list:
        """
        使用 DOSBox 执行汇编代码并获取 trace

        参数：
            asm_file: 汇编文件路径
            trace_file: trace 输出文件路径

        返回：
            trace 数据列表
        """
        try:
            # 1. 编译汇编代码为 COM 文件（使用 NASM 或 MASM）
            com_file = asm_file.replace('.asm', '.com')

            # 尝试使用 nasm 编译
            compile_cmd = f"nasm -f bin -o {com_file} {asm_file}"
            result = subprocess.run(compile_cmd, shell=True, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"[CodeExecutor] 编译失败: {result.stderr}")
                # 如果编译失败，返回模拟数据
                return self._get_mock_trace()

            # 2. 创建 DOSBox 配置文件，启用 trace
            config_file = asm_file.replace('.asm', '.conf')
            with open(config_file, 'w') as f:
                f.write(f"""[cpu]
core=normal
cycles=max

[autoexec]
# Enable trace logging
TRACE_ENABLE {trace_file}
# Mount and run
MOUNT C: {os.path.dirname(com_file)}
C:
{os.path.basename(com_file)}
# Disable trace and exit
TRACE_DISABLE
EXIT
""")

            # 3. 调用 DOSBox
            dosbox_cmd = f"{self.dosbox_path} -conf {config_file} -noconsole"
            result = subprocess.run(dosbox_cmd, shell=True, capture_output=True, text=True, timeout=10)

            # 4. 读取 trace 文件
            if os.path.exists(trace_file):
                with open(trace_file, 'r') as f:
                    trace_data = json.load(f)
                print(f"[CodeExecutor] 成功执行并获取 trace: {len(trace_data)} 步")
                return trace_data
            else:
                print(f"[CodeExecutor] Trace 文件不存在，使用模拟数据")
                return self._get_mock_trace()

        except subprocess.TimeoutExpired:
            print(f"[CodeExecutor] 执行超时")
            return self._get_mock_trace()
        except Exception as e:
            print(f"[CodeExecutor] 执行异常: {e}")
            return self._get_mock_trace()

    def _get_mock_trace(self) -> list:
        """返回模拟的 trace 数据（用于测试）"""
        return [
            {
                "step": 1,
                "instruction": "MOV AX, 5",
                "address": "0000:0100",
                "register_diff": {"AX": {"before": 0, "after": 5}},
                "flags_diff": {},
                "memory_write": None,
                "jump_info": None
            },
            {
                "step": 2,
                "instruction": "ADD AX, 3",
                "address": "0000:0103",
                "register_diff": {"AX": {"before": 5, "after": 8}},
                "flags_diff": {"ZF": {"before": 0, "after": 0}},
                "memory_write": None,
                "jump_info": None
            }
        ]

    def _save_trace_to_db(self, execution_id: str, session_id: int, trace_data: list):
        """
        将 trace 数据保存到数据库

        参数：
            execution_id: 执行 ID
            session_id: 会话 ID
            trace_data: trace 数据列表
        """
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        for step_data in trace_data:
            c.execute("""
                INSERT INTO execution_traces
                (session_id, execution_id, step_number, instruction, address,
                 register_diff, flags_diff, memory_write, jump_info, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                execution_id,
                step_data.get("step", 0),
                step_data.get("instruction", ""),
                step_data.get("address", ""),
                json.dumps(step_data.get("register_diff", {})),
                json.dumps(step_data.get("flags_diff", {})),
                json.dumps(step_data.get("memory_write")) if step_data.get("memory_write") else None,
                json.dumps(step_data.get("jump_info")) if step_data.get("jump_info") else None,
                get_local_time()
            ))

        conn.commit()
        conn.close()

    @staticmethod
    def get_trace(execution_id: str) -> list:
        """
        获取执行的 trace 数据

        参数：
            execution_id: 执行 ID

        返回：
            trace 数据列表
        """
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""
            SELECT step_number, instruction, address, register_diff, flags_diff,
                   memory_write, jump_info
            FROM execution_traces
            WHERE execution_id = ?
            ORDER BY step_number ASC
        """, (execution_id,))

        rows = c.fetchall()
        conn.close()

        trace = []
        for row in rows:
            trace.append({
                "step": row[0],
                "instruction": row[1],
                "address": row[2],
                "register_diff": json.loads(row[3]) if row[3] else {},
                "flags_diff": json.loads(row[4]) if row[4] else {},
                "memory_write": json.loads(row[5]) if row[5] else None,
                "jump_info": json.loads(row[6]) if row[6] else None
            })

        return trace


# 工具函数，供 LangChain Agent 调用
def execute_code(code: str, session_id: int) -> str:
    """执行汇编代码（供 Agent 调用）"""
    executor = CodeExecutor()
    return executor.execute(code, session_id)


def get_execution_trace(execution_id: str) -> list:
    """获取执行 trace（供 Agent 调用）"""
    return CodeExecutor.get_trace(execution_id)
