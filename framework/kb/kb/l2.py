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


def build_synthesis_prompt(name: str, children: list[dict]) -> str:
    # Synthesize from children's PREVIEWS (sentences), not their 20-char folds, so
    # the parent has real signal; ask it to cite the child file each claim came from
    # (provenance for drill-down). It cannot see source, so no [Lxx] lines.
    kids = "\n".join(f"  - {c.get('path')}: {c.get('preview', '')}" for c in children)
    return (
        f"Summarize the module '{name}' from its children's one-sentence previews "
        "(you cannot see their source). When you state what the module does, name the "
        "child file it comes from in parentheses, e.g. (math/clip.cc). Do NOT invent "
        "line numbers.\n\n"
        + _SCHEMA_RULES.format(level="inferred")
        + '\nChildren:\n' + kids
    )


_SYMBOL_KINDS = ("function", "method", "class", "struct")


def symbol_spans(file_syms: list[dict], total_lines: int) -> dict[str, tuple[int, int]]:
    """Per-symbol source span [start, end] using the same next-def heuristic as the
    call graph: a definition owns lines from its start to just before the next def."""
    ss = sorted(file_syms, key=lambda s: s.get("line", 0))
    spans: dict[str, tuple[int, int]] = {}
    for i, s in enumerate(ss):
        start = max(1, int(s.get("line", 1)))
        end = (int(ss[i + 1]["line"]) - 1) if i + 1 < len(ss) else total_lines
        spans[s["id"]] = (start, max(start, end))
    return spans


def build_symbol_prompt(rel: str, name: str, kind: str, source: str,
                        start: int, end: int) -> str:
    lines = source.splitlines()
    end = min(end, len(lines))
    numbered = "\n".join(f"{i:>4}| {lines[i - 1]}" for i in range(start, end + 1))
    return (
        f"Summarize the {kind} `{name}` defined in {rel} (lines {start}-{end}).\n\n"
        + _SCHEMA_RULES.format(level="code")
        + 'Because evidence_level is "code", "full" MUST contain at least one [Lnn] '
        'citation to a real line shown below (line numbers are the file\'s own).\n\n'
        f"---- {rel}::{name} ----\n{numbered}\n---- end ----"
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
                     attempts: int = 3, entail_source: str | None = None,
                     entail_samples: int = 1) -> GenResult:
    """Generate, lint, and self-repair up to `attempts` times. Lint is the loop.

    If `entail_source` is given, a second gate runs after lint: each cited claim is
    checked for entailment against its cited lines (kb.eval); unsupported claims are fed
    back so only claims actually supported by their citations ship. Raises entailment by
    construction at the cost of extra LLM calls."""
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
        if not errs and entail_source is not None:
            from . import eval as _eval        # lazy: avoid import cycle (eval imports l2)
            bad = _eval.unsupported_claims(str(s.get("full", "")), entail_source,
                                           backend, entail_samples)
            if bad:
                errs = [f"unsupported claim: {b}" for b in bad]
                p = (prompt + "\n\nThese claims are NOT entailed by the lines they cite:\n"
                     + "\n".join(f"  - {b}" for b in bad)
                     + "\nCite the exact supporting line for each, or weaken/remove the "
                       "claim. Return corrected JSON.")
                continue
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
          use_incremental: bool = True, granularity: str = "file",
          top_n: int = 8, entail: bool = False) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    # symbol records from L1, if present: names feed the lint's backtick check; full
    # records (with importance + line) feed per-symbol L2 (granularity="symbol").
    symbol_names: set[str] | None = None
    symbols: list[dict] = []
    sp = os.path.join(l1_dir, "symbols.jsonl")
    if os.path.isfile(sp):
        symbols = [json.loads(l) for l in open(sp, encoding="utf-8") if l.strip()]
        symbol_names = {s.get("name") for s in symbols}
    syms_by_path: dict[str, list[dict]] = {}
    if granularity == "symbol":
        for s in symbols:
            if s.get("kind") in _SYMBOL_KINDS:
                syms_by_path.setdefault(s.get("path"), []).append(s)

    cache_path = os.path.join(out_dir, "l2_cache.json")
    cache = {}
    if use_incremental and os.path.isfile(cache_path):
        cache = json.load(open(cache_path, encoding="utf-8"))

    clean, quarantine, new_cache = [], [], {}
    children_by_dir: dict[str, list[dict]] = {}
    stats = {"generated": 0, "cached": 0, "quarantined": 0}

    def _resolve(ident, h, gen):
        """(summary, status, errors): from cache when the hash matches, else generate.
        Cache entries carry their status so a hit re-routes exactly as the first run did
        — a quarantined summary is never silently reclassified as clean."""
        cached = cache.get(ident)
        if use_incremental and cached and cached.get("hash") == h:
            stats["cached"] += 1
            return cached["summary"], cached.get("status", "clean"), cached.get("errors", [])
        res = gen()
        stats["generated" if res.status == "clean" else "quarantined"] += 1
        return res.summary, res.status, res.errors

    def _emit(ident, h, summary, status, errors):
        """Record (with status) and route to clean/quarantine. Returns True iff clean.
        The single gate that keeps quarantined summaries out of the trusted set, even on
        a cache hit."""
        new_cache[ident] = {"hash": h, "summary": summary,
                            "status": status, "errors": errors}
        if status == "clean":
            clean.append(summary)
            return True
        quarantine.append({**summary, "_errors": errors})
        return False

    files = list(_iter_source_files(code_root, only, max_bytes))
    if limit:
        files = files[:limit]

    # ---- leaves: one summary per source file ----
    for rel, full in files:
        source = open(full, encoding="utf-8", errors="ignore").read()
        nlines = source.count("\n") + 1
        h = incremental.input_hash(source, [])  # leaf: input is its own source
        s, status, errors = _resolve(rel, h, lambda: generate_summary(
            build_leaf_prompt(rel, source), backend=backend, ident=rel,
            path=rel, source_lines=nlines,
            symbol_names=symbol_names, attempts=attempts,
            entail_source=(source if entail else None)))
        if not _emit(rel, h, s, status, errors):
            continue
        children_by_dir.setdefault(os.path.dirname(rel) or ".", []).append(
            {"path": rel, "fold": s.get("fold", ""), "preview": s.get("preview", "")})

        # ---- per-symbol leaves (granularity="symbol"): top-N by importance ----
        # The file summary above stays (feeds the module tree + is the fallback for
        # the long tail); important symbols additionally get a symbol-scoped summary.
        if granularity == "symbol" and rel in syms_by_path:
            file_syms = syms_by_path[rel]
            spans = symbol_spans(file_syms, nlines)
            ranked = sorted(file_syms, key=lambda x: -x.get("importance", 0.0))[:top_n]
            for sym in ranked:
                start, end = spans[sym["id"]]
                sh = incremental.input_hash("\n".join(
                    source.splitlines()[start - 1:end]), [])
                ss, status, errors = _resolve(sym["id"], sh, lambda: generate_summary(
                    build_symbol_prompt(rel, sym["name"], sym.get("kind", ""),
                                        source, start, end),
                    backend=backend, ident=sym["id"], path=rel,
                    source_lines=nlines,
                    symbol_names=symbol_names, attempts=attempts,
                    entail_source=(source if entail else None)))
                ss["scope"] = "symbol"
                _emit(sym["id"], sh, ss, status, errors)

    # ---- synthesis: one summary per directory, from child previews ----
    # Firewall keys on previews (sentences), not 20-char folds: a behavior change
    # that alters the meaning re-rolls the parent, instead of silently going stale.
    for d, kids in sorted(children_by_dir.items()):
        ident = f"module:{d}"
        h = incremental.input_hash("", sorted(k["preview"] for k in kids))
        s, status, errors = _resolve(ident, h, lambda: generate_summary(
            build_synthesis_prompt(d, kids), backend=backend,
            ident=ident, path=None, source_lines=None,
            symbol_names=symbol_names, attempts=attempts))
        _emit(ident, h, s, status, errors)

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
    b.add_argument("--granularity", default="file", choices=["file", "symbol"])
    b.add_argument("--top-n", type=int, default=8, help="symbols/file to summarize (symbol mode)")
    b.add_argument("--entail", action="store_true",
                   help="gate each summary on per-claim entailment (extra LLM calls)")
    b.add_argument("--no-incremental", action="store_true")
    a = ap.parse_args(argv)
    if a.subcmd == "build":
        report = build(a.l1_dir, a.code_root, a.out_dir, backend=_make_backend(a),
                       limit=a.limit, only=a.only, max_bytes=a.max_bytes,
                       attempts=a.attempts, use_incremental=not a.no_incremental,
                       granularity=a.granularity, top_n=a.top_n, entail=a.entail)
        print(json.dumps(report))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
