# Tools

Optional automation for keeping the notes honest. Doc-only setups can ignore this
directory; it becomes valuable once the codebase changes faster than you re-verify
by hand (Phase 7).

## `check-doc-drift.sh`

Flags which notes cite code paths that changed in the codebase. It does not prove
the docs are right — it narrows re-verification to exactly the entries at risk, so
drift control stops depending on someone remembering to run Phase 7.

### Run locally

```
NOTES_DIR=/path/to/notes CODEBASE=/path/to/codebase \
  template/tools/check-doc-drift.sh origin/main
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
