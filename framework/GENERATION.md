# Auto-Generation Pipeline (generate → review → keep fresh)

How an instance is **automatically drafted**, **owner-reviewed**, and **kept fresh** — the
"auto-generate, then each responsible colleague reviews" workflow. Grounded in the research
finding that no source claims grounding alone is enough: every generated claim is **grounded +
human-gated** (see `docs/research/digital-colleague-kb.md`).

## The loop

```
  build a draft            raise to L3                 gate                  keep fresh
  ────────────────         ─────────────────────       ─────────────        ──────────────────
  generate-instance.sh  →  generator agent      →      owner review    →     drift CI re-runs
  (deterministic seed)     (judgment: concepts/        (CODEOWNERS,          on cited-code change
                            flows/why, ◐ tags)          ◐ → ✓)               → regenerate section
```

Two halves, kept honest by the split:
- **Deterministic** (`generate-instance.sh`): facts that can be derived mechanically —
  structural map, entry-point candidates, candidate concepts (top symbols by reference
  frequency via the L1 index), stable `file → symbol` anchors, provenance. Never invents
  understanding.
- **Judgment** (the generator agent): which concepts are load-bearing, the *why*, the data
  structures, the flows. Everything it writes is tagged `◐` until verified.

## Step 1 — Draft (deterministic)

```
framework/tools/generate-instance.sh <codebase> <out_instance_dir>
```
Copies the scaffold, builds the L1 symbol index (`build-symbol-index.sh`), and writes
`DRAFT-SEED.md` (structural map + entry points + candidate concepts + provenance), pinning the
codebase commit and framework version.

## Step 2 — Raise to L3 (generator agent)

The agent reads `AGENT-warm-up.md` and runs the phases (`ONBOARD-GUIDE.md`), but **starts from
`DRAFT-SEED.md` instead of a blank repo**, and uses the L1 tools to stay grounded:
- `find-symbol.sh <codebase> <name>` → confirm/refresh each `file → symbol` anchor.
- `.docforge/symbols/repomap.md` → pick the load-bearing concepts.
- For each concept/flow it must hit the `STANDARD.md` L3 bar (data structure + *why* + worked
  API call; flow + error branch), tag every claim `◐`, and set `Last verified against commit:`
  to the seeded sha.
- It must **never fabricate**: if the *why* isn't recoverable, mark it `?` (the standard's rule).
  Run behavior where feasible to promote `◐ → ✓` (e.g. the ONNX Runtime instance was run).

## Step 3 — Owner review (the gate)

The draft is opened as a PR. **A human owner must approve before it is trusted** — the
research's universal pattern (grounding + a human gate). Enforce with `CODEOWNERS` in the host
repo, e.g.:

```
# .github/CODEOWNERS  (in the codebase or notes repo)
/docs/onboarding-notes/                @platform-team
/docs/onboarding-notes/runtime/        @qnn-team @htp-team
```

Review checklist (per entry): claim is correct against the cited anchor; `◐/✓/?` is honest;
invariants are right; no secrets; reads cleanly (`WRITING-STYLE.md`). The owner flips reviewed
claims `◐ → ✓` and ticks the maturity level in `ONBOARD-CHECKLIST.md`.

## Step 4 — Keep fresh (drift CI)

On every PR to the **codebase**, run the drift gate so docs can't silently rot:
```yaml
# .github/workflows/doc-drift.yml (in the codebase repo)
on: pull_request
jobs:
  drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: Flag notes citing changed code
        run: |
          NOTES_DIR="docs/onboarding-notes" CODEBASE="." \
            docs/onboarding-notes/.docforge/framework/tools/check-doc-drift.sh "origin/${{ github.base_ref }}"
```
When it fires, the generator agent regenerates only the affected sections (re-run
`find-symbol.sh` on the moved symbols, refresh anchors + provenance) and re-opens for owner
review. Also gate the notes repo with `check-index.sh` (Knowledge Map coverage) and
`bash -n` on the tools.

## Trust rules (non-negotiable)
- **Grounded + gated.** No claim ships without an anchor and an owner's `✓`.
- **Tag honestly.** `◐` (read), `✓` (run/authoritative), `?` (speculation). Never fabricate a
  rationale — `?` beats a confident guess.
- **Pin provenance.** Every entry records the codebase commit it was verified against; drift CI
  catches staleness.
- **Owner accountable.** `CODEOWNERS` names who keeps each area true (the Linux MAINTAINERS
  lesson from `STANDARD.md`).

## For ML-runtime codebases (QNN/SNPE/Hexagon/ExecuTorch/ONNX Runtime)
Seed per runtime with `generate-instance.sh`; the candidate concepts will surface the
op/kernel registry, the backend/EP/delegate interface, and the partitioner (the universal
extension points). The agent documents the two axes (**add an op** / **add a backend**) and the
"Life of an inference" flow; the owner (the team that owns that backend) reviews `◐ → ✓`. For
gated SDKs (QNN/SNPE), run the whole pipeline **inside the org** where the source lives.
