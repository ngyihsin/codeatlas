# Contributing

This repository is the **framework** for `docforge-onboard` — the methodology, the
scaffold, the schemas, and the tools. It is *not* a place for notes about a specific
codebase; those live in an instance inside the target codebase (see `GOVERNANCE.md`).

## What you can change here

| You are changing… | Plane | Notes |
|---|---|---|
| The quality bar, phases, writing rules | `framework/` | Must follow the meta-rule below |
| The blank starting files | `scaffold/` | Keep them honest stubs, not filled content |
| The contracts (INDEX/header/tags) | `framework/schema/` | Bump the schema version on incompatible change |
| The tools | `framework/tools/` | Keep them dependency-light and POSIX-friendly |
| A sample instance | `examples/` | Illustrative only; tag every claim `◐` |

## The meta-rule

A change to `framework/STANDARD.md` **must itself meet the bar it defines.** If you add
a requirement, the standard's own prose must satisfy it. The standard is the one
document allowed to grade itself.

## Process

1. Open a PR describing the change and which plane it touches.
2. Choose a SemVer bump (see `GOVERNANCE.md` → Flow A):
   - **major** if existing instances must do work → add **migration notes**.
   - **minor** for additive changes; **patch** for fixes/clarifications.
3. Update `framework/VERSION` and add a `CHANGELOG.md` entry.
4. If you touched `framework/schema/`, bump that schema's version too.
5. Run the checks before pushing:
   ```
   bash -n framework/tools/*.sh                       # scripts parse
   for d in scaffold examples/*-onboarding-notes; do  # INDEX covers all concepts/flows
     framework/tools/check-index.sh "$d"
   done
   ```
6. Keep cross-references as **bare filenames** (location-independent). The physical
   location of each file is recorded once in `framework/MANIFEST.md`; do not hard-code
   relative paths between planes.

## Style

All Markdown here follows `framework/WRITING-STYLE.md`: short sentences, active voice,
tables for comparisons, a diagram for any flow of three or more steps, and a stable
`file → symbol` anchor for every code claim.
