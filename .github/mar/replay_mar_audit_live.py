#!/usr/bin/env python3
"""Replay the mar-audit "Collect" step against the real GitHub API (read-only).

Runs the old and the new workflow's step on the same input and feeds each
payload to ``scripts/mar_gate.py audit``. It opens no issues and writes no
statuses; ``gh`` must be authenticated with read access.

    replay_mar_audit_live.py OLD.yml NEW.yml REPO_ROOT SPEC...

SPEC is ``owner/repo@<sha>`` (workflow_dispatch mode) or
``owner/repo@<merge sha>:<file of commit shas>`` (push mode).
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

import yaml

STEP = "Collect merged PRs and their MAR status"


def script(path):
    wf = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    for job in wf["jobs"].values():
        for st in job["steps"]:
            if st.get("name") == STEP:
                return st["run"]
    raise SystemExit("step not found")


def run(label, wf_path, repo, sha, gate_repo, event_commits=None):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"mar-audit-{label}-"))
    env = dict(
        os.environ,
        REPO=repo,
        BASE="beta",
        EVENT="workflow_dispatch",
        INPUT_SHA=sha,
        HEAD_SHA=sha,
        RUNNER_TEMP=str(tmp),
    )
    if event_commits is not None:
        ev = tmp / "event.json"
        ev.write_text(
            json.dumps({"after": sha, "commits": [{"id": c} for c in event_commits]}),
            encoding="utf-8",
        )
        env.update(EVENT="push", GITHUB_EVENT_PATH=str(ev))
    env.pop("GH_TOKEN", None)
    p = subprocess.run(
        ["bash", "-c", script(wf_path)], env=env, capture_output=True, text=True
    )
    err = [line for line in p.stderr.splitlines() if "Argument list" in line][:1]
    payload = tmp / "audit-payload.json"
    size = payload.stat().st_size if payload.exists() else 0
    verdict = ""
    if p.returncode == 0:
        out = tmp / "out"
        g = subprocess.run(
            [
                sys.executable,
                os.path.join(gate_repo, "scripts/mar_gate.py"),
                "--github-output",
                str(out),
                "audit",
                "--payload-file",
                str(payload),
                "--findings",
                str(tmp / "findings.json"),
            ],
            capture_output=True,
            text=True,
        )
        verdict = (
            out.read_text(encoding="utf-8").replace("\n", " ")
            if out.exists()
            else g.stderr[-200:]
        )
    print(
        f"{label:4} {repo} {sha[:7]} rc={p.returncode} payload={size}B"
        f" {err} gate: {verdict}"
    )


if __name__ == "__main__":
    old, new, gate_repo = sys.argv[1:4]
    for spec in sys.argv[4:]:
        repo, rest = spec.split("@")
        if ":" in rest:
            sha, cfile = rest.split(":")
            commits = pathlib.Path(cfile).read_text(encoding="utf-8").split()
            run("OLD", old, repo, sha, gate_repo, commits)
            run("NEW", new, repo, sha, gate_repo, commits)
            continue
        run("OLD", old, repo, rest, gate_repo)
        run("NEW", new, repo, rest, gate_repo)
