import sys
import os
import json
# Add app/ to sys.path for core/ imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.youtube_api import YouTubeAPI
from core.filters import filter_videos
from core.csv_utils import (
    save_results_csv,
    read_seen_history,
    append_seen_history,
    log_run
)

def main():
    settings_path = "settings.json"
    if not os.path.exists(settings_path):
        print("ERROR: settings.json not found.")
        return

    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)

    # Extract settings
    keywords = settings.get("keywords", [])
    views_min = settings.get("views_min")
    views_max = settings.get("views_max")
    subs_min = settings.get("subs_min")
    subs_max = settings.get("subs_max")
    duration_mode = settings.get("duration", "Any")
    duration_min = settings.get("duration_min")
    duration_max = settings.get("duration_max")
    region = settings.get("region")
    language = settings.get("language")
    skip_hidden_subs = settings.get("skip_hidden_subs", True)
    fresh_search = settings.get("fresh_search", False)
    api_cap = settings.get("api_cap", 9500)
    pages_per_keyword = settings.get("pages_per_keyword", 1)

    seen_history_path = "data/seen_history.csv"
    if fresh_search and os.path.exists(seen_history_path):
        os.remove(seen_history_path)
    seen_ids = read_seen_history(seen_history_path)

    api = YouTubeAPI(quota_cap=api_cap)
    all_results = []

    for keyword in keywords:
        for page in range(pages_per_keyword):
            try:
                video_ids = api.search_videos(
                    keyword,
                    regionCode=region if region else None,
                    relevanceLanguage=language if language else None
                )
            except Exception as e:
                print(f"API Error for '{keyword}': {e}")
                continue

            # Deduplication
            video_ids = [vid for vid in video_ids if vid not in seen_ids]
            if not video_ids:
                continue

            try:
                details = api.get_videos_details(video_ids[:50])
                channel_ids = [item["snippet"]["channelId"] for item in details if "snippet" in item]
                channel_details = api.get_channels_details(channel_ids)
            except Exception as e:
                print(f"Details error for '{keyword}': {e}")
                continue

            # Build channel info dict
            chinfo = {}
            for item in channel_details:
                cid = item["id"]
                chinfo[cid] = {
                    "subscriberCount": item["statistics"].get("subscriberCount", "0"),
                    "hiddenSubscriberCount": item["statistics"].get("hiddenSubscriberCount", False),
                }

            filtered = filter_videos(
                details,
                views_min=views_min,
                views_max=views_max,
                duration_min=duration_min,
                duration_max=duration_max,
                region=region,
                language=language,
                subs_min=subs_min,
                subs_max=subs_max,
                skip_hidden_subs=skip_hidden_subs,
                channels_info=chinfo,
            )

            for item in filtered:
                title = item["snippet"]["title"]
                description = item["snippet"]["description"]
                tags = item["snippet"].get("tags", [])
                channel = item["snippet"]["channelTitle"]
                channel_id = item["snippet"]["channelId"]
                video_id = item["id"]
                views = item["statistics"].get("viewCount", "0")
                subs = chinfo[channel_id].get("subscriberCount", "0")
                duration_seconds = 0
                try:
                    import isodate
                    duration_seconds = int(isodate.parse_duration(item["contentDetails"]["duration"]).total_seconds())
                except Exception:
                    pass
                published = item["snippet"]["publishedAt"][:10]
                all_results.append({
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "video_url": f"https://www.youtube.com/watch?v={video_id}",
                    "video_id": video_id,
                    "channel_title": channel,
                    "channel_id": channel_id,
                    "subscriber_count": subs,
                    "view_count": views,
                    "duration_minutes": duration_seconds // 60,
                    "published_at": published,
                    "keyword": keyword,
                })
                append_seen_history(video_id, out_file=seen_history_path)

    if all_results:
        save_results_csv(all_results, keyword=";".join(keywords))
        print(f"Saved {len(all_results)} results to CSV.")
        # Add this logging call:
        log_run(
            keywords_count=len(keywords),
            results_count=len(all_results),
            quota_used=api.quota_used
        )
    else:
        print("No results found.")
        # Log even for empty results:
        log_run(
            keywords_count=len(keywords),
            results_count=0,
            quota_used=api.quota_used
        )

if __name__ == "__main__":
    main()