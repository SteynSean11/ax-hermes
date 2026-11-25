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

## Disabled upstream workflows

**Context:** `RUNBOOK-INFRA-700-001`, gate GC, step C4. Upstream workflows
that need secrets this fork lacks, or that enforce NousResearch process,
are **disabled, not deleted**: each one is renamed with `git mv` to
`<name>.yml.disabled`, and its content is unchanged. GitHub Actions loads
only `*.yml` and `*.yaml` from `.github/workflows/`, so a `.disabled` file
is inert. An upstream sync shows a clean rename and keeps the original
content available.

Evidence was collected on 2026-11-25:

- **Repo secrets (names only):** `CLAUDE_CODE_OAUTH_TOKEN`.
- **Repo variables:** `MAR_REQUIRED_WORKFLOWS`.
- **Branches:** `beta` only. There is no `main` branch on this fork.
- **Recent runs:** `gh run list --workflow <file> -L 5`. Sub-workflows
  that are called through `ci.yml` (`workflow_call`) have no runs of their
  own, so their evidence comes from the jobs inside the `CI` runs on
  PR #4 and PR #5.

| File | Classification | Reason | Re-enable |
|---|---|---|---|
| `contributor-check.yml` | disable-upstream-only | Enforces upstream contributor attribution against `origin/main`. The fork has no `main`, so on PR #5 the job fails with `fatal: Not a valid object name origin/main` (exit 128). This supersedes the "Known gap" section above. | `git mv` it back to `.yml`. Restore the `contributor-check` job in `ci.yml` and its entries in the `comment-live` and `all-checks-pass` `needs:`. Point `origin/main` at `origin/beta` first |
| `history-check.yml` | disable-upstream-only | Requires a common ancestor with upstream `origin/main`. `beta` is an orphan history and `main` does not exist, so it fails on every PR ("This PR has no common ancestor with main") | Same as above, for the `history-check` job. Only useful after a rebase onto upstream `main` |
| `review-labels.yml` | disable-upstream-only | Upstream maintainer gate: any CI-sensitive change needs the `ci-reviewed` label. It failed on PR #5. On this fork, MAR is the review gate | `git mv` it back. Restore the `review-labels` job in `ci.yml` and its `needs:` entries in `comment-live` and `all-checks-pass` |
| `label-rerun.yml` | disable-upstream-only | Companion to `review-labels.yml`: it reruns CI when `ci-reviewed` is added. It has no purpose without that gate | `git mv` it back together with `review-labels.yml` |
| `deploy-site.yml` | disable-needs-secret | Deploys upstream's docs site through Vercel. It needs `VERCEL_DEPLOY_HOOK`, `APP_PRIVATE_KEY` and `vars.APP_CLIENT_ID`, which are all absent, and its jobs are guarded to `NousResearch/hermes-agent`. It triggers on `main` pushes and releases, and has no runs here | Add the secrets and the variable, drop the repo guard, then `git mv` it back |
| `docker.yml` | disable-needs-secret | Builds and publishes `nousresearch/hermes-agent` to Docker Hub. It needs `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`, and every job is guarded to `NousResearch/hermes-agent`, so all three jobs were `skipped` on PR #4 and PR #5. The `docker` job is removed from `ci.yml`. `tests/docker/` only ran from this workflow, so it never ran on this fork | Set `IMAGE_NAME`, add the secrets, drop the repo guard, `git mv` it back, then restore the `docker` job in `ci.yml` and `ci-timings` `needs:` |
| `js-autofix.yml` | disable-needs-secret | Pushes eslint autofix PRs from `main` with a GitHub App token. It needs `APP_PRIVATE_KEY` and `vars.APP_CLIENT_ID`, and triggers on `main` only. It has no runs here | Add the App credentials, retarget to `beta`, then `git mv` it back |
| `publish-e2e-evidence.yml` | disable-needs-secret | Runs after every `CI` completion. It needs `GH_IMAGE_SESSION_TOKEN` in the `gh-image` environment. **It failed on all 5 recent runs** with `GH_SESSION_TOKEN is required` | Add the `gh-image` environment and the secret, then `git mv` it back |
| `skills-index.yml` | disable-needs-secret | Builds upstream's skills index, which feeds `deploy-site.yml`. It needs `APP_PRIVATE_KEY` and `vars.APP_CLIENT_ID`, and is guarded to `NousResearch/hermes-agent`. It ran twice a day as a `skipped` no-op (5 of 5 recent runs) | Re-enable together with `deploy-site.yml` |
| `skills-index-freshness.yml` | disable-needs-secret | Probes upstream's live `hermes-agent.nousresearch.com` index and opens issues. It uses the `trusted-automation` environment, is guarded to `NousResearch/hermes-agent`, and ran every 4 hours as a `skipped` no-op (5 of 5 recent runs) | Re-enable together with `skills-index.yml` |

Kept (not renamed):

| File | Classification | Evidence |
|---|---|---|
| `ci.yml` | keep-but-fix | The orchestrator. The only edit removes the `uses:` calls and `needs:` entries for the disabled sub-workflows. A dangling `uses: ./.github/workflows/<x>.yml` would make the entire `CI` workflow fail to load |
| `mar-review.yml`, `mar-audit.yml` | keep | They produce the required `MAR` check and the post-merge audit. Recent runs are `success` |
| `security.yml` | keep | It produces the required `Gitleaks current-tree scan` and `Semgrep static analysis` checks. Recent runs are `success` |
| `osv-scanner.yml` | keep | The weekly schedule and the `CI` job are both `success` |
| `tests.yml` | keep | Slices 1–6 and 8 plus `e2e` pass. Slice 7/8 has a known failure that comes from the runner image; see below |
| `lint.yml`, `js-tests.yml`, `e2e-desktop.yml`, `docs-site-checks.yml`, `uv-lockfile-check.yml`, `infographic-check.yml`, `lockfile-diff.yml`, `docker-lint.yml`, `supply-chain-audit.yml` | keep | All were `success` in `CI` on PR #5. They need no secrets and run the fork's own code |

### Known failure: `Python tests / Run tests slice 7/8`

`tests/tools/test_execution_flag_detection.py::test_real_binaries_execute_leading_dash_program_payload[sort-args2-{bulk}-False]`
fails on every CI run since 2026-10-30 (PR #3 run 41000632328, PR #4 run 44127212733, PR #5 runs 45622144371 and 45629157508). The cause is
the runner image, not a fork regression:

- GitHub's `ubuntu-latest` now uses **Ubuntu 26.04**, where `/usr/bin/sort`
  is **uutils (rust-coreutils)**, not GNU coreutils.
- uutils `sort` rejects a leading-dash value for `--compress-program`
  (`error: unexpected argument '-p' found`, exit 2) and never runs the
  program. GNU `sort` (`/usr/bin/gnusort` on 26.04) runs it. The test
  asserts the GNU behaviour.
- The detector under test, `tools.approval`, stays **conservative**: it
  still flags `sort --compress-program -x`. Only the real-binary probe's
  premise no longer holds on this image. This is an upstream test, so it
  is documented here and not changed.

Because `tests` feeds `All required checks pass`, that aggregate stays red
until this is resolved upstream. It is not a required check: the required
checks are `MAR`, `Gitleaks current-tree scan` and `Semgrep static analysis`,
and `MAR_REQUIRED_WORKFLOWS=Security`.
