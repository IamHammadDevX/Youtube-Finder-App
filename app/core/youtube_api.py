import os
import requests
from typing import List, Dict

class YouTubeAPI:
    SEARCH_LIST_COST = 100
    VIDEOS_LIST_COST = 1
    CHANNELS_LIST_COST = 1

    def __init__(self, api_key=None, quota_cap=9500):
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError("YOUTUBE_API_KEY environment variable not set")
        self.quota_cap = quota_cap
        self.quota_used = 0

    def estimate_run_cost(self, keywords, pages_per_keyword=1):
        """Estimate quota cost for a search operation"""
        estimated_results = len(keywords) * pages_per_keyword * 10  # Assume ~10 results per page
        search_cost = len(keywords) * pages_per_keyword * self.SEARCH_LIST_COST
        details_cost = estimated_results * (self.VIDEOS_LIST_COST + self.CHANNELS_LIST_COST)
        return search_cost + details_cost

    def can_afford(self, cost):
        return (self.quota_used + cost) <= self.quota_cap

    def search_videos(self, query, **params) -> List[Dict]:
        """Search videos by keyword/phrase. Returns list of video IDs."""
        if not self.can_afford(self.SEARCH_LIST_COST):
            return []
        url = "https://www.googleapis.com/youtube/v3/search"
        req_params = {
            "part": "snippet",
            "type": "video",
            "maxResults": 50,
            "q": query,
            "key": self.api_key,
            **params
        }
        resp = requests.get(url, params=req_params)
        self.quota_used += self.SEARCH_LIST_COST
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [item["id"]["videoId"] for item in items if "videoId" in item["id"]]

    def get_videos_details(self, video_ids: List[str]) -> List[Dict]:
        """Fetch metadata for a list of video IDs."""
        if not self.can_afford(self.VIDEOS_LIST_COST):
            return []
        url = "https://www.googleapis.com/youtube/v3/videos"
        ids = ",".join(video_ids)
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": ids,
            "key": self.api_key
        }
        resp = requests.get(url, params=params)
        self.quota_used += self.VIDEOS_LIST_COST
        resp.raise_for_status()
        return resp.json().get("items", [])

    def get_channels_details(self, channel_ids: List[str]) -> List[Dict]:
        """Fetch subscriber count and hidden status for channel IDs."""
        if not self.can_afford(self.CHANNELS_LIST_COST):
            return []
        url = "https://www.googleapis.com/youtube/v3/channels"
        ids = ",".join(channel_ids)
        params = {
            "part": "statistics",
            "id": ids,
            "key": self.api_key
        }
        resp = requests.get(url, params=params)
        self.quota_used += self.CHANNELS_LIST_COST
        resp.raise_for_status()
        return resp.json().get("items", [])

    def reset_quota(self):
        self.quota_used = 0