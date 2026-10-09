# LeetCode-Style Judge — Flask + Render

A small online-judge API: an in-memory set of problems (Two Sum, Palindrome Number), each with
test cases. A submission is run against every test case in a sandboxed subprocess (the same
pattern as the standalone `code-runner` project), and the result is compared to the expected
output per test case.

**Answering the question this was built to answer first:** can a single Render service run
submitted code against test cases, or does it need to be split into a separate
execution-service + judge-service talking to each other? **Tested directly — one service is
enough.** See Section 2 for the actual test run. A microservice split is still a reasonable
design choice for other reasons (Section 6), just not a requirement Render forces on you here.

---

## 1. Project structure

```
leetcode-judge/
├── app.py                      # Problems (in-memory), grading logic, API
├── requirements.txt
├── render.yaml
├── GUIDE.md                    # This file
└── .github/
    └── workflows/
        └── deploy.yml
```

---

## 2. Tested: single-service grading works

Ran real submissions against a live local instance:

| Submission                                      | Result                                                      |
|-----------------------------------------------------|------------------------------------------------------------------|
| Correct Two Sum (hash map)                          | `"passed": true, "score": "3/3"`, per-case `actual` matches `expected` |
| Wrong Two Sum (always returns `[0, 0]`)              | `"passed": false, "score": "0/3"`, each case shows `actual` vs `expected` |
| Correct Palindrome Number                           | `"passed": true, "score": "3/3"`                                   |
| Submission that raises (`1 / 0`)                    | Each case shows a clean Python traceback in `error`, `"score": "0/3"` |
| Submission that infinite-loops                      | Each case times out at 5s with `"error": "Timed out after 5s"`      |
| `GET /problems/not-a-real-problem`                   | `404`, `{"error": "Problem not found"}`                             |

No crashes, no hung requests, no server-level errors in any case — a buggy or malicious
submission only ever affects its own sandboxed subprocess and still returns a clean JSON result.
This confirms the single-service design handles grading correctly; nothing here needed a second
service.

---

## 3. The two problems (in-memory "database")

```python
PROBLEMS = {
    "two-sum": {
        "id": "two-sum",
        "title": "Two Sum",
        "difficulty": "Easy",
        "description": "...",
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
```

A plain Python dict, reset on every restart — intentionally the simplest thing that works. See
Section 7 for whether/how you'd move this to a real database.

**Known simplification:** grading uses exact equality (`actual == expected`). For Two Sum
specifically, a real judge usually accepts the indices in either order, since more than one valid
pair-finding approach exists. This demo's expected outputs match what a standard left-to-right
hash-map scan returns, which is what most people naturally write first — but a technically
correct solution that finds the pair in a different order could fail a test case here. Worth
knowing before treating this as a strict correctness judge versus a demo.

---

## 4. How grading actually runs a submission

```python
def run_against_test_case(user_code, function_name, test_input):
    """Runs user_code plus a small harness as one sandboxed subprocess, with
    the test case's input piped in via stdin as JSON, and the function's
    return value read back via stdout as JSON."""
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
```

The user's submitted code (expected to define a function, e.g. `def twoSum(nums, target): ...`)
gets a few lines appended: read the test case's input as JSON from stdin, call the function by
name with those values as keyword arguments, print the return value as JSON. One subprocess per
test case, reusing the exact same `apply_limits()` sandboxing (CPU time, memory, process count,
output size, 5s timeout) as the standalone code-runner.

---

## 5. Full source — `app.py`

```python
import os
import json
import resource
import shutil
import subprocess
import tempfile

from flask import Flask, request, jsonify

app = Flask(__name__)

TIMEOUT_SECONDS = 5
CPU_TIME_LIMIT = 5
MEMORY_LIMIT_BYTES = 100 * 1024 * 1024
MAX_OUTPUT_BYTES = 1 * 1024 * 1024
MAX_PROCESSES = 10


def apply_limits():
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_TIME_LIMIT, CPU_TIME_LIMIT))
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_NPROC, (MAX_PROCESSES, MAX_PROCESSES))
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


@app.route("/")
def health():
    return jsonify(status="ok", service="leetcode-judge", problems=len(PROBLEMS))


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
        hidden_test_case_count=len(problem["test_cases"]) - 1,
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
```

`requirements.txt`:

```
Flask==3.0.3
gunicorn==22.0.0
```

---

## 6. API reference

| Method | Endpoint             | Description                                           |
|--------|-----------------------|---------------------------------------------------------|
| GET    | `/`                   | Health check                                            |
| GET    | `/problems`           | List all problems (id, title, difficulty)               |
| GET    | `/problems/<id>`      | One problem's description, starter code, and one worked example |
| POST   | `/submit`              | `{problem_id, code}` → grades against all test cases     |

```bash
curl https://<your-app>.onrender.com/problems

curl -X POST https://<your-app>.onrender.com/submit \
  -H "Content-Type: application/json" \
  -d '{"problem_id": "two-sum", "code": "def twoSum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i\n"}'
```

---

## 7. If you *did* want the microservice split

Section 2 showed a single service handles this correctly, so the split below is a genuine design
choice (separation of concerns, independently scaling the execution layer, adding other language
runtimes later) — not something forced by any Render limitation. If you want it:

- **`execution-service`** — a dumb, language-agnostic sandboxed runner. Basically the standalone
  `code-runner` project: one `POST /execute` endpoint that takes code + stdin input, returns
  stdout/stderr/exit code. Knows nothing about problems or test cases.
- **`judge-service`** — owns `PROBLEMS`, the grading loop, and the public `/problems` and
  `/submit` API. For each test case, instead of running the subprocess itself, it makes an HTTP
  call to `execution-service`'s `/execute` (passing the harness-wrapped code + JSON input as the
  subprocess's stdin), then does the same `actual == expected` comparison on the response.

Both deploy the same way as everything else in this project set: each as its own repo with its
own CI, a `render.yaml` for each in a shared `render_ops` repo, `judge-service`'s Blueprint
pointed at `execution-service`'s public Render URL via an env var (e.g.
`EXECUTION_SERVICE_URL=https://execution-service.onrender.com`). Happy to build this version too
if you want the actual two-service, inter-service-HTTP-call architecture rather than just the
description of it.

---

## 8. Provision infrastructure with the Render Blueprint

```yaml
services:
  - type: web
    name: leetcode-judge
    runtime: python
    plan: free
    region: oregon
    branch: main
    buildCommand: "pip install -r requirements.txt"
    startCommand: "gunicorn app:app --bind 0.0.0.0:$PORT --timeout 30"
    healthCheckPath: /
    autoDeploy: false
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.9
```

Steps: push to GitHub → Render Dashboard → **New → Blueprint** → connect the repo → **Apply**.

---

## 9. GitHub Actions CI/CD

Same pattern as the rest of this project set: install → smoke test → on push to `main`, trigger
the Render deploy hook.

1. Render Dashboard → service → **Settings → Deploy Hook** → copy the URL.
2. GitHub repo → **Settings → Secrets and variables → Actions** → new secret
   `RENDER_DEPLOY_HOOK_URL`.
3. Push to `main`.

---

## 10. Security notes (same as the standalone code-runner)

This is process-level sandboxing (CPU/memory/process/output limits + timeout), not real container
isolation — appropriate for a demo judge with a small, known problem set, not for fending off
genuinely adversarial submissions at scale. A submission still runs as a real OS process in this
container and could, e.g., `import os` and poke at the filesystem. If this ever needs to hold up
against hostile users specifically trying to break out, see the standalone `code-runner` project's
security section for what a stronger sandbox would require (an external Firecracker/gVisor-based
runner, since Render itself can't host that isolation layer).