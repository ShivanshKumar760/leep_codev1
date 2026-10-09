(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const els = {
    status: $("server-status"),
    list: $("problem-list"),
    workspace: $("workspace"),
    empty: $("empty-state"),
    title: $("problem-title"),
    difficulty: $("problem-difficulty"),
    description: $("problem-description"),
    exampleInput: $("example-input"),
    exampleExpected: $("example-expected"),
    hiddenCount: $("hidden-count"),
    code: $("code"),
    gutter: $("gutter"),
    submit: $("submit-btn"),
    reset: $("reset-btn"),
    summary: $("summary"),
    results: $("results"),
    resultsEmpty: $("results-empty"),
  };

  let current = null; // currently loaded problem
  const storageKey = (id) => `leepcode:code:${id}`;

  // ---------- helpers ----------
  const diffClass = (d) => "d-" + String(d).toLowerCase();

  async function api(path, options) {
    const res = await fetch(path, options);
    let body = null;
    try { body = await res.json(); } catch (_) { /* non-JSON response */ }
    if (!res.ok) {
      throw new Error((body && body.error) || `Request failed (${res.status})`);
    }
    return body;
  }

  const pretty = (v) => JSON.stringify(v);

  function safeStorage(fn) {
    try { return fn(); } catch (_) { return null; }
  }

  // ---------- server status ----------
  async function checkHealth() {
    try {
      await api("/health");
      els.status.textContent = "Judge online";
      els.status.className = "status ok";
    } catch (_) {
      els.status.textContent = "Judge offline";
      els.status.className = "status down";
    }
  }

  // ---------- problem list ----------
  async function loadProblems() {
    const problems = await api("/problems");
    els.list.replaceChildren();
    for (const p of problems) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "#" + p.id;
      a.dataset.id = p.id;

      const name = document.createElement("span");
      name.textContent = p.title;
      const diff = document.createElement("span");
      diff.className = "d " + diffClass(p.difficulty);
      diff.textContent = p.difficulty;

      a.append(name, diff);
      li.append(a);
      els.list.append(li);
    }
    return problems;
  }

  function markActive(id) {
    for (const a of els.list.querySelectorAll("a")) {
      if (a.dataset.id === id) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
    }
  }

  // ---------- problem view ----------
  async function openProblem(id) {
    try {
      const p = await api("/problems/" + encodeURIComponent(id));
      current = p;
      markActive(id);

      els.title.textContent = p.title;
      els.difficulty.textContent = p.difficulty;
      els.difficulty.className = "badge " + diffClass(p.difficulty);
      els.description.textContent = p.description;
      els.exampleInput.textContent = pretty(p.example.input);
      els.exampleExpected.textContent = pretty(p.example.expected);
      els.hiddenCount.textContent =
        `Your code runs against ${p.hidden_test_case_count} test cases, including the example.`;

      const saved = safeStorage(() => localStorage.getItem(storageKey(id)));
      els.code.value = saved !== null && saved !== "" ? saved : p.starter_code;
      updateGutter();
      clearResults();

      els.workspace.hidden = false;
      els.empty.hidden = true;
      document.title = `${p.title} · Leepcode Judge`;
    } catch (err) {
      current = null;
      els.workspace.hidden = true;
      els.empty.hidden = false;
      els.empty.textContent = err.message;
    }
  }

  // ---------- editor ----------
  function updateGutter() {
    const lines = els.code.value.split("\n").length;
    let text = "";
    for (let i = 1; i <= lines; i++) text += i + (i < lines ? "\n" : "");
    els.gutter.textContent = text;
    els.gutter.scrollTop = els.code.scrollTop;
  }

  els.code.addEventListener("input", () => {
    updateGutter();
    if (current) safeStorage(() => localStorage.setItem(storageKey(current.id), els.code.value));
  });
  els.code.addEventListener("scroll", () => { els.gutter.scrollTop = els.code.scrollTop; });

  els.code.addEventListener("keydown", (e) => {
    if (e.key === "Tab" && !e.shiftKey) {
      e.preventDefault();
      const { selectionStart: s, selectionEnd: end, value } = els.code;
      els.code.value = value.slice(0, s) + "    " + value.slice(end);
      els.code.selectionStart = els.code.selectionEnd = s + 4;
      els.code.dispatchEvent(new Event("input"));
    } else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      submit();
    }
  });

  els.reset.addEventListener("click", () => {
    if (!current) return;
    if (!confirm("Replace your code with the starter code?")) return;
    els.code.value = current.starter_code;
    safeStorage(() => localStorage.removeItem(storageKey(current.id)));
    updateGutter();
  });

  // ---------- submit + results ----------
  function clearResults() {
    els.summary.hidden = true;
    els.results.replaceChildren();
    els.resultsEmpty.hidden = false;
  }

  function addRow(dl, term, value, isCode = true) {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    if (isCode) {
      const pre = document.createElement("pre");
      pre.textContent = value;
      dd.append(pre);
    } else {
      dd.textContent = value;
    }
    dl.append(dt, dd);
  }

  function renderResults(data) {
    els.resultsEmpty.hidden = true;

    els.summary.hidden = false;
    els.summary.className = "summary " + (data.passed ? "pass" : "fail");
    els.summary.replaceChildren();
    const verdict = document.createElement("span");
    verdict.textContent = data.passed ? "All tests passed" : "Some tests failed";
    const score = document.createElement("span");
    score.className = "score";
    score.textContent = data.score + " passed";
    els.summary.append(verdict, score);

    els.results.replaceChildren();
    data.results.forEach((r, i) => {
      const li = document.createElement("li");
      li.className = "case " + (r.passed ? "pass" : "fail");

      const title = document.createElement("div");
      title.className = "case-title";
      title.textContent = `Test ${i + 1}: ${r.passed ? "Passed" : "Failed"}`;

      const dl = document.createElement("dl");
      addRow(dl, "Input", pretty(r.input));
      addRow(dl, "Expected", pretty(r.expected));
      if ("actual" in r) addRow(dl, "Your output", pretty(r.actual));
      if (r.error) {
        const dt = document.createElement("dt");
        dt.textContent = "Error";
        const dd = document.createElement("dd");
        const pre = document.createElement("pre");
        pre.className = "error";
        pre.textContent = r.error;
        dd.append(pre);
        dl.append(dt, dd);
      }

      li.append(title, dl);
      els.results.append(li);
    });

    els.summary.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function submit() {
    if (!current || els.submit.disabled) return;
    const code = els.code.value;
    if (!code.trim()) {
      els.resultsEmpty.hidden = false;
      els.resultsEmpty.textContent = "Write some code before running the tests.";
      return;
    }

    els.submit.disabled = true;
    els.submit.textContent = "Running…";
    try {
      const data = await api("/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ problem_id: current.id, code }),
      });
      renderResults(data);
    } catch (err) {
      clearResults();
      els.resultsEmpty.textContent = err.message;
    } finally {
      els.submit.disabled = false;
      els.submit.textContent = "Run tests";
    }
  }
  els.submit.addEventListener("click", submit);

  // ---------- routing ----------
  const routeId = () => decodeURIComponent(location.hash.replace(/^#/, ""));

  window.addEventListener("hashchange", () => {
    const id = routeId();
    if (id) openProblem(id);
  });

  (async function init() {
    checkHealth();
    try {
      const problems = await loadProblems();
      const id = routeId();
      if (id) openProblem(id);
      else if (problems.length) location.hash = problems[0].id;
    } catch (err) {
      els.empty.textContent = "Could not load problems: " + err.message;
    }
  })();
})();