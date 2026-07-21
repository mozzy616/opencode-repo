import urllib.request
import urllib.parse
import re

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.kodi_utils import log, notify, dialog_ok, dialog_yesno, dialog_select, set_resolved_url, get_setting
from resources.lib.rd_api import resolve_magnet, unrestrict_link, instant_availability, user_torrents_list
from resources.lib.torrentio import get_movie_sources, get_episode_sources
from resources.lib.tmdb_api import get_external_ids
from resources.lib.constants import QUALITY_ORDER
from resources.lib.scrapers import search_movie as scraper_search_movie, search_episode as scraper_search_episode
from resources.lib.cache import get_cached_hashes, set_cached_hashes

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


def _play_source(source, title):
    magnet = source.get("magnet", "")
    info_hash = source.get("infoHash", "")

    if not info_hash and magnet:
        m = re.search(r"btih:([a-fA-F0-9]{40})", magnet)
        if m:
            info_hash = m.group(1)

    torrent_title = source.get("title", source.get("name", title))
    behavior_hints = source.get("behaviorHints", {})
    fname = behavior_hints.get("filename", "")
    file_name = fname or torrent_title or title

    url = source.get("url", "")
    if url and ("/torrent/" in url or "/stream/" in url):
        url = ""
    if not url:
        url = info_hash

    if url and (url.startswith("http://") or url.startswith("https://")):
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0")
            urllib.request.urlopen(req, timeout=5)
            return _play_url(url, file_name)
        except:
            log("Direct URL unreachable, trying magnet approach", xbmc.LOGINFO)

    actual_magnet = magnet
    if not actual_magnet and info_hash and len(info_hash) >= 40:
        actual_magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(torrent_title or title))

    if actual_magnet:
        try:
            result = resolve_magnet(actual_magnet, torrent_title or title)
            if result and result.get("url"):
                return _play_url(result["url"], result.get("filename", file_name))
        except Exception as e:
            log("Magnet resolve error: %s" % str(e), xbmc.LOGERROR)

    if actual_magnet and TRY_LORDPLAYER:
        try:
            return _play_via_lordplayer(actual_magnet, file_name)
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
    stitle = s.get("title", s.get("name", ""))
    quality = s.get("_quality", s.get("quality", "?"))
    size_str = ""
    size_raw = s.get("size", "")
    if size_raw:
        size_str = " [%s]" % str(size_raw)

    seeders = s.get("seeders", s.get("seed", 0))
    seed_str = " [S:%s]" % seeders if seeders else ""
    cached = s.get("isDebridCached", False) or s.get("debrid", False)

    if cached:
        tag = "[COLOR lime][RD Instant][/COLOR]"
    else:
        tag = "[COLOR orange][LPlayer][/COLOR]" if TRY_LORDPLAYER else "[COLOR orange][Torrent][/COLOR]"

    if stitle:
        return "%s%s %s %s%s" % (tag, quality, stitle[:55], size_str, seed_str)
    return "%s%s %s%s" % (tag, quality, size_str, seed_str)


def _merge_sources(torrentio_sources, scraper_sources):
    all_sources = []

    for s in torrentio_sources:
        rd_token = get_setting("rd_token", "")
        all_sources.append({
            "infoHash": s.get("infoHash", ""),
            "title": s.get("title", ""),
            "name": s.get("name", s.get("title", "")),
            "url": s.get("url", ""),
            "behaviorHints": s.get("behaviorHints", {}),
            "_quality": s.get("_quality", "?"),
            "seeders": s.get("seeders", s.get("seed", 0)),
            "size": s.get("size", ""),
            "isDebridCached": bool(rd_token),
        })

    seen_hashes = set()
    for s in all_sources:
        h = s.get("infoHash", "")
        if h:
            seen_hashes.add(h.lower()[:40])

    for s in scraper_sources:
        h = (s.get("hash") or "").lower()[:40]
        if h and h in seen_hashes:
            continue
        if h:
            seen_hashes.add(h)
            magnet = s.get("magnet", "")
            if not magnet and h:
                import urllib.parse as up
                magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (h, up.quote(s.get("name", "")))
        all_sources.append({
            "infoHash": h,
            "magnet": s.get("magnet", ""),
            "title": s.get("name", ""),
            "name": s.get("name", ""),
            "url": s.get("magnet", ""),
            "_quality": s.get("quality", _detect_scraper_quality(s.get("name", ""))),
            "seeders": s.get("seeders", 0),
            "size": s.get("size", ""),
            "isDebridCached": s.get("debrid", False),
        })

    all_sources.sort(key=lambda s: (
        not s.get("isDebridCached", False),
        QUALITY_ORDER.get(s.get("_quality", "Unknown"), 99),
        -(s.get("seeders", 0) or 0)
    ))
    return all_sources


def _check_rd_cache(sources):
    token = get_setting("rd_token", "")
    if not token:
        return sources

    hashes = []
    hash_to_idx = {}
    for idx, s in enumerate(sources):
        h = s.get("infoHash", "")
        if h and len(h) >= 40 and not s.get("isDebridCached"):
            hl = h.lower()[:40]
            hashes.append(hl)
            hash_to_idx[hl] = idx

    if not hashes:
        return sources

    # Step 1: Check local SQLite cache
    db_cached, unknown = get_cached_hashes(hashes)
    for h in db_cached:
        if h in hash_to_idx:
            sources[hash_to_idx[h]]["isDebridCached"] = True

    if not unknown:
        log("RD cache: all hashes resolved from local DB (%d cached)" % len(db_cached))
        return _sort_sources(sources)

    # Step 2: Try instantAvailability for unknown hashes
    newly_cached = []
    try:
        cached = instant_availability(unknown)
        if cached:
            for h, info in cached.items():
                hkey = h.lower()[:40]
                if hkey in hash_to_idx and isinstance(info, dict) and info:
                    sources[hash_to_idx[hkey]]["isDebridCached"] = True
                    newly_cached.append(hkey)
            log("RD instantAvailability: %d cached, checked %d" % (len(newly_cached), len(unknown)))
    except Exception:
        pass

    # Step 3: Fallback - check user's RD torrents list for remaining unknown
    remaining = [h for h in unknown if h not in newly_cached]
    if remaining:
        try:
            existing = user_torrents_list()
            if existing:
                rd_hashes = set()
                for t in existing:
                    th = (t.get("hash") or "").lower()[:40]
                    if th and t.get("status") == "downloaded":
                        rd_hashes.add(th)
                for h in remaining:
                    if h in rd_hashes:
                        sources[hash_to_idx[h]]["isDebridCached"] = True
                        newly_cached.append(h)
                log("RD torrents list: %d cached from %d existing" % (len(newly_cached), len(rd_hashes)))
        except Exception:
            pass

    # Step 4: Save newly found cached hashes to local DB
    if newly_cached:
        set_cached_hashes(newly_cached, is_cached=True)

    # Also save NOT cached hashes so we don't re-check them (with shorter TTL they'll expire)
    not_cached = [h for h in unknown if h not in newly_cached]
    if not_cached:
        set_cached_hashes(not_cached, is_cached=False)

    return _sort_sources(sources)


def _sort_sources(sources):
    sources.sort(key=lambda s: (
        not s.get("isDebridCached", False),
        QUALITY_ORDER.get(s.get("_quality", "Unknown"), 99),
        -(s.get("seeders", 0) or 0)
    ))
    return sources

    hashes = []
    hash_to_idx = {}
    for idx, s in enumerate(sources):
        h = s.get("infoHash", "")
        if h and len(h) >= 40 and not s.get("isDebridCached"):
            hl = h.lower()[:40]
            hashes.append(hl)
            hash_to_idx[hl] = idx

    if not hashes:
        return sources

    found = 0

    # Try instantAvailability first
    try:
        cached = instant_availability(hashes)
        if cached:
            for h, info in cached.items():
                hkey = h.lower()[:40]
                if hkey in hash_to_idx:
                    if isinstance(info, dict) and info:
                        idx = hash_to_idx[hkey]
                        sources[idx]["isDebridCached"] = True
                        found += 1
            log("RD instantAvailability: %d/%d cached" % (found, len(hashes)))
    except Exception as e:
        log("RD instantAvailability failed: %s, trying torrents list..." % str(e), xbmc.LOGWARNING)

    # Fallback: check against user's existing RD torrents
    if found == 0:
        try:
            existing = user_torrents_list()
            if existing:
                rd_hashes = set()
                for t in existing:
                    th = (t.get("hash") or "").lower()[:40]
                    if th and t.get("status") == "downloaded":
                        rd_hashes.add(th)
                for hkey, idx in hash_to_idx.items():
                    if hkey in rd_hashes and not sources[idx].get("isDebridCached"):
                        sources[idx]["isDebridCached"] = True
                        found += 1
                log("RD torrents list: %d/%d cached from %d existing" % (found, len(hashes), len(rd_hashes)))
        except Exception as e:
            log("RD torrents list fallback failed: %s" % str(e), xbmc.LOGWARNING)

    sources.sort(key=lambda s: (
        not s.get("isDebridCached", False),
        QUALITY_ORDER.get(s.get("_quality", "Unknown"), 99),
        -(s.get("seeders", 0) or 0)
    ))
    return sources


def _detect_scraper_quality(name):
    name = (name or "").lower()
    if "4k" in name or "2160" in name or "uhd" in name:
        return "4K"
    if "1080" in name:
        return "1080p"
    if "720" in name:
        return "720p"
    return "SD"


def play_movie(imdb_id, tmdb_id, title, year=""):
    if not imdb_id and tmdb_id:
        ext = get_external_ids(tmdb_id, "movie")
        if ext:
            imdb_id = ext.get("imdb_id") or ""
    if not imdb_id:
        log("No imdb_id for movie: %s (tmdb=%s)" % (title, tmdb_id), xbmc.LOGWARNING)
        dialog_ok("RDFlix", "Could not find source IDs for\n%s" % title)
        set_resolved_url(False, xbmcgui.ListItem(label=title))
        return

    log("Searching all sources for movie: %s" % title)
    tio_sources = get_movie_sources(imdb_id)
    scr_sources = scraper_search_movie(imdb_id, title, year)
    sources = _merge_sources(tio_sources, scr_sources)
    sources = _check_rd_cache(sources)

    if not sources:
        dialog_ok("RDFlix", "No sources found for\n%s" % title)
        set_resolved_url(False, xbmcgui.ListItem(label=title))
        return

    if len(sources) == 1:
        s = sources[0]
        if not _play_source(s, title):
            dialog_ok("RDFlix", "Failed to play\n%s" % title)
            set_resolved_url(False, xbmcgui.ListItem(label=title))
        return

    labels = [_build_source_label(s) for s in sources]
    idx = dialog_select("Select Source - %s" % title, labels)
    if idx < 0:
        set_resolved_url(False, xbmcgui.ListItem(label=title))
        return

    if not _play_source(sources[idx], title):
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
    if not imdb_id:
        log("No imdb_id for episode: %s (tmdb=%s)" % (full_title, tmdb_id), xbmc.LOGWARNING)
        dialog_ok("RDFlix", "Could not find source IDs for\n%s" % full_title)
        set_resolved_url(False, xbmcgui.ListItem(label=full_title))
        return

    log("Searching all sources for episode: %s" % full_title)
    tio_sources = get_episode_sources(imdb_id, s_int, e_int)
    scr_sources = scraper_search_episode(imdb_id, show_title, season, episode, "")
    sources = _merge_sources(tio_sources, scr_sources)
    sources = _check_rd_cache(sources)

    if not sources:
        dialog_ok("RDFlix", "No sources found for\n%s" % full_title)
        set_resolved_url(False, xbmcgui.ListItem(label=full_title))
        return

    if len(sources) == 1:
        s = sources[0]
        label = "%s - S%02dE%02d" % (show_title, s_int, e_int)
        if not _play_source(s, label):
            dialog_ok("RDFlix", "Failed to play\n%s" % full_title)
            set_resolved_url(False, xbmcgui.ListItem(label=label))
        return

    labels = [_build_source_label(s) for s in sources]
    idx = dialog_select("Select Source - %s" % full_title, labels)
    if idx < 0:
        set_resolved_url(False, xbmcgui.ListItem(label=full_title))
        return

    label = "%s - S%02dE%02d" % (show_title, s_int, e_int)
    if not _play_source(sources[idx], label):
        dialog_ok("RDFlix", "Failed to play\n%s" % full_title)
        set_resolved_url(False, xbmcgui.ListItem(label=label))
