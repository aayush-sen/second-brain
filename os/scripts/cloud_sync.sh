#!/bin/bash
# cloud_sync — two-way sync between the vault's os/ subset and pierce-os (private).
# Always pull-then-push. File-level last-writer-wins; vault history keeps everything.
# Run: cloud_sync.sh (launchd every 300s).
set -euo pipefail

VAULT="/Users/aayush/Desktop/second brain"
REMOTE="pierce"                                   # git remote name for pierce-os
BASE_FILE="$VAULT/os/integrations/cloud_sync_base"
CLOUD_CLAUDE="$VAULT/os/integrations/CLAUDE.md.cloud"
cd "$VAULT"

LOCK="$VAULT/os/integrations/cloud_sync.lock"
if ! mkdir "$LOCK" 2>/dev/null; then exit 0; fi
trap 'rmdir "$LOCK"' EXIT

# reachable? (empty repo is reachable but has no refs yet)
git ls-remote "$REMOTE" >/dev/null 2>&1 || { echo "$(date +%F\ %T) unreachable (offline?)"; exit 0; }
if git fetch "$REMOTE" main --quiet 2>/dev/null; then
  REMOTE_SHA=$(git rev-parse FETCH_HEAD)
else
  REMOTE_SHA=""                                   # first push: repo still empty
fi
BASE_SHA=$(cat "$BASE_FILE" 2>/dev/null || echo "")

# ---- pull: fold cloud commits into the vault (only os/ paths the cloud changed) ----
if [ -n "$REMOTE_SHA" ] && [ -n "$BASE_SHA" ] && [ "$REMOTE_SHA" != "$BASE_SHA" ]; then
  CHANGED=$(git diff --name-only "$BASE_SHA" "$REMOTE_SHA" -- os | grep -v '^os/integrations/cloud_sync' || true)
  if [ -n "$CHANGED" ]; then
    echo "$CHANGED" | while IFS= read -r f; do
      if git cat-file -e "$REMOTE_SHA:$f" 2>/dev/null; then
        mkdir -p "$(dirname "$f")"
        git show "$REMOTE_SHA:$f" > "$f"
      else
        rm -f "$f"                                # deleted in cloud
      fi
      git add -A -- "$f"
    done
    git diff --cached --quiet || git commit -q -m "os: cloud pull ${REMOTE_SHA:0:7}"
    echo "$(date +%F\ %T) pulled $(echo "$CHANGED" | wc -l | tr -d ' ') file(s) from ${REMOTE_SHA:0:7}"
  fi
fi

# ---- push: snapshot the cloud-safe subset as one commit on top of remote main ----
# capture the tracked-file list BEFORE switching to the temp index
# (NUL-separated in a temp file — bash variables can't hold NULs)
LIST=$(mktemp)
git ls-files -z os .claude/skills .claude/agents | while IFS= read -r -d '' f; do
  [ -f "$f" ] && printf '%s\0' "$f"; done > "$LIST"
TMP_INDEX=$(mktemp)
export GIT_INDEX_FILE="$TMP_INDEX"
git read-tree --empty
git update-index -z --add --stdin < "$LIST"
rm -f "$LIST"
HASH=$(git hash-object -w "$CLOUD_CLAUDE")
git update-index --add --cacheinfo 100644 "$HASH" CLAUDE.md
TREE=$(git write-tree)
unset GIT_INDEX_FILE
rm -f "$TMP_INDEX"

if [ -z "$REMOTE_SHA" ]; then
  COMMIT=$(git commit-tree "$TREE" -m "os: initial cloud mirror")
elif [ "$TREE" != "$(git rev-parse "$REMOTE_SHA^{tree}")" ]; then
  COMMIT=$(git commit-tree "$TREE" -p "$REMOTE_SHA" -m "os: mac sync $(date +%F\ %H:%M)")
else
  echo "$REMOTE_SHA" > "$BASE_FILE"; exit 0      # nothing new either way
fi
git push --quiet "$REMOTE" "$COMMIT:refs/heads/main"
echo "$COMMIT" > "$BASE_FILE"
echo "$(date +%F\ %T) pushed ${COMMIT:0:7}"
