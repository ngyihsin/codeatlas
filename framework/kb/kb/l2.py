"""
kb.l2 — L2 explanation generator (the summary *runner*).

Turns L1's mechanical index into reviewed-quality English explanations, one per
node, by spawning an **AI-agent executable** (Claude Code in headless mode) as a
subprocess and feeding it the real source. It is the piece that was previously
only a schema + a lint gate; this is the generator that actually produces the
summaries the gate checks.

Design (matches docs/research/digital-colleague-kb-spec.md, Part 2 "L2"):

  - bottom-up, bounded scope: a *leaf* (file) is summarized from its full source;
    a *module* is summarized only from its children's `fold`s (token-cheap, and
    it is what the incremental firewall keys on) — never from the children's full
    code.
  - evidence discipline: the prompt forces `[Lxx]` citations + an `evidence_level`
    declaration; leaf summaries claim `code` and must cite real lines, synthesis
    summaries claim `inferred` (derived from child folds).
  - lint is a *control loop*, not just a gate: every generated summary is run
    through kb.lint; on failure the exact errors are fed back to the agent and it
    retries. Only lint-clean summaries land in summaries.jsonl (confidence
    `draft`); anything that can't pass after N attempts is quarantined for a human
    and never enters the trusted set. L2 is never auto-trusted — module-owner
    review promotes `draft` -> `reviewed`.
  - freshness: each node's inputs are content-hashed (kb.incremental.input_hash);
    an unchanged node reuses its cached summary, so re-runs only pay for the dirty
    sub-tree.

The model is pluggable behind `Backend`:
  - ClaudeCodeBackend — spawns `claude -p ... --output-format json --tools ""`.
  - CommandBackend     — any other agent executable (prompt on argv or stdin).
  - MockBackend        — deterministic, for tests/CI (no network, no spawn).

CLI:
  python -m kb.l2 build <l1_out_dir> <code_root> <out_dir> [--backend claude|cmd]
      [--cmd "TEMPLATE"] [--model NAME] [--limit N] [--only SUBPATH]
      [--max-bytes 20000] [--attempts 3] [--no-incremental]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

from . import incremental
from .lint import lint_summary

# --------------------------------------------------------------------------- #
# Backends (the pluggable model)                                              #
# --------------------------------------------------------------------------- #


class BackendError(RuntimeError):
    """A backend failed to produce text (spawn/timeout/protocol error)."""


class Backend:
    """Produce assistant text for a prompt. Implementations must be side-effect free."""

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        raise NotImplementedError

    @property
    def cost_usd(self) -> float:
        return 0.0


class ClaudeCodeBackend(Backend):
    """Spawn Claude Code headlessly. Pure text-gen: all tools disabled, JSON out.

    Parses the v2.x result envelope: {"subtype":"success","is_error":false,
    "result":"<assistant text>","total_cost_usd":...}. Raises BackendError on a
    non-zero exit, a timeout, malformed JSON, or is_error=true.
    """

    def __init__(self, binary: str = "claude", model: str | None = None,
                 timeout: int = 120, extra_args: tuple[str, ...] = ()):
        self.binary = binary
        self.model = model
        self.timeout = timeout
        self.extra_args = tuple(extra_args)
        self._cost = 0.0

    @property
    def cost_usd(self) -> float:
        return self._cost

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        cmd = [self.binary, "-p", prompt, "--output-format", "json", "--tools", ""]
        if self.model:
            cmd += ["--model", self.model]
        if system:
            cmd += ["--append-system-prompt", system]
        cmd += list(self.extra_args)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=self.timeout)
        except subprocess.TimeoutExpired as e:
            raise BackendError(f"claude timed out after {self.timeout}s") from e
        except FileNotFoundError as e:
            raise BackendError(f"agent binary not found: {self.binary!r}") from e
        if proc.returncode != 0:
            raise BackendError(
                f"claude exited {proc.returncode}: {proc.stderr.strip()[:300]}")
        try:
            env = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise BackendError(
                f"claude stdout not JSON: {proc.stdout.strip()[:200]}") from e
        if env.get("is_error") or env.get("subtype") != "success":
            raise BackendError(
                f"claude reported error: subtype={env.get('subtype')} "
                f"{str(env.get('result'))[:200]}")
        self._cost += float(env.get("total_cost_usd") or 0.0)
        return str(env.get("result", ""))


class CommandBackend(Backend):
    """Any agent executable. `template` may contain {prompt}; if it doesn't, the
    prompt is piped on stdin. Stdout is returned verbatim (set output as plain
    text in the underlying tool)."""

    def __init__(self, template: str, timeout: int = 120):
        import shlex
        self.argv = shlex.split(template)
        self.timeout = timeout
        self._uses_placeholder = any("{prompt}" in a for a in self.argv)

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        full = prompt if system is None else f"{system}\n\n{prompt}"
        if self._uses_placeholder:
            argv = [a.replace("{prompt}", full) for a in self.argv]
            stdin = None
        else:
            argv, stdin = self.argv, full
        try:
            proc = subprocess.run(argv, input=stdin, capture_output=True,
                                  text=True, timeout=self.timeout)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise BackendError(str(e)) from e
        if proc.returncode != 0:
            raise BackendError(f"command exited {proc.returncode}: "
                               f"{proc.stderr.strip()[:300]}")
        return proc.stdout


class MockBackend(Backend):
    """Deterministic backend for tests/CI. `responder(prompt, attempt)` -> text."""

    def __init__(self, responder):
        self.responder = responder
        self.calls = 0

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        out = self.responder(prompt, self.calls)
        self.calls += 1
        return out


# --------------------------------------------------------------------------- #
# Prompts                                                                      #
# --------------------------------------------------------------------------- #

_SYSTEM = (
    "You document C/C++ ML-runtime code for a machine-read knowledge base. "
    "Be terse and factual. Never guess: if you cannot see it in the provided "
    "source, do not claim it. Output ONLY a single JSON object, no prose, no "
    "code fences."
)

_SCHEMA_RULES = (
    'Return JSON with exactly these keys:\n'
    '  "fold": a label, AT MOST 20 characters.\n'
    '  "preview": one sentence (<= 200 chars).\n'
    '  "full": 1-4 sentences. Every factual claim about the code MUST cite the '
    'line it comes from as [Lnn] (or a range [Lnn-mm]) using the line numbers '
    'shown in the source. Cite ONLY line numbers that appear below.\n'
    '  "evidence_level": "{level}".\n'
)


def build_leaf_prompt(rel_path: str, source: str) -> str:
    numbered = "\n".join(f"{i:>4}| {ln}"
                         for i, ln in enumerate(source.splitlines(), 1))
    return (
        f"Summarize this source file: {rel_path}\n\n"
        + _SCHEMA_RULES.format(level="code")
        + 'Because evidence_level is "code", "full" MUST contain at least one '
        '[Lnn] citation to a real line below.\n\n'
        f"---- {rel_path} ----\n{numbered}\n---- end ----"
    )


def build_synthesis_prompt(name: str, child_folds: list[str]) -> str:
    kids = "\n".join(f"  - {f}" for f in child_folds)
    return (
        f"Summarize the module '{name}' from its children's one-line folds only "
        "(you cannot see their source). Do not invent line numbers.\n\n"
        + _SCHEMA_RULES.format(level="inferred")
        + '\nChildren:\n' + kids
    )


# --------------------------------------------------------------------------- #
# Parse + generate-with-repair (the lint control loop)                        #
# --------------------------------------------------------------------------- #

_JSON_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def parse_summary(text: str) -> dict:
    """Extract the JSON object from agent output (tolerant of fences/prose)."""
    m = _JSON_OBJ.search(text)
    if not m:
        raise ValueError(f"no JSON object in model output: {text[:160]!r}")
    return json.loads(m.group(0))


@dataclass
class GenResult:
    summary: dict
    status: str           # "clean" | "quarantined"
    attempts: int
    errors: list[str] = field(default_factory=list)


def generate_summary(prompt: str, *, backend: Backend, ident: str, path: str | None,
                     source_lines: int | None, symbol_names: set[str] | None,
                     attempts: int = 3) -> GenResult:
    """Generate, lint, and self-repair up to `attempts` times. Lint is the loop."""
    p, last, errs = prompt, {}, ["no attempt made"]
    for n in range(1, attempts + 1):
        raw = backend.generate(p, system=_SYSTEM)
        try:
            s = parse_summary(raw)
        except (ValueError, json.JSONDecodeError) as e:
            errs = [f"output not valid JSON: {e}"]
            p = prompt + f"\n\nYour previous reply was not valid JSON ({e}). " \
                         "Return ONLY the JSON object."
            continue
        s["id"] = ident
        if path is not None:
            s["path"] = path
        last = s
        errs = lint_summary(s, source_lines, symbol_names)
        if not errs:
            s.setdefault("confidence", "draft")
            return GenResult(s, "clean", n)
        # feed the exact lint failures back to the agent and retry
        p = (prompt + "\n\nYour previous answer FAILED these machine checks:\n"
             + "\n".join(f"  - {e}" for e in errs)
             + "\nReturn a corrected JSON object that passes all checks.")
    return GenResult(last, "quarantined", attempts, errs)


# --------------------------------------------------------------------------- #
# Orchestrator                                                                 #
# --------------------------------------------------------------------------- #

_SRC_EXT = (".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx")


def _iter_source_files(code_root: str, only: str | None, max_bytes: int):
    for dirpath, _dirs, files in os.walk(code_root):
        for fn in sorted(files):
            if not fn.endswith(_SRC_EXT):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, code_root)
            if only and not rel.startswith(only):
                continue
            try:
                if os.path.getsize(full) > max_bytes:
                    continue
            except OSError:
                continue
            yield rel, full


def build(l1_dir: str, code_root: str, out_dir: str, *, backend: Backend,
          limit: int | None = None, only: str | None = None,
          max_bytes: int = 20000, attempts: int = 3,
          use_incremental: bool = True) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    # symbol names (for the lint's backtick-symbol check) from L1, if present
    symbol_names: set[str] | None = None
    sp = os.path.join(l1_dir, "symbols.jsonl")
    if os.path.isfile(sp):
        symbol_names = {json.loads(l).get("name")
                        for l in open(sp, encoding="utf-8") if l.strip()}

    cache_path = os.path.join(out_dir, "l2_cache.json")
    cache = {}
    if use_incremental and os.path.isfile(cache_path):
        cache = json.load(open(cache_path, encoding="utf-8"))

    clean, quarantine, new_cache = [], [], {}
    folds_by_dir: dict[str, list[str]] = {}
    stats = {"generated": 0, "cached": 0, "quarantined": 0}

    files = list(_iter_source_files(code_root, only, max_bytes))
    if limit:
        files = files[:limit]

    # ---- leaves: one summary per source file ----
    for rel, full in files:
        source = open(full, encoding="utf-8", errors="ignore").read()
        h = incremental.input_hash(source, [])  # leaf: input is its own source
        cached = cache.get(rel)
        if use_incremental and cached and cached.get("hash") == h:
            s = cached["summary"]
            stats["cached"] += 1
        else:
            res = generate_summary(
                build_leaf_prompt(rel, source), backend=backend, ident=rel,
                path=rel, source_lines=source.count("\n") + 1,
                symbol_names=symbol_names, attempts=attempts)
            s = res.summary
            if res.status == "clean":
                stats["generated"] += 1
            else:
                stats["quarantined"] += 1
                quarantine.append({**s, "_errors": res.errors})
                new_cache[rel] = {"hash": h, "summary": s}
                continue
        new_cache[rel] = {"hash": h, "summary": s}
        clean.append(s)
        folds_by_dir.setdefault(os.path.dirname(rel) or ".", []).append(
            s.get("fold", ""))

    # ---- synthesis: one summary per directory, from child folds (firewall key) ----
    for d, child_folds in sorted(folds_by_dir.items()):
        ident = f"module:{d}"
        h = incremental.input_hash("", sorted(child_folds))  # firewall keys on folds
        cached = cache.get(ident)
        if use_incremental and cached and cached.get("hash") == h:
            s = cached["summary"]
            stats["cached"] += 1
        else:
            res = generate_summary(
                build_synthesis_prompt(d, child_folds), backend=backend,
                ident=ident, path=None, source_lines=None,
                symbol_names=symbol_names, attempts=attempts)
            s = res.summary
            if res.status == "clean":
                stats["generated"] += 1
            else:
                stats["quarantined"] += 1
                quarantine.append({**s, "_errors": res.errors})
                new_cache[ident] = {"hash": h, "summary": s}
                continue
        new_cache[ident] = {"hash": h, "summary": s}
        clean.append(s)

    # ---- write outputs ----
    with open(os.path.join(out_dir, "summaries.jsonl"), "w", encoding="utf-8") as f:
        for s in clean:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "quarantine.jsonl"), "w", encoding="utf-8") as f:
        for s in quarantine:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    json.dump(new_cache, open(cache_path, "w", encoding="utf-8"))

    report = {**stats, "summaries": len(clean), "cost_usd": round(backend.cost_usd, 4),
              "out": out_dir}
    return report


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #


def _make_backend(args) -> Backend:
    if args.backend == "claude":
        return ClaudeCodeBackend(model=args.model, timeout=args.timeout)
    if args.backend == "cmd":
        if not args.cmd:
            raise SystemExit("--backend cmd requires --cmd \"TEMPLATE\"")
        return CommandBackend(args.cmd, timeout=args.timeout)
    raise SystemExit(f"unknown backend: {args.backend}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="kb.l2")
    sub = ap.add_subparsers(dest="subcmd", required=True)  # not "cmd": --cmd would clobber it
    b = sub.add_parser("build", help="generate L2 summaries")
    b.add_argument("l1_dir"); b.add_argument("code_root"); b.add_argument("out_dir")
    b.add_argument("--backend", default="claude", choices=["claude", "cmd"])
    b.add_argument("--cmd", default=None)
    b.add_argument("--model", default=None)
    b.add_argument("--limit", type=int, default=None)
    b.add_argument("--only", default=None)
    b.add_argument("--max-bytes", type=int, default=20000)
    b.add_argument("--attempts", type=int, default=3)
    b.add_argument("--timeout", type=int, default=120)
    b.add_argument("--no-incremental", action="store_true")
    a = ap.parse_args(argv)
    if a.subcmd == "build":
        report = build(a.l1_dir, a.code_root, a.out_dir, backend=_make_backend(a),
                       limit=a.limit, only=a.only, max_bytes=a.max_bytes,
                       attempts=a.attempts, use_incremental=not a.no_incremental)
        print(json.dumps(report))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
