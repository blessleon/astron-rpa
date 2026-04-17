#!/usr/bin/env bash
set -euo pipefail

# repo root is parent of .vscode
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

# collect staged files under frontend with desired extensions
files=()
while IFS= read -r -d '' f; do
  case "$f" in
    frontend/*.js|frontend/*.jsx|frontend/*.ts|frontend/*.tsx|frontend/*.vue)
      files+=("${f#frontend/}") ;;
  esac
done < <(git diff --cached --name-only --diff-filter=ACM -z)

if [ ${#files[@]} -eq 0 ]; then
  echo "No staged frontend JS/TS/Vue files to lint." >&2
  exit 0
fi

cd frontend
npx eslint --quiet --fix -- "${files[@]}"