from __future__ import annotations

import argparse
from pathlib import Path

from briefing.config import load_config
from briefing.pipeline import run_pipeline


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate a multimedia briefing from text or PDF.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the briefing pipeline")
    run_parser.add_argument("--input", required=True, type=Path, help="Input .txt, .md, or .pdf source")
    run_parser.add_argument("--out", required=True, type=Path, help="Output directory")
    run_parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"), help="YAML config")
    run_parser.add_argument(
        "--no-video-model",
        action="store_true",
        help="Use static cutaway placeholders instead of invoking Wan2.2",
    )
    run_parser.add_argument(
        "--video-mode",
        choices=["placeholder", "wan", "api", "skip"],
        default=None,
        help="Override configured video mode",
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        config = load_config(args.config)
        if args.no_video_model:
            config.video.mode = "placeholder"
        if args.video_mode is not None:
            config.video.mode = args.video_mode
        plan = run_pipeline(args.input, args.out, config)
        print(f"Rendered briefing plan: {args.out / 'briefing_plan.json'}")
        print(f"Rendered briefing video: {args.out / 'briefing.mp4'}")
        print(f"Sections: {len(plan.sections)}")
