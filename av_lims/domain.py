"""Deterministic laboratory calculations and policies, independent of Frappe."""

import ast
import hashlib
import json
import re
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, DecimalException, localcontext


class LabRuleError(ValueError):
    pass


def decimal(value):
    try:
        result = Decimal(str(value))
    except (DecimalException, ValueError, TypeError) as exc:
        raise LabRuleError("A finite numeric value is required") from exc
    if not result.is_finite() or abs(result) > Decimal("1e30"):
        raise LabRuleError("Numeric value is outside the supported range")
    return result


def expression_names(expression):
    if len(expression) > 512:
        raise LabRuleError("Expression is too long")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise LabRuleError("Invalid calculation expression") from exc
    if len(list(ast.walk(tree))) > 100:
        raise LabRuleError("Expression is too complex")
    return tree, {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def calculate(expression, values):
    tree, _ = expression_names(expression)
    names = {k: decimal(v) for k, v in values.items()}

    def evaluate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return decimal(node.value)
        if isinstance(node, ast.Name) and node.id in names:
            return names[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = evaluate(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.BinOp):
            a, b = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Add):
                result = a + b
            elif isinstance(node.op, ast.Sub):
                result = a - b
            elif isinstance(node.op, ast.Mult):
                result = a * b
            elif isinstance(node.op, ast.Div):
                result = a / b
            elif isinstance(node.op, ast.Pow) and b == b.to_integral_value() and abs(b) <= 6:
                result = a ** int(b)
            else:
                raise LabRuleError("Unsupported calculation operator")
            return decimal(result)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            args = [evaluate(x) for x in node.args]
            if not args:
                raise LabRuleError("A function needs at least one argument")
            if node.func.id == "mean":
                return decimal(sum(args) / len(args))
            if node.func.id == "min":
                return min(args)
            if node.func.id == "max":
                return max(args)
            if node.func.id == "sqrt" and len(args) == 1:
                return decimal(args[0].sqrt())
        raise LabRuleError("Unsupported expression or unknown parameter")

    try:
        with localcontext() as context:
            context.prec = 50
            return decimal(evaluate(tree.body))
    except DecimalException as exc:
        raise LabRuleError("Calculation failed; check inputs and division by zero") from exc


def validate_method(inputs, outputs):
    codes = [x["code"] for x in inputs]
    out_codes = [x["code"] for x in outputs]
    all_codes = codes + out_codes
    if not inputs or not outputs or len(all_codes) != len(set(all_codes)):
        raise LabRuleError("Methods require inputs and outputs with distinct parameter codes")
    if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,39}", x) for x in all_codes):
        raise LabRuleError("Parameter codes must be simple identifiers")
    allowed = set(codes) | {"mean", "min", "max", "sqrt"}
    for output in outputs:
        tree, names = expression_names(output["expression"])
        if names - allowed:
            raise LabRuleError("Calculation references an undefined input")
        for node in ast.walk(tree):
            if not isinstance(
                node,
                (
                    ast.Expression,
                    ast.Constant,
                    ast.Name,
                    ast.Load,
                    ast.UnaryOp,
                    ast.UAdd,
                    ast.USub,
                    ast.BinOp,
                    ast.Add,
                    ast.Sub,
                    ast.Mult,
                    ast.Div,
                    ast.Pow,
                    ast.Call,
                ),
            ):
                raise LabRuleError("Unsupported syntax in method expression")
            if isinstance(node, ast.Call) and (
                not isinstance(node.func, ast.Name)
                or node.func.id not in {"mean", "min", "max", "sqrt"}
                or not node.args
                or node.keywords
            ):
                raise LabRuleError("Unsupported calculation function")
        if not 0 <= int(output.get("precision") or 0) <= 9:
            raise LabRuleError("Output precision must be between 0 and 9")


def process_results(inputs, outputs, observations):
    validate_method(inputs, outputs)
    obs_codes = [x["code"] for x in observations]
    if len(obs_codes) != len(set(obs_codes)) or set(obs_codes) - {x["code"] for x in inputs}:
        raise LabRuleError("Observations contain duplicate or unknown parameters")
    values = {
        x["code"]: decimal(x["value"])
        for x in observations
        if x.get("value") is not None and x.get("recorded", True)
    }
    required = {x["code"] for x in inputs if x.get("mandatory", True)}
    if required - values.keys():
        raise LabRuleError("Required observations are missing")
    result = []
    for output in outputs:
        precision = int(output.get("precision") or 0)
        with localcontext() as context:
            context.prec = 50
            value = calculate(output["expression"], values).quantize(
                Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP
            )
        result.append(
            {
                "code": output["code"],
                "value": float(value),
                "precision": precision,
                "uom": output.get("uom") or "",
            }
        )
    return result


def digest(value):
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)
    return hashlib.sha256(serialized.encode()).hexdigest()


def evaluate_conformity(results, limits):
    values = {r["code"]: decimal(r["value"]) for r in results}
    if not limits or len({x["code"] for x in limits}) != len(limits):
        raise LabRuleError("Distinct specification limits are required")
    evaluations = []
    for limit in limits:
        if limit["code"] not in values:
            raise LabRuleError("A specified result is missing")
        lower = decimal(limit["lower_limit"]) if limit.get("has_lower") else None
        upper = decimal(limit["upper_limit"]) if limit.get("has_upper") else None
        if lower is None and upper is None:
            raise LabRuleError("A specification needs a lower or upper limit")
        if lower is not None and upper is not None and lower > upper:
            raise LabRuleError("Specification lower limit exceeds upper limit")
        value = values[limit["code"]]
        passed = (lower is None or value >= lower) and (upper is None or value <= upper)
        evaluations.append(
            {
                "code": limit["code"],
                "value": str(value),
                "lower": str(lower) if lower is not None else None,
                "upper": str(upper) if upper is not None else None,
                "outcome": "Pass" if passed else "Fail",
            }
        )
    return evaluations


def schedule_window(prepared_on, target_hours, early_hours=0, late_hours=0):
    target, early, late = map(decimal, [target_hours, early_hours, late_hours])
    if target <= 0 or early < 0 or late < 0 or early > target or max(target, early, late) > 876000:
        raise LabRuleError("Invalid specimen test age or tolerance")
    due = prepared_on + timedelta(hours=float(target))
    return due, due - timedelta(hours=float(early)), due + timedelta(hours=float(late))


TRANSITIONS = {
    "Lab Inspection Test Plan": {"Release": ("Draft", "Released", "manager")},
    "Lab Hold Point Release": {"Release Hold": ("Draft", "Approved", "approver")},
    "Lab Work Authorization": {"Authorize": ("Draft", "Authorized", "approver")},
    "Lab Sample Receipt": {"Receive": ("Draft", "Received", "lead")},
    "Lab Work Plan": {"Release": ("Draft", "Released", "lead")},
    "Lab Chain of Custody": {
        "Activate": ("Draft", "Active", "lead"),
        "Complete": ("Active", "Completed", "technician"),
        "Reopen": ("Completed", "Active", "lead"),
    },
    "Lab Test Execution": {
        "Complete Raw": ("Draft", "Raw Complete", "technician"),
        "Process": ("Raw Complete", "Processed", "lead"),
    },
    "Lab QA Review": {
        "Accept": ("Draft", "Accepted", "manager"),
        "Require Correction": ("Draft", "Correction Required", "manager"),
    },
    "Lab Nonconformance": {"Open": ("Draft", "Open", "lead"), "Close": ("Open", "Closed", "manager")},
    "Lab Corrective Action": {"Return to QA": ("Draft", "Returned to QA", "manager")},
    "Lab Result Report": {"Approve": ("Draft", "Approved", "approver")},
    "Lab Result Dispatch": {"Issue": ("Draft", "Issued", "lead")},
    "Lab Test Method Version": {"Approve": ("Draft", "Approved", "manager")},
    "Lab QA Checklist Version": {"Approve": ("Draft", "Approved", "manager")},
    "Lab Specification Version": {"Approve": ("Draft", "Approved", "approver")},
    "Lab Equipment Check": {"Verify": ("Draft", "Verified", "manager")},
    "Lab Competency": {"Verify": ("Draft", "Verified", "manager")},
    "Lab Conditioning Record": {"Complete": ("Draft", "Completed", "technician")},
    "Lab Conformity Evaluation": {"Evaluate": ("Draft", "Evaluated", "manager")},
}
