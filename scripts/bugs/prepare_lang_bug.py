"""Prepare Defects4J v1.4.0 Lang bugs for the ISBL pipeline on Windows (no Defects4J CLI, no SVN).

For bug N:
 1. find the FIXED commit in the upstream Apache history: commits whose message names the Jira issue and on whose
    tree Defects4J's src patch (fixed -> buggy) applies cleanly (earliest such commit);
 2. `git worktree` at that commit, apply the src patch -> buggy source, fixed-version tests (Defects4J convention);
 3. compile with Maven on JDK 8; test files that javac 8 cannot compile (and that are not relevant tests) are
    removed iteratively, the same workaround as for Lang-1;
 4. fetch the Jira bug report; run the Defects4J relevant tests under the per-test JaCoCo runner;
 5. SANITY: every Defects4J trigger test must fail in the coverage run, otherwise the bug is marked invalid.
Everything is recorded in data/bugs/Lang-N/manifest.json (status ok / reason for failure).
Usage: python scripts/bugs/prepare_lang_bug.py 2 3 4      or      python scripts/bugs/prepare_lang_bug.py all"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from isbl.baseline import spectrum  # noqa: E402

REPO = os.path.join(ROOT, "work-lang")
D4J = os.path.join(ROOT, "defects4j", "framework", "projects", "Lang")
JAVA_HOME = os.path.join(ROOT, "tools", "jdk8u504-b01")
WORK = os.path.join(ROOT, "work")
MVN = shutil.which("mvn") or "mvn"
MVN_FLAGS = ["-B", "-q", "-Drat.skip=true", "-Dcheckstyle.skip=true", "-Dfindbugs.skip=true", "-Dcobertura.skip=true",
             "-Dmaven.javadoc.skip=true", "-Dclirr.skip=true", "-Danimal.sniffer.skip=true"]


def env_jdk8():
    e = dict(os.environ)
    e["JAVA_HOME"] = JAVA_HOME
    e["PATH"] = os.path.join(JAVA_HOME, "bin") + os.pathsep + e["PATH"]
    return e


def run(cmd, cwd=None, env=None, timeout=900):
    p = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       universal_newlines=True, encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, p.stdout


def git(*args, **kw):
    return run(["git", "-C", kw.pop("cwd", REPO)] + list(args), **kw)


def commit_db_line(n):
    with open(os.path.join(D4J, "commit-db"), encoding="utf-8") as f:
        for line in f:
            p = line.strip().split(",")
            if p[0] == str(n):
                return p
    raise KeyError(n)


def patch_files(patch_path):
    with open(patch_path, encoding="utf-8", errors="replace") as f:
        return [l[6:].strip() for l in f if l.startswith("+++ b/")]


def patch_applies(commit, patch_path):
    """Does the (fixed -> buggy) patch apply cleanly to the tree of `commit`? Uses a scratch index, no checkout."""
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ)
        env["GIT_INDEX_FILE"] = os.path.join(td, "idx")
        rc, _ = run(["git", "-C", REPO, "read-tree", commit], env=env)
        if rc != 0:
            return False
        rc, _ = run(["git", "-C", REPO, "apply", "--cached", "--check", patch_path], env=env)
        return rc == 0


def find_fixed_commit(n, issue, patch_path):
    rc, out = git("log", "--all", "--format=%H", "-E", "--grep=%s([^0-9]|$)" % issue, "--reverse")
    cands = out.split() if rc == 0 else []
    tried = []
    for c in cands:
        tried.append(c[:9])
        if patch_applies(c, patch_path):
            return c, "grep", tried
    files = patch_files(patch_path)
    if files:                                           # fallback: earliest commit touching the file where it applies
        rc, out = git("log", "--all", "--format=%H", "--reverse", "--", files[0])
        for c in (out.split() if rc == 0 else [])[:400]:
            if c in cands:
                continue
            if patch_applies(c, patch_path):
                return c, "history-fallback", tried
    return None, "no-candidate", tried


def fetch_report(issue, dest):
    url = "https://issues.apache.org/jira/rest/api/2/issue/%s?fields=summary,description" % issue
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "isbl-research"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode("utf-8"))
            with open(dest, "w", encoding="utf-8") as f:
                json.dump({"key": issue, "fields": {"summary": d["fields"].get("summary"),
                                                    "description": d["fields"].get("description")}}, f)
            return True
        except Exception as e:                          # noqa: BLE001
            err = str(e)
            time.sleep(1.5)
    return err


def compile_with_workaround(wt, protected_classes, log):
    removed = []
    env = env_jdk8()
    for attempt in range(10):
        rc, out = run([MVN] + MVN_FLAGS + ["-DskipTests", "test-compile"], cwd=wt, env=env, timeout=1200)
        if rc == 0:
            return True, removed
        bad = {os.path.normpath(m.lstrip("/")) for m in re.findall(r"\[ERROR\]\s+(\S+\.java):\[\d+,\d+\]", out)}
        if not bad:
            log.append(out[-1500:])
            return False, removed
        progressed = False
        for f in bad:
            norm = f.replace("\\", "/")
            if "/src/main/" in norm:
                log.append("main source does not compile: " + norm)
                return False, removed
            cls = os.path.splitext(os.path.basename(norm))[0]
            if cls in protected_classes:
                log.append("required test does not compile: " + norm)
                return False, removed
            if os.path.exists(f):
                os.remove(f)
                removed.append(norm.split("/src/test/java/")[-1])
                progressed = True
        if not progressed:
            log.append(out[-1500:])
            return False, removed
    return False, removed


def prepare(n, force=False):
    t0 = time.time()
    bdir = os.path.join(ROOT, "data", "bugs", "Lang-%d" % n)
    os.makedirs(bdir, exist_ok=True)
    man_path = os.path.join(bdir, "manifest.json")
    if os.path.exists(man_path) and not force:
        m = json.load(open(man_path))
        if m.get("status") in ("ok", "failed"):
            return m
    m = {"bug_id": n, "status": "failed", "reason": None, "notes": []}

    def finish(reason=None, status="failed"):
        m["status"], m["reason"] = status, reason
        m["prepare_sec"] = round(time.time() - t0, 1)
        with open(man_path, "w") as f:
            json.dump(m, f, indent=2)
        return m

    p = commit_db_line(n)
    issue = p[3]
    m["issue"] = issue
    # the Defects4J clone on Windows has CRLF patch files (core.autocrlf); normalise to LF so git apply matches the blobs
    patch = os.path.join(bdir, "src.patch")
    with open(os.path.join(D4J, "patches", "%d.src.patch" % n), "rb") as f:
        raw = f.read().replace(b"\r\n", b"\n")
    with open(patch, "wb") as f:
        f.write(raw)
    fixed, how, tried = find_fixed_commit(n, issue, patch)
    m["fixed_commit_search"] = {"method": how, "grep_candidates_tried": tried}
    if not fixed:
        return finish("no upstream commit found where the Defects4J patch applies")
    m["fixed_commit"] = fixed
    # worktree
    wt = os.path.join(WORK, "Lang-%d" % n)
    if os.path.exists(wt):
        git("worktree", "remove", "--force", wt)
        shutil.rmtree(wt, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    for attempt in range(5):
        rc, out = run(["git", "-c", "core.autocrlf=false", "-C", REPO, "worktree", "add", "--detach", wt, fixed])
        if rc == 0:
            break
        time.sleep(2)
    else:
        return finish("git worktree failed: " + out[-300:])
    rc, out = run(["git", "-c", "core.autocrlf=false", "-C", wt, "apply", patch])
    if rc != 0:
        return finish("patch did not apply in worktree: " + out[-300:])
    pf = patch_files(patch)
    rc, _ = git("diff", "--quiet", fixed + "^", "--", *pf, cwd=wt)
    m["buggy_equals_parent_of_fix_commit"] = (rc == 0)
    if not os.path.exists(os.path.join(wt, "pom.xml")):
        return finish("no pom.xml in this revision (Ant-only build is not supported here)")
    # relevant / trigger tests
    rel = [l.strip() for l in open(os.path.join(D4J, "relevant_tests", str(n)), encoding="utf-8") if l.strip()]
    trig_file = os.path.join(D4J, "trigger_tests", str(n))
    trig = spectrum.parse_trigger_tests(trig_file)
    protected = {c.split(".")[-1] for c in rel}
    log = []
    ok, removed = compile_with_workaround(wt, protected, log)
    m["excluded_test_files"] = removed
    if not ok:
        return finish("compile failed: " + " | ".join(log)[:600])
    cp_file = os.path.join(bdir, "cp.txt")
    rc, out = run([MVN] + MVN_FLAGS + ["dependency:build-classpath", "-Dmdep.outputFile=" + cp_file], cwd=wt,
                  env=env_jdk8(), timeout=900)
    if rc != 0 or not os.path.exists(cp_file):
        return finish("classpath resolution failed: " + out[-300:])
    ok = fetch_report(issue, os.path.join(ROOT, "data", "bug_reports", "Lang-%d.json" % n))
    if ok is not True:
        return finish("bug report not available from Jira (%s)" % ok)
    # tests present?
    tdir = os.path.join(wt, "target", "test-classes")
    present = [c for c in rel if os.path.exists(os.path.join(tdir, c.replace(".", os.sep) + ".class"))]
    m["relevant_test_classes"], m["relevant_test_classes_present"] = len(rel), len(present)
    if not present:
        return finish("no relevant test class compiled")
    cov_dir = os.path.join(ROOT, "data", "coverage")
    os.makedirs(cov_dir, exist_ok=True)
    cov = os.path.join(cov_dir, "Lang-%d_relevant.tsv" % n)
    cp = open(cp_file).read().strip().split(";")
    t1 = time.time()
    try:
        spectrum.collect_coverage(os.path.join(JAVA_HOME, "bin", "java"), os.path.join(wt, "target", "classes"),
                                  [tdir] + cp, present, cov, os.path.join(ROOT, "tools", "jacoco"),
                                  os.path.join(ROOT, "tools", "runner"), timeout=1500)
    except Exception as e:                              # noqa: BLE001
        return finish("coverage run failed: %s" % str(e)[:300])
    m["coverage_sec"] = round(time.time() - t1, 1)
    tests = spectrum.parse_coverage(cov)
    failing = {name for name, okk, _ in tests if not okk}
    m["num_tests"], m["num_failing_all"] = len(tests), len(failing)
    m["trigger_tests"] = sorted(trig)
    m["trigger_tests_failing"] = sorted(t for t in trig if t in failing)
    if not trig or not all(t in failing for t in trig):
        return finish("sanity check failed: trigger test(s) do not fail on this buggy checkout "
                      "(failing: %d, trigger: %d)" % (len(failing), len(trig)))
    # config
    cfg = json.load(open(os.path.join(ROOT, "configs", "lang1_k50.json")))
    cfg.update(bug_id=n, repo="work/Lang-%d" % n, classpath_file="data/bugs/Lang-%d/cp.txt" % n,
               coverage_file="data/coverage/Lang-%d.tsv" % n, buggy_commit=fixed + "+src.patch (reverse)",
               fixed_commit=fixed, bug_report="data/bug_reports/Lang-%d.json" % n, test_classes=present,
               trigger_tests_file="defects4j/framework/projects/Lang/trigger_tests/%d" % n,
               answer_key_patch="data/bugs/Lang-%d/src.patch" % n)
    os.makedirs(os.path.join(ROOT, "configs", "bugs"), exist_ok=True)
    with open(os.path.join(ROOT, "configs", "bugs", "Lang-%d.json" % n), "w") as f:
        json.dump(cfg, f, indent=2)
    return finish(None, "ok")


def main(argv):
    force = "--force" in argv
    ids = [a for a in argv[1:] if not a.startswith("--")]
    ns = list(range(1, 66)) if ids == ["all"] else [int(a) for a in ids]
    for n in ns:
        m = prepare(n, force=force)
        print("Lang-%-3d %-6s %s%s" % (n, m["status"], (m.get("reason") or "")[:140],
                                       "  (%.0fs)" % m.get("prepare_sec", 0)), flush=True)


if __name__ == "__main__":
    main(sys.argv)
