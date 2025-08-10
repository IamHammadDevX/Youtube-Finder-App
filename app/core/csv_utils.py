import csv
import os
from datetime import datetime

def save_results_csv(results, keyword, out_dir="export"):
    """
    Save results to daily CSV. Each result: dict with all columns.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(out_dir, f"results_{date_str}.csv")
    os.makedirs(out_dir, exist_ok=True)
    fieldnames = [
        "title", "description", "tags", "video_url", "video_id", "channel_title",
        "channel_id", "subscriber_count", "view_count", "duration_minutes",
        "published_at", "keyword"
    ]
    with open(filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "tags": ",".join(r.get("tags", [])),
                "video_url": f"https://www.youtube.com/watch?v={r.get('video_id', '')}",
                "video_id": r.get("video_id", ""),
                "channel_title": r.get("channel_title", ""),
                "channel_id": r.get("channel_id", ""),
                "subscriber_count": r.get("subscriber_count", ""),
                "view_count": r.get("view_count", ""),
                "duration_minutes": r.get("duration_minutes", ""),
                "published_at": r.get("published_at", ""),
                "keyword": keyword
            })

def append_seen_history(video_id, out_file="data/seen_history.csv"):
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    with open(out_file, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([video_id, date_str])

def read_seen_history(in_file="data/seen_history.csv"):
    if not os.path.exists(in_file):
        return set()
    seen = set()
    with open(in_file, "r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if row:
                seen.add(row[0])
    return seen

def log_run(keywords_count=0, results_count=0, quota_used=0, error=None, log_dir="logs"):
    """
    Logs each run's metrics to runs.csv
    Columns: run_timestamp, quota_used, keywords_count, results_count, error
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "runs.csv")
    file_exists = os.path.exists(log_file)
    
    with open(log_file, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["run_timestamp", "quota_used", "keywords_count", "results_count", "error"])
        writer.writerow([
            datetime.now().isoformat(),
            quota_used,
            keywords_count,
            results_count,
            error or ""
        ])