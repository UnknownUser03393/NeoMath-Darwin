"""
tts-edge.py — Generate narration MP3 files using Microsoft Edge Neural TTS.
Much more natural than macOS `say`.
"""
import subprocess
import sys
import re
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
NARRATION = ROOT / "narration.md"

VOICE = "zh-CN-XiaoxiaoNeural"  # Female, Warm — best for narration
# Alternative: "zh-CN-YunyangNeural" (Male, Professional)
EDGE_TTS = "/Volumes/VolumnD/Development/NeoMath/desktop/.venv/bin/edge-tts"


def parse_narration(path: Path) -> List[tuple]:
    content = path.read_text(encoding="utf-8")
    segments = []
    time_pattern = re.compile(r"##\s*(\d{2}:\d{2})[–-](\d{2}:\d{2})")
    scene_pattern = re.compile(r"Scene\s*(\d{2})")

    current_time = ("00:00", "00:00")
    current_scene = "00"
    in_narration = False
    lines: List[str] = []

    for raw_line in content.split("\n"):
        line = raw_line.strip()
        m = time_pattern.match(line)
        if m:
            if lines:
                segments.append((current_time[0], current_time[1], current_scene, " ".join(lines)))
                lines = []
            current_time = (m.group(1), m.group(2))
            sm = scene_pattern.search(line)
            if sm:
                current_scene = sm.group(1)
            in_narration = False
            continue

        if line.startswith("##") or line.startswith("---") or line.startswith("画面") or line.startswith("操作"):
            continue

        if line.startswith("旁白："):
            in_narration = True
            continue

        if in_narration and line:
            lines.append(line)

    if lines:
        segments.append((current_time[0], current_time[1], current_scene, " ".join(lines)))

    return segments


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    segments = parse_narration(NARRATION)

    if len(sys.argv) > 1:
        segments = [s for s in segments if s[2] == sys.argv[1]]

    print(f"Voice: {VOICE}")
    print(f"Generating {len(segments)} narration segments...\n")

    for start, end, scene_id, text in segments:
        out_mp3 = OUTPUT / f"narration-s{scene_id}.mp3"
        desc = text[:80].replace("\n", " ")
        print(f"  Scene {scene_id}  [{start}–{end}]  {desc}...")

        subprocess.run(
            [EDGE_TTS, "--voice", VOICE, "--rate=-8%", "--text", text, "--write-media", str(out_mp3)],
            check=True, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print(f"    → {out_mp3.name}")

    print(f"\nDone. {len(segments)} files → {OUTPUT}/")


if __name__ == "__main__":
    main()
