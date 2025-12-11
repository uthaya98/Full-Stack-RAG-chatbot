from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import ast
import operator as op

router = APIRouter()

# supported operators
allowed_operators = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
    ast.Mod: op.mod,
}

def safe_eval(expr: str):
    """
    Safely evaluate arithmetic expressions using ast.
    Allows numbers, + - * / ** % and parentheses.
    """
    try:
        node = ast.parse(expr, mode='eval').body
    except Exception as e:
        raise ValueError("Invalid expression")

    def _eval(n):
        if isinstance(n, ast.Constant):  # Py3.8+ uses Constant for numbers
            if isinstance(n.value, (int, float)):
                return n.value
            raise ValueError("Invalid constant")
        if isinstance(n, ast.BinOp):
            op_type = type(n.op)
            if op_type not in allowed_operators:
                raise ValueError("Operator not allowed")
            return allowed_operators[op_type](_eval(n.left), _eval(n.right))
        if isinstance(n, ast.UnaryOp):
            op_type = type(n.op)
            if op_type not in allowed_operators:
                raise ValueError("Operator not allowed")
            return allowed_operators[op_type](_eval(n.operand))
        raise ValueError("Unsupported expression")
    return _eval(node)

class CalcRequest(BaseModel):
    expr: str

@router.get("/calc")
def calc_get(expr: str):
    if not expr:
        raise HTTPException(status_code=400, detail="expr query param required")
    try:
        result = safe_eval(expr)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/calc")
def calc_post(req: CalcRequest):
    return calc_get(req.expr)
