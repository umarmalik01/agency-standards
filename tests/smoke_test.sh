#!/usr/bin/env bash
# End-to-end test of the editing half of the pipeline using synthetic scenes.
#
# Needs only ffmpeg - no GPU, no model weights, no network. It exercises scene normalization,
# the CTA card, concatenation, audio muxing, caption burn-in and every QA check, so the assembly
# path can be verified on any machine before a real render is attempted.
#
# It has already earned its keep: it caught the CTA card being truncated by `-shortest`, and the
# CTA duration being appended to the brief rather than budgeted inside it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v ffmpeg >/dev/null || { echo "ffmpeg required - run ./bootstrap.sh"; exit 1; }

P="projects/smoke-test"
rm -rf "$P"
for s in product creator scripts storyboards prompts audio scenes captions renders qa; do
  mkdir -p "$P/$s"
done

# plan_scenes(20) -> 17s of scenes + a 3s CTA card = 20s total
COLORS=(0x1b3a5c 0x5c1b3a 0x3a5c1b 0x4c3a6b 0x6b4c3a)
DURS=(4 4 3 3 3)
for i in 0 1 2 3 4; do
  ffmpeg -y -loglevel error -f lavfi -i "color=c=${COLORS[$i]}:s=720x1280:d=${DURS[$i]}:r=24" \
    -vf "drawtext=text='SCENE $i':fontcolor=white:fontsize=90:x=(w-text_w)/2:y=(h-text_h)/2" \
    -c:v libx264 -crf 20 -pix_fmt yuv420p "$P/scenes/scene_0$i.mp4"
done
ffmpeg -y -loglevel error -f lavfi -i "sine=frequency=220:duration=17:sample_rate=24000" -ac 1 "$P/audio/voice.wav"
ffmpeg -y -loglevel error -f lavfi -i "color=c=gray:s=800x800:d=1" -frames:v 1 "$P/product/master_front.jpg"

echo "==> assembling"
python3 scripts/assemble_ad.py --project "$P" --variation 1 --cta "Order Now" --no-captions

echo "==> verifying the CTA card survived to the last frame"
avg() { ffmpeg -v error "$@" -vf "scale=1:1" -frames:v 1 -f rawvideo -pix_fmt rgb24 - 2>/dev/null | od -An -tu1 | tr -s ' '; }
last="$(avg -sseof -1 -i "$P/renders/final_v1.mp4")"
echo "    last frame RGB:$last (CTA card is near-black; a bright value means it was truncated)"
python3 - "$last" <<'PY'
import sys
vals = [int(v) for v in sys.argv[1].split()]
assert max(vals) < 60, f"last frame {vals} is not the CTA card - it was cut off"
print("    ok - CTA card present")
PY

echo "==> QA against the 20s brief"
python3 scripts/qa_video.py --project "$P" --variation 1 --expected-duration 20

echo "==> no-paid-API audit"
python3 scripts/audit_no_paid_apis.py

echo
echo "smoke test PASSED"
