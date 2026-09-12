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


OUTPUT_PATH = Path("data/smoke/transcription.mid")


def audio_duration_seconds(audio_path: Path) -> float:
    """Return duration from audio metadata without loading a transcription model."""
    info = soundfile.info(audio_path)
    return info.frames / info.samplerate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="audio file to transcribe")
    args = parser.parse_args()
    audio_path: Path = args.input

    if not audio_path.is_file():
        parser.error(f"Audio input does not exist: {audio_path}")

    duration = audio_duration_seconds(audio_path)
    transcriber = MuScriptorTranscriber()
    started = time.perf_counter()
    midi_bytes = transcriber.transcribe(audio_path)
    inference_seconds = time.perf_counter() - started

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_bytes(midi_bytes)
    print(f"Device: {transcriber.device}")
    print(f"Model: {transcriber.MODEL_SIZE}")
    print(f"Audio duration: {duration:.2f} seconds")
    print(f"Inference: {inference_seconds:.2f} seconds")
    print(f"RTF: {inference_seconds / duration:.3f}")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
