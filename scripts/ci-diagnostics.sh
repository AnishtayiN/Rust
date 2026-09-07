#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ci-diagnostics.sh — post the collected CI log tails to the head commit.
#
# Debugging a workflow run normally means opening the job log, but neither the
# Actions log nor the artifact store is reachable from every environment
# (sandboxes, restricted networks, no browser).  The REST API for commit
# comments is, so jobs tee the interesting command output into
# "$RUNNER_TEMP"/{step,verify,build}.log and call this script on failure, which
# turns those files into a single comment on the commit under test.
#
# Best effort by design: it always exits 0 so that a diagnostics hiccup can
# never mask the real error.
#
# Used by .github/workflows/ci.yml:
#   - name: Publish diagnostics
#     if: failure()
#     env: { GH_TOKEN: ${{ github.token }} }
#     run: bash scripts/ci-diagnostics.sh
# ---------------------------------------------------------------------------
set -uo pipefail

# $RUNNER_TEMP is a Windows path on Windows runners, which is what we want:
# the helper below hands the file to a native python.exe.
WORK_DIR="${RUNNER_TEMP:-/tmp}"
OUT="${DIAG_FILE:-$WORK_DIR/diag.md}"
LIMIT="${DIAG_BYTES:-45000}"

: > "$OUT"
for file in "$WORK_DIR/step.log" "$WORK_DIR/verify.log" "$WORK_DIR/build.log"; do
    [ -f "$file" ] || continue
    {
        echo "#### $(basename "$file")"
        echo '```text'
        tail -c "$LIMIT" "$file"
        echo ''
        echo '```'
    } >> "$OUT"
done

if [ ! -s "$OUT" ]; then
    echo "ci-diagnostics: nothing to report"
    exit 0
fi

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "ci-diagnostics: no python interpreter; printing the log instead" >&2
    tail -c 4000 "$OUT"
    exit 0
fi

# shellcheck disable=SC2086
"$PY" - "$OUT" <<'PYEOF' || echo "ci-diagnostics: the helper failed; ignoring"
import json, os, pathlib, sys, urllib.request

body = pathlib.Path(sys.argv[1]).read_text(errors="replace")
repo = os.environ.get("GITHUB_REPOSITORY", "")
sha = os.environ.get("GITHUB_SHA", "")
token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
if not repo or not sha or not token:
    print("ci-diagnostics: GITHUB_REPOSITORY/GITHUB_SHA/token missing; printing the log instead")
    print(body[-8000:])
    raise SystemExit(0)

title = "### Failing job: " + os.environ.get("GITHUB_JOB", "?")
title += " (run " + os.environ.get("GITHUB_RUN_ID", "?") + ")\n\n"
api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
request = urllib.request.Request(
    api + "/repos/" + repo + "/commits/" + sha + "/comments",
    data=json.dumps({"body": title + body}).encode(),
    method="POST",
    headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    },
)
try:
    with urllib.request.urlopen(request, timeout=30) as reply:
        print("ci-diagnostics: posted " + str(len(body)) + " bytes to " + repo + "@" + sha[:8])
except Exception as error:  # noqa: BLE001 - diagnostics must never fail the job
    print("ci-diagnostics: could not post the comment (" + repr(error) + "); printing instead")
    print(body[-8000:])
PYEOF

exit 0
