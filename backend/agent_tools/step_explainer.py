"""
Step Explainer - 执行步骤解释工具
从 trace 数据中解析执行过程，生成结构化解释
"""
import json
from typing import Dict, List


class StepExplainer:
    """解析和解释单步执行信息"""

    # 指令说明
    INSTRUCTION_DESCRIPTIONS = {
        "mov": "数据传送指令，将源操作数的值复制到目标操作数",
        "add": "加法指令，将两个操作数相加，结果存入目标操作数",
        "sub": "减法指令，从目标操作数中减去源操作数",
        "mul": "无符号乘法指令，将 AL/AX 与操作数相乘",
        "div": "无符号除法指令，将 AX/DX:AX 除以操作数",
        "inc": "自增指令，将操作数加 1",
        "dec": "自减指令，将操作数减 1",
        "and": "按位与指令，对两个操作数进行按位与运算",
        "or": "按位或指令，对两个操作数进行按位或运算",
        "xor": "按位异或指令，对两个操作数进行按位异或运算",
        "not": "按位取反指令，对操作数进行按位取反",
        "cmp": "比较指令，通过减法比较两个操作数，但不保存结果",
        "jmp": "无条件跳转指令，跳转到指定地址",
        "je": "相等则跳转，当 ZF=1 时跳转",
        "jne": "不相等则跳转，当 ZF=0 时跳转",
        "jz": "为零则跳转，当 ZF=1 时跳转",
        "jnz": "不为零则跳转，当 ZF=0 时跳转",
        "jg": "大于则跳转（有符号），当 ZF=0 且 SF=OF 时跳转",
        "jl": "小于则跳转（有符号），当 SF≠OF 时跳转",
        "ja": "大于则跳转（无符号），当 CF=0 且 ZF=0 时跳转",
        "jb": "小于则跳转（无符号），当 CF=1 时跳转",
        "call": "调用子程序，将返回地址压栈并跳转",
        "ret": "从子程序返回，从栈中弹出返回地址并跳转",
        "push": "压栈指令，将操作数压入栈",
        "pop": "出栈指令，从栈中弹出数据到操作数",
        "loop": "循环指令，CX 减 1，若 CX≠0 则跳转",
    }

    # 标志位说明
    FLAG_DESCRIPTIONS = {
        "CF": "进位标志 (Carry Flag)",
        "PF": "奇偶标志 (Parity Flag)",
        "AF": "辅助进位标志 (Auxiliary Carry Flag)",
        "ZF": "零标志 (Zero Flag)",
        "SF": "符号标志 (Sign Flag)",
        "OF": "溢出标志 (Overflow Flag)",
    }

    @staticmethod
    def explain_step(step_data: Dict) -> str:
        """
        解释单步执行信息

        参数：
            step_data: 单步 trace 数据
                {
                    "step": 1,
                    "instruction": "MOV AX, 5",
                    "address": "0000:0100",
                    "register_diff": {"AX": {"before": 0, "after": 5}},
                    "flags_diff": {...},
                    "memory_write": {...},
                    "jump_info": {...}
                }

        返回：
            结构化的解释字符串
        """
        parts = []

        # 步骤编号和地址
        step_num = step_data.get("step", 0)
        address = step_data.get("address", "")
        instruction = step_data.get("instruction", "")

        parts.append(f"【步骤 {step_num}】地址: {address}")
        parts.append(f"指令: {instruction}")

        # 指令说明
        opcode = instruction.split()[0].lower() if instruction else ""
        if opcode in StepExplainer.INSTRUCTION_DESCRIPTIONS:
            parts.append(f"说明: {StepExplainer.INSTRUCTION_DESCRIPTIONS[opcode]}")

        # 寄存器变化
        register_diff = step_data.get("register_diff", {})
        if register_diff:
            parts.append("\n寄存器变化:")
            for reg, change in register_diff.items():
                before = change.get("before", 0)
                after = change.get("after", 0)
                parts.append(f"  {reg}: {before} → {after}")

        # 标志位变化
        flags_diff = step_data.get("flags_diff", {})
        if flags_diff:
            parts.append("\n标志位变化:")
            for flag, change in flags_diff.items():
                before = change.get("before", 0)
                after = change.get("after", 0)
                flag_desc = StepExplainer.FLAG_DESCRIPTIONS.get(flag, flag)
                parts.append(f"  {flag_desc}: {before} → {after}")

        # 内存写入
        memory_write = step_data.get("memory_write")
        if memory_write:
            addr = memory_write.get("address", "")
            value = memory_write.get("value", 0)
            parts.append(f"\n内存写入: [{addr}] = {value}")

        # 跳转信息
        jump_info = step_data.get("jump_info")
        if jump_info:
            jumped = jump_info.get("jumped", False)
            target = jump_info.get("target", "")
            if jumped:
                parts.append(f"\n跳转: 已跳转到 {target}")
            else:
                parts.append(f"\n跳转: 未跳转（条件不满足）")

        return "\n".join(parts)

    @staticmethod
    def explain_trace(trace_data: List[Dict]) -> str:
        """
        解释完整的 trace

        参数：
            trace_data: trace 数据列表

        返回：
            完整的执行过程解释
        """
        if not trace_data:
            return "没有执行数据"

        parts = ["【执行过程分析】\n"]

        for step in trace_data:
            parts.append(StepExplainer.explain_step(step))
            parts.append("\n" + "-" * 50 + "\n")

        # 总结
        parts.append(f"\n总共执行了 {len(trace_data)} 条指令")

        return "\n".join(parts)

    @staticmethod
    def get_key_changes(trace_data: List[Dict]) -> Dict:
        """
        提取关键变化信息

        参数：
            trace_data: trace 数据列表

        返回：
            {
                "register_changes": {...},  # 所有寄存器的最终变化
                "flag_changes": {...},      # 所有标志位的最终变化
                "jump_count": 0,            # 跳转次数
                "memory_writes": [...]      # 内存写入列表
            }
        """
        register_changes = {}
        flag_changes = {}
        jump_count = 0
        memory_writes = []

        for step in trace_data:
            # 累积寄存器变化
            for reg, change in step.get("register_diff", {}).items():
                if reg not in register_changes:
                    register_changes[reg] = {"initial": change.get("before", 0)}
                register_changes[reg]["final"] = change.get("after", 0)

            # 累积标志位变化
            for flag, change in step.get("flags_diff", {}).items():
                if flag not in flag_changes:
                    flag_changes[flag] = {"initial": change.get("before", 0)}
                flag_changes[flag]["final"] = change.get("after", 0)

            # 统计跳转
            jump_info = step.get("jump_info")
            if jump_info and jump_info.get("jumped"):
                jump_count += 1

            # 收集内存写入
            memory_write = step.get("memory_write")
            if memory_write:
                memory_writes.append(memory_write)

        return {
            "register_changes": register_changes,
            "flag_changes": flag_changes,
            "jump_count": jump_count,
            "memory_writes": memory_writes
        }


# 工具函数，供 LangChain Agent 调用
def explain_step(step_data: dict) -> str:
    """解释单步执行（供 Agent 调用）"""
    return StepExplainer.explain_step(step_data)


def explain_trace(trace_data: list) -> str:
    """解释完整 trace（供 Agent 调用）"""
    return StepExplainer.explain_trace(trace_data)
