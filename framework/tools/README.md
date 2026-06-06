# Tools

Automation that keeps an instance honest and in sync with the framework. These are
**framework** files (in an instance they live in `.docforge/framework/tools/`).

| Tool | Job |
|---|---|
| `check-index.sh` | Verify `INDEX.md`'s Knowledge Map covers every concept/flow in `CONCEPTS.md` / `FLOWS.md`. Read-only. |
| `update-framework.sh` | Refresh an instance's `.docforge/framework/` cache to a framework version (touches only the cache). |
| `check-doc-drift.sh` | Flag which notes cite code paths that changed in the codebase. |
| `build-symbol-index.sh` | **L1 code index:** build a symbol table + a token-budgeted "repo map" of the most-referenced symbols (universal-ctags + ripgrep). |
| `find-symbol.sh` | **L1 localization:** resolve a symbol → its definition `file → symbol` anchor + reference sites. |
| `generate-instance.sh` | **Auto-gen (deterministic half):** draft an instance from a checkout — copy scaffold + L1 index + seed structural map / entry points / candidate concepts / provenance into `DRAFT-SEED.md`. |

None of these tools modify your authored docs — they verify, report, or index.

## L1 structured-code layer (`build-symbol-index.sh`, `find-symbol.sh`)

The "structured code knowledge" layer from `docs/research/digital-colleague-kb.md`: give an
agent a structured map + a localization primitive so it finds code precisely instead of
loading the repo into context. Dependency-light (universal-ctags + ripgrep); the richer,
heavier upgrade is tree-sitter / LSP / SCIP / stack graphs.

```
# Build a symbol index + repo map for a codebase (writes <code>/.docforge/symbols/)
framework/tools/build-symbol-index.sh <codebase> [out_dir] [top_n]
#   -> tags.jsonl (all definitions), symbols.tsv, repomap.md (top-N by reference frequency)

# Localize a symbol (uses the prebuilt index if present, else runs ctags live)
framework/tools/find-symbol.sh <codebase> <symbol-name> [max_refs]
#   -> definition anchor(s) in `file -> symbol` form + reference sites
```

These produce/validate the framework's stable `file → symbol` anchors. Validated against real
source: `find-symbol redis/src dictFind` → `dict.c → dictFind` (matches the Redis instance);
`find-symbol pybind11/include type_caster` → `cast.h → type_caster` (matches the pybind11
instance). Requires `ctags` (universal-ctags) and `rg` on PATH.

## Auto-generation pipeline (`generate-instance.sh`)

The deterministic half of the generate → review → keep-fresh pipeline (full spec:
`../GENERATION.md`):

```
framework/tools/generate-instance.sh <codebase> <out_instance_dir>
```
Copies the scaffold, builds the L1 index, and seeds `DRAFT-SEED.md` with the mechanically
derivable facts (structural map, entry-point candidates, candidate concepts, provenance —
codebase commit + framework version), everything marked `◐`/TODO. The **generator agent** then
raises it to L3 using `find-symbol.sh`; the **owner reviews `◐ → ✓`** (CODEOWNERS); **drift CI**
(`check-doc-drift.sh`) regenerates affected sections when cited code changes. It never
fabricates understanding — it stages facts for the agent + owner. (Validated: drafts a full
Redis instance @4625b89; `src/server.c → main` surfaces as the entry point; `check-index`
passes on the draft.)

## `check-index.sh`

Verifies that every `## Concept:` and `## Flow:` authored in `CONCEPTS.md` /
`FLOWS.md` appears in the `INDEX.md` Knowledge Map. The Knowledge Map is authored (the
single source of truth); this linter never rewrites it.

```
framework/tools/check-index.sh <instance-dir>          # exit 1 if a concept/flow is missing
framework/tools/check-index.sh --check <instance-dir>  # same; --check accepted for CI symmetry
```

Run it after adding a concept or flow. See `../schema/index.schema.md`.

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
