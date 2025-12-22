from __future__ import annotations
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class CodeChunk:
    file_path: str
    symbol: str
    start_line: int
    end_line: int
    text: str


def _get_source_segment(lines: List[str], start: int, end: int) -> str:
    start = max(1, start)
    end = min(len(lines), end)
    return "".join(lines[start - 1:end])


def chunk_python_file(path: Path, text: str) -> List[CodeChunk]:
    """
    将 Python 文件按「类 / 函数」切块，用于 embedding。
    特别针对【中文注释】做语义提权：
    - 前 20 行（通常是注释 / docstring）权重更高
    """
    lines = text.splitlines(keepends=True)

    try:
        tree = ast.parse(text)
    except SyntaxError:
        # 语法错误兜底：整个文件一个 chunk
        return [
            CodeChunk(
                file_path=str(path),
                symbol="__file__",
                start_line=1,
                end_line=len(lines),
                text=text,
            )
        ]

    chunks: List[CodeChunk] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.class_stack: List[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.class_stack.append(node.name)

            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)

            symbol = ".".join(self.class_stack)

            # ⭐ 中文注释提权
            chunk_text = (
                "# 中文注释与说明（高权重）\n"
                + _get_source_segment(lines, start, min(end, start + 20))
                + "\n\n# 完整实现\n"
                + _get_source_segment(lines, start, end)
            )

            chunks.append(
                CodeChunk(
                    file_path=str(path),
                    symbol=symbol,
                    start_line=start,
                    end_line=end,
                    text=chunk_text,
                )
            )

            self.generic_visit(node)
            self.class_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)

            base = node.name
            symbol = ".".join(self.class_stack + [base]) if self.class_stack else base

            chunk_text = (
                "# 中文注释与说明（高权重）\n"
                + _get_source_segment(lines, start, min(end, start + 20))
                + "\n\n# 完整实现\n"
                + _get_source_segment(lines, start, end)
            )

            chunks.append(
                CodeChunk(
                    file_path=str(path),
                    symbol=symbol,
                    start_line=start,
                    end_line=end,
                    text=chunk_text,
                )
            )

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)

            base = node.name
            symbol = ".".join(self.class_stack + [base]) if self.class_stack else base

            chunk_text = (
                "# 中文注释与说明（高权重）\n"
                + _get_source_segment(lines, start, min(end, start + 20))
                + "\n\n# 完整实现\n"
                + _get_source_segment(lines, start, end)
            )

            chunks.append(
                CodeChunk(
                    file_path=str(path),
                    symbol=symbol,
                    start_line=start,
                    end_line=end,
                    text=chunk_text,
                )
            )

    Visitor().visit(tree)

    # 极端情况兜底
    if not chunks:
        chunks.append(
            CodeChunk(
                file_path=str(path),
                symbol="__file__",
                start_line=1,
                end_line=len(lines),
                text=text,
            )
        )

    return chunks
