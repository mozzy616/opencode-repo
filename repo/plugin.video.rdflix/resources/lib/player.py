import urllib.request
import urllib.parse
import re

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.kodi_utils import log, notify, dialog_ok, dialog_yesno, dialog_select, set_resolved_url
from resources.lib.rd_api import resolve_magnet, unrestrict_link
from resources.lib.torrentio import get_movie_sources, get_episode_sources
from resources.lib.tmdb_api import get_external_ids
from resources.lib.constants import QUALITY_ORDER

TRY_LORDPLAYER = False
try:
    lid = "plugin.video.lordplayer.droid" if xbmc.getCondVisibility("System.HasAddon(plugin.video.lordplayer.droid)") else "plugin.video.lordplayer"
    TRY_LORDPLAYER = True
except:
    pass


def _play_url(url, title):
    try:
        li = xbmcgui.ListItem(path=url, label=title)
        li.setProperty("IsPlayable", "true")
        set_resolved_url(True, li)
        return True
    except Exception as e:
        log("Play URL error: %s" % str(e), xbmc.LOGERROR)
        return False


def _play_rd_stream(stream, title):
    info_hash = stream.get("infoHash", "")
    torrent_title = stream.get("title", title)
    behavior_hints = stream.get("behaviorHints", {})
    file_name = behavior_hints.get("filename", torrent_title or title)

    url = stream.get("url", "")
    if url and ("/torrent/" in url or "/stream/" in url):
        url = info_hash
    elif not url:
        url = info_hash

    if url and (url.startswith("http://") or url.startswith("https://")):
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0")
            urllib.request.urlopen(req, timeout=5)
            return _play_url(url, file_name)
        except:
            log("Direct URL unreachable, trying magnet approach", xbmc.LOGINFO)

    if info_hash and len(info_hash) >= 40:
        magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(torrent_title or title))
        try:
            result = resolve_magnet(magnet, torrent_title or title)
            if result and result.get("url"):
                return _play_url(result["url"], result.get("filename", file_name))
        except Exception as e:
            log("Magnet resolve error: %s" % str(e), xbmc.LOGERROR)

    if info_hash and TRY_LORDPLAYER:
        try:
            magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(torrent_title or title))
            return _play_via_lordplayer(magnet, file_name)
        except:
            pass

    return False


def _play_via_lordplayer(magnet, title):
    try:
        lid = "plugin.video.lordplayer.droid" if xbmc.getCondVisibility("System.HasAddon(plugin.video.lordplayer.droid)") else "plugin.video.lordplayer"
        plugin_url = "plugin://%s/play_magnet?magnet=%s&buffer=true" % (lid, urllib.parse.quote(magnet, safe=""))
        li = xbmcgui.ListItem(path=plugin_url, label=title)
        li.setProperty("IsPlayable", "true")
        set_resolved_url(True, li)
        return True
    except Exception as e:
        log("LordPlayer error: %s" % str(e), xbmc.LOGERROR)
        return False


def _build_source_label(s):
    stitle = s.get("title", "").strip()
    quality = s.get("_quality", "?")
    size_str = ""
    behavior = s.get("behaviorHints", {})
    fname = behavior.get("filename", "")
    size_match = re.search(r"(\d+(?:\.\d+)?)\s*(GB|MB)", fname, re.IGNORECASE)
    if size_match:
        size_str = " [%s%s]" % (size_match.group(1), size_match.group(2).upper())
    seeders = s.get("seeders", s.get("seed", 0))
    seed_str = " [S:%s]" % seeders if seeders else ""
    cached = s.get("isDebridCached", False)

    if cached:
        tag = "[COLOR lime][RD Instant][/COLOR]"
    else:
        tag = "[COLOR orange][LPlayer][/COLOR]" if TRY_LORDPLAYER else "[COLOR orange][Torrent][/COLOR]"

    if stitle:
        return "%s%s %s %s%s" % (tag, quality, stitle[:55], size_str, seed_str)
    return "%s%s %s%s" % (tag, quality, size_str, seed_str)


def play_movie(imdb_id, tmdb_id, title, year=""):
    if not imdb_id and tmdb_id:
        ext = get_external_ids(tmdb_id, "movie")
        if ext:
            imdb_id = ext.get("imdb_id") or ""
            log("Resolved imdb_id from tmdb: %s" % imdb_id)
    if not imdb_id:
        log("No imdb_id for movie: %s (tmdb=%s)" % (title, tmdb_id), xbmc.LOGWARNING)
        dialog_ok("RDFlix", "Could not find source IDs for\n%s" % title)
        set_resolved_url(False, xbmcgui.ListItem(label=title))
        return

    sources = get_movie_sources(imdb_id)

    if not sources:
        dialog_ok("RDFlix", "No sources found for\n%s" % title)
        set_resolved_url(False, xbmcgui.ListItem(label=title))
        return

    sources.sort(key=lambda s: (not s.get("isDebridCached", False), QUALITY_ORDER.get(s.get("_quality", "Unknown"), 99)))

    if len(sources) == 1:
        s = sources[0]
        log("Playing single source: %s" % s.get("title", ""))
        if not _play_rd_stream(s, title):
            dialog_ok("RDFlix", "Failed to play\n%s" % title)
            set_resolved_url(False, xbmcgui.ListItem(label=title))
        return

    labels = [_build_source_label(s) for s in sources]
    idx = dialog_select("Select Source - %s" % title, labels)
    if idx < 0:
        set_resolved_url(False, xbmcgui.ListItem(label=title))
        return

    chosen = sources[idx]
    if not _play_rd_stream(chosen, title):
        dialog_ok("RDFlix", "Failed to play\n%s" % title)
        set_resolved_url(False, xbmcgui.ListItem(label=title))


def play_episode(imdb_id, tmdb_id, show_title, season, episode, episode_title=""):
    s_int = int(season) if season else 0
    e_int = int(episode) if episode else 0
    full_title = "%s S%02dE%02d" % (show_title, s_int, e_int)

    if not imdb_id and tmdb_id:
        ext = get_external_ids(tmdb_id, "tv")
        if ext:
            imdb_id = ext.get("imdb_id") or ""
            log("Resolved imdb_id from tmdb: %s" % imdb_id)
    if not imdb_id:
        log("No imdb_id for episode: %s (tmdb=%s)" % (full_title, tmdb_id), xbmc.LOGWARNING)
        dialog_ok("RDFlix", "Could not find source IDs for\n%s" % full_title)
        set_resolved_url(False, xbmcgui.ListItem(label=full_title))
        return

    sources = get_episode_sources(imdb_id, s_int, e_int)

    if not sources:
        dialog_ok("RDFlix", "No sources found for\n%s" % full_title)
        set_resolved_url(False, xbmcgui.ListItem(label=full_title))
        return

    sources.sort(key=lambda s: (not s.get("isDebridCached", False), QUALITY_ORDER.get(s.get("_quality", "Unknown"), 99)))

    if len(sources) == 1:
        s = sources[0]
        label = "%s - S%02dE%02d" % (show_title, s_int, e_int)
        if not _play_rd_stream(s, label):
            dialog_ok("RDFlix", "Failed to play\n%s" % full_title)
            set_resolved_url(False, xbmcgui.ListItem(label=label))
        return

    labels = [_build_source_label(s) for s in sources]
    idx = dialog_select("Select Source - %s" % full_title, labels)
    if idx < 0:
        set_resolved_url(False, xbmcgui.ListItem(label=full_title))
        return

    chosen = sources[idx]
    label = "%s - S%02dE%02d" % (show_title, s_int, e_int)
    if not _play_rd_stream(chosen, label):
        dialog_ok("RDFlix", "Failed to play\n%s" % full_title)
        set_resolved_url(False, xbmcgui.ListItem(label=label))
