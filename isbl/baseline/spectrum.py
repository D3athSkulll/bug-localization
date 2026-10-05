"""Coverage collection (JaCoCo via tools/runner/CoverageRunner), spectrum construction and reduction."""
import os
import subprocess


def collect_coverage(java, classes_dir, classpath, test_classes, out_file, jacoco_dir, runner_dir, timeout=1800):
    """Runs the tests under the JaCoCo agent, one coverage snapshot per test method. Returns out_file."""
    agent = os.path.join(jacoco_dir, "org.jacoco.agent-0.8.12-runtime.jar")
    jj = [os.path.join(jacoco_dir, j) for j in
          ("org.jacoco.core-0.8.12.jar", "asm-9.7.jar", "asm-commons-9.7.jar", "asm-tree-9.7.jar")] + [agent]
    cp = os.pathsep.join([runner_dir, classes_dir] + classpath + jj)
    cmd = [java, "-javaagent:%s=output=none" % agent, "-cp", cp, "CoverageRunner", classes_dir, out_file]
    cmd += list(test_classes)
    subprocess.run(cmd, check=True, timeout=timeout)
    return out_file


def parse_coverage(path):
    """-> list of (test_name, passed: bool, {file: set(lines)})"""
    tests, cur = [], None
    with open(path, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if p[0] == "T":
                cur = (p[1], p[2] == "PASS", {})
                tests.append(cur)
            elif p[0] == "C" and cur is not None:
                cur[2][p[1]] = set(int(x) for x in p[2].split(","))
    return tests


def build_spectrum(tests):
    """tests: output of parse_coverage. Returns {(file, line): (ef, ep, nf, np)} for every statement
    covered by at least one test (statements covered by no test get no spectrum entry)."""
    total_f = sum(1 for _, ok, _ in tests if not ok)
    total_p = sum(1 for _, ok, _ in tests if ok)
    ef, ep = {}, {}
    for _, ok, cov in tests:
        d = ep if ok else ef
        for fl, lines in cov.items():
            for ln in lines:
                d[(fl, ln)] = d.get((fl, ln), 0) + 1
    return {s: (ef.get(s, 0), ep.get(s, 0), total_f - ef.get(s, 0), total_p - ep.get(s, 0))
            for s in set(ef) | set(ep)}


def reduce_spectrum(spectrum, suspicious_files):
    keep = set(suspicious_files)
    return {s: v for s, v in spectrum.items() if s[0] in keep}


def reduce_tests(tests, suspicious_files):
    """Paper section II-B: delete coverage of statements outside the suspicious files, then delete test
    cases that no longer cover any statement. nf (all failed tests in the spectrum) is therefore counted
    on the reduced test set. Returns a new list in the parse_coverage format."""
    keep = set(suspicious_files)
    out = []
    for name, ok, cov in tests:
        c = {f: l for f, l in cov.items() if f in keep}
        if c:
            out.append((name, ok, c))
    return out


def parse_trigger_tests(path):
    """Defects4J trigger_tests file -> set of 'method(class)' names (the format used in the coverage file)."""
    out = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("--- "):
                cls, _, meth = line[4:].strip().partition("::")
                out.add("%s(%s)" % (meth, cls))
    return out


def keep_trigger_failures(tests, trigger):
    """Defects4J convention: a test counts as failing only if it is a documented trigger test. Any other failing
    test (it also fails on the fixed version: locale/JDK differences) is removed from the spectrum entirely.
    Returns (filtered_tests, removed_names)."""
    kept, removed = [], []
    for name, ok, cov in tests:
        if not ok and name not in trigger:
            removed.append(name)
        else:
            kept.append((name, ok, cov))
    return kept, removed


def parse_runner_stats(path):
    """The 'M' line written by CoverageRunner: where the JVM spent its time (ms)."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("M\t"):
                _, n, t, d, a, tot = line.rstrip("\n").split("\t")
                return {"tests": int(n), "test_exec_ms": int(t), "jacoco_dump_ms": int(d),
                        "jacoco_analyze_ms": int(a), "jvm_total_ms": int(tot)}
    return None
