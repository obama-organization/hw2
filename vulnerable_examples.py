import ast
import json
import math
import operator
import re
import sqlite3
import subprocess
from contextlib import closing

import environ
from django.utils.html import escape

env = environ.Env()

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)


def search_fixed(request, MyModel):
    q = request.GET.get("q", "")
    return MyModel.objects.filter(name__icontains=q)


def save_comment_fixed(request, CommentModel):
    user_input = request.POST.get("comment", "")
    comment = CommentModel()
    comment.html = escape(user_input)
    comment.save()
    return comment


SAFE_FILENAME = re.compile(r"[A-Za-z0-9_-]{1,64}")


def backup_fixed(request):
    filename = request.GET.get("file", "")
    if not SAFE_FILENAME.fullmatch(filename):
        raise ValueError("Invalid file name")
    subprocess.run(
        ["tar", "-czf", f"/backup/{filename}.tar.gz", f"/data/{filename}"],
        check=True,
    )
    return "ok"


def load_object_fixed(uploaded_file):
    data = json.loads(uploaded_file.read())
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    return data


def update_profile_fixed(request):
    return "profile updated"


def get_user_data(username):
    with closing(sqlite3.connect("users.db")) as db:
        cursor = db.execute("SELECT * FROM users WHERE username = ?", (username,))
        return cursor.fetchall()


OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
MAX_EXPRESSION_LENGTH = 200
MAX_EXPONENT = 100
MAX_RESULT_DIGITS = 1000


def _evaluate(node):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](_evaluate(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and (
            abs(right) > MAX_EXPONENT
            or (abs(left) > 1 and abs(right) * math.log10(abs(left)) > MAX_RESULT_DIGITS)
        ):
            raise ValueError("Exponent is too large")
        return OPERATORS[type(node.op)](left, right)
    raise ValueError("Only numbers and + - * / // % ** are allowed")


def safe_eval(expression):
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise ValueError("Expression is too long")
    return _evaluate(ast.parse(expression, mode="eval"))


def calculate_expression(expression):
    try:
        result = safe_eval(expression)
        print(f"Result: {result}")
        return result
    except (ValueError, SyntaxError, ZeroDivisionError) as e:
        print(f"Error: {e}")
        return None


def run_user_expression():
    user_input = input("Enter math expression: ")
    print("Result:", calculate_expression(user_input))


if __name__ == "__main__":
    calculate_expression("2 + 3 * 4")
