# framework/ — the versioned methodology (read-only)

This directory is the **framework** plane: the methodology that an instance *depends
on at a pinned version*. In a created instance it appears as a read-only cache under
`.docforge/framework/`, refreshed by `tools/update-framework.sh` — **never
hand-edited there.**

Edit these files only here, in the upstream repo, via `CONTRIBUTING.md` and `Flow A`
of `GOVERNANCE.md`.

## Contents

| File | Role |
|---|---|
| `STANDARD.md` | What "good" looks like: the bar, exemplars, the L0–L3 rubric |
| `ONBOARD-GUIDE.md` | The phase-by-phase process |
| `WRITING-STYLE.md` | Writing rules for human + agent readers |
| `AGENT-PROTOCOL.md` | The canonical behavioral rules for the authoring agent |
| `EXAMPLES.md` | Illustrative fragments (full instances live in `/examples`) |
| `MANIFEST.md` | The file-role taxonomy for the whole project |
| `schema/` | Versioned contracts: INDEX, doc header, tag vocabulary |
| `tools/` | `check-index.sh`, `update-framework.sh`, `check-doc-drift.sh` |
| `VERSION` | the framework version (ships inside the plane) |

## A note on references

Cross-references in these files use **bare filenames** (e.g., `CONCEPTS.md`,
`STANDARD.md`), because the framework is location-independent: the same logical doc
set is laid out one way in this repo and another way inside an instance. The physical
location of each file is recorded in `MANIFEST.md`. Do not hard-code relative paths
between planes.
