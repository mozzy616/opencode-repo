import urllib.request
import urllib.parse
import re

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.kodi_utils import log, notify, dialog_ok, dialog_yesno, dialog_select, set_resolved_url, get_setting, translate_path, end_directory
from resources.lib.rd_api import resolve_magnet, unrestrict_link, instant_availability, user_torrents_list
from resources.lib.torrentio import get_movie_sources, get_episode_sources
from resources.lib.tmdb_api import get_external_ids
from resources.lib.constants import QUALITY_ORDER
from resources.lib.scrapers import search_movie as scraper_search_movie, search_episode as scraper_search_episode
from resources.lib.cache import get_cached_hashes, set_cached_hashes
from resources.lib.analytics import update_continue_watching
from resources.lib.ad_api import resolve_magnet as ad_resolve_magnet
from resources.lib.rd_api import add_magnet as rd_add_magnet
import threading
from resources.lib.pm_api import resolve_magnet as pm_resolve_magnet
from resources.lib.trakt_api import scrobble_start, scrobble_stop, is_authenticated as trakt_authenticated
import json

TRACKERS = "&tr=udp://tracker.opentrackr.org:1337/announce&tr=udp://open.stealth.si:80/announce&tr=udp://tracker.torrent.eu.org:451/announce"

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


def _verify_playback_started(timeout=12):
    """Return True if a player is actively playing within `timeout` seconds."""
    monitor = xbmc.Monitor()
    player = xbmc.Player()
    waited = 0
    while waited < timeout:
        if player.isPlaying():
            return True
        if monitor.abortRequested():
            return False
        xbmc.sleep(500)
        waited += 1
    return False


def _is_dmca_video(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=8) as r:
            cl = r.headers.get("Content-Length", "0")
            size = int(cl) if cl else 0
            log("RD file size check: %d bytes" % size)
            if 0 < size < 52428800:
                log("RD file too small (%d bytes < 50MB), likely DMCA notice" % size)
                return True
    except Exception as e:
        log("DMCA check failed: %s" % str(e))
    return False


def _play_source(source, title):
    """Dispatch to the correct player based on source type (RD or LordPlayer)."""
    is_rd = source.get("isDebridCached", False) or source.get("debrid", False)
    if is_rd:
        return _play_rd_source(source, title)
    return _play_lp_source(source, title)


def _play_rd_source(source, title):
    """Play a Real-Debrid cached source (instant URL or magnet resolve). No LordPlayer fallback."""
    magnet = source.get("magnet", "")
    info_hash = source.get("infoHash", "")
    behavior_hints = source.get("behaviorHints", {})
    if not info_hash:
        info_hash = behavior_hints.get("infoHash", "")
    if not magnet:
        magnet = behavior_hints.get("magnet", "")

    torrent_title = source.get("title", source.get("name", title))
    fname = behavior_hints.get("filename", "")
    file_name = fname or torrent_title or title

    url = source.get("url", "")
    if url and ("/torrent/" in url or "/stream/" in url):
        url = ""

    # 1) RD instant download URL
    if url and url.startswith("http"):
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0")
            resp = urllib.request.urlopen(req, timeout=8)
            final_url = resp.geturl() or url
            if any(x in final_url.lower() for x in ["configure", "exception", "error/", "autorize", "authorize"]):
                raise Exception("Invalid redirect")
            cl = resp.headers.get("Content-Length", "0")
            size = int(cl) if cl else 0
            if 0 < size < 52428800:
                raise Exception("DMCA detected")
            if _play_url(final_url, file_name):
                return True
        except Exception as e:
            log("RD direct URL failed (%s), trying magnet resolve" % str(e), xbmc.LOGINFO)

    # 2) RD magnet resolve
    actual_magnet = magnet
    if not actual_magnet and info_hash and len(info_hash) >= 40:
        actual_magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(torrent_title or title))

    if actual_magnet:
        result = None
        for resolver in [resolve_magnet, ad_resolve_magnet, pm_resolve_magnet]:
            try:
                result = resolver(actual_magnet, torrent_title or title)
                if result and result.get("url"):
                    break
            except:
                continue
        if result and result.get("url"):
            if not _is_dmca_video(result["url"]):
                return _play_url(result["url"], result.get("filename", file_name))

    log("RD source failed to play", xbmc.LOGINFO)
    return False


def _play_lp_source(source, title):
    """Play a LordPlayer (torrent) source. No RD fallback."""
    magnet = source.get("magnet", "")
    info_hash = source.get("infoHash", "")
    behavior_hints = source.get("behaviorHints", {})
    if not info_hash:
        info_hash = behavior_hints.get("infoHash", "")
    if not magnet:
        magnet = behavior_hints.get("magnet", "")
    if not info_hash and magnet:
        m = re.search(r"btih:([a-fA-F0-9]{40})", magnet)
        if m:
            info_hash = m.group(1)

    torrent_title = source.get("title", source.get("name", title))
    fname = behavior_hints.get("filename", "")
    file_name = fname or torrent_title or title

    actual_magnet = magnet
    if not actual_magnet and info_hash and len(info_hash) >= 40:
        actual_magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(torrent_title or title))

    if not actual_magnet:
        notify("RDFlix", "This source has no magnet link.\nPick another source.", duration=6000)
        return False
    if not TRY_LORDPLAYER:
        return False
    if not re.search(r"btih:([a-fA-F0-9]{40})", actual_magnet):
        notify("RDFlix", "This source has an invalid magnet link.\nPick another source.", duration=6000)
        return False
    return _play_via_lordplayer(actual_magnet, file_name)


def _prebuffer_magnet(magnet, min_bytes=10 * 1024 * 1024, timeout=45):
    """Add magnet to torrest, select the largest video, wait for ~10MB buffered.
    Returns a serve URL or None."""
    if not TRY_LORDPLAYER:
        return None
    try:
        if not re.search(r"btih:([a-fA-F0-9]{40})", magnet):
            log("Prebuffer: invalid magnet (non-hex hash), skipping", xbmc.LOGWARNING)
            return None
        uri = magnet if TRACKERS in magnet else magnet + TRACKERS
        base = "http://127.0.0.1:61235"
        d = _torrest_req(base, "POST", "/add/magnet", {"uri": uri, "ignore_duplicate": "true", "download": "false"})
        th = d.get("info_hash", "")
        if not th:
            return None
        for _ in range(30):
            st = _torrest_req(base, "GET", "/torrents/%s/status" % th)
            if st.get("has_metadata"):
                break
            xbmc.sleep(1000)
        files = _torrest_req(base, "GET", "/torrents/%s/files" % th) or []
        vids = [f for f in files if f.get("path", "").lower().endswith((".mp4", ".mkv", ".avi", ".m4v", ".mov", ".webm", ".ts"))]
        if not vids:
            vids = files
        if not vids:
            return None
        vids.sort(key=lambda f: f.get("size", 0), reverse=True)
        fid = vids[0].get("id")
        try:
            _torrest_req(base, "PUT", "/torrents/%s/files/%s/download" % (th, fid), {"buffer": "true"})
        except Exception:
            pass
        for _ in range(timeout):
            fs = _torrest_req(base, "GET", "/torrents/%s/files/%s/status" % (th, fid))
            done = fs.get("total_done", 0) or 0
            if not done:
                bp = fs.get("buffering_progress", 0) or 0
                bt = fs.get("buffering_total", 0) or 0
                done = int(bt * bp / 100.0)
            if done >= min_bytes:
                break
            xbmc.sleep(1000)
        return "%s/torrents/%s/files/%s/serve" % (base, th, fid)
    except Exception as e:
        log("Prebuffer error: %s" % str(e), xbmc.LOGERROR)
        return None


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
    is_pack = _is_season_pack(stitle)

    if cached:
        tag = "[COLOR lime]RD[/COLOR] "
    elif is_pack:
        tag = "[COLOR yellow]PACK[/COLOR] "
    else:
        tag = "[COLOR orange]LP[/COLOR] " if TRY_LORDPLAYER else "[COLOR orange]TR[/COLOR] "

    label = "%s%s %s%s%s" % (tag, quality, stitle[:45] if stitle else "Unknown", size_str, seed_str)
    return label.strip()


def _is_season_pack(name):
    """Detect if a torrent name is a full season pack (not a single episode)."""
    import re
    name = name or ""
    patterns = [
        r'[Ss]\d{1,2}\s*(complete|full|season|pack)',  
        r'[Ss](eason)?\s*\d{1,2}\s*$',                  
        r'[Ss]\d{1,2}\.E\d{1,2}',                        
    ]
    has_season = bool(re.search(r'[Ss]\d{1,2}', name))
    has_episode = bool(re.search(r'[Ss]\d{1,2}[Ee]\d{1,2}', name))
    has_pack = any(re.search(p, name, re.IGNORECASE) for p in patterns)
    return has_season and not has_episode and (has_pack or "complete" in name.lower() or "season" in name.lower() or re.match(r'.*S\d{1,2}\s+', name))


_PACK_CONTEXT = {}


def _ep_from_filename(name):
    name = name or ""
    m = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})', name)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'[Ee](\d{1,2})', name)
    if m:
        return 0, int(m.group(1))
    return None, None


def _rd_pack_files(magnet):
    """List video files in a season pack via Real-Debrid."""
    from resources.lib.rd_api import torrent_info as rd_torrent_info
    m = re.search(r"btih:([a-fA-F0-9]{40})", magnet)
    if not m:
        return []
    h = m.group(1).lower()
    tid = None
    for t in (user_torrents_list() or []):
        if t.get("hash", "").lower() == h:
            tid = t.get("id")
            break
    if not tid:
        tid = rd_add_magnet(magnet)
    if not tid:
        return []
    for _ in range(20):
        info = rd_torrent_info(tid) or {}
        if info.get("status", "") != "magnet_conversion" and info.get("files"):
            break
        xbmc.sleep(1000)
    info = rd_torrent_info(tid) or {}
    if info.get("status", "") != "downloaded":
        return []
    out = []
    for f in info.get("files", []):
        if f.get("path", "").lower().endswith((".mp4", ".mkv", ".avi", ".m4v", ".mov", ".webm", ".ts")):
            out.append({
                "id": f.get("id"),
                "path": f.get("path", ""),
                "size": f.get("bytes", 0),
                "rd": True,
                "torrent_id": tid,
                "download": f.get("download", ""),
            })
    return out


def _lp_pack_files(magnet):
    """List video files in a season pack via the torrest (LordPlayer) daemon."""
    if not TRY_LORDPLAYER:
        return []
    uri = magnet if TRACKERS in magnet else magnet + TRACKERS
    base = "http://127.0.0.1:61235"
    d = _torrest_req(base, "POST", "/add/magnet", {"uri": uri, "ignore_duplicate": "true", "download": "false"})
    th = d.get("info_hash", "")
    if not th:
        return []
    for _ in range(30):
        st = _torrest_req(base, "GET", "/torrents/%s/status" % th)
        if st.get("has_metadata"):
            break
        xbmc.sleep(1000)
    out = []
    for f in (_torrest_req(base, "GET", "/torrents/%s/files" % th) or []):
        if f.get("path", "").lower().endswith((".mp4", ".mkv", ".avi", ".m4v", ".mov", ".webm", ".ts")):
            out.append({
                "id": f.get("id"),
                "path": f.get("path", ""),
                "size": f.get("size", 0),
                "rd": False,
                "th": th,
            })
    return out


def _list_pack_files(magnet, title):
    files = _rd_pack_files(magnet)
    if files:
        return files
    return _lp_pack_files(magnet)


def _pack_file_url(f, title):
    if f.get("rd"):
        try:
            from resources.lib.rd_api import unrestrict_link
            dl = unrestrict_link(f.get("download", ""))
            if dl and dl.get("download"):
                return dl["download"]
        except Exception as e:
            log("Pack RD play error: %s" % str(e))
        return None
    th = f.get("th")
    try:
        _torrest_req("http://127.0.0.1:61235", "PUT", "/torrents/%s/files/%s/download" % (th, f["id"]), {"buffer": "true"})
    except Exception:
        pass
    return "http://127.0.0.1:61235/torrents/%s/files/%s/serve" % (th, f["id"])


def _browse_season_pack(source, title):
    """Add season pack magnet, browse episode files, play the selected episode.
    Returns (season, episode) of the played file, or (None, None)."""
    import re as regex
    magnet = source.get("magnet", "")
    info_hash = source.get("infoHash", "")
    if not magnet and info_hash and len(info_hash) >= 40:
        magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(title))
    if not magnet:
        dialog_ok("RDFlix", "No magnet link for this season pack")
        return None, None

    files = _list_pack_files(magnet, title)
    if not files:
        dialog_ok("RDFlix", "Could not load season pack files")
        return None, None

    labels = []
    for f in files:
        fname = f.get("path", "Unknown")
        s, e = _ep_from_filename(fname)
        size = f.get("size", 0)
        size_str = ""
        if size >= 1073741824:
            size_str = "%.1f GB" % (size / 1073741824)
        elif size >= 1048576:
            size_str = "%.0f MB" % (size / 1048576)
        if s and e:
            labels.append("S%02dE%02d - %s [%s]" % (s, e, fname, size_str))
        else:
            labels.append("%s [%s]" % (fname, size_str))

    idx = dialog_select("Season Pack - %s" % title[:30], labels)
    if idx < 0:
        return None, None

    chosen = files[idx]
    url = _pack_file_url(chosen, title)
    if not url:
        dialog_ok("RDFlix", "Could not play this file")
        return None, None

    _PACK_CONTEXT["magnet"] = magnet
    _PACK_CONTEXT["title"] = title

    s, e = _ep_from_filename(chosen.get("path", ""))
    li = xbmcgui.ListItem(path=url, label=chosen.get("path", title))
    li.setProperty("IsPlayable", "true")
    set_resolved_url(True, li)
    return (s if s else 0, e if e else 0)


def _merge_sources(torrentio_sources, scraper_sources):
    all_sources = []

    for s in torrentio_sources:
        bh = s.get("behaviorHints", {})
        ihash = s.get("infoHash", "") or bh.get("infoHash", "")
        url = s.get("url", "")

        if not ihash:
            if "playback" in url or "exception" in url or "configure" in url or "error" in url.lower():
                continue

        all_sources.append({
            "infoHash": ihash,
            "title": s.get("title", ""),
            "name": s.get("name", s.get("title", "")),
            "url": url,
            "behaviorHints": bh,
            "_quality": s.get("_quality", "?"),
            "seeders": s.get("seeders", s.get("seed", 0)),
            "size": s.get("size", ""),
            "isDebridCached": True,
            "_origin": s.get("_origin", ""),
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
            "_origin": "Scraper",
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
        else:
            log("RD instantAvailability: 0 cached from %d hashes" % len(unknown))
    except Exception as e:
        log("RD instantAvailability failed (may be disabled): %s" % str(e), xbmc.LOGWARNING)

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


def _detect_scraper_quality(name):
    name = (name or "").lower()
    if "4k" in name or "2160" in name or "uhd" in name:
        return "4K"
    if "1080" in name:
        return "1080p"
    if "720" in name:
        return "720p"
    return "SD"


def _handle_source_action(source, title, imdb_id="", season=None, episode=None, show_title="", resume_at=0):
    """Show Play/Download dialog for a selected source.
    Returns (season, episode) of the played file, or None if not played."""
    if not source:
        set_resolved_url(False, xbmcgui.ListItem(label=title))
        return None

    choice = dialog_select("Choose action - %s" % title[:40], ["Play", "Download"])
    if choice < 0:
        set_resolved_url(False, xbmcgui.ListItem(label=title))
        return None

    if choice == 0:
        s_int = int(season) if season else 0
        e_int = int(episode) if episode else 0
        is_pack = _is_season_pack(source.get("title", source.get("name", "")))
        if is_pack:
            pack_s, pack_e = _browse_season_pack(source, title)
            if pack_s is None or pack_e is None:
                set_resolved_url(False, xbmcgui.ListItem(label=title))
                return None
            if imdb_id and trakt_authenticated():
                try:
                    scrobble_start("start", imdb_id, show_title or title, pack_s, pack_e)
                except:
                    pass
            return (pack_s, pack_e)

        if not _play_source(source, title):
            dialog_ok("RDFlix", "Failed to play\n%s" % title)
            set_resolved_url(False, xbmcgui.ListItem(label=title))
            return None

        if resume_at > 0:
            xbmc.sleep(2000)
            try:
                player = xbmc.Player()
                if player.isPlaying():
                    player.seekTime(resume_at)
                    log("Resumed playback at %ds" % resume_at)
            except:
                pass

        if get_setting("auto_subtitles", "false") == "true":
            xbmc.sleep(3000)
            try:
                xbmc.executebuiltin("ActivateWindow(subtitlesearch)")
            except:
                pass

        if imdb_id and trakt_authenticated():
            try:
                scrobble_start("start", imdb_id, show_title or title, season, episode)
            except:
                pass
        return (s_int, e_int)
    elif choice == 1:
        _download_source(source, title)
        set_resolved_url(False, xbmcgui.ListItem())
        return None


def _follow_redirect(url):
    """Follow a URL's redirects (HEAD) and return the final download URL."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.geturl() or url
    except Exception:
        return url


def _choose_download_folder():
    import os
    default_path = get_setting("download_path", "")
    if not default_path:
        default_path = "special://home/userdata/downloads/"
    default_path = translate_path(default_path) or translate_path("special://home/userdata/downloads/")
    dest_folder = xbmcgui.Dialog().browse(0, "Choose download folder", "files", "", False, True, default_path)
    if not dest_folder:
        dest_folder = default_path
    os.makedirs(dest_folder, exist_ok=True)
    return dest_folder


def _download_source(source, title):
    """Dispatch download based on source type (RD or LordPlayer)."""
    is_rd = source.get("isDebridCached", False) or source.get("debrid", False)
    if is_rd:
        ok = _download_rd_source(source, title)
    else:
        ok = _download_lp_source(source, title)
    if not ok:
        dialog_ok("RDFlix", "Could not download\n%s" % title)


def _download_rd_source(source, title):
    """Download a Real-Debrid cached source (instant URL or magnet resolve). No LordPlayer fallback."""
    magnet = source.get("magnet", "")
    info_hash = source.get("infoHash", "")
    behavior_hints = source.get("behaviorHints", {})
    fname = behavior_hints.get("filename", source.get("name", source.get("title", title)))
    if not fname.endswith((".mp4", ".mkv", ".avi", ".m4v", ".mov", ".webm", ".ts")):
        fname += ".mp4"

    dest_folder = _choose_download_folder()

    url = source.get("url", "")
    if url and url.startswith("http"):
        if not ("/torrent/" in url or "/stream/" in url or "127.0.0.1" in url):
            final_url = _follow_redirect(url)
            if final_url and _do_download(final_url, dest_folder, fname, title):
                return True

    if not magnet and info_hash and len(info_hash) >= 40:
        magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(title))
    if magnet:
        try:
            result = resolve_magnet(magnet, title)
            if result and result.get("url"):
                if _do_download(result["url"], dest_folder, fname, title):
                    return True
        except Exception as e:
            log("Download RD resolve error: %s" % str(e), xbmc.LOGERROR)
    return False


def _download_lp_source(source, title):
    """Download a LordPlayer (torrent) source. No RD fallback."""
    magnet = source.get("magnet", "")
    info_hash = source.get("infoHash", "")
    behavior_hints = source.get("behaviorHints", {})
    fname = behavior_hints.get("filename", source.get("name", source.get("title", title)))
    if not fname.endswith((".mp4", ".mkv", ".avi", ".m4v", ".mov", ".webm", ".ts")):
        fname += ".mp4"
    if not magnet and info_hash and len(info_hash) >= 40:
        magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(title))
    if not magnet:
        return False
    if not re.search(r"btih:([a-fA-F0-9]{40})", magnet):
        return False
    dest_folder = _choose_download_folder()
    return _lordplayer_download(magnet, title, dest_folder)


def _lordplayer_download(magnet, title, dest_folder):
    """Download via LordPlayer's torrest daemon (http://127.0.0.1:61235)."""
    import os
    if not magnet.startswith("magnet:"):
        return False
    if TRACKERS not in magnet:
        magnet += TRACKERS

    try:
        torrest_url = "http://127.0.0.1:61235"
        d = _torrest_req(torrest_url, "POST", "/add/magnet",
                         {"uri": magnet, "ignore_duplicate": "true", "download": "true"})
        info_hash = d.get("info_hash", "")
        if not info_hash:
            return False

        for _ in range(60):
            st = _torrest_req(torrest_url, "GET", "/torrents/%s/status" % info_hash)
            if st and st.get("has_metadata"):
                break
            xbmc.sleep(1000)

        progress = xbmcgui.DialogProgress()
        progress.create("RDFlix - LordPlayer Download", title)
        done = False

        while not progress.iscanceled():
            st = _torrest_req(torrest_url, "GET", "/torrents/%s/status" % info_hash)
            if not st:
                break
            prog = st.get("progress", 0)
            pct = int(min(prog, 1.0) * 100)
            state_names = {0: "queued", 1: "checking", 2: "downloading", 3: "meta",
                           4: "finished", 5: "seeding", 6: "alloc", 7: "check fast"}
            sn = state_names.get(st.get("state", -1), str(st.get("state", "?")))
            progress.update(pct, "%d%% - %s" % (pct, sn))
            if prog >= 1.0:
                done = True
                break
            xbmc.sleep(2000)
        progress.close()

        if done:
            files = _torrest_req(torrest_url, "GET", "/torrents/%s/files" % info_hash)
            if files:
                vids = [f for f in files if f.get("path", "").lower().endswith(
                    (".mp4", ".mkv", ".avi", ".m4v", ".mov", ".webm"))]
                if not vids:
                    return False
                fid = vids[0].get("id")
                if len(vids) > 1:
                    labels = [os.path.basename(f.get("path", "Unknown")) for f in vids]
                    pick = xbmcgui.Dialog().select("Select file", labels)
                    if pick >= 0:
                        fid = vids[pick].get("id")
                fname = os.path.basename(vids[0].get("path", "video.mp4"))
                serve = "%s/torrents/%s/files/%s/serve" % (torrest_url, info_hash, fid)
                log("Download: LP serve URL %s" % serve)

                dl_prog = xbmcgui.DialogProgress()
                dl_prog.create("RDFlix - Saving", fname)
                req = urllib.request.Request(serve, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=300) as src:
                    out = os.path.join(dest_folder, fname)
                    with open(out, "wb") as f:
                        total = int(src.headers.get("Content-Length", 0))
                        wrote = 0
                        while True:
                            chunk = src.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                            wrote += len(chunk)
                            if total:
                                dl_prog.update(int(wrote / total * 100),
                                               "%d / %d MB" % (wrote // 1048576, total // 1048576))
                dl_prog.close()
                notify("RDFlix", "Download Complete: %s" % fname, xbmcgui.NOTIFICATION_INFO, 5000)
                return True
        return False
    except Exception as e:
        log("LordPlayer download error: %s" % str(e), xbmc.LOGERROR)
        return False


def _torrest_req(base_url, method, path, params=None):
    url = base_url + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _do_download(url, dest_folder, filename, title):
    import os, xbmcgui
    out = os.path.join(dest_folder, filename)
    progress = xbmcgui.DialogProgress()
    progress.create("RDFlix - Download", title)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=300) as src:
            total = int(src.headers.get("Content-Length", 0))
            wrote = 0
            with open(out, "wb") as f:
                while not progress.iscanceled():
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    wrote += len(chunk)
                    if total:
                        pct = int(wrote / total * 100)
                        progress.update(pct, "%d / %d MB" % (wrote // 1048576, total // 1048576))
        progress.close()
        if progress.iscanceled():
            log("Download cancelled: %s" % out)
            return False
        log("Download complete: %s" % out)
        notify("RDFlix", "Download Complete: %s" % filename, xbmcgui.NOTIFICATION_INFO, 5000)
        return True
    except Exception as e:
        progress.close()
        log("Download error: %s" % str(e), xbmc.LOGERROR)
        return False


def _imdb_cache():
    if not hasattr(_imdb_cache, "_data"):
        _imdb_cache._data = {}
    return _imdb_cache._data


def _resolve_imdb_id(tmdb_id, media_type):
    cache = _imdb_cache()
    key = "%s_%s" % (media_type, tmdb_id)
    if key in cache:
        return cache[key]
    ext = get_external_ids(tmdb_id, media_type)
    imdb_id = ext.get("imdb_id") or "" if ext else ""
    cache[key] = imdb_id
    return imdb_id


def _show_source_select(sources, title):
    """Show source selection with RD filter toggle. Returns selected source or None."""
    rd_count = sum(1 for s in sources if s.get("isDebridCached"))
    lp_count = len(sources) - rd_count
    notify("RDFlix", "%d sources (%d RD, %d LP)" % (len(sources), rd_count, lp_count), duration=2000)

    show_all = True
    while True:
        if show_all:
            filtered = sources
            labels = [_build_source_label(s) for s in filtered]
        else:
            filtered = [s for s in sources if s.get("isDebridCached")]
            if not filtered:
                dialog_ok("RDFlix", "No RD Instant sources available")
                show_all = True
                continue
            labels = [_build_source_label(s) for s in filtered]

        toggle_text = "[B]Show All (%d)[/B]" % len(sources) if not show_all else "[B]RD Only (%d)[/B]" % rd_count
        labels.insert(0, toggle_text)
        labels.append("[B]Rescrape[/B]")

        title_text = "%s (%d/%d RD)" % (title[:40], len(filtered) if show_all else rd_count, len(sources))
        idx = dialog_select(title_text, labels)
        if idx < 0:
            return None
        if idx == 0:
            show_all = not show_all
            continue
        if idx >= len(labels) - 1:
            return "rescrape"
        real_idx = idx - 1
        if real_idx < len(filtered):
            return filtered[real_idx]


def play_movie(imdb_id, tmdb_id, title, year="", resume_pct=0, download=False):
    if not imdb_id and tmdb_id:
        imdb_id = _resolve_imdb_id(tmdb_id, "movie")
    if not imdb_id:
        log("No imdb_id for movie: %s (tmdb=%s), trying text search" % (title, tmdb_id), xbmc.LOGWARNING)
        tio_sources = []
        scr_sources = scraper_search_movie("", title, year)
        if not scr_sources:
            dialog_ok("RDFlix", "No sources found for\n%s" % title)
            if download:
                end_directory()
            else:
                set_resolved_url(False, xbmcgui.ListItem(label=title))
            return
        sources = _merge_sources([], scr_sources)
        sources = _check_rd_cache(sources)
    else:
        log("Searching all sources for movie: %s" % title)
        tio_sources = get_movie_sources(imdb_id)
        scr_sources = scraper_search_movie(imdb_id, title, year)
        sources = _merge_sources(tio_sources, scr_sources)
        sources = _check_rd_cache(sources)

    if not sources:
        dialog_ok("RDFlix", "No sources found for\n%s" % title)
        if download:
            end_directory()
        else:
            set_resolved_url(False, xbmcgui.ListItem(label=title))
        return

    choice = _show_source_select(sources, title)
    if choice is None:
        if download:
            end_directory()
        else:
            set_resolved_url(False, xbmcgui.ListItem(label=title))
    elif choice == "rescrape":
        import xbmcplugin
        from resources.lib.kodi_utils import HANDLE, build_url
        xbmcplugin.endOfDirectory(HANDLE)
        play_movie(imdb_id, tmdb_id, title, year, download=download)
    else:
        if download:
            _download_source(choice, title)
            end_directory()
        else:
            _handle_source_action(choice, title, imdb_id, resume_at=int(float(resume_pct) / 100 * 5400))


def play_episode(imdb_id, tmdb_id, show_title, season, episode, episode_title="", resume_pct=0, download=False):
    _PACK_CONTEXT.clear()
    s_int = int(season) if season else 0
    e_int = int(episode) if episode else 0
    full_title = "%s S%02dE%02d" % (show_title, s_int, e_int)

    if not imdb_id and tmdb_id:
        imdb_id = _resolve_imdb_id(tmdb_id, "tv")
    if not imdb_id:
        log("No imdb_id for episode: %s (tmdb=%s), trying text search" % (full_title, tmdb_id), xbmc.LOGWARNING)
        tio_sources = []
        scr_sources = scraper_search_episode("", show_title, season, episode, "")
        if not scr_sources:
            dialog_ok("RDFlix", "No sources found for\n%s" % full_title)
            if download:
                end_directory()
            else:
                set_resolved_url(False, xbmcgui.ListItem(label=full_title))
            return
        sources = _merge_sources([], scr_sources)
        sources = _check_rd_cache(sources)
    else:
        log("Searching all sources for episode: %s" % full_title)
        tio_sources = get_episode_sources(imdb_id, s_int, e_int)
        scr_sources = scraper_search_episode(imdb_id, show_title, season, episode, "")
        sources = _merge_sources(tio_sources, scr_sources)
        sources = _check_rd_cache(sources)

    if not sources:
        dialog_ok("RDFlix", "No sources found for\n%s" % full_title)
        if download:
            end_directory()
        else:
            set_resolved_url(False, xbmcgui.ListItem(label=full_title))
        return

    if len(sources) == 1:
        if download:
            _download_source(sources[0], full_title)
            end_directory()
        else:
            res = _handle_source_action(sources[0], full_title, imdb_id, season, episode, show_title, resume_at=int(float(resume_pct) / 100 * 2700))
            if res:
                played_s, played_e = res
                if not played_s:
                    played_s = s_int
                if not played_e:
                    played_e = e_int
                xbmc.sleep(3000)
                _autoplay_next(imdb_id, tmdb_id, show_title, played_s, played_e)
        return

    choice = _show_source_select(sources, full_title)
    if choice is None:
        if download:
            end_directory()
        else:
            set_resolved_url(False, xbmcgui.ListItem(label=full_title))
    elif choice == "rescrape":
        import xbmcplugin
        from resources.lib.kodi_utils import HANDLE
        xbmcplugin.endOfDirectory(HANDLE)
        play_episode(imdb_id, tmdb_id, show_title, season, episode, episode_title, download=download)
    else:
        if download:
            _download_source(choice, full_title)
            end_directory()
        else:
            res = _handle_source_action(choice, full_title, imdb_id, season, episode, show_title, resume_at=int(float(resume_pct) / 100 * 2700))
            if res:
                played_s, played_e = res
                if not played_s:
                    played_s = s_int
                if not played_e:
                    played_e = e_int
                xbmc.sleep(3000)
                _autoplay_next(imdb_id, tmdb_id, show_title, played_s, played_e)


def _autoplay_next(imdb_id, tmdb_id, show_title, season, episode):
    if get_setting("autoplay_next", "false") != "true":
        return

    s_int = int(season)
    e_int = int(episode)
    log("Autoplay: monitoring S%02dE%02d" % (s_int, e_int))

    player = xbmc.Player()
    monitor = xbmc.Monitor()

    xbmc.sleep(3000)

    for _ in range(240):
        if player.isPlaying():
            break
        if monitor.abortRequested():
            return
        xbmc.sleep(500)

    if not player.isPlaying():
        return

    total = 0
    for _ in range(60):
        total = player.getTotalTime()
        if total > 60:
            break
        if monitor.abortRequested():
            return
        xbmc.sleep(1000)
    log("Autoplay: total time = %ds" % total)

    next_s = s_int
    next_e = e_int + 1
    waited = False
    next_source = None
    reached_end = False
    last_time = 0

    while not monitor.abortRequested():
        if player.isPlaying():
            t = player.getTime()
            if t > 0:
                last_time = t
            if total > 0:
                remaining = int(total - t)
                if remaining <= 90 and not waited:
                    waited = True
                    log("Autoplay: pre-fetching S%02dE%02d" % (next_s, next_e))
                    next_source = _fetch_next_episode_source(imdb_id, tmdb_id, show_title, next_s, next_e)
                    if next_source:
                        magnet = next_source.get("magnet", "")
                        info_hash = next_source.get("infoHash", "")
                        if not magnet and info_hash and len(info_hash) >= 40:
                            magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(show_title))
                        if magnet:
                            threading.Thread(target=_precache_async, args=(magnet,), daemon=True).start()
                if remaining <= 3:
                    reached_end = True
                    break
        else:
            if total > 0 and last_time > 0 and (total - last_time) <= 120:
                reached_end = True
            break
        xbmc.sleep(1000)

    if monitor.abortRequested():
        return

    if not reached_end:
        log("Autoplay: user pressed stop, aborting chain")
        try:
            cur_time = player.getTime()
            if total > 0:
                pct = cur_time / total * 100
                update_continue_watching(imdb_id, tmdb_id, show_title, s_int, e_int, show_title, pct)
        except:
            pass
        return

    watched_pct = 1.0
    try:
        cur_time = player.getTime()
        if total > 0 and cur_time > 0:
            watched_pct = cur_time / total
    except:
        log("Autoplay: player state lost after playback ended")
        watched_pct = 1.0

    if watched_pct >= 0.85:
        try:
            update_continue_watching(imdb_id, tmdb_id, show_title, s_int, e_int, show_title, 100)
        except:
            pass
    else:
        log("Autoplay: user stopped playback (%.0f%% watched)" % (watched_pct * 100))
        return

    notify("RDFlix", "Auto Play Is Finding Your Next Episode")

    # If we never pre-fetched, do it now
    if not waited:
        log("Autoplay: fetching S%02dE%02d after playback ended" % (next_s, next_e))
        next_source = _fetch_next_episode_source(imdb_id, tmdb_id, show_title, next_s, next_e)

    log("Autoplay: playing S%02dE%02d" % (next_s, next_e))

    # 1) Try the season pack we came from first
    if _PACK_CONTEXT.get("magnet"):
        if _play_from_pack(_PACK_CONTEXT["magnet"], _PACK_CONTEXT.get("title", show_title), next_s, next_e):
            xbmc.sleep(2000)
            _autoplay_next(imdb_id, tmdb_id, show_title, next_s, next_e)
            return
        log("Autoplay: next episode not in pack, scraping instead")
        _PACK_CONTEXT.clear()

    # 2) Scrape normally
    if next_source:
        label = "%s - S%02dE%02d" % (show_title, next_s, next_e)
        xbmc.sleep(5000)
        if _autoplay_source(next_source, label):
            xbmc.sleep(2000)
            _autoplay_next(imdb_id, tmdb_id, show_title, next_s, next_e)
        else:
            log("Autoplay: failed to play next episode", xbmc.LOGWARNING)
    else:
        log("Autoplay: no source found for S%02dE%02d" % (next_s, next_e))


def _play_from_pack(magnet, title, season, episode):
    """Play a specific episode from a season pack (RD or torrest). Returns True if playback started."""
    files = _list_pack_files(magnet, title)
    if not files:
        return False
    match = None
    for f in files:
        s, e = _ep_from_filename(f.get("path", ""))
        if s == season and e == episode:
            match = f
            break
    if match is None:
        for f in files:
            s, e = _ep_from_filename(f.get("path", ""))
            if e == episode:
                match = f
                break
    if match is None:
        return False
    url = _pack_file_url(match, title)
    if not url:
        return False
    li = xbmcgui.ListItem(path=url, label=match.get("path", title))
    li.setProperty("IsPlayable", "true")
    xbmc.Player().play(url, li)
    return _verify_playback_started(15)


def _autoplay_source(source, title):
    """Dispatch autoplay to the correct player based on source type (RD or LordPlayer)."""
    is_rd = source.get("isDebridCached", False) or source.get("debrid", False)
    if is_rd:
        return _autoplay_rd_source(source, title)
    return _autoplay_lp_source(source, title)


def _autoplay_rd_source(source, title):
    """Autoplay a Real-Debrid cached source (instant URL or magnet resolve). No LordPlayer fallback."""
    magnet = source.get("magnet", "")
    info_hash = source.get("infoHash", "")
    behavior_hints = source.get("behaviorHints", {})
    if not info_hash:
        info_hash = behavior_hints.get("infoHash", "")
    if not magnet:
        magnet = behavior_hints.get("magnet", "")
    torrent_title = source.get("title", source.get("name", title))
    fname = behavior_hints.get("filename", "")
    file_name = fname or torrent_title or title

    url = source.get("url", "")
    if url and url.startswith("http"):
        try:
            if _is_dmca_video(url):
                log("Autoplay: direct RD URL is DMCA notice, skipping")
            else:
                req = urllib.request.Request(url, method="HEAD")
                req.add_header("User-Agent", "Mozilla/5.0")
                resp = urllib.request.urlopen(req, timeout=8)
                final_url = resp.geturl() or url
                if any(x in final_url.lower() for x in ["configure", "exception", "error/", "autorize", "authorize"]):
                    log("Autoplay: redirect led to error page, skipping")
                else:
                    li = xbmcgui.ListItem(path=final_url, label=file_name)
                    li.setProperty("IsPlayable", "true")
                    xbmc.Player().play(final_url, li)
                    if _verify_playback_started():
                        return True
        except Exception as e:
            log("Autoplay: direct RD URL error: %s" % str(e), xbmc.LOGINFO)

    actual_magnet = magnet
    if not actual_magnet and info_hash and len(info_hash) >= 40:
        actual_magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(torrent_title or title))
    if actual_magnet:
        try:
            result = resolve_magnet(actual_magnet, torrent_title or title)
            if result and result.get("url") and not _is_dmca_video(result["url"]):
                li = xbmcgui.ListItem(path=result["url"], label=file_name)
                li.setProperty("IsPlayable", "true")
                xbmc.Player().play(result["url"], li)
                if _verify_playback_started():
                    return True
        except Exception as e:
            log("Autoplay RD resolve error: %s" % str(e), xbmc.LOGERROR)
    return False


def _autoplay_lp_source(source, title):
    """Autoplay a LordPlayer (torrent) source. No RD fallback."""
    magnet = source.get("magnet", "")
    info_hash = source.get("infoHash", "")
    behavior_hints = source.get("behaviorHints", {})
    if not info_hash:
        info_hash = behavior_hints.get("infoHash", "")
    if not magnet:
        magnet = behavior_hints.get("magnet", "")
    torrent_title = source.get("title", source.get("name", title))
    fname = behavior_hints.get("filename", "")
    file_name = fname or torrent_title or title

    magnet_link = magnet
    if not magnet_link and info_hash and len(info_hash) >= 40:
        magnet_link = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(torrent_title or title))

    if not magnet_link or not TRY_LORDPLAYER:
        return False
    if not re.search(r"btih:([a-fA-F0-9]{40})", magnet_link):
        return False
    lid = "plugin.video.lordplayer.droid" if xbmc.getCondVisibility("System.HasAddon(plugin.video.lordplayer.droid)") else "plugin.video.lordplayer"
    plugin_url = "plugin://%s/play_magnet?magnet=%s&buffer=true" % (lid, urllib.parse.quote(magnet_link, safe=""))
    li = xbmcgui.ListItem(path=plugin_url, label=file_name)
    li.setProperty("IsPlayable", "true")
    xbmc.Player().play(plugin_url, li)
    return _verify_playback_started(30)


def _fetch_next_episode_source(imdb_id, tmdb_id, show_title, season, episode):
    try:
        tio_sources = get_episode_sources(imdb_id, season, episode)
        scr_sources = scraper_search_episode(imdb_id, show_title, season, episode, "")
        sources = _merge_sources(tio_sources, scr_sources)
        sources = _check_rd_cache(sources)

        if sources:
            return sources[0]

        next_s = season + 1
        if next_s <= 50:
            log("Autoplay: trying next season S%02dE01" % next_s)
            tio_sources = get_episode_sources(imdb_id, next_s, 1)
            scr_sources = scraper_search_episode(imdb_id, show_title, next_s, 1, "")
            sources = _merge_sources(tio_sources, scr_sources)
            sources = _check_rd_cache(sources)
            if sources:
                return sources[0]
    except Exception as e:
        log("Autoplay fetch error: %s" % str(e), xbmc.LOGERROR)
    return None


def _precache_async(magnet):
    """Silently add magnet to RD cloud in background thread."""
    try:
        rd_add_magnet(magnet)
        log("Precache: magnet added to RD")
    except Exception as e:
        log("Precache error: %s" % str(e))
