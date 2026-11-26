# Evidence: mar-audit Collect step, argv limit (E2BIG) fix

This answers MAR forensic finding 1, "no reproducible evidence". It contains:

- an offline regression test with no network or token: `.github/mar/test_mar_audit_collect.py`
- a read-only live replay against the real GitHub API: `.github/mar/replay_mar_audit_live.py`

Both scripts extract the `Collect merged PRs and their MAR status` step from a workflow file and run it with bash.

## Reproduce the offline test (bash, jq, PyYAML)

```
git show origin/beta:.github/workflows/mar-audit.yml > /tmp/old.yml
python3 .github/mar/test_mar_audit_collect.py /tmp/old.yml --expect-fail      # old step: exit 126
python3 .github/mar/test_mar_audit_collect.py .github/workflows/mar-audit.yml # new step: PASS
```

The stub `gh` returns 12 commits, each with a ~24 KiB PR payload and a ~24 KiB MAR status. That pushes the old step's `jq --argjson` argument past the 128 KiB `MAX_ARG_STRLEN` limit.

## Offline test output (2026-11-25)

```
$ python3 .github/mar/test_mar_audit_collect.py <origin/beta mar-audit.yml> --expect-fail
origin/beta:.github/workflows/mar-audit.yml: FAIL exit=126 stderr=['bash: line 40: /usr/bin/jq: Argument list too long']
exit=0

$ python3 .github/mar/test_mar_audit_collect.py .github/workflows/mar-audit.yml
.github/workflows/mar-audit.yml: PASS exit=0 payload_bytes=583185 commits=12 statuses=12
exit=0
```

## Live replay output (2026-11-25T13:51Z, read-only GitHub API)

For each case, the replay builds the event, runs the old and the new step on the same input, and feeds each payload to `scripts/mar_gate.py audit`. It opens no issues and writes no statuses.

- **Push mode:** a `push` event built from the PR's real commit list (`gh api pulls/<n>/commits`).
- **Single SHA:** a `workflow_dispatch` replay of one merge commit.

```
OLD  SteynSean11/ax-eco-context 657b19b rc=126 payload=0B ['bash: line 40: /usr/bin/jq: Argument list too long'] gate:
NEW  SteynSean11/ax-eco-context 657b19b rc=0 payload=199343B [] gate: breach=false count=0
OLD  SteynSean11/ax-eco-context b7cf39d rc=126 payload=0B ['bash: line 40: /usr/bin/jq: Argument list too long'] gate:
NEW  SteynSean11/ax-eco-context b7cf39d rc=0 payload=406545B [] gate: breach=false count=0
OLD  SteynSean11/ax-eco-context df0ec00 rc=0 payload=30741B [] gate: breach=false count=0
NEW  SteynSean11/ax-eco-context df0ec00 rc=0 payload=30741B [] gate: breach=false count=0
OLD  SteynSean11/ax-eco-context b15dba4 rc=0 payload=28940B [] gate: breach=true count=1
NEW  SteynSean11/ax-eco-context b15dba4 rc=0 payload=28940B [] gate: breach=true count=1
OLD  SteynSean11/ax-trax cf6260a rc=0 payload=28762B [] gate: breach=false count=0
NEW  SteynSean11/ax-trax cf6260a rc=0 payload=28762B [] gate: breach=false count=0
OLD  SteynSean11/ax-gateway 2c82598 rc=0 payload=33485B [] gate: breach=false count=0
NEW  SteynSean11/ax-gateway 2c82598 rc=0 payload=33485B [] gate: breach=false count=0
```

- **Push-mode cases:** 657b19b (#95, 8 commits) and b7cf39d (#98, 14 commits). The old step fails at the same line with the same error as production runs 45045546709 and 44955847150. The new step completes and the gate reports no breach.
- **Single-SHA cases:** old and new give identical payload sizes and verdicts. That includes the known #105 breach (breach=true, issue #106).

The fix diff is byte-identical across ax-eco-context, ax-trax, ax-gateway, ax-omega, ax-hermes and ax-mempalace. Only the `runs-on` line differs between those repos, and it lies outside the changed block.
