import argparse
import json
import os
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta
from pathlib import Path

from enhance import build_chain, process_single_item


AI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AI_DIR.parent


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Raw jsonl file to watch")
    parser.add_argument("--done-file", help="Marker file created when the crawler is done")
    parser.add_argument("--max_workers", type=int, default=int(os.environ.get("ENHANCE_MAX_WORKERS", "1")))
    parser.add_argument("--poll-interval", type=float, default=float(os.environ.get("ENHANCE_POLL_INTERVAL", "1")))
    parser.add_argument("--history-days", type=int, default=int(os.environ.get("ARXIV_DEDUP_HISTORY_DAYS", "7")))
    return parser.parse_args()


def enhanced_path(raw_file: Path, language: str) -> Path:
    return raw_file.with_name(f"{raw_file.stem}_AI_enhanced_{language}.jsonl")


def load_jsonl(path: Path):
    if not path.exists():
        return []

    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Skipping invalid JSON line in {path}: {e}", file=sys.stderr)
    return items


def load_ids(path: Path):
    return {item["id"] for item in load_jsonl(path) if item.get("id")}


def load_history_ids(raw_file: Path, language: str, history_days: int):
    try:
        run_date = datetime.strptime(raw_file.stem, "%Y-%m-%d")
    except ValueError:
        return set()

    ids = set()
    for i in range(1, history_days + 1):
        date_str = (run_date - timedelta(days=i)).strftime("%Y-%m-%d")
        ids.update(load_ids(raw_file.with_name(f"{date_str}.jsonl")))
        ids.update(load_ids(raw_file.with_name(f"{date_str}_AI_enhanced_{language}.jsonl")))
    return ids


def append_jsonl(path: Path, item: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def update_file_list(data_dir: Path):
    assets_dir = PROJECT_ROOT / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(path.name for path in data_dir.glob("*.jsonl"))
    temp_file = assets_dir / "file-list.txt.tmp"
    target_file = assets_dir / "file-list.txt"

    with open(temp_file, "w", encoding="utf-8") as f:
        for file_name in files:
            f.write(file_name + "\n")

    os.replace(temp_file, target_file)


def main():
    args = parse_args()
    raw_file = Path(args.data).resolve()
    language = os.environ.get("LANGUAGE", "Chinese")
    model_name = os.environ.get("MODEL_NAME", "deepseek-chat")
    target_file = enhanced_path(raw_file, language)
    done_file = Path(args.done_file).resolve() if args.done_file else None

    completed_ids = load_ids(target_file)
    history_ids = load_history_ids(raw_file, language, args.history_days)
    initial_completed_count = len(completed_ids)
    in_progress_ids = set()
    submitted_ids = set()
    futures = {}
    success_count = 0
    filtered_count = 0
    failed_count = 0

    print(f"Watching raw data: {raw_file}", file=sys.stderr)
    print(f"Writing enhanced data: {target_file}", file=sys.stderr)
    print(f"Loaded {len(completed_ids)} completed ids and {len(history_ids)} history ids", file=sys.stderr)

    update_file_list(raw_file.parent)
    chain = build_chain(model_name)

    def should_submit(item):
        paper_id = item.get("id")
        if not paper_id:
            return False
        if paper_id in history_ids or paper_id in completed_ids:
            return False
        if paper_id in in_progress_ids or paper_id in submitted_ids:
            return False
        return True

    with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as executor:
        while True:
            for item in load_jsonl(raw_file):
                if not should_submit(item):
                    continue
                paper_id = item["id"]
                in_progress_ids.add(paper_id)
                submitted_ids.add(paper_id)
                future = executor.submit(process_single_item, chain, dict(item), language)
                futures[future] = paper_id

            if futures:
                done, _ = wait(futures.keys(), timeout=args.poll_interval, return_when=FIRST_COMPLETED)
            else:
                done = set()
                time.sleep(args.poll_interval)

            for future in done:
                paper_id = futures.pop(future)
                in_progress_ids.discard(paper_id)
                try:
                    result = future.result()
                except Exception as e:
                    failed_count += 1
                    print(f"Enhancement failed for {paper_id}: {e}", file=sys.stderr)
                    continue

                if result is None:
                    filtered_count += 1
                    print(f"Skipping filtered paper {paper_id}", file=sys.stderr)
                    completed_ids.add(paper_id)
                    continue

                append_jsonl(target_file, result)
                completed_ids.add(paper_id)
                success_count += 1
                update_file_list(raw_file.parent)
                print(f"Enhanced {paper_id}", file=sys.stderr)

            crawler_done = done_file.exists() if done_file else True
            if crawler_done and not futures:
                has_pending = any(should_submit(item) for item in load_jsonl(raw_file))
                if not has_pending:
                    break

    update_file_list(raw_file.parent)
    print("Enhancer queue drained", file=sys.stderr)
    print(
        "AI enhancement summary: "
        f"success={success_count}, filtered={filtered_count}, failed={failed_count}, "
        f"already_completed={initial_completed_count}, submitted={len(submitted_ids)}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
