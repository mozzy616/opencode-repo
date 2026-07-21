import json
import urllib.request
import urllib.error
import urllib.parse

import xbmc

from resources.lib.constants import TORRENTIO_BASE, USER_AGENT, QUALITY_ORDER, LOG_PREFIX
from resources.lib.kodi_utils import get_setting, log


def _fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            count = len(data.get("streams", []))
            log("Torrentio response: %d streams (bytes=%d)" % (count, len(raw)))
            return data
    except urllib.error.HTTPError as e:
        log("Torrentio HTTP %d: %s" % (e.code, url[:120]), xbmc.LOGERROR)
        return None
    except urllib.error.URLError as e:
        log("Torrentio URL error: %s" % str(e), xbmc.LOGERROR)
        return None
    except Exception as e:
        log("Torrentio fetch error: %s" % str(e), xbmc.LOGERROR)
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
        if rank <= max_rank:
            s["_quality"] = quality
            filtered.append(s)
    return filtered


def _build_url(base_path, rd_token=""):
    url = "%s%s.json" % (TORRENTIO_BASE, base_path)
    if rd_token:
        url += "?real_debrid=%s" % urllib.parse.quote(rd_token)
    return url


def get_movie_sources(imdb_id):
    rd_token = get_setting("rd_token", "")
    url = _build_url("/stream/movie/%s" % imdb_id, rd_token)
    log("Torrentio movie: %s" % imdb_id)
    resp = _fetch_json(url)
    if resp and "streams" in resp:
        max_quality = _get_max_quality()
        filtered = _filter_by_quality(resp["streams"], max_quality)
        filtered.sort(key=lambda s: QUALITY_ORDER.get(s.get("_quality", "Unknown"), 99))
        return filtered
    return []


def get_episode_sources(imdb_id, season, episode):
    rd_token = get_setting("rd_token", "")
    url = _build_url("/stream/series/%s:%s:%s" % (imdb_id, season, episode), rd_token)
    log("Torrentio episode: %s S%sE%s" % (imdb_id, season, episode))
    resp = _fetch_json(url)
    if resp and "streams" in resp:
        max_quality = _get_max_quality()
        filtered = _filter_by_quality(resp["streams"], max_quality)
        filtered.sort(key=lambda s: QUALITY_ORDER.get(s.get("_quality", "Unknown"), 99))
        return filtered
    return []
