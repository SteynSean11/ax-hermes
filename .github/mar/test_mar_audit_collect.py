#!/usr/bin/env python3
"""Offline regression test for the mar-audit "Collect" step (argv size limit).

Runs the Collect step of a mar-audit workflow file against a stub ``gh`` that
returns large but valid API payloads, so no token or network is needed.

    python3 .github/mar/test_mar_audit_collect.py .github/workflows/mar-audit.yml

Exit 0: the step completes and writes a payload with the expected shape.
Exit 1: the step fails (before the fix: jq "Argument list too long", 126).

Requires bash, jq and PyYAML. Pass ``--expect-fail`` to assert that an older
workflow reproduces the failure.
"""

import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile

import yaml

STEP = "Collect merged PRs and their MAR status"
N_COMMITS = 12  # each commit's pulls payload is ~24 KiB -> ~290 KiB in total
STUB_GH = r"""#!/usr/bin/env bash
# Stub gh: one merged PR per commit, padded body; MAR status padded too.
path="$2"
pad=$(head -c 24000 /dev/zero | tr '\0' 'x')
pr='{"number":1,"merged_at":"2026-11-22T00:00:00Z","base":{"ref":"beta"}'
st='{"state":"success","statuses":[{"context":"MAR","state":"success"'
case "$path" in
  */pulls)
    sha="${path%/pulls}"; sha="${sha##*/}"
    printf '[%s,"head":{"sha":"head-%s"},"body":"%s"}]\n' "$pr" "$sha" "$pad"
    ;;
  */status*)
    printf '%s,"description":"%s"}]}\n' "$st" "$pad"
    ;;
  *) echo '{}' ;;
esac
"""


def collect_script(workflow: pathlib.Path) -> str:
    wf = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    for job in wf["jobs"].values():
        for step in job["steps"]:
            if step.get("name") == STEP:
                return step["run"]
    raise SystemExit(f"{workflow}: step '{STEP}' not found")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    expect_fail = "--expect-fail" in sys.argv
    workflow = pathlib.Path(args[0] if args else ".github/workflows/mar-audit.yml")
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = pathlib.Path(tmp)
        bindir = tmpd / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(STUB_GH, encoding="utf-8")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        shas = [f"{i:040x}" for i in range(1, N_COMMITS + 1)]
        event = tmpd / "event.json"
        event.write_text(
            json.dumps({"after": shas[-1], "commits": [{"id": s} for s in shas]}),
            encoding="utf-8",
        )
        env = dict(
            os.environ,
            PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}",
            REPO="example/repo",
            BASE="beta",
            EVENT="push",
            GITHUB_EVENT_PATH=str(event),
            RUNNER_TEMP=str(tmpd),
        )
        proc = subprocess.run(
            ["bash", "-c", collect_script(workflow)],
            env=env,
            capture_output=True,
            text=True,
        )
        payload = tmpd / "audit-payload.json"
        ok = proc.returncode == 0 and payload.exists()
        detail = f"exit={proc.returncode}"
        if ok:
            data = json.loads(payload.read_text(encoding="utf-8"))
            n_commits, n_statuses = len(data["commits"]), len(data["statuses"])
            ok = n_commits == N_COMMITS and n_statuses == N_COMMITS
            size = payload.stat().st_size
            detail += f" payload_bytes={size} commits={n_commits} statuses={n_statuses}"
        else:
            errs = [
                line
                for line in proc.stderr.splitlines()
                if "Argument list too long" in line
            ]
            detail += f" stderr={errs[:1]}"
    print(f"{workflow}: {'PASS' if ok else 'FAIL'} {detail}")
    if expect_fail:
        return 0 if not ok else 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
