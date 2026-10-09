# import os
# import json
# import resource
# import shutil
# import subprocess
# import tempfile

# from flask import Flaks , request , jsonify

# app = Flask(__name__)

# TIMEOUT_SECONDS = 5
# CPU_TIME_LIMIT = 5
# MEMORY_LIMIT_BYTES = 100*1024*1024
# MAX_OUTPUT_BYTES = 1*1024*1024
# MAX_PROCESS = 10


# def apply_limits():
#     resource.setrlimit(resource.RLIMIT_CPU,(CPU_TIME_LIMIT,CPU_TIME_LIMIT))
#     resource.setrlimit(resource.RLIMIT_AS,(MEMORY_LIMIT_BYTES,MEMORY_LIMIT_BYTES))
#     resource.setrlimit(resource.RLIMIT_NPROC,(MAX_PROCESS,MAX_PROCESS))
#     resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))

# PROBLEMS = {
#     "two-sum": {
#         "id": "two-sum",
#         "title": "Two Sum",
#         "difficulty": "Easy",
#         "description": (
#             "Given an array of integers nums and an integer target, return "
#             "indices of the two numbers such that they add up to target. "
#             "You may assume each input has exactly one solution, and you "
#             "may not use the same element twice."
#         ),
#         "function_name": "twoSum",
#         "starter_code": "def twoSum(nums, target):\n    # write your solution here\n    pass\n",
#         "test_cases": [
#             {"input": {"nums": [2, 7, 11, 15], "target": 9}, "expected": [0, 1]},
#             {"input": {"nums": [3, 2, 4], "target": 6}, "expected": [1, 2]},
#             {"input": {"nums": [3, 3], "target": 6}, "expected": [0, 1]},
#         ],
#     },
#     "palindrome-number": {
#         "id": "palindrome-number",
#         "title": "Palindrome Number",
#         "difficulty": "Easy",
#         "description": "Given an integer x, return true if x is a palindrome integer, and false otherwise.",
#         "function_name": "isPalindrome",
#         "starter_code": "def isPalindrome(x):\n    # write your solution here\n    pass\n",
#         "test_cases": [
#             {"input": {"x": 121}, "expected": True},
#             {"input": {"x": -121}, "expected": False},
#             {"input": {"x": 10}, "expected": False},
#         ],
#     },
# }

# def run_aginst_test_case(user_code,function_name,test_input):
#     # harness = (user_code+"\n\nimport json,sys\n"+"__payload=json.loads(sys.stdin.read())\n"+f"__result = {function_name}(**__payload)\n"+"print(json.dumps({'result':__result}))\n")
#     harness = (
#         user_code
#         + "\n\nimport json, sys\n"
#         + "__payload = json.loads(sys.stdin.read())\n"
#         + f"__result = {function_name}(**__payload)\n"
#         + "print(json.dumps({'result': __result}))\n"
#     )

#     tmp_dir = tempfile.mkdtemp(prefix="submit_")
#     script_path = os.path.join(tmp_dir,"script.py")
#     try:
#         with open(script_path,"w") as f:
#             f.write(harness)
#         result = subprocess.run(
#             ["python3","-I","script.py"],
#             cwd=tmp_dir,
#             input=json.dumps(test_input),
#             capture_output=True,
#             text=True,
#             timeout=TIMEOUT_SECONDS,
#             preexec_fn=apply_limits,
#             env={"PATH":"/usr/bin:/bin"},
#         )

#         if result.returncode != 0:
#             return {"ok":False,"error":(result.stderr or "Runtime error")[-2000:]}
#         try:
#             last_line = result.stdout.strip().splitlines()[-1]
#             parsed = json.loads(last_line)
#         except (ValueError, IndexError):
#             return {"ok": False, "error": "Could not parse output: " + result.stdout[-500:]}

#         return {"ok":True,"actual":parsed.get("result")}
#     except subprocess.TimeoutExpired:
#         return {"ok": False, "error": f"Timed out after {TIMEOUT_SECONDS}s"}
#     finally:
#         shutil.rmtree(tmp_dir, ignore_errors=True)


# @app.route("/")
# def health():
#     return jsonify(status="ok",service="leepcode-judge",problems=len(PROBLEMS))


# @app.route("/problems")
# def list_problems():
#     return jsonify([
#         {"id": p["id"], "title": p["title"], "difficulty": p["difficulty"]}
#         for p in PROBLEMS.values()
#     ])

# @app.route("/problems/<problem_id>")
# def get_problem(problem_id):
#     problem = PROBLEMS.get(problem_id)
#     if not problem:
#         return jsonify(error="Problem not found"), 404

#     return jsonify(
#         id=problem["id"],
#         title=problem["title"],
#         difficulty=problem["difficulty"],
#         description=problem["description"],
#         starter_code=problem["starter_code"],
#         example=problem["test_cases"][0],
#         hidden_test_case_count=len(problem["test_cases"]) 
#     )

# @app.route("/submit", methods=["POST"])
# def submit():
#     data = request.get_json(silent=True) or {}
#     problem_id = data.get("problem_id")
#     code = data.get("code")

#     if not problem_id or not code:
#         return jsonify(error="Missing 'problem_id' or 'code'"), 400

#     problem = PROBLEMS.get(problem_id)
#     if not problem:
#         return jsonify(error="Problem not found"), 404

#     results = []
#     passed_count = 0

#     for case in problem["test_cases"]:
#         outcome = run_against_test_case(code, problem["function_name"], case["input"])

#         if not outcome["ok"]:
#             results.append({
#                 "input": case["input"],
#                 "expected": case["expected"],
#                 "passed": False,
#                 "error": outcome["error"],
#             })
#             continue

#         is_pass = outcome["actual"] == case["expected"]
#         if is_pass:
#             passed_count += 1

#         results.append({
#             "input": case["input"],
#             "expected": case["expected"],
#             "actual": outcome["actual"],
#             "passed": is_pass,
#         })

#     total = len(problem["test_cases"])
#     return jsonify(
#         problem_id=problem_id,
#         passed=passed_count == total,
#         score=f"{passed_count}/{total}",
#         results=results,
#     )


# if __name__ == "__main__":
#     port = int(os.environ.get("PORT", 5000))
#     app.run(host="0.0.0.0", port=port, debug=False)



import os
import json
import resource
import shutil
import subprocess
import tempfile

from flask import Flask, request, jsonify, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Static files are served at /static/<file> from the ./static folder
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")

TIMEOUT_SECONDS = 5
CPU_TIME_LIMIT = 5
MEMORY_LIMIT_BYTES = 100 * 1024 * 1024
MAX_OUTPUT_BYTES = 1 * 1024 * 1024
MAX_PROCESS = 10


def apply_limits():
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_TIME_LIMIT, CPU_TIME_LIMIT))
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_NPROC, (MAX_PROCESS, MAX_PROCESS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))


PROBLEMS = {
    "two-sum": {
        "id": "two-sum",
        "title": "Two Sum",
        "difficulty": "Easy",
        "description": (
            "Given an array of integers nums and an integer target, return "
            "indices of the two numbers such that they add up to target. "
            "You may assume each input has exactly one solution, and you "
            "may not use the same element twice."
        ),
        "function_name": "twoSum",
        "starter_code": "def twoSum(nums, target):\n    # write your solution here\n    pass\n",
        "test_cases": [
            {"input": {"nums": [2, 7, 11, 15], "target": 9}, "expected": [0, 1]},
            {"input": {"nums": [3, 2, 4], "target": 6}, "expected": [1, 2]},
            {"input": {"nums": [3, 3], "target": 6}, "expected": [0, 1]},
        ],
    },
    "palindrome-number": {
        "id": "palindrome-number",
        "title": "Palindrome Number",
        "difficulty": "Easy",
        "description": "Given an integer x, return true if x is a palindrome integer, and false otherwise.",
        "function_name": "isPalindrome",
        "starter_code": "def isPalindrome(x):\n    # write your solution here\n    pass\n",
        "test_cases": [
            {"input": {"x": 121}, "expected": True},
            {"input": {"x": -121}, "expected": False},
            {"input": {"x": 10}, "expected": False},
        ],
    },
}


def run_against_test_case(user_code, function_name, test_input):
    harness = (
        user_code
        + "\n\nimport json, sys\n"
        + "__payload = json.loads(sys.stdin.read())\n"
        + f"__result = {function_name}(**__payload)\n"
        + "print(json.dumps({'result': __result}))\n"
    )

    tmp_dir = tempfile.mkdtemp(prefix="submit_")
    script_path = os.path.join(tmp_dir, "script.py")
    try:
        with open(script_path, "w") as f:
            f.write(harness)
        result = subprocess.run(
            ["python3", "-I", "script.py"],
            cwd=tmp_dir,
            input=json.dumps(test_input),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            preexec_fn=apply_limits,
            env={"PATH": "/usr/bin:/bin"},
        )

        if result.returncode != 0:
            return {"ok": False, "error": (result.stderr or "Runtime error")[-2000:]}
        try:
            last_line = result.stdout.strip().splitlines()[-1]
            parsed = json.loads(last_line)
        except (ValueError, IndexError):
            return {"ok": False, "error": "Could not parse output: " + result.stdout[-500:]}

        return {"ok": True, "actual": parsed.get("result")}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timed out after {TIMEOUT_SECONDS}s"}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------- frontend ----------
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


# ---------- API ----------
@app.route("/health")
def health():
    return jsonify(status="ok", service="leepcode-judge", problems=len(PROBLEMS))


@app.route("/problems")
def list_problems():
    return jsonify([
        {"id": p["id"], "title": p["title"], "difficulty": p["difficulty"]}
        for p in PROBLEMS.values()
    ])


@app.route("/problems/<problem_id>")
def get_problem(problem_id):
    problem = PROBLEMS.get(problem_id)
    if not problem:
        return jsonify(error="Problem not found"), 404

    return jsonify(
        id=problem["id"],
        title=problem["title"],
        difficulty=problem["difficulty"],
        description=problem["description"],
        starter_code=problem["starter_code"],
        example=problem["test_cases"][0],
        hidden_test_case_count=len(problem["test_cases"]),
    )


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True) or {}
    problem_id = data.get("problem_id")
    code = data.get("code")

    if not problem_id or not code:
        return jsonify(error="Missing 'problem_id' or 'code'"), 400

    problem = PROBLEMS.get(problem_id)
    if not problem:
        return jsonify(error="Problem not found"), 404

    results = []
    passed_count = 0

    for case in problem["test_cases"]:
        outcome = run_against_test_case(code, problem["function_name"], case["input"])

        if not outcome["ok"]:
            results.append({
                "input": case["input"],
                "expected": case["expected"],
                "passed": False,
                "error": outcome["error"],
            })
            continue

        is_pass = outcome["actual"] == case["expected"]
        if is_pass:
            passed_count += 1

        results.append({
            "input": case["input"],
            "expected": case["expected"],
            "actual": outcome["actual"],
            "passed": is_pass,
        })

    total = len(problem["test_cases"])
    return jsonify(
        problem_id=problem_id,
        passed=passed_count == total,
        score=f"{passed_count}/{total}",
        results=results,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)