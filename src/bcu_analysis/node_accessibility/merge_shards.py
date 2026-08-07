"""Merge and validate node-accessibility shard outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--base-path",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--shard-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--expected-nodes",
        type=int,
        required=True,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    shard_paths = sorted(
        args.shard_dir.glob(
            "typical_adult_shard_[0-9][0-9].csv"
        )
    )

    if not shard_paths:
        raise FileNotFoundError(
            f"No shard files found in {args.shard_dir}"
        )

    input_paths = [args.base_path, *shard_paths]

    frames = [
        pd.read_csv(path)
        for path in input_paths
    ]

    combined = pd.concat(
        frames,
        ignore_index=True,
    )

    duplicates_before = (
        combined["node_id"].duplicated().sum()
    )

    combined = (
        combined
        .drop_duplicates(
            subset="node_id",
            keep="first",
        )
        .sort_values("node_id")
        .reset_index(drop=True)
    )

    args.output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    combined.to_csv(
        args.output_path,
        index=False,
    )

    unique_nodes = combined["node_id"].nunique()

    print("Input files:", len(input_paths))
    print("Rows before deduplication:", len(pd.concat(frames)))
    print("Duplicates before:", duplicates_before)
    print("Rows after deduplication:", len(combined))
    print("Unique nodes:", unique_nodes)
    print("Output:", args.output_path)

    if len(combined) != args.expected_nodes:
        raise RuntimeError(
            f"Expected {args.expected_nodes:,} rows, "
            f"found {len(combined):,}."
        )

    if unique_nodes != args.expected_nodes:
        raise RuntimeError(
            f"Expected {args.expected_nodes:,} unique nodes, "
            f"found {unique_nodes:,}."
        )


if __name__ == "__main__":
    main()
