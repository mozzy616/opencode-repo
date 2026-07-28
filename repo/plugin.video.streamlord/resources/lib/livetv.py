import re
import urllib.request
import urllib.error
import urllib.parse

import xbmcvfs

from resources.lib.kodi_utils import log, get_setting, translate_path


def _fetch_text(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log("LiveTV fetch error: %s" % str(e))
        return None


def _cache_path():
    path = translate_path("special://profile/addon_data/plugin.video.rdflix/livetv_cache/")
    import os
    os.makedirs(path, exist_ok=True)
    return path


def _load_cached(filename):
    import os
    fp = os.path.join(_cache_path(), filename)
    if os.path.exists(fp):
        with open(fp, "r", encoding="utf-8") as f:
            return f.read()
    return None


def _save_cached(filename, content):
    import os
    fp = os.path.join(_cache_path(), filename)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)


def get_playlist_urls():
    raw = get_setting("livetv_urls", "")
    if not raw:
        return ["https://s.id/d9M3U8"]
    urls = []
    for line in raw.splitlines():
        line = line.strip()
        if line and line.startswith("http"):
            urls.append(line)
    if not urls:
        return ["https://s.id/d9M3U8"]
    return urls


def parse_m3u(content):
    """Parse M3U/M3U8 content into a list of channel dicts."""
    channels = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            info = {}
            name = ""
            # Parse attributes
            attrs = re.findall(r'([\w-]+)="([^"]*)"', line)
            for k, v in attrs:
                info[k.lower()] = v
            # Parse name after comma
            comma = line.rfind(",")
            if comma >= 0:
                name = line[comma + 1:].strip()
            info["name"] = name or "Unknown Channel"
            # Get URL from next line
            i += 1
            if i < len(lines):
                url = lines[i].strip()
                if url and not url.startswith("#"):
                    info["url"] = url
                    channels.append(info)
        i += 1
    return channels


def load_channels():
    """Load all channels from configured playlists."""
    urls = get_playlist_urls()
    if not urls:
        return []

    all_channels = []
    for url in urls:
        log("LiveTV: fetching %s" % url[:80])
        content = _fetch_text(url)
        if content:
            channels = parse_m3u(content)
            all_channels.extend(channels)
            log("LiveTV: %d channels from %s" % (len(channels), url[:60]))

    return all_channels


def get_groups(channels):
    """Extract unique groups from channel list, splitting semicolon-separated values."""
    groups = set()
    for c in channels:
        group_str = c.get("tvg-group", c.get("group-title", "Other"))
        for g in group_str.split(";"):
            g = g.strip()
            if g:
                groups.add(g)
    return sorted(groups)


def get_channels_by_group(channels, group):
    """Filter channels by group. Checks if group is contained in channel's group-title."""
    result = []
    for c in channels:
        cg = c.get("tvg-group", c.get("group-title", "Other"))
        if group == cg or group in cg.split(";"):
            result.append(c)
    return result


def build_cached_name(url):
    import urllib.parse
    return "livetv_" + urllib.parse.quote(url, safe="")[:50] + ".m3u"
