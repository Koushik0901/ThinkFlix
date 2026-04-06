from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from briefing.config import load_config
from briefing.pipeline import run_pipeline


def main(argv: list[str] | None = None) -> None:
    _load_environment()
    parser = argparse.ArgumentParser(description="Generate a multimedia briefing from text or PDF.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the briefing pipeline")
    run_parser.add_argument("--input", required=True, type=Path, help="Input .txt, .md, or .pdf source")
    run_parser.add_argument("--out", required=True, type=Path, help="Output directory")
    run_parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"), help="YAML config")
    run_parser.add_argument(
        "--no-visual-provider",
        "--no-video-model",
        dest="no_visual_provider",
        action="store_true",
        help="Use local placeholder visuals instead of invoking the provider-backed visual generator",
    )
    run_parser.add_argument(
        "--visual-mode",
        "--video-mode",
        dest="visual_mode",
        choices=["local", "api"],
        default=None,
        help="Override configured visual mode",
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        config = load_config(args.config)
        if args.no_visual_provider:
            config.visuals.mode = "local"
        if args.visual_mode is not None:
            config.visuals.mode = args.visual_mode
        plan = run_pipeline(args.input, args.out, config)
        print(f"Rendered briefing plan: {args.out / 'briefing_plan.json'}")
        print(f"Rendered briefing video: {args.out / 'briefing.mp4'}")
        print(f"Sections: {len(plan.sections)}")


def _load_environment() -> None:
    load_dotenv(dotenv_path=Path(".env"), override=False)
