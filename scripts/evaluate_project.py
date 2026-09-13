"""Compare three piano arrangements from a saved ScoreIR without inference or writes."""

import argparse
from pathlib import Path
import sys
from uuid import UUID

# Direct script execution places only scripts/ on sys.path.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from pianofold.arrangement import arrange
from pianofold.arrangement.profiles import RICH, SIMPLE, STANDARD
from pianofold.evaluation.metrics import calculate_metrics, format_metrics_table
from pianofold.symbolic.quantize import quantize_score
from pianofold.symbolic.serialize import read_score


def canonical_uuid(value: str) -> str:
    """Accept canonical UUID project IDs, as the local API does."""
    try:
        result = str(UUID(value))
    except ValueError:
        raise argparse.ArgumentTypeError("project_id must be a canonical UUID") from None
    if result != value:
        raise argparse.ArgumentTypeError("project_id must be a canonical UUID")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_id", type=canonical_uuid)
    parser.add_argument(
        "--project-root", type=Path, default=REPOSITORY_ROOT / "data" / "projects",
        help="project storage directory (default: repository data/projects)",
    )
    args = parser.parse_args()
    project_dir = args.project_root.resolve() / args.project_id
    if not project_dir.is_dir() or project_dir.resolve() != project_dir:
        parser.error(f"Unknown project: {args.project_id}")
    score_path = project_dir / "score_ir.json"
    if not score_path.is_file() or score_path.resolve() != score_path:
        parser.error(f"Project {args.project_id} has no readable score_ir.json")
    try:
        score = quantize_score(read_score(score_path), 120.0)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(f"Cannot read project score_ir.json: {error}")
    metrics = {
        profile.name: calculate_metrics(score, arrange(score, profile))
        for profile in (SIMPLE, STANDARD, RICH)
    }
    print(format_metrics_table(metrics))


if __name__ == "__main__":
    main()
