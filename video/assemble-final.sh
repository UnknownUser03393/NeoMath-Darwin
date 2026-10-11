#!/bin/bash
# assemble-final.sh — NeoMath demo video with Neural TTS narration
set -euo pipefail
cd "$(dirname "$0")"
OUT="output"

echo "=== Padding product videos to match narration ==="

# Pad each product video to match its narration duration
pad_video() {
  local src="$1" dst="$2" target_dur="$3"
  local src_dur
  src_dur=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$src" 2>/dev/null || echo "0")
  local pad
  pad=$(python3 -c "print(max(0, ${target_dur} - ${src_dur} + 0.3))")

  echo "  $(basename "$src"): ${src_dur%.*}s → ${target_dur%.*}s (pad ${pad%.*}s)"
  ffmpeg -v error -y -i "$src" \
    -filter_complex "[0:v]tpad=stop_mode=clone:stop_duration=${pad}[v]" \
    -map "[v]" -c:v libvpx-vp9 -crf 32 -b:v 0 -deadline realtime -cpu-used 5 \
    "$dst"
}

# Product narration durations from edge-tts (-8% rate):
# Actually measure them:
D04=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$OUT/narration-s04.mp3" 2>/dev/null)
D05=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$OUT/narration-s05.mp3" 2>/dev/null)
D06=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$OUT/narration-s06.mp3" 2>/dev/null)

pad_video "$OUT/product-04-lost-root.webm" "$OUT/product-04-padded.webm" "$D04"
pad_video "$OUT/product-05-semantic.webm"  "$OUT/product-05-padded.webm" "$D05"
pad_video "$OUT/product-06-xdlt.webm"      "$OUT/product-06-padded.webm" "$D06"

echo ""
echo "=== Building concat audio ==="

AUDIO_LIST="$OUT/concat-audio.txt"
rm -f "$AUDIO_LIST"
for s in 01 02 03 04 05 06 07 08 09 10; do
  echo "file '$(realpath "$OUT/narration-s${s}.mp3")'" >> "$AUDIO_LIST"
done

ffmpeg -v error -y -f concat -safe 0 -i "$AUDIO_LIST" -c copy "$OUT/audio-concat.mp3"
ADUR=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$OUT/audio-concat.mp3" 2>/dev/null || echo "0")
echo "  Audio: ${ADUR}s"

echo ""
echo "=== Muxing final (concat filter: 11 video segments + audio) ==="

# Use concat filter to avoid webm demuxer corruption from -c copy concat.
# Each input is decoded independently, then concatenated cleanly.
VDUR=$(python3 -c "
durs = [
  9.88,   # 01-narrated-hook
  29.08,  # 02-narrated-problem
  16.72,  # 03-narrated-workflow
  43.64,  # product-04-padded
  22.60,  # product-05-padded
  26.76,  # product-06-padded
  29.96,  # 07-narrated-trust-model
  21.36,  # 08-narrated-engineering
  29.36,  # 09-narrated-ai-collaboration
  11.48,  # 10-narrated-reflection
  11.48,  # 10-narrated-end
]
print(sum(durs))
")
VPAD=$(python3 -c "print(max(0, ${ADUR} - ${VDUR} + 0.5))")
echo "  Video total: ${VDUR}s  Audio: ${ADUR}s  Tail pad: ${VPAD}s"

ffmpeg -v error -y \
  -i "$OUT/01-narrated-hook.webm" \
  -i "$OUT/02-narrated-problem.webm" \
  -i "$OUT/03-narrated-workflow.webm" \
  -i "$OUT/product-04-padded.webm" \
  -i "$OUT/product-05-padded.webm" \
  -i "$OUT/product-06-padded.webm" \
  -i "$OUT/07-narrated-trust-model.webm" \
  -i "$OUT/08-narrated-engineering.webm" \
  -i "$OUT/09-narrated-ai-collaboration.webm" \
  -i "$OUT/10-narrated-reflection.webm" \
  -i "$OUT/10-narrated-end.webm" \
  -i "$OUT/audio-concat.mp3" \
  -filter_complex "[0:v][1:v][2:v][3:v][4:v][5:v][6:v][7:v][8:v][9:v][10:v]concat=n=11:v=1:a=0[vc];[vc]tpad=stop_mode=clone:stop_duration=${VPAD}[vpad]" \
  -map "[vpad]" -map 11:a \
  -c:v libx264 -preset fast -crf 22 \
  -c:a aac -b:a 192k \
  -pix_fmt yuv420p \
  -movflags +faststart \
  "$OUT/neomath-demo-rough.mp4"

FDUR=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$OUT/neomath-demo-rough.mp4" 2>/dev/null || echo "?")
SIZE=$(ls -lh "$OUT/neomath-demo-rough.mp4" | awk '{print $5}')

echo ""
echo "================================================"
echo "  Final: neomath-demo-rough.mp4"
echo "  Duration: ${FDUR}s"
echo "  Size: ${SIZE}"
echo "  Voice: zh-CN-XiaoxiaoNeural (Edge Neural TTS)"
echo "================================================"
