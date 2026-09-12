"""Deliberately transcribe one local audio file with MuScriptor-small."""

import argparse
import sys
import time
from pathlib import Path

import soundfile

# ``python scripts/smoke_transcribe.py`` places only ``scripts/`` on sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pianofold.transcription.muscriptor import MuScriptorTranscriber
from pianofold.symbolic.serialize import write_score


OUTPUT_DIR = Path("data/smoke")


def audio_duration_seconds(audio_path: Path) -> float:
    """Return duration from audio metadata without loading a transcription model."""
    info = soundfile.info(audio_path)
    return info.frames / info.samplerate


def run(
    audio_path: Path,
    transcriber: object,
    output_dir: Path,
    *,
    duration_seconds: float,
) -> tuple[Path, Path]:
    """Persist both products of one transcription call for the next stages."""
    started = time.perf_counter()
    output = transcriber.transcribe_with_midi(audio_path)
    transcription_seconds = time.perf_counter() - started
    output_dir.mkdir(parents=True, exist_ok=True)
    midi_path = output_dir / "transcription.mid"
    score_path = output_dir / "score_ir.json"
    midi_path.write_bytes(output.midi_bytes)
    write_score(score_path, output.score)
    print(f"Device: {transcriber.device}")
    print(f"Model: {transcriber.MODEL_SIZE}")
    print(f"Audio duration: {duration_seconds:.2f} seconds")
    print(f"Transcription call total (may include model loading): {transcription_seconds:.2f} seconds")
    print(f"Transcription call RTF: {transcription_seconds / duration_seconds:.3f}")
    print(f"Raw MIDI output: {midi_path}")
    print(f"ScoreIR output: {score_path}")
    return midi_path, score_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="audio file to transcribe")
    args = parser.parse_args()
    audio_path: Path = args.input

    if not audio_path.is_file():
        parser.error(f"Audio input does not exist: {audio_path}")

    duration = audio_duration_seconds(audio_path)
    run(audio_path, MuScriptorTranscriber(), OUTPUT_DIR, duration_seconds=duration)


if __name__ == "__main__":
    main()
