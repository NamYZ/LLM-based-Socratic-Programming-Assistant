"""
Agent 工具提示词
描述每个工具的作用和使用场景
"""

TOOL_DESCRIPTIONS = """
【可用工具】

1. get_student_progress(session_id: int) -> dict
   获取学生的学习进度和理解程度
   返回：已回答的问题、当前提示强度等
   使用场景：了解学生的学习状态，决定提示强度

2. update_student_progress(session_id: int, topic: str, question: str, answered: bool, hint_level: int)
   更新学生的学习进度
   使用场景：记录学生回答了某个问题，或需要提高提示强度

3. analyze_code(code: str) -> dict
   静态分析汇编代码，识别潜在问题
   返回：语法错误、逻辑警告、建议等
   使用场景：快速识别明显的代码问题

4. execute_code(code: str, session_id: int) -> str
   执行 8086 汇编代码，记录 trace 到数据库
   返回：execution_id（用于后续查询 trace）
   使用场景：需要观察代码实际执行过程时

5. get_execution_trace(execution_id: str) -> list
   获取代码执行的详细 trace 信息
   返回：每一步的指令、寄存器变化、标志位变化等
   使用场景：分析代码执行过程，发现问题

6. explain_step(step_data: dict) -> str
   解析单步执行信息，生成结构化解释
   返回：该步骤的详细解释（指令含义、影响等）
   使用场景：帮助理解某一步执行的细节

7. generate_hint(context: dict, hint_level: int) -> str
   根据上下文和提示强度生成引导性问题
   参数：
     - context: 包含代码、问题、学生状态等
     - hint_level: 0-3，0最弱，3最强
   返回：引导性问题（不包含代码）
   使用场景：生成合适强度的提示问题

【工具使用原则】
- 优先使用 Student Tree 了解学生状态
- 需要分析执行过程时才使用 Code Executor
- 根据学生的理解程度调整 hint_level
- 始终通过 Hint Generator 生成最终问题
"""
