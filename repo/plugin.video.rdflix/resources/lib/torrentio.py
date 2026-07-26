import json
import urllib.request
import urllib.error
import urllib.parse

import xbmc

from resources.lib.constants import TORRENTIO_BASE, USER_AGENT, QUALITY_ORDER, LOG_PREFIX
from resources.lib.kodi_utils import get_setting, log


def _fetch_json(url, source_name="stremio"):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            count = len(data.get("streams", []))
            log("%s response: %d streams (%d bytes)" % (source_name, count, len(raw)))
            return data
    except urllib.error.HTTPError as e:
        log("%s HTTP %d: %s" % (source_name, e.code, url[:120]), xbmc.LOGERROR)
        return None
    except urllib.error.URLError as e:
        log("%s URL error: %s" % (source_name, str(e)), xbmc.LOGERROR)
        return None
    except Exception as e:
        log("%s fetch error: %s" % (source_name, str(e)), xbmc.LOGERROR)
        return None


def _get_max_quality():
    return get_setting("max_quality", "4K")


def _filter_by_quality(streams, max_quality="4K"):
    max_rank = QUALITY_ORDER.get(max_quality, 99)
    filtered = []
    for s in streams:
        title = s.get("title", "")
        quality = "Unknown"
        title_lower = title.lower()
        if "4k" in title_lower or "2160p" in title_lower:
            quality = "4K"
        elif "1080p" in title_lower:
            quality = "1080p"
        elif "720p" in title_lower:
            quality = "720p"
        elif "480p" in title_lower:
            quality = "480p"
        elif "cam" in title_lower or "scr" in title_lower:
            quality = "CAM"
        rank = QUALITY_ORDER.get(quality, 99)
        if rank >= max_rank:
            s["_quality"] = quality
            filtered.append(s)
    return filtered


def _query_stremio_api(base_url, path, rd_token, ad_token="", pm_token=""):
    if not base_url:
        return []
    base_url = base_url.strip().rstrip("/")
    if not base_url:
        return []

    name = base_url.split("/")[-1] if "/" in base_url else base_url
    all_streams = []
    seen_hashes = set()

    for svc_name, token in [("realdebrid", rd_token), ("alldebrid", ad_token), ("premiumize", pm_token)]:
        if not token:
            continue
        url = "%s/%s=%s%s.json" % (base_url, svc_name, urllib.parse.quote(token), path)
        log("Querying %s (%s): %s" % (name, svc_name, path))
        resp = _fetch_json(url, name)
        if resp and "streams" in resp:
            for s in resp["streams"]:
                h = s.get("infoHash", "")
                if h and h.lower() in seen_hashes:
                    continue
                if h:
                    seen_hashes.add(h.lower())
                all_streams.append(s)

    if all_streams:
        max_quality = _get_max_quality()
        filtered = _filter_by_quality(all_streams, max_quality)
        filtered.sort(key=lambda s: QUALITY_ORDER.get(s.get("_quality", "Unknown"), 99))
        return filtered
    return []


def _build_url(base_path, rd_token=""):
    if rd_token:
        url = "%s/realdebrid=%s%s.json" % (TORRENTIO_BASE, urllib.parse.quote(rd_token), base_path)
    else:
        url = "%s%s.json" % (TORRENTIO_BASE, base_path)
    return url


def _get_extra_urls():
    builtin = [
        "https://comet.elfhosted.com",
        "https://mediafusion.elfhosted.com",
    ]
    urls = list(builtin)
    raw = get_setting("extra_stremio_urls", "")
    if raw:
        for line in raw.splitlines():
            line = line.strip()
            if line and line.startswith("http"):
                urls.append(line)
    return urls


def get_movie_sources(imdb_id):
    rd_token = get_setting("rd_token", "")
    ad_token = get_setting("ad_token", "")
    pm_token = get_setting("pm_token", "")
    all_sources = []

    for svc_name, token in [("realdebrid", rd_token), ("alldebrid", ad_token), ("premiumize", pm_token)]:
        if not token:
            continue
        url = "%s/%s=%s/stream/movie/%s.json" % (TORRENTIO_BASE, svc_name, urllib.parse.quote(token), imdb_id)
        resp = _fetch_json(url, "Torrentio")
        if resp and "streams" in resp:
            max_quality = _get_max_quality()
            filtered = _filter_by_quality(resp["streams"], max_quality)
            filtered.sort(key=lambda s: QUALITY_ORDER.get(s.get("_quality", "Unknown"), 99))
            all_sources.extend(filtered)

    for extra_url in _get_extra_urls():
        extra_sources = _query_stremio_api(extra_url, "/stream/movie/%s" % imdb_id, rd_token, ad_token, pm_token)
        all_sources.extend(extra_sources)

    log("Torrentio + extras movie total: %d sources" % len(all_sources))
    return all_sources


def get_episode_sources(imdb_id, season, episode):
    rd_token = get_setting("rd_token", "")
    ad_token = get_setting("ad_token", "")
    pm_token = get_setting("pm_token", "")
    all_sources = []

    for svc_name, token in [("realdebrid", rd_token), ("alldebrid", ad_token), ("premiumize", pm_token)]:
        if not token:
            continue
        url = "%s/%s=%s/stream/series/%s:%s:%s.json" % (TORRENTIO_BASE, svc_name, urllib.parse.quote(token), imdb_id, season, episode)
        resp = _fetch_json(url, "Torrentio")
        if resp and "streams" in resp:
            max_quality = _get_max_quality()
            filtered = _filter_by_quality(resp["streams"], max_quality)
            filtered.sort(key=lambda s: QUALITY_ORDER.get(s.get("_quality", "Unknown"), 99))
            all_sources.extend(filtered)

    for extra_url in _get_extra_urls():
        extra_sources = _query_stremio_api(extra_url, "/stream/series/%s:%s:%s" % (imdb_id, season, episode), rd_token, ad_token, pm_token)
        all_sources.extend(extra_sources)

    log("Torrentio + extras episode total: %d sources" % len(all_sources))
    return all_sources
