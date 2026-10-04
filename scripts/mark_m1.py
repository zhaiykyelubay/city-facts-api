#!/usr/bin/env python3
"""
INF 345 Milestone 1 - marks a student's project repository.

Three gates. Any gate failure caps the milestone at 0.
Then 100 points in four blocks of 25.

    python3 mark_m1.py --repo https://github.com/<user>/<project>
    python3 mark_m1.py --path .            # mark a local checkout

"A merged pull request" is read from GitHub (any merge button counts: merge
commit, squash or rebase). If GitHub cannot be reached, the marker falls back
to what the git history shows.

"Tests that can fail" is checked directly: the marker deletes your
application's source files in a scratch copy and runs scripts/test.sh again.
It must fail. Tests that still pass with no application are not testing it.

Exit code 0 only if the score is 100. That exit code is what a pipeline
turns into a tick or a cross.

Nothing in this file is hidden from students. It is the rubric.
"""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------- helpers

def run(cmd, cwd=None, timeout=120, env=None):
    """Run a command, never raise. Returns (rc, stdout, stderr)."""
    e = dict(os.environ)
    if env:
        e.update(env)
    try:
        p = subprocess.run(cmd, cwd=cwd, env=e, timeout=timeout,
                           capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"
    except OSError as exc:
        return 127, "", str(exc)


def free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def http(url, timeout=3):
    """Returns (status, body, seconds) or (None, reason, seconds)."""
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read(4096).decode("utf-8", "replace"), time.time() - t0
    except urllib.error.HTTPError as exc:
        return exc.code, "", time.time() - t0
    except Exception as exc:
        return None, str(exc), time.time() - t0


# ------------------------------------------------------------------ gates

# Two tiers, because the two mistakes cost differently. Wrongly accusing a
# student of committing a credential is worse than missing a placeholder, so
# the fuzzy tier is allowed a generous allowlist. The high-confidence tier is
# not: those formats are credentials or they are the vendor's own doc value.

HIGH_CONFIDENCE = [
    (r"AKIA[0-9A-Z]{16}", "AWS access key id"),
    (r"gh[pousr]_[A-Za-z0-9]{36,}", "GitHub token"),
    (r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----", "private key"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack token"),
]

# Values that appear verbatim in vendor documentation and in half the
# tutorials on the internet. Not secrets.
DOC_VALUES = re.compile(r"(?i)(EXAMPLE|wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY)")

FUZZY = [
    (r"(?i)\b(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*"
     r"['\"][^'\"\s]{12,}['\"]", "hardcoded credential"),
]

FUZZY_ALLOW = re.compile(
    r"(?i)(example|sample|placeholder|dummy|change[_-]?me|replace[_-]?me"
    r"|your[_\-\w]*|[_\-]here\b|xxx+|<[^>]+>|\$\{[^}]+\}|\bfake\b"
    r"|redacted|todo|test[_-]?token|secret[_-]?key[_-]?here)")


def gate_repo(path):
    if not os.path.isdir(os.path.join(path, ".git")):
        return False, "no .git directory - is this a git repository?"
    return True, "repository present"


def gate_no_secrets(path):
    """Scan the whole history, not just the working tree."""
    rc, out, _ = run(["git", "log", "-p", "--all", "--no-color"],
                     cwd=path, timeout=180)
    if rc == 124:
        return False, "history scan timed out"
    hits = []
    for line in out.splitlines():
        if not line.startswith("+"):
            continue
        flagged = None
        for pat, label in HIGH_CONFIDENCE:
            m = re.search(pat, line)
            if m and not DOC_VALUES.search(m.group(0)):
                flagged = f"{label}: {m.group(0)[:40]}"
                break
        if not flagged:
            for pat, label in FUZZY:
                m = re.search(pat, line)
                if m and not FUZZY_ALLOW.search(m.group(0)):
                    flagged = f"{label}: {m.group(0)[:60]}"
                    break
        if flagged:
            hits.append(flagged)
    if hits:
        uniq = sorted(set(hits))[:3]
        return False, "credential found in git history - " + "; ".join(uniq)
    return True, "no credentials found in history"


def gate_test_script(path):
    p = os.path.join(path, "scripts", "test.sh")
    if not os.path.isfile(p):
        return False, "scripts/test.sh does not exist"
    if not os.access(p, os.X_OK):
        return False, ("scripts/test.sh is not executable. Run "
                       "'chmod +x scripts/test.sh', commit, and push. Git "
                       "records the executable bit - the week 2 slide.")
    return True, "scripts/test.sh present and executable"


# --------------------------------------------------------------- 25 x 4

def block_runs(path):
    """25 - starts, honours $PORT, answers GET /."""
    runner = os.path.join(path, "scripts", "run.sh")
    if not os.path.isfile(runner):
        return 0, "scripts/run.sh does not exist"
    if not os.access(runner, os.X_OK):
        return 0, "scripts/run.sh is not executable (chmod +x)"

    port = free_port()
    proc = subprocess.Popen(["./scripts/run.sh"], cwd=path,
                            env={**os.environ, "PORT": str(port)},
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, start_new_session=True)
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            if proc.poll() is not None:
                tail = (proc.stdout.read() or "")[-400:]
                return 0, (f"scripts/run.sh exited early (code {proc.returncode}). "
                           f"Output: {tail.strip()[:300]}")
            status, _, _ = http(f"http://127.0.0.1:{port}/", timeout=2)
            if status and 200 <= status < 400:
                return 25, f"answered {status} on PORT={port} from the environment"
            time.sleep(0.5)
        return 0, (f"nothing answered on port {port} within 20 seconds. The marker "
                   f"sets PORT to a random value - a hardcoded port fails here.")
    finally:
        _kill(proc)


def block_healthz(path):
    """25 - /healthz: 200, non-empty, fast, repeatable."""
    runner = os.path.join(path, "scripts", "run.sh")
    if not os.path.isfile(runner):
        return 0, "scripts/run.sh does not exist"
    port = free_port()
    proc = subprocess.Popen(["./scripts/run.sh"], cwd=path,
                            env={**os.environ, "PORT": str(port)},
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            text=True, start_new_session=True)
    try:
        url = f"http://127.0.0.1:{port}/healthz"
        deadline = time.time() + 20
        first = None
        while time.time() < deadline:
            first = http(url, timeout=2)
            if first[0] is not None:
                break
            time.sleep(0.5)
        if not first or first[0] is None:
            return 0, "/healthz did not respond within 20 seconds"
        status, body, secs = first
        if status != 200:
            return 0, f"/healthz returned {status}, expected 200"
        if not body.strip():
            return 0, "/healthz returned 200 but an empty body"
        if secs > 1.0:
            return 0, (f"/healthz took {secs:.2f}s. A health check must answer in "
                       f"under a second - Kubernetes will not wait (week 9).")
        again, _, _ = http(url, timeout=2)
        if again != 200:
            return 0, f"/healthz returned 200 then {again} - it must be repeatable"
        return 25, f"200 in {secs*1000:.0f}ms, twice"
    finally:
        _kill(proc)


TESTS_LINE = re.compile(r"^\s*TESTS:\s*(\d+)\s*/\s*(\d+)\s*$", re.M)


def block_tests(path):
    """25 - suite passes, reports >= 3 tests, and is repeatable."""
    rc, out, err = run(["./scripts/test.sh"], cwd=path, timeout=180)
    if rc == 124:
        return 0, "scripts/test.sh did not finish within 180 seconds"
    if rc != 0:
        tail = (err or out).strip()[-300:]
        return 0, f"scripts/test.sh exited {rc}. Last output: {tail}"
    m = TESTS_LINE.search(out)
    if not m:
        return 0, ("scripts/test.sh did not print a line 'TESTS: n/n'. Every test "
                   "framework prints a summary in its own format; this one line "
                   "makes yours machine-readable.")
    passed, total = int(m.group(1)), int(m.group(2))
    if total < 3:
        return 0, f"TESTS: {passed}/{total} - at least 3 tests are required"
    if passed != total:
        return 0, f"TESTS: {passed}/{total} - the suite must pass"
    rc2, out2, _ = run(["./scripts/test.sh"], cwd=path, timeout=180)
    if rc2 != 0:
        return 0, ("passed once then failed on a second run - tests must not "
                   "depend on leftover state")
    ok, note = tests_can_fail(path)
    if not ok:
        return 0, note
    return 25, f"{total} tests, passing, repeatable; {note}"


# "Tests that can fail": delete the application in a scratch copy and run the
# suite again. A suite that still passes is not testing the application.
SRC_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".go", ".java", ".kt", ".cs",
           ".rs", ".rb", ".php", ".scala", ".swift", ".c", ".cc", ".cpp",
           ".h", ".ex", ".exs", ".dart", ".fs"}
SKIP_DIRS = {".git", "scripts", "node_modules", "vendor", "build", "dist",
             "target", ".venv", "venv", "__pycache__", ".github"}
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs"}
TEST_FILE = re.compile(r"^(test_.*|.*_test\.[A-Za-z]+|.*\.(test|spec)\.[A-Za-z]+"
                       r"|.*Tests?\.(java|kt|cs|php|scala|swift)|.*_spec\.rb"
                       r"|conftest\.py)$")


def is_test_file(rel):
    parts = rel.replace("\\", "/").split("/")
    if any(p in TEST_DIRS for p in parts[:-1]):
        return True
    return bool(TEST_FILE.match(parts[-1]))


def app_sources(path):
    found = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), path)
            if os.path.splitext(f)[1] in SRC_EXT and not is_test_file(rel):
                found.append(rel)
    return sorted(found)


def tests_can_fail(path):
    sources = app_sources(path)
    if not sources:
        return True, "no application source files recognised, so the delete check was skipped"
    scratch = tempfile.mkdtemp(prefix="m1-mutant-")
    try:
        copy = os.path.join(scratch, "repo")
        shutil.copytree(path, copy, symlinks=True)
        for rel in sources:
            try:
                os.remove(os.path.join(copy, rel))
            except OSError:
                pass
        rc, out, _ = run(["./scripts/test.sh"], cwd=copy, timeout=120)
        m = TESTS_LINE.search(out or "")
        still_green = rc == 0 and (not m or m.group(1) == m.group(2))
        if still_green:
            shown = ", ".join(sources[:3]) + (" ..." if len(sources) > 3 else "")
            return False, (f"the tests still pass with the application deleted "
                           f"({shown}). Tests that cannot fail are not tests - "
                           f"they must call your service.")
        return True, "and they fail when the application is removed"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


# Evidence of a merged pull request. GitHub knows for certain; the git history
# only knows for merge commits and GitHub's default squash subject "Title (#12)".
PULLS = {"source": None, "merged": []}


def repo_slug(url):
    m = re.search(r"github\.com[:/]+([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", url or "")
    return f"{m.group(1)}/{m.group(2)}" if m else None


def fetch_merged_pulls(slug):
    """Merged PRs from the GitHub API, or None if GitHub cannot be asked."""
    if not slug:
        return None
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "inf345-marker"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{slug}/pulls?state=closed&per_page=100"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except Exception:
        return None
    if not isinstance(data, list):
        return None
    return [{"number": p.get("number"), "title": p.get("title", "")}
            for p in data if p.get("merged_at")]


def merged_pr(path):
    if PULLS["source"] == "github":
        if PULLS["merged"]:
            return True, f"pull request #{PULLS['merged'][0]['number']} merged on GitHub"
        return False, ("no pull request has been merged on GitHub - open one from a "
                       "branch and merge it with any of the merge buttons")
    rc, out, _ = run(["git", "log", "--merges", "--oneline"], cwd=path)
    if rc == 0 and out.strip():
        return True, "merge commit in the history (GitHub not reachable)"
    rc, out, _ = run(["git", "log", "--format=%s"], cwd=path)
    if rc == 0 and re.search(r"\(#\d+\)\s*$", out, re.M):
        return True, "squash-merged pull request in the history (GitHub not reachable)"
    return False, ("no merged pull request found. GitHub could not be reached, and "
                   "the history shows no merge commit or squash-merge '(#n)' subject")


README_SECTIONS = [
    (r"(?im)^#{1,4}\s.*\b(what|about|overview|description)\b", "what it does"),
    (r"(?im)^#{1,4}\s.*\b(run|running|usage|start)\b", "how to run it"),
    (r"(?im)^#{1,4}\s.*\b(test|testing)\b", "how to test it"),
    (r"(?i)\bPORT\b", "which port it listens on"),
]


def block_repo(path):
    """25 - history, PR, .gitignore, README."""
    problems = []

    rc, out, _ = run(["git", "rev-list", "--count", "HEAD"], cwd=path)
    commits = int(out.strip() or 0) if rc == 0 else 0
    if commits < 5:
        problems.append(f"{commits} commits, at least 5 required")

    pr_ok, pr_note = merged_pr(path)
    if not pr_ok:
        problems.append(pr_note)

    if not os.path.isfile(os.path.join(path, ".gitignore")):
        problems.append("no .gitignore")
    else:
        rc, out, _ = run(["git", "ls-files"], cwd=path)
        junk = [f for f in out.splitlines()
                if re.search(r"(^|/)(node_modules|__pycache__|\.venv|venv|"
                             r"target|dist|build)/", f) or f.endswith(".pyc")]
        if junk:
            problems.append(f"build artefacts committed, e.g. {junk[0]}")

    readme = None
    for name in ("README.md", "readme.md", "README.MD"):
        p = os.path.join(path, name)
        if os.path.isfile(p):
            readme = open(p, encoding="utf-8", errors="replace").read()
            break
    if readme is None:
        problems.append("no README.md")
    else:
        missing = [label for pat, label in README_SECTIONS
                   if not re.search(pat, readme)]
        if missing:
            problems.append("README does not cover: " + ", ".join(missing))

    if problems:
        return 0, "; ".join(problems)
    return 25, f"{commits} commits, {pr_note}, README complete"


def _kill(proc):
    try:
        os.killpg(os.getpgid(proc.pid), 15)
        proc.wait(timeout=5)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except Exception:
            pass


# -------------------------------------------------------------------- main

GATES = [("repository", gate_repo),
         ("no credentials", gate_no_secrets),
         ("scripts/test.sh", gate_test_script)]

BLOCKS = [("runs", block_runs),
          ("healthz", block_healthz),
          ("tests", block_tests),
          ("repository quality", block_repo)]


def mark(path, as_json=False):
    report = {"gates": [], "blocks": [], "score": 0, "capped": False}

    for name, fn in GATES:
        ok, detail = fn(path)
        report["gates"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            report["capped"] = True

    if not report["capped"]:
        for name, fn in BLOCKS:
            pts, detail = fn(path)
            report["blocks"].append({"name": name, "points": pts, "detail": detail})
            report["score"] += pts

    if as_json:
        print(json.dumps(report, indent=2))
        return 0 if report["score"] == 100 else 1

    print()
    for g in report["gates"]:
        mark_ = "ok " if g["ok"] else "FAIL"
        print(f"  [gate {mark_}] {g['name']}: {g['detail']}")
    if report["capped"]:
        print("\n  A gate failed, so this milestone scores 0 regardless of "
              "everything else.\n\nSCORE: 0/100")
        return 1
    print()
    for b in report["blocks"]:
        print(f"  [ {b['points']:>2}/25 ] {b['name']}")
        print(f"            {b['detail']}")
    print(f"\nSCORE: {report['score']}/100")
    return 0 if report["score"] == 100 else 1


def main():
    ap = argparse.ArgumentParser(description="Mark INF 345 milestone 1.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--repo", help="clone this URL and mark it")
    src.add_argument("--path", help="mark this local directory")
    src.add_argument("--fetch-pulls", metavar="OWNER/REPO",
                     help="print the merged pull requests as JSON and exit")
    ap.add_argument("--pulls-json", help="use merged pull requests from this file "
                    "instead of asking GitHub (the course runner uses this)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.fetch_pulls:
        merged = fetch_merged_pulls(a.fetch_pulls)
        print(json.dumps({"slug": a.fetch_pulls, "merged": merged}))
        return 0 if merged is not None else 1

    if a.pulls_json:
        try:
            d = json.load(open(a.pulls_json))
            if d.get("merged") is not None:
                PULLS.update(source="github", merged=d["merged"])
        except Exception:
            pass

    if a.path:
        path = os.path.abspath(a.path)
        if PULLS["source"] is None:
            _, origin, _ = run(["git", "remote", "get-url", "origin"], cwd=path)
            merged = fetch_merged_pulls(repo_slug(origin.strip()))
            if merged is not None:
                PULLS.update(source="github", merged=merged)
        return mark(path, a.json)

    if PULLS["source"] is None:
        merged = fetch_merged_pulls(repo_slug(a.repo))
        if merged is not None:
            PULLS.update(source="github", merged=merged)

    tmp = tempfile.mkdtemp(prefix="m1-")
    try:
        rc, _, err = run(["git", "clone", "--quiet", a.repo, tmp], timeout=180)
        if rc != 0:
            print(f"::error::Could not clone {a.repo}. Is it public? {err.strip()[:200]}")
            return 1
        return mark(tmp, a.json)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())