# Changelog

All notable changes to the **framework** are recorded here. The version is in
`VERSION`. Format follows [Keep a Changelog](https://keepachangelog.com/); the project
uses [Semantic Versioning](https://semver.org/).

Each entry that requires existing instances to do work carries **Migration notes** —
read those for every version you cross when running `update-framework.sh`.

## [Unreleased]

## [0.1.0] — 2026-06-06

First versioned release. Establishes the three-plane architecture (framework /
scaffold / instance) and the governance flows.

### Added
- `framework/` plane: the versioned, read-only methodology — `STANDARD.md`,
  `ONBOARD-GUIDE.md`, `WRITING-STYLE.md`, `EXAMPLES.md`.
- `framework/AGENT-PROTOCOL.md`: the canonical behavioral rules for the authoring agent
  (extracted from the old `AGENT-warm-up.md`).
- `framework/schema/`: versioned contracts — `index.schema.md`, `doc-header.schema.md`,
  `tags.md`.
- `framework/MANIFEST.md`: the file-role taxonomy (framework / authored / generated /
  state).
- `framework/tools/`: `check-doc-drift.sh`, `generate.sh` (rebuild generated
  projections), `update-framework.sh` (refresh an instance's framework cache).
- `scaffold/` plane: the blank fill-in starting point; `AGENT-warm-up.md` is now thin
  and pins `template_version`.
- Generated projections (`CLAUDE.md`, `INDEX.md`) carry a "do not edit" banner and
  generate markers.
- Root governance: `GOVERNANCE.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `VERSION`.
- Worked reference instances under `examples/`: Redis (C) and pybind11 (C++/Python/CMake).

### Changed
- The repository is split from a single flat `template/` directory into `framework/`
  and `scaffold/` planes, separating the upstream methodology from the fill-in files.

### Migration notes (from a pre-0.1.0 flat `template/` copy)
- A pre-0.1.0 instance copied the whole flat `template/`. To adopt 0.1.0:
  1. Keep your authored files (`OVERVIEW`, `CONCEPTS`, `FLOWS`, `HOW-TO`,
     `OPEN-QUESTIONS`) and your state (`HANDOFF`, `ONBOARD-CHECKLIST`, `logs/`).
  2. Move the framework files out of your instance and into a `.docforge/framework/`
     cache via `update-framework.sh`; stop hand-editing them.
  3. Add `template_version: 0.1.0` to the `HANDOFF.md` state block.
  4. Run `generate.sh` to rebuild `CLAUDE.md` and `INDEX.md` as projections.
