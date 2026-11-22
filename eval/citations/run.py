"""Prepare blinded review packets or score a completed atomic-assertion inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from protocol import prepare, read_jsonl, score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("--capture", required=True)
    build.add_argument("--out", required=True)
    build.add_argument("--sample-size", type=int, default=30)
    build.add_argument("--seed", type=int, default=20261122)
    review = commands.add_parser("score")
    review.add_argument("--packets", required=True)
    review.add_argument("--reviews", required=True)
    review.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        if args.sample_size < 1:
            parser.error("--sample-size must be positive")
        packets = prepare(args.capture, args.out, args.sample_size, args.seed)
        print(f"Prepared {len(packets)} blinded packets")
    else:
        report = score(read_jsonl(args.packets), read_jsonl(args.reviews))
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(
            json.dumps(
                {k: v for k, v in report.items() if k != "findings"},
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
