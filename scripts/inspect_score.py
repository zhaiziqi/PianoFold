"""Print a compact summary of a serialized ScoreIR document."""

import argparse
import sys
from collections import Counter
from pathlib import Path

# ``python scripts/inspect_score.py`` places only ``scripts/`` on sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pianofold.symbolic.serialize import read_score


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="score_ir.json file to inspect")
    args = parser.parse_args()

    score = read_score(args.file)
    instruments = sorted({note.instrument for note in score.notes})
    counts = Counter(note.instrument for note in score.notes)
    pitch_range = (
        f"{min(note.pitch for note in score.notes)}–{max(note.pitch for note in score.notes)}"
        if score.notes
        else "n/a"
    )

    print(f"Notes: {len(score.notes)}")
    print(f"Instruments: {', '.join(instruments) if instruments else 'n/a'}")
    print(f"Pitch range: {pitch_range}")
    print(f"Duration: {score.duration:.3f}s")
    for instrument in instruments:
        print(f"{instrument}: {counts[instrument]}")


if __name__ == "__main__":
    main()
