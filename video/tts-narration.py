"""
tts-narration.py

Parses narration.md and generates per-scene AIFF narration audio
using macOS `say` with Tingting (zh_CN) voice.

Output: video/output/narration-s*.aiff
"""
import re
import subprocess
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
NARRATION = ROOT / "narration.md"

VOICE = "Tingting"
RATE = 180


def parse_narration(path: Path) -> List[tuple]:
    """
    Parse narration.md into segments: (start_time, end_time, scene_id, text)
    """
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
            # Flush previous segment
            if lines:
                segments.append((current_time[0], current_time[1], current_scene, " ".join(lines)))
                lines = []
            current_time = (m.group(1), m.group(2))
            sm = scene_pattern.search(line)
            if sm:
                current_scene = sm.group(1)
            in_narration = False
            continue

        if line.startswith("##") or line.startswith("---"):
            continue
        if line.startswith("画面") or line.startswith("操作"):
            continue

        if line.startswith("旁白："):
            in_narration = True
            continue

        if in_narration and line:
            lines.append(line)

    # Flush last segment
    if lines:
        segments.append((current_time[0], current_time[1], current_scene, " ".join(lines)))

    return segments


def speak(text: str, out_path: Path) -> Path:
    """Generate AIFF audio using macOS say command."""
    clean = text.replace("\n", " ").replace("  ", " ")
    cmd = ["say", "-v", VOICE, "-r", str(RATE), "-o", str(out_path), clean]
    subprocess.run(cmd, check=True, timeout=120)
    return out_path


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    segments = parse_narration(NARRATION)

    print(f"Parsed {len(segments)} narration segments\n")

    for start, end, scene_id, text in segments:
        fname = f"narration-s{scene_id}.aiff"
        out_path = OUTPUT / fname
        desc = text[:80].replace("\n", " ")
        print(f"  Scene {scene_id}  [{start}–{end}]  {desc}...")
        speak(text, out_path)

    print(f"\nGenerated {len(segments)} audio files → {OUTPUT}/")


if __name__ == "__main__":
    main()
