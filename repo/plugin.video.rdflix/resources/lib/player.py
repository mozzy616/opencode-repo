import urllib.request
import urllib.parse
import re

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.kodi_utils import log, notify, dialog_ok, dialog_yesno, dialog_select, set_resolved_url, get_setting, translate_path
from resources.lib.rd_api import resolve_magnet, unrestrict_link, instant_availability, user_torrents_list
from resources.lib.torrentio import get_movie_sources, get_episode_sources
from resources.lib.tmdb_api import get_external_ids
from resources.lib.constants import QUALITY_ORDER
from resources.lib.scrapers import search_movie as scraper_search_movie, search_episode as scraper_search_episode
from resources.lib.cache import get_cached_hashes, set_cached_hashes
from resources.lib.ad_api import resolve_magnet as ad_resolve_magnet
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
        result = None
        for resolver in [resolve_magnet, ad_resolve_magnet, pm_resolve_magnet]:
            try:
                result = resolver(actual_magnet, torrent_title or title)
                if result and result.get("url"):
                    break
            except:
                continue

        if result and result.get("url"):
            return _play_url(result["url"], result.get("filename", file_name))

    is_rd_cached = source.get("isDebridCached", False)
    if actual_magnet and TRY_LORDPLAYER and not is_rd_cached:
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
        tag = "[COLOR lime]RD[/COLOR] "
    else:
        tag = "[COLOR orange]LP[/COLOR] " if TRY_LORDPLAYER else "[COLOR orange]TR[/COLOR] "

    label = "%s%s %s%s%s" % (tag, quality, stitle[:50] if stitle else "Unknown", size_str, seed_str)
    return label.strip()


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


def _handle_source_action(source, title, imdb_id="", season=None, episode=None, show_title=""):
    """Show Play/Download dialog for a selected source. Returns True if played."""
    if not source:
        set_resolved_url(False, xbmcgui.ListItem(label=title))
        return False

    choice = dialog_select("Choose action - %s" % title[:40], ["Play", "Download"])
    if choice < 0:
        set_resolved_url(False, xbmcgui.ListItem(label=title))
        return False

    if choice == 0:
        if not _play_source(source, title):
            dialog_ok("RDFlix", "Failed to play\n%s" % title)
            set_resolved_url(False, xbmcgui.ListItem(label=title))
            return False
        if imdb_id and trakt_authenticated():
            try:
                scrobble_start("start", imdb_id, show_title or title, season, episode)
            except:
                pass
        return True
    elif choice == 1:
        _download_source(source, title)
        import xbmcplugin
        from resources.lib.kodi_utils import HANDLE
        xbmcplugin.endOfDirectory(HANDLE)
        return False


def _download_source(source, title):
    """Download via RD first, then LordPlayer as fallback."""
    magnet = source.get("magnet", "")
    info_hash = source.get("infoHash", "")
    behavior_hints = source.get("behaviorHints", {})
    fname = behavior_hints.get("filename", source.get("name", source.get("title", title)))

    if not fname.endswith((".mp4", ".mkv", ".avi", ".m4v", ".mov", ".webm", ".ts")):
        fname += ".mp4"

    download_path = get_setting("download_path", "")
    if not download_path:
        download_path = "special://home/userdata/downloads/"
    dest_folder = translate_path(download_path)
    if not dest_folder:
        dest_folder = translate_path("special://home/userdata/downloads/")

    import os
    os.makedirs(dest_folder, exist_ok=True)

    # 1. Direct RD download URL from torrentio/comet (RD Instant)
    url = source.get("url", "")
    if url and (url.startswith("http://") or url.startswith("https://")):
        if not ("/torrent/" in url or "/stream/" in url or "127.0.0.1" in url):
            log("Download: trying RD direct URL")
            if _do_download(url, dest_folder, fname, title):
                return

    # 2. RD magnet resolve
    if not magnet and info_hash and len(info_hash) >= 40:
        magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(title))

    if magnet:
        try:
            result = resolve_magnet(magnet, title)
            if result and result.get("url"):
                log("Download: resolved via RD")
                if _do_download(result["url"], dest_folder, fname, title):
                    return
        except Exception as e:
            log("Download RD resolve error: %s" % str(e), xbmc.LOGERROR)

    # 3. LordPlayer download via torrest daemon
    if magnet and TRY_LORDPLAYER:
        if _lordplayer_download(magnet, title, dest_folder):
            return

    dialog_ok("RDFlix", "Could not download\n%s" % title)


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


def play_movie(imdb_id, tmdb_id, title, year=""):
    if not imdb_id and tmdb_id:
        imdb_id = _resolve_imdb_id(tmdb_id, "movie")
    if not imdb_id:
        log("No imdb_id for movie: %s (tmdb=%s), trying text search" % (title, tmdb_id), xbmc.LOGWARNING)
        tio_sources = []
        scr_sources = scraper_search_movie("", title, year)
        if not scr_sources:
            dialog_ok("RDFlix", "No sources found for\n%s" % title)
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
        set_resolved_url(False, xbmcgui.ListItem(label=title))
        return

    choice = _show_source_select(sources, title)
    if choice is None:
        set_resolved_url(False, xbmcgui.ListItem(label=title))
    elif choice == "rescrape":
        import xbmcplugin
        from resources.lib.kodi_utils import HANDLE, build_url
        xbmcplugin.endOfDirectory(HANDLE)
        play_movie(imdb_id, tmdb_id, title, year)
    else:
        _handle_source_action(choice, title, imdb_id)


def play_episode(imdb_id, tmdb_id, show_title, season, episode, episode_title=""):
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
        set_resolved_url(False, xbmcgui.ListItem(label=full_title))
        return

    if len(sources) == 1:
        if _handle_source_action(sources[0], full_title, imdb_id, season, episode, show_title):
            _autoplay_next(imdb_id, tmdb_id, show_title, s_int, e_int)
        return

    choice = _show_source_select(sources, full_title)
    if choice is None:
        set_resolved_url(False, xbmcgui.ListItem(label=full_title))
    elif choice == "rescrape":
        import xbmcplugin
        from resources.lib.kodi_utils import HANDLE
        xbmcplugin.endOfDirectory(HANDLE)
        play_episode(imdb_id, tmdb_id, show_title, season, episode, episode_title)
    else:
        if _handle_source_action(choice, full_title, imdb_id, season, episode, show_title):
            _autoplay_next(imdb_id, tmdb_id, show_title, s_int, e_int)


def _autoplay_next(imdb_id, tmdb_id, show_title, season, episode):
    if get_setting("autoplay_next", "false") != "true":
        return

    s_int = int(season)
    e_int = int(episode)
    log("Autoplay: monitoring S%02dE%02d" % (s_int, e_int))

    player = xbmc.Player()
    monitor = xbmc.Monitor()

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

    while player.isPlaying() and not monitor.abortRequested():
        if total > 0:
            remaining = int(total - player.getTime())
            if remaining <= 90 and not waited:
                waited = True
                log("Autoplay: pre-fetching S%02dE%02d" % (next_s, next_e))
                next_source = _fetch_next_episode_source(imdb_id, tmdb_id, show_title, next_s, next_e)
            if remaining <= 2:
                break
        xbmc.sleep(3000)

    if monitor.abortRequested():
        return

    # If we never pre-fetched, do it now
    if not waited:
        log("Autoplay: fetching S%02dE%02d after playback ended" % (next_s, next_e))
        next_source = _fetch_next_episode_source(imdb_id, tmdb_id, show_title, next_s, next_e)

    log("Autoplay: playing S%02dE%02d" % (next_s, next_e))

    if next_source:
        label = "%s - S%02dE%02d" % (show_title, next_s, next_e)
        if _autoplay_source(next_source, label):
            xbmc.sleep(2000)
            _autoplay_next(imdb_id, tmdb_id, show_title, next_s, next_e)
        else:
            log("Autoplay: failed to play next episode", xbmc.LOGWARNING)
    else:
        log("Autoplay: no source found for S%02dE%02d" % (next_s, next_e))


def _autoplay_source(source, title):
    """Play a source using Player().play() for auto-play chaining."""
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

    # Direct URL from torrentio/comet (RD instant)
    url = source.get("url", "")
    if url and url.startswith("http"):
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0")
            urllib.request.urlopen(req, timeout=5)
            li = xbmcgui.ListItem(path=url, label=file_name)
            xbmc.Player().play(url, li)
            return True
        except:
            pass

    # Try RD magnet resolve
    if info_hash and len(info_hash) >= 40:
        actual_magnet = magnet or "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(torrent_title or title))
        try:
            result = resolve_magnet(actual_magnet, torrent_title or title)
            if result and result.get("url"):
                li = xbmcgui.ListItem(path=result["url"], label=file_name)
                xbmc.Player().play(result["url"], li)
                return True
        except Exception as e:
            log("Autoplay RD resolve error: %s" % str(e), xbmc.LOGERROR)

    # LordPlayer fallback
    magnet_link = magnet
    if not magnet_link and info_hash and len(info_hash) >= 40:
        magnet_link = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(torrent_title or title))

    if magnet_link and TRY_LORDPLAYER:
        try:
            lid = "plugin.video.lordplayer.droid" if xbmc.getCondVisibility("System.HasAddon(plugin.video.lordplayer.droid)") else "plugin.video.lordplayer"
            plugin_url = "plugin://%s/play_magnet?magnet=%s&buffer=true" % (lid, urllib.parse.quote(magnet_link, safe=""))
            li = xbmcgui.ListItem(path=plugin_url, label=file_name)
            xbmc.Player().play(plugin_url, li)
            return True
        except Exception as e:
            log("Autoplay LordPlayer error: %s" % str(e), xbmc.LOGERROR)

    return False


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
