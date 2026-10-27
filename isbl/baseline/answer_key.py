"""Answer key (the real buggy statements) read from a Defects4J source patch.

Defects4J's patches/N.src.patch transforms the FIXED version into the BUGGY version (applying it to the fixed
checkout gives the buggy source). In the unified diff, '+' lines are therefore lines of the buggy version.
Rule per contiguous change block:
  * block contains '+' lines  -> those lines (buggy-version numbering) are the buggy statements;
  * block only removes lines  -> the fix ADDED code (omission bug); the buggy statement is the first buggy line
                                 after the gap (same rule as before: "next line").
Used ONLY for evaluation, never by the localisation."""
import re

_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def answer_key_from_patch(patch_text, src_prefix="src/main/java/"):
    """Returns {(relative/File.java, line)}; files outside src_prefix (e.g. tests) are ignored."""
    stmts = set()
    cur = None
    new_ln = 0
    block_has_plus = False
    in_block = False
    pending_gap = False

    def close_block():
        nonlocal in_block, block_has_plus, pending_gap
        if in_block and not block_has_plus:
            pending_gap = True            # attach to the next buggy-version line
        in_block, block_has_plus = False, False

    for line in patch_text.splitlines():
        if line.startswith("diff --git") or line.startswith("--- ") and not in_block and cur is None:
            pass
        if line.startswith("+++ "):
            close_block()
            pending_gap = False
            path = line[4:].strip()
            path = path[2:] if path.startswith("b/") else path
            cur = path[len(src_prefix):] if path.startswith(src_prefix) else None
            continue
        if line.startswith("--- "):
            continue
        m = _HUNK.match(line)
        if m:
            close_block()
            pending_gap = False
            new_ln = int(m.group(3))
            continue
        if cur is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            if pending_gap:
                pending_gap = False
            in_block, block_has_plus = True, True
            stmts.add((cur, new_ln))
            new_ln += 1
        elif line.startswith("-") and not line.startswith("---"):
            in_block = True
        elif line.startswith("\\"):
            continue
        else:                                   # context line
            close_block()
            if pending_gap:
                stmts.add((cur, new_ln))
                pending_gap = False
            new_ln += 1
    close_block()
    return stmts
