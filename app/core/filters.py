import isodate

def filter_videos(
    videos, 
    views_min=None, views_max=None,
    duration_min=None, duration_max=None,
    region=None, language=None,
    subs_min=None, subs_max=None,
    skip_hidden_subs=True,
    channels_info=None
):
    """
    Filter videos by views, duration, region, language, subscribers, and hidden subs.
    channels_info: dict of channel_id -> {subscriberCount, hiddenSubscriberCount}
    Returns filtered list.
    """
    filtered = []
    for v in videos:
        stats = v.get("statistics", {})
        snippet = v.get("snippet", {})
        content = v.get("contentDetails", {})
        channel_id = snippet.get("channelId")
        region_code = snippet.get("regionCode", None)
        lang_code = snippet.get("defaultLanguage", None)
        
        # Views filter
        views = int(stats.get("viewCount", "0"))
        if views_min is not None and views < views_min:
            continue
        if views_max is not None and views > views_max:
            continue

        # Duration filter
        dur = isodate.parse_duration(content.get("duration", "PT0S")).total_seconds() // 60
        if duration_min is not None and dur < duration_min:
            continue
        if duration_max is not None and dur > duration_max:
            continue

        # Region filter
        if region and region_code and region_code != region:
            continue

        # Language filter
        if language and lang_code and lang_code != language:
            continue

        # Subscribers filter
        chinfo = channels_info.get(channel_id, {}) if channels_info else {}
        subs = int(chinfo.get("subscriberCount", "0")) if "subscriberCount" in chinfo else None
        hidden = chinfo.get("hiddenSubscriberCount", False)
        if skip_hidden_subs and hidden:
            continue
        if subs_min is not None and subs is not None and subs < subs_min:
            continue
        if subs_max is not None and subs is not None and subs > subs_max:
            continue

        filtered.append(v)
    return filtered