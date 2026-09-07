#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ci-diagnostics.sh — post the collected CI log tails to the head commit.
#
# Debugging a workflow run is normally a matter of opening the job log, but
# neither the Actions log nor the artifact store is reachable from every
# environment (sandboxes, restricted networks, no browser).  The REST API for
# commit comments, however, is: so each job tees the interesting command output
# to a file and calls this script on failure, which turns the tail of those
# files into one comment on the commit under test.
#
# Best effort by design: it always exits 0, so it can never mask the real error
# with a diagnostics problem.
#
# Used by .github/workflows/ci.yml; run from any step with
#   - run: bash scripts/ci-diagnostics.sh
#     if: failure()
# ---------------------------------------------------------------------------
set -uo pipefail

# $RUNNER_TEMP is a Windows path on Windows runners, so use it instead of
# /tmp: the helper below hands the file to a native python.exe.
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

PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
    echo "ci-diagnostics: no python interpreter found; dumping the log instead" >&2
    cat "$OUT" | tail -c 4000
    exit 0
fi

"$PY" - "$OUT" <<'PYEOF'
import json, os, pathlib, sys, urllib.request

body = pathlib.Path(sys.argv[1]).read_text(errors="replace")
header = f"### Failing job diagnostics ({os.environ.get('GITHUB_JOB', '?'}), run {os.environ.get('GITHUB_RUN_ID', '?')})\n\n"
api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
repo = os.environ["GITHUB_REPOSITORY"]
sha = os.environ["GITHUB_SHA"]
token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
request = urllib.request.Request(
    f"{api}/repos/{repo}/commits/{sha}/comments",
    data=json.dumps({"body": header + body}).encode(),
    method="POST",
    headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    },
)
try:
    with urllib.request.urlopen(request, timeout=30) as reply:
        print(f"ci-diagnostics: posted {len(body)} bytes to {repo}@{sha[:8]} (status {reply.status})")
except Exception as error:  # noqa: BLE001 - diagnostics must never fail the job
    print(f"ci-diagnostics: could not post the comment ({error}); echoing instead")
    print(body[-8000:])
PYEOF
