# Fork CI notes — ax-hermes

This file records the ApexSigma CI baseline port applied to this fork, so
that a future upstream sync is a merge, not a re-derivation.

**Context:** `RUNBOOK-INFRA-700-001` (gate GC, finding C4) of
`apexsigma-eco-tools`. The audit recorded that `ax-hermes` and
`ax-mempalace` had no CI, no Security workflow, no MAR and no branch
protection, while being the intended daily-driver and collective-memory
repositories. This directory carries the shared baseline over.

## What changed

| Path | Origin | Notes |
|---|---|---|
| `workflows/mar-review.yml` | copied **byte-identical** from `ax-trax@origin/beta` | git blob `edd4a7a2043b0348844f2dd2cf5d001865c5bbaa` — the same blob as `ax-trax`, `ax-gateway`, `ax-omega` and `ax-eco-context` |
| `workflows/mar-audit.yml` | copied byte-identical from `ax-trax@origin/beta` | git blob `ff19a727b66cf509df70fb4eef003b636b6b4bd1` — the post-merge MAR audit (SPEC-MAR-003 §12 option D) |
| `workflows/security.yml` | **new** | Gitleaks + Semgrep. See "Why there is no OSV job here" below |
| `mar/prompt.md` | copied byte-identical from `ax-trax@origin/beta` | The MAR reviewer prompt contract |
| `mar/verdict.schema.json` | copied byte-identical from `ax-trax@origin/beta` | The MAR verdict schema |
| `scripts/mar_gate.py` | copied byte-identical from `ax-trax@origin/beta` | git blob `a5c9d3b7768341d5036bacc5d0a796ed4b18e202`. Pure decision logic; the workflow does all network I/O. Stdlib only, no new dependency |

Everything added is **additive**: upstream `origin/beta` has no
`.github/mar/` and no `scripts/mar_gate.py`, and no upstream file was
modified or renamed.

## What already existed

Unlike ax-mempalace, this fork already ships upstream's CI system on
`beta`:

- `.github/workflows/ci.yml` — the upstream orchestrator, named **`CI`**.
  It triggers on `pull_request` (all branches) and `push` to `main`, runs a
  change classifier (`scripts/ci/classify_changes.py`), and fans out to
  `tests.yml`, `lint.yml`, `js-tests.yml`, `e2e-desktop.yml`,
  `docs-site-checks.yml`, `history-check.yml`, `contributor-check.yml`,
  `uv-lockfile-check.yml`, `infographic-check.yml`, `lockfile-diff.yml`,
  `docker-lint.yml`, `docker.yml`, `supply-chain-audit.yml`,
  `review-labels.yml` and `osv-scanner.yml`.
- `.github/workflows/osv-scanner.yml` — upstream's own OSV scan, surfaced by
  the orchestrator as the `OSV scan` job.
- `scripts/run_tests.sh` and `scripts/run_tests_parallel.py` — upstream's
  hermetic test runner.

**No new CI job was added.** Upstream's `CI` workflow already provides the
tests and lint, and it is already named `CI`, which is exactly what the MAR
gate needs (`MAR_REQUIRED_WORKFLOWS` defaults to `CI,Security`).

Note for maintainers: the working tree of this fork uses a **cone-mode
sparse checkout** (`.git/info/sparse-checkout`) that whitelists
`agent/`, `hermes_cli/`, `plugins/`, `tests/`, `tools/` and similar
directories. `.github/` and `scripts/` are **in the git tree** but may be
absent from the working tree until the sparse patterns are widened. A
missing `.github/` in a local checkout is a sparse-checkout artefact, not
evidence that the repo lacks workflows.

## Why there is no OSV job in `security.yml`

Upstream already scans the lockfiles:

```
osv-scanner:
  name: OSV scan
  uses: ./.github/workflows/osv-scanner.yml
```

That workflow scans `uv.lock`, `package-lock.json` and
`website/package-lock.json`, uploads SARIF and emits a `review_status`.
It is `fail-on-vuln: false` by upstream design.

A second OSV job over the same `uv.lock` inside `security.yml` would be
redundant, would double the CI minutes, and would fight upstream's SARIF
contract. So the split is:

| Concern | Provided by | Workflow name |
|---|---|---|
| OSV dependency scan | upstream `osv-scanner.yml` | `CI` (the `OSV scan` job) |
| Committed-secret scan | this port, `security.yml` | `Security` (`Gitleaks current-tree scan`) |
| Static analysis | this port, `security.yml` | `Security` (`Semgrep static analysis`) |

Both `CI` and `Security` must be green for MAR to run, so the dependency
scan is still part of the MAR evidence gate.

## Two deliberate differences from the shared `security.yml` baseline

### 1. Semgrep scans `.`, not `src`

The shared baseline scans a `src/` layout. This fork is a flat package:
Python sources at the repository root plus `agent/`, `hermes_cli/`,
`plugins/`, `tools/`, `gateway/`. There is no `src/` here, and
`semgrep --error src` aborts with `Invalid scanning root: src` (verified
locally).

### 2. Semgrep uses `--baseline-commit`

The upstream tree carries pre-existing findings under `p/security-audit`,
including WARNING-severity audit rules (`dynamic-urllib-use-detected`,
`insecure-hash-algorithm-sha1`) and a small number of ERROR rules
(`last-user-is-root`, `subprocess-shell-true`, `use-defused-xml`).

This is inherited upstream code, not a regression from this port. A C4
baseline that lands red teaches everyone to ignore the Security gate.

`--baseline-commit` compares against the integration branch and reports
only findings **not already present** on it. Existing debt is
grandfathered; any **new** issue still fails the build. `--severity ERROR`
additionally drops the WARNING-severity audit rules, which are advisory
("audit uses of urllib calls to ensure user data cannot control the URLs")
rather than defects.

Verified locally on this tree:

| Scenario | Result |
|---|---|
| baseline scan (`--baseline-commit origin/beta`) | 0 findings |
| a newly added file with a real `subprocess.run(..., shell=True)` call | **1 blocking finding** |

## Why `scripts/` and not `.github/`

`mar-review.yml` reads `scripts/mar_gate.py` from the **base branch** via a
sparse checkout, and `mar-audit.yml` reads it from the base-branch commit.
That path is fixed by the workflow contract in SPEC-MAR-003, so the file
cannot live under `.github/` without diverging from the byte-identical
`mar-review.yml` requirement. Upstream has no `scripts/mar_gate.py`, so
this is a pure addition and an upstream sync stays clean.

## What still needs an owner

- **Secret `CLAUDE_CODE_OAUTH_TOKEN`** on `SteynSean11/ax-hermes` — **set
  by the owner on 2026-10-30.** Without it the MAR workflow records
  `error` (never `success`): "MAR not run: CLAUDE_CODE_OAUTH_TOKEN is not
  set".

## Branch protection

`beta` is protected (applied 2026-10-30, after the baseline PR merged).

| Setting | Value |
|---|---|
| required checks | `MAR`, `Gitleaks current-tree scan`, `Semgrep static analysis` |
| `enforce_admins` | `true` |
| required approving reviews | 0 |
| force pushes / deletions | blocked |

**Why `Security` but not `CI`.** This fork inherits upstream's CI
orchestrator, which has pre-existing failures unrelated to the ApexSigma
baseline:

- `tests/tools/test_execution_flag_detection.py::test_real_binaries_execute_leading_dash_program_payload`
  — verified failing on the base commit with the C4 port's changes
  stashed, so it is upstream's, not the port's
- a Playwright Desktop E2E timeout (`background dot should appear`)

Requiring `CI` would deadlock every PR. The two surfaces this fork owns —
the committed-secret scan and the static analysis — are the `Security`
workflow's jobs, and both are green.

When this branch is re-based onto upstream `main` (which restores the
packages the current test suite imports), add the `CI` requirement back.

## Known gap: the contributor attribution check enumerates the whole history

Upstream's `contributor-check.yml` computes its merge base against
`origin/main`:

```sh
MERGE_BASE=$(git merge-base origin/main HEAD)
NEW_EMAILS=$(git log ${MERGE_BASE}..HEAD --format='%ae' --no-merges | sort -u)
```

On this fork `beta` and `main` have **unrelated histories** — `beta` is a
2-commit orphan (a squashed upstream snapshot `b4f8c491d` plus one
ApexSigma commit `61ff50abd`), while `main` is upstream's own line. There
is no merge base, so `MERGE_BASE` is empty and `git log ..HEAD` resolves
to `git log HEAD`: **every author reachable from HEAD**, not just the
PR's new commits.

That set is three emails, and two are handled by upstream's own rules:

| Email | Handling |
|---|---|
| `307254004+hermes-seaeye[bot]@users.noreply.github.com` | skipped (bot) |
| `steynsean11@gmail.com` | mapped via `contributors/emails/` |
| `sean.steyn@caffe.co.za` | mapped via `contributors/emails/` |

Both mappings were added with upstream's own tool,
`scripts/add_contributor.py`. The upstream check is **not** modified —
its `origin/main` merge base is correct for upstream, where `main` is
the default branch; it is this fork's unrelated-history layout that
widens the email set, and the mapping is the fix upstream's workflow
prescribes for an unmapped email.

The check only runs on PRs that touch `.github/` (the change classifier
treats any `.github/` change as CI-sensitive), so it was skipped on every
PR before the branch-protection notes were added.

## Integration branch

`beta` is the integration branch. Upstream's default branch is `main`;
`beta` matches the other four ApexSigma repositories and is where the
ApexSigma-side work lands. Upstream's `main` workflows are left untouched.
