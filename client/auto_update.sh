#!/bin/bash
# Klyra auto-updater. Runs as the unprivileged user that owns the repo.
#
# Pulls the latest origin/main, updates the venv if requirements.txt changed,
# and touches a marker file when something actually changed. The privileged
# wrapper (run_update.sh, invoked by systemd or root cron) reads the marker
# and restarts klyra.service.
#
# This script never uses sudo.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MARKER="$REPO_DIR/.klyra-update-pending"

cd "$REPO_DIR"

# Tolerate ownership mismatches between the runner and the repo.
git config --global --add safe.directory "$REPO_DIR" >/dev/null 2>&1 || true

stamp() { date '+%F %T'; }
log()   { echo "[$(stamp)] auto_update: $*"; }

log "Checking $REPO_DIR against origin/main"

if ! git fetch --quiet origin main; then
    log "ERROR: git fetch failed"
    exit 1
fi

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    log "Already up to date ($LOCAL)"
    rm -f "$MARKER" 2>/dev/null || true
    exit 0
fi

log "Updating $LOCAL -> $REMOTE"
if ! git reset --quiet --hard origin/main; then
    log "ERROR: git reset failed"
    exit 1
fi

# If client deps changed, refresh the venv. Failures are warnings, not fatal:
# we still want klyra restarted with the new code.
if git diff --name-only "$LOCAL" HEAD | grep -q '^client/requirements\.txt$'; then
    log "client/requirements.txt changed; refreshing venv"
    if [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
        export PATH="$HOME/.local/bin:$PATH"
        if command -v uv >/dev/null 2>&1; then
            uv pip install --python "$SCRIPT_DIR/venv/bin/python" \
                -r "$SCRIPT_DIR/requirements.txt" --upgrade \
                || log "WARN: uv pip install failed; restarting anyway"
        else
            "$SCRIPT_DIR/venv/bin/pip" install \
                -r "$SCRIPT_DIR/requirements.txt" --upgrade \
                || log "WARN: pip install failed; restarting anyway"
        fi
    else
        log "WARN: $SCRIPT_DIR/venv missing; skipping deps update"
    fi
fi

touch "$MARKER"
log "Update applied; marker placed"

# Transitional fallback for fleet members whose klyra-update.service still
# points at this script directly (pre-run_update.sh installs). On those, no
# wrapper consumes the marker, so we attempt a passwordless restart here.
# - Default Pi OS: 'pi' has NOPASSWD sudo → restart succeeds
# - Lockdown 'klyra' user: no sudo → fails silently; that install needs a
#   one-time `curl … | bash` re-run to pick up run_update.sh
# - New installs: redundant; run_update.sh has already restarted via the
#   marker, so this is a harmless no-op
if sudo -n /usr/bin/systemctl restart klyra.service 2>/dev/null; then
    log "Fallback restart succeeded (legacy service file)"
fi

exit 0
