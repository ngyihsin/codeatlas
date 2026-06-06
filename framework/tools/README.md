# Tools

Automation that keeps an instance honest and in sync with the framework. These are
**framework** files (in an instance they live in `.docforge/framework/tools/`).

| Tool | Job |
|---|---|
| `generate.sh` | Rebuild the generated registry in `INDEX.md` from `CONCEPTS.md` / `FLOWS.md`. `--check` for CI. |
| `update-framework.sh` | Refresh an instance's `.docforge/framework/` cache to a framework version (touches only the cache). |
| `check-doc-drift.sh` | Flag which notes cite code paths that changed in the codebase. |

## `generate.sh`

Rebuilds the `GENERATED:registry` block in an instance's `INDEX.md` — a deterministic
projection of the `## Concept:` and `## Flow:` entries (name, anchor, status). Authored
sections of `INDEX.md` are never touched.

```
framework/tools/generate.sh <instance-dir>          # rewrite the block
framework/tools/generate.sh --check <instance-dir>  # exit 1 if stale (CI gate)
```

Run it after editing concepts or flows. See `../schema/index.schema.md`.

## `update-framework.sh`

Refreshes the read-only framework cache an instance depends on.

```
framework/tools/update-framework.sh <instance-dir>
```

Then bump `template_version` in the instance's `HANDOFF.md` and read the
`CHANGELOG.md` migration notes for the versions you crossed. See `GOVERNANCE.md`
→ Flow B.

## `check-doc-drift.sh`

Flags which notes cite code paths that changed in the codebase. It does not prove
the docs are right — it narrows re-verification to exactly the entries at risk, so
drift control stops depending on someone remembering to run Phase 7.

### Run locally

```
NOTES_DIR=/path/to/notes CODEBASE=/path/to/codebase \
  framework/tools/check-doc-drift.sh origin/main
```

Exit `0` = nothing cited changed. Exit `1` = drift suspected; the output lists the
changed paths and the notes that cite them. Re-verify those entries and update each
`Last verified against commit:`.

### Run in CI (GitHub Actions example)

Add this to the **codebase** repository so every pull request that touches cited
code warns the author:

```yaml
# .github/workflows/doc-drift.yml
name: doc-drift
on: pull_request
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }        # full history so BASE_REF resolves
      - name: Check documentation drift
        run: |
          NOTES_DIR="docs/onboarding-notes" CODEBASE="." \
            docs/onboarding-notes/tools/check-doc-drift.sh "origin/${{ github.base_ref }}"
```

Make the job non-blocking (a warning) at first; promote it to a required check once
the notes are stable. Pair it with the manual re-confirmation pass in Phase 7 —
the script finds *what* drifted; a human or agent still decides whether the claim is
still true.
