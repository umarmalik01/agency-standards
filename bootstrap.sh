#!/usr/bin/env bash
# Recreate every FREE/open-source dependency on a clean Linux or WSL system.
#
# Installs nothing billable, asks for no paid API key, and touches no repository but this one.
# System packages need sudo only when ffmpeg is genuinely absent; everything else is user-level.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

WITH_TORCH=1
WITH_MUSETALK=0
VENV=".venv"

usage() {
  cat <<'USAGE'
Usage: ./bootstrap.sh [--no-torch] [--with-musetalk] [--venv PATH]

  --no-torch        skip torch/diffusers (text + editing only; generate on HF Space or Kaggle)
  --with-musetalk   also clone MuseTalk for optional lip-sync (large; weights downloaded separately)
  --venv PATH       virtualenv location (default .venv)
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-torch) WITH_TORCH=0; shift ;;
    --with-musetalk) WITH_MUSETALK=1; shift ;;
    --venv) VENV="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

say() { printf '\n==> %s\n' "$1"; }

say "Restoring pinned Claude skill dependencies"
SUPERCMO_REPO="https://github.com/SupercmoHQ/superCMO-skills.git"
SUPERCMO_COMMIT="a6dd060ed46132e1944b1dd38981cb9ffcc42fc8"
AUTO_EDIT_REPO="https://github.com/natyang1234/auto-edit-video-skill.git"
AUTO_EDIT_COMMIT="934f081c737028b537a8e40b8286c635a783297f"
SKILLS_ROOT="$ROOT/.claude/skills"
mkdir -p "$SKILLS_ROOT"
TMP_DEPS="$(mktemp -d)"
trap 'rm -rf "$TMP_DEPS"' EXIT

if [[ ! -f "$SKILLS_ROOT/planning-campaigns/SKILL.md" ]]; then
  git clone -q "$SUPERCMO_REPO" "$TMP_DEPS/supercmo"
  git -C "$TMP_DEPS/supercmo" checkout -q "$SUPERCMO_COMMIT"
  for skill in planning-campaigns writing-ad-copy writing-video-scripts writing-video-prompts analyzing-products analyzing-brand; do
    cp -a "$TMP_DEPS/supercmo/skills/$skill" "$SKILLS_ROOT/$skill"
  done
  # Paid-model prompt guides are deliberately not retained. Keep only Wan guidance.
  if [[ -d "$SKILLS_ROOT/writing-video-prompts/references" ]]; then
    find "$SKILLS_ROOT/writing-video-prompts/references" -type f ! -name 'prompt-wan.md' -delete
  fi
  echo "SuperCMO text-only skills restored at $SUPERCMO_COMMIT"
else
  echo "SuperCMO text-only skills already present"
fi

if [[ ! -f "$SKILLS_ROOT/auto-edit-video/SKILL.md" ]]; then
  git clone -q "$AUTO_EDIT_REPO" "$TMP_DEPS/auto-edit-video-skill"
  git -C "$TMP_DEPS/auto-edit-video-skill" checkout -q "$AUTO_EDIT_COMMIT"
  cp -a "$TMP_DEPS/auto-edit-video-skill/skills/auto-edit-video" "$SKILLS_ROOT/auto-edit-video"
  echo "auto-edit-video restored at $AUTO_EDIT_COMMIT"
else
  echo "auto-edit-video already present"
fi

say "Checking Python"
command -v python3 >/dev/null || { echo "python3 not found - install Python 3.10+"; exit 1; }
python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    sys.exit(f"Python 3.10+ required, found {sys.version.split()[0]}")
print(f"python {sys.version.split()[0]} ok")
PY

say "Checking FFmpeg"
if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then
  echo "ffmpeg present: $(ffmpeg -version | head -1)"
else
  echo "ffmpeg/ffprobe missing."
  if command -v apt-get >/dev/null; then
    echo "Installing via apt (needs sudo)..."
    sudo apt-get update -qq && sudo apt-get install -y ffmpeg
  elif command -v brew >/dev/null; then
    brew install ffmpeg
  else
    echo "Install ffmpeg with your package manager, then re-run." >&2
    exit 1
  fi
fi

say "Creating virtualenv at $VENV"
[[ -d "$VENV" ]] || python3 -m venv "$VENV"
# shellcheck disable=SC1090
source "$VENV/bin/activate"
python -m pip install -q --upgrade pip wheel

if [[ $WITH_TORCH -eq 1 ]]; then
  say "Installing full requirements (torch, diffusers, kokoro, whisper)"
  pip install -q -r requirements.txt
else
  say "Installing text + editing dependencies only (--no-torch)"
  pip install -q openai-whisper soundfile numpy pillow pyyaml imageio imageio-ffmpeg
fi

if [[ $WITH_MUSETALK -eq 1 ]]; then
  say "Cloning MuseTalk (optional lip-sync)"
  mkdir -p third_party
  [[ -d third_party/MuseTalk ]] || git clone --depth 1 https://github.com/TMElyralab/MuseTalk third_party/MuseTalk
  echo "Weights are NOT downloaded automatically - run MuseTalk's own download_weights.sh."
fi

[[ -f .env ]] || { cp .env.example .env; say "Created .env from .env.example (gitignored)"; }
mkdir -p projects

say "Running no-paid-API audit"
python scripts/audit_no_paid_apis.py

say "Running setup check"
python scripts/check_setup.py || true

cat <<'DONE'

Bootstrap complete.

  source .venv/bin/activate
  python scripts/check_setup.py

Generation runs on your own GPU, a free HF ZeroGPU Space, or the free Kaggle notebook.
No paid provider is configured, and none may be added - see POLICY_NO_PAID_APIS.md.
DONE
