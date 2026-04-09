"""
Code Analyzer - 8086 汇编代码静态分析工具
对代码进行轻量级静态分析，识别潜在问题
"""
import re
from typing import Dict, List


class CodeAnalyzer:
    """8086 汇编代码静态分析器"""

    # 8086 常用寄存器
    REGISTERS_8BIT = ['al', 'ah', 'bl', 'bh', 'cl', 'ch', 'dl', 'dh']
    REGISTERS_16BIT = ['ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp']
    SEGMENT_REGISTERS = ['cs', 'ds', 'es', 'ss']

    # 常用指令
    DATA_TRANSFER = ['mov', 'push', 'pop', 'xchg', 'lea', 'lds', 'les']
    ARITHMETIC = ['add', 'sub', 'mul', 'div', 'inc', 'dec', 'neg', 'cmp']
    LOGICAL = ['and', 'or', 'xor', 'not', 'test', 'shl', 'shr', 'sal', 'sar', 'rol', 'ror']
    CONTROL = ['jmp', 'je', 'jne', 'jz', 'jnz', 'jg', 'jl', 'jge', 'jle', 'ja', 'jb', 'jae', 'jbe', 'call', 'ret', 'loop']
    STRING = ['movs', 'movsb', 'movsw', 'cmps', 'scas', 'lods', 'stos']

    @staticmethod
    def analyze(code: str) -> Dict:
        """
        分析汇编代码，返回潜在问题

        参数：
            code: 汇编代码字符串

        返回：
            {
                "errors": [...],      # 语法错误
                "warnings": [...],    # 警告
                "suggestions": [...], # 建议
                "stats": {...}        # 统计信息
            }
        """
        errors = []
        warnings = []
        suggestions = []

        # 预处理：移除注释，按行分割
        lines = CodeAnalyzer._preprocess(code)

        # 统计信息
        stats = {
            "total_lines": len(lines),
            "instruction_count": 0,
            "label_count": 0,
            "used_registers": set()
        }

        # 逐行分析
        for line_num, line in enumerate(lines, 1):
            if not line.strip():
                continue

            # 检查是否是标签
            if CodeAnalyzer._is_label(line):
                stats["label_count"] += 1
                continue

            # 解析指令
            instruction = CodeAnalyzer._parse_instruction(line)
            if not instruction:
                continue

            stats["instruction_count"] += 1

            # 检查指令合法性
            opcode = instruction["opcode"].lower()
            operands = instruction["operands"]

            # 收集使用的寄存器
            for operand in operands:
                reg = CodeAnalyzer._extract_register(operand)
                if reg:
                    stats["used_registers"].add(reg)

            # 检查常见错误
            CodeAnalyzer._check_operand_mismatch(opcode, operands, line_num, errors)
            CodeAnalyzer._check_segment_usage(operands, line_num, warnings)
            CodeAnalyzer._check_division(opcode, line_num, warnings)

        # 转换 set 为 list
        stats["used_registers"] = list(stats["used_registers"])

        # 生成建议
        if stats["instruction_count"] == 0:
            suggestions.append("代码中没有找到有效的指令")

        return {
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "stats": stats
        }

    @staticmethod
    def _preprocess(code: str) -> List[str]:
        """预处理代码：移除注释，分割行"""
        lines = []
        for line in code.split('\n'):
            # 移除注释（; 开头）
            if ';' in line:
                line = line[:line.index(';')]
            line = line.strip()
            if line:
                lines.append(line)
        return lines

    @staticmethod
    def _is_label(line: str) -> bool:
        """判断是否是标签"""
        return ':' in line and not line.startswith('[')

    @staticmethod
    def _parse_instruction(line: str) -> Dict:
        """解析指令"""
        parts = re.split(r'\s+', line, maxsplit=1)
        if not parts:
            return None

        opcode = parts[0].lower()
        operands = []

        if len(parts) > 1:
            # 分割操作数（逗号分隔）
            operands = [op.strip() for op in parts[1].split(',')]

        return {
            "opcode": opcode,
            "operands": operands
        }

    @staticmethod
    def _extract_register(operand: str) -> str:
        """从操作数中提取寄存器"""
        operand = operand.lower()
        all_regs = (CodeAnalyzer.REGISTERS_8BIT +
                    CodeAnalyzer.REGISTERS_16BIT +
                    CodeAnalyzer.SEGMENT_REGISTERS)

        for reg in all_regs:
            if reg in operand:
                return reg
        return None

    @staticmethod
    def _check_operand_mismatch(opcode: str, operands: List[str], line_num: int, errors: List):
        """检查操作数不匹配"""
        if opcode == 'mov' and len(operands) == 2:
            # 检查 mov 指令的操作数大小是否匹配
            src = operands[1].lower()
            dst = operands[0].lower()

            # 简单检查：8位和16位寄存器不能混用
            src_reg = CodeAnalyzer._extract_register(src)
            dst_reg = CodeAnalyzer._extract_register(dst)

            if src_reg and dst_reg:
                src_is_8bit = src_reg in CodeAnalyzer.REGISTERS_8BIT
                dst_is_8bit = dst_reg in CodeAnalyzer.REGISTERS_8BIT

                if src_is_8bit != dst_is_8bit:
                    errors.append(f"第 {line_num} 行: 操作数大小不匹配（8位和16位寄存器不能混用）")

    @staticmethod
    def _check_segment_usage(operands: List[str], line_num: int, warnings: List):
        """检查段寄存器使用"""
        for operand in operands:
            for seg_reg in CodeAnalyzer.SEGMENT_REGISTERS:
                if seg_reg in operand.lower():
                    warnings.append(f"第 {line_num} 行: 使用了段寄存器 {seg_reg.upper()}，请确保理解其作用")

    @staticmethod
    def _check_division(opcode: str, line_num: int, warnings: List):
        """检查除法指令"""
        if opcode in ['div', 'idiv']:
            warnings.append(f"第 {line_num} 行: 除法指令需要注意除数不能为0，且结果可能溢出")


# 工具函数，供 LangChain Agent 调用
def analyze_code(code: str) -> dict:
    """分析汇编代码（供 Agent 调用）"""
    return CodeAnalyzer.analyze(code)
