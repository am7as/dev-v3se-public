"""Summarize data from any configured source.

    pixi run process --source local
    pixi run process --source hf_hub --dataset-id imdb
    pixi run process --source mimer_shared
"""
from __future__ import annotations

import argparse
import sys

from data_multi import config, processing, router, sources


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=None, choices=[*sources.available(), None])
    ap.add_argument("--dataset", default=None, help="Subdir for file-based sources.")
    ap.add_argument("--dataset-id", default=None, help="HF dataset id for source=hf_hub.")
    ap.add_argument("--split", default="train", help="HF split.")
    ap.add_argument("--out", default="summary.json")
    args = ap.parse_args(argv)

    source_name = args.source or config.source()
    print(f"source : {source_name}")

    if source_name == "hf_hub":
        if not args.dataset_id:
            ap.error("--dataset-id is required for source=hf_hub")
        mod = sources.get("hf_hub")
        ds = mod.load(args.dataset_id, split=args.split)
        summary = processing.summarize_hf_dataset(ds)
        summary["source"] = "hf_hub"
        summary["dataset_id"] = args.dataset_id
    else:
        root = router.resolve(source_name, dataset=args.dataset)
        print(f"reading: {root}")
        summary = processing.summarize_csvs(root)
        summary["source"] = source_name

    out = config.ensure_results_dir() / args.out
    processing.write_summary(summary, out)
    print(f"wrote  : {out}")
    print(f"summary: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
