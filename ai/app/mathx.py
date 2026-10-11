"""Safe arithmetic evaluator for the calculator tool (no eval())."""
from __future__ import annotations

import ast
import math
import operator

from .errors import ToolError

MAX_EXPR_LEN = 200

_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _pow(a, b):
    if abs(b) > 10_000 or (abs(a) > 1e6 and abs(b) > 100):
        raise ToolError("Exponent too large.")
    return operator.pow(a, b)


def _factorial(n):
    if not float(n).is_integer() or n < 0 or n > 170:
        raise ToolError("factorial() needs an integer between 0 and 170.")
    return math.factorial(int(n))


_BIN = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: _pow,
}
_UN = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "ln": math.log,
    "log": math.log,  # log(x) natural, log(x, base) any base
    "log10": math.log10,
    "log2": math.log2,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "floor": math.floor,
    "ceil": math.ceil,
    "factorial": _factorial,
}


def _eval(node: ast.AST):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ToolError("Only numbers are allowed.")
        return node.value
    if isinstance(node, ast.Name):
        if node.id in _CONSTS:
            return _CONSTS[node.id]
        raise ToolError(f"Unknown name '{node.id}'.")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        return _BIN[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UN:
        return _UN[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        if node.keywords:
            raise ToolError("Keyword arguments are not supported.")
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ToolError("Unsupported expression. Use numbers, + - * / // % ** ( ) and common math functions.")


def calculate(expression: str) -> float | int:
    expr = expression.strip().replace("^", "**")
    if not expr:
        raise ToolError("Empty expression.")
    if len(expr) > MAX_EXPR_LEN:
        raise ToolError(f"Expression too long (max {MAX_EXPR_LEN} characters).")
    try:
        tree = ast.parse(expr, mode="eval")
        result = _eval(tree)
    except ToolError:
        raise
    except ZeroDivisionError as exc:
        raise ToolError("Division by zero.") from exc
    except (ValueError, OverflowError, TypeError, SyntaxError, RecursionError) as exc:
        raise ToolError(f"Could not evaluate that expression ({type(exc).__name__}).") from exc
    if isinstance(result, complex) or isinstance(result, bool) or not isinstance(result, (int, float)):
        raise ToolError("The result is not a real number.")
    if isinstance(result, float) and (math.isnan(result) or math.isinf(result)):
        raise ToolError("The result is not a finite number.")
    if isinstance(result, float) and result.is_integer() and abs(result) < 1e15:
        return int(result)
    return result
