"""Turn a persisted ScoreIR transcription into a baseline piano MIDI file."""

import argparse
import sys
from pathlib import Path

# ``python scripts/smoke_arrange.py`` places only ``scripts/`` on sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pianofold.arrangement.baseline import baseline_reduce
from pianofold.export.midi import arrangement_to_midi
from pianofold.symbolic.quantize import quantize_score
from pianofold.symbolic.serialize import read_score


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score_ir_json", type=Path)
    parser.add_argument("output_mid", type=Path)
    parser.add_argument("--bpm", type=float, default=120.0)
    args = parser.parse_args()

    score = read_score(args.score_ir_json)
    arrangement = baseline_reduce(quantize_score(score, args.bpm))
    output = arrangement_to_midi(arrangement, args.output_mid, args.bpm)
    print(f"source notes: {len(score.notes)}")
    print(f"arrangement notes: {len(arrangement.notes)}")
    print(output)


if __name__ == "__main__":
    main()
