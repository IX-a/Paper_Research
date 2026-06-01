import csv
import io
import json
import os
import urllib.request

METRICS_FILE = os.path.join(os.path.dirname(__file__), "journal_metrics.json")

SCIMAGO_CSV_URL = "https://www.scimagojr.com/journalrank.php?out=csv"


def load_metrics(path: str = METRICS_FILE) -> dict:
    """Load journal metrics from local JSON cache."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def get_if(journal_name: str, metrics: dict) -> float | None:
    return metrics.get(journal_name.lower().strip())


def download_metrics(output_path: str = METRICS_FILE) -> dict:
    """Download SCImago journal data and convert to JSON cache."""
    req = urllib.request.Request(SCIMAGO_CSV_URL, headers={"User-Agent": "PaperResearch/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return {}

    reader = csv.DictReader(io.StringIO(raw), delimiter=";")
    metrics = {}
    for row in reader:
        title = row.get("Title", "").strip()
        sjr = row.get("SJR", "").strip()
        if title and sjr:
            try:
                metrics[title.lower()] = float(sjr.replace(",", "."))
            except ValueError:
                pass

    if metrics:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False)

    return metrics
