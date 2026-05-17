# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import arxiv
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

from scrapy.exceptions import DropItem


class DailyArxivPipeline:
    def __init__(self):
        self.page_size = 100
        delay_seconds = float(os.environ.get("ARXIV_API_DELAY_SECONDS", "10"))
        num_retries = int(os.environ.get("ARXIV_API_NUM_RETRIES", "5"))
        self.client = arxiv.Client(
            page_size=self.page_size,
            delay_seconds=delay_seconds,
            num_retries=num_retries,
        )

    def process_item(self, item: dict, spider):
        if item.get("summary") and item.get("title") and item.get("authors"):
            return item

        item["pdf"] = f"https://arxiv.org/pdf/{item['id']}"
        item["abs"] = f"https://arxiv.org/abs/{item['id']}"
        search = arxiv.Search(
            id_list=[item["id"]],
        )
        paper = next(self.client.results(search))
        item["authors"] = [a.name for a in paper.authors]
        item["title"] = paper.title
        item["categories"] = paper.categories
        item["comment"] = paper.comment
        item["summary"] = paper.summary
        return item


class StreamingRawPipeline:
    """Persist each crawled paper immediately for the enhancer worker."""

    def __init__(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.data_dir = Path(os.environ.get("ARXIV_DATA_DIR", self.project_root / "data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.today = os.environ.get("ARXIV_RUN_DATE") or datetime.now().strftime("%Y-%m-%d")
        self.language = os.environ.get("LANGUAGE", "Chinese")
        self.history_days = int(os.environ.get("ARXIV_DEDUP_HISTORY_DAYS", "7"))

        self.raw_file = self.data_dir / f"{self.today}.jsonl"

        self.history_ids = self._load_history_ids()
        self.raw_ids = self._load_ids(self.raw_file)

        self.raw_handle = None

    def open_spider(self, spider):
        self.raw_handle = open(self.raw_file, "a", encoding="utf-8")
        self._update_file_list()
        spider.logger.info(
            "Streaming raw arXiv items to %s; loaded %d raw ids and %d historical ids",
            self.raw_file,
            len(self.raw_ids),
            len(self.history_ids),
        )

    def close_spider(self, spider):
        if self.raw_handle:
            self.raw_handle.close()

    def process_item(self, item: dict, spider):
        paper_id = item.get("id")
        if not paper_id:
            raise DropItem("Skipping item without id")

        if paper_id in self.history_ids:
            raise DropItem(f"Skipping historical duplicate paper {paper_id}")

        if paper_id in self.raw_ids:
            raise DropItem(f"Skipping already persisted paper {paper_id}")

        self._append_jsonl(self.raw_handle, item)
        self.raw_ids.add(paper_id)
        self._update_file_list()
        return item

    def _load_history_ids(self):
        history_ids = set()
        for i in range(1, self.history_days + 1):
            date_str = (datetime.strptime(self.today, "%Y-%m-%d") - timedelta(days=i)).strftime("%Y-%m-%d")
            history_ids.update(self._load_ids(self.data_dir / f"{date_str}.jsonl"))
            history_ids.update(self._load_ids(self.data_dir / f"{date_str}_AI_enhanced_{self.language}.jsonl"))
        return history_ids

    @staticmethod
    def _load_ids(file_path: Path):
        if not file_path.exists():
            return set()

        ids = set()
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                paper_id = item.get("id")
                if paper_id:
                    ids.add(paper_id)
        return ids

    @staticmethod
    def _append_jsonl(handle, item: dict):
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())

    def _update_file_list(self):
        assets_dir = self.project_root / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        files = sorted(path.name for path in self.data_dir.glob("*.jsonl"))
        temp_file = assets_dir / "file-list.txt.tmp"
        target_file = assets_dir / "file-list.txt"

        with open(temp_file, "w", encoding="utf-8") as f:
            for file_name in files:
                f.write(file_name + "\n")

        os.replace(temp_file, target_file)