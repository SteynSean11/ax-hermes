# CLAUDE.md — hermes-agent

Read `AGENTS.md` in this directory first; it is the authoritative agent guide for this repo.

## Workspace layout (T-WORKSPACE-100)

This repo follows the binding workspace rules in `~/projects/AGENTS.md` § Workspace layout
and WIP placement (authoritative copy: `~/projects/trax/trax/T-WORKSPACE-100/SPEC-WORKSPACE-100.md`):

- The repo root is not a dumping ground: no loose notes, logs, handoffs, scripts output or worktrees.
- Tracks owned by this repo live in `trax/T-<PRJKT>-<NNN>/`; all their WIP lives inside the track dir:
  git worktrees in `worktrees/<slug>/`, local notes and handoffs in `wip/` (both gitignored).
- Cross-repo, workspace-wide and Trax-system tracks live in `~/projects/trax/trax/`.
- No secrets in track directories.
