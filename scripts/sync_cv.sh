#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_dir"

generated_candidates=(
  index.html resume.json llms.txt robots.txt sitemap.xml assets/cv-qr.svg
)
for path in assets/*-{180,360}.{avif,webp,jpg}; do
  [[ -e $path ]] && generated_candidates+=("$path")
done
generated=()
for path in "${generated_candidates[@]}"; do
  git ls-files --error-unmatch -- "$path" >/dev/null 2>&1 && generated+=("$path")
done

# Ces fichiers sont entièrement reconstruits depuis cv.yml et le template. Les
# restaurer évite qu'ils bloquent git pull, sans toucher aux sources éditables.
if ((${#generated[@]})); then
  git restore --worktree -- "${generated[@]}"
fi
git pull --rebase --autostash
make update
