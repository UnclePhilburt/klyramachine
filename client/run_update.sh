#!/bin/bash
# Privileged orchestrator for the klyra auto-updater. Always invoked as
# root (by klyra-update.service or root cron). Drops to the unprivileged
# repo owner to do the git pull, then restarts klyra.service if the
# updater left a marker.
#
# Manual invocation: sudo /path/to/client/run_update.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MARKER="$REPO_DIR/.klyra-update-pending"

stamp() { date '+%F %T'; }
log()   { echo "[$(stamp)] run_update: $*"; }

if [ "$(id -u)" -ne 0 ]; then
    log "ERROR: must run as root (got uid $(id -u))"
    exit 1
fi

# Pick the unprivileged user that owns the repo. Prefer the dedicated
# 'klyra' user if it exists (lockdown installs); otherwise fall back to
# whoever owns the repo on disk.
if id klyra >/dev/null 2>&1; then
    RUN_AS=klyra
else
    RUN_AS=$(stat -c '%U' "$REPO_DIR" 2>/dev/null || echo "")
fi

if [ -z "$RUN_AS" ] || [ "$RUN_AS" = "UNKNOWN" ] || [ "$RUN_AS" = "root" ]; then
    log "ERROR: could not determine unprivileged repo owner (got '$RUN_AS')"
    exit 1
fi

RUN_HOME=$(getent passwd "$RUN_AS" | cut -d: -f6)
[ -n "$RUN_HOME" ] || RUN_HOME="/home/$RUN_AS"

log "Running auto_update.sh as $RUN_AS (HOME=$RUN_HOME)"

# runuser strips the environment; pass HOME and a sane PATH so uv/git/pip work.
runuser -u "$RUN_AS" -- env \
    HOME="$RUN_HOME" \
    PATH="$RUN_HOME/.local/bin:/usr/local/bin:/usr/bin:/bin" \
    /bin/bash "$SCRIPT_DIR/auto_update.sh"
RC=$?

if [ "$RC" -ne 0 ]; then
    log "auto_update.sh exited $RC"
fi

# Even on partial failure, if a marker was placed we should restart klyra
# so it picks up whatever new code did land.
if [ -f "$MARKER" ]; then
    log "Marker found; restarting klyra.service"
    rm -f "$MARKER"
    if /usr/bin/systemctl restart klyra.service; then
        log "klyra.service restarted"
    else
        log "ERROR: failed to restart klyra.service"
        exit 1
    fi
else
    log "No marker; nothing to restart"
fi

exit "$RC"
