"""StreamLord extras - TMDB browsing, Trakt, Live TV, Sports, Open Magnet."""
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import xbmcaddon
import sys
import json
import re
import urllib.parse
import urllib.request
import traceback

ADDON = "plugin.video.streamlord"
BASE_URL = sys.argv[0]
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

TMDB_KEY = "84259f99204eeb7d45c7e3d8e36c6123"
TMDB_API = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p"


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("[StreamLord] %s" % msg, level)


def get_url(**kwargs):
    return "{0}?{1}".format(BASE_URL, urllib.parse.urlencode(kwargs))


def tmdb_img(path, size="w342"):
    return "%s/%s%s" % (TMDB_IMG, size, path) if path else ""


def tmdb_fetch(path, params=None):
    try:
        if params is None:
            params = {}
        params["api_key"] = TMDB_KEY
        params["language"] = "en-US"
        url = "%s%s?%s" % (TMDB_API, path, urllib.parse.urlencode(params))
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except:
        return {}


def _add_item(label, action, icon="DefaultVideo.png", is_folder=True, extra_params=None, info=None, art=None):
    params = {"action": action}
    if extra_params:
        params.update(extra_params)
    li = xbmcgui.ListItem(label=label)
    if info:
        li.setInfo("video", info)
    art_dict = {"icon": icon}
    if art:
        art_dict.update(art)
    li.setArt(art_dict)
    if not is_folder:
        li.setProperty("IsPlayable", "true")
    xbmcplugin.addDirectoryItem(HANDLE, get_url(**params), li, isFolder=is_folder)


# --- TMDB Browse ---

def browse_tmdb(category="trending", media="movie", page=1):
    if media == "movie":
        path = "/movie/%s" % category
    else:
        path = "/tv/%s" % category
    data = tmdb_fetch(path, {"page": str(page)})
    results = data.get("results", [])
    fanart = ""
    for r in results:
        title = r.get("title") or r.get("name", "Unknown")
        year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        tid = r.get("id")
        poster = tmdb_img(r.get("poster_path", ""))
        backdrop = tmdb_img(r.get("backdrop_path", ""), "original")
        if backdrop and not fanart:
            fanart = backdrop
        plot = r.get("overview", "")[:200]
        rating = r.get("vote_average", 0)
        label = title
        if year:
            label += " [%s]" % year
        if media == "movie":
            _add_item(label, "play_movie", "DefaultVideo.png", False,
                      {"title": title, "year": year, "tmdb_id": str(tid), "imdb_id": ""},
                      {"title": title, "year": int(year or 0), "plot": plot, "rating": rating},
                      {"thumb": poster, "fanart": backdrop})
        else:
            _add_item(label, "tv_browse_seasons", "DefaultTVShows.png", True,
                      {"tmdb_id": str(tid), "show_title": title, "imdb_id": ""},
                      {"title": title, "plot": plot, "rating": rating},
                      {"thumb": poster, "fanart": backdrop})
    if fanart:
        xbmcplugin.setPluginFanart(HANDLE, fanart)
    total_pages = data.get("total_pages", 1)
    if page < total_pages:
        _add_item("[B]Next Page >[/B]", "browse_tmdb", "DefaultFolderBack.png", True,
                  {"category": category, "media": media, "page": page + 1})
    xbmcplugin.endOfDirectory(HANDLE)


def browse_tmdb_genres(media="movie"):
    if media == "movie":
        path = "/genre/movie/list"
    else:
        path = "/genre/tv/list"
    data = tmdb_fetch(path)
    genres = data.get("genres", [])
    for g in genres:
        _add_item(g.get("name", "?"), "browse_tmdb_genre_list", "DefaultGenre.png", True,
                  {"genre_id": str(g.get("id")), "genre_name": g.get("name", ""), "media": media, "page": "1"})
    xbmcplugin.endOfDirectory(HANDLE)


def browse_tmdb_genre_list(genre_id, genre_name, media="movie", page=1):
    if media == "movie":
        path = "/discover/movie"
    else:
        path = "/discover/tv"
    data = tmdb_fetch(path, {"with_genres": genre_id, "page": str(page), "sort_by": "popularity.desc"})
    results = data.get("results", [])
    fanart = ""
    for r in results:
        title = r.get("title") or r.get("name", "Unknown")
        year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        tid = r.get("id")
        poster = tmdb_img(r.get("poster_path", ""))
        backdrop = tmdb_img(r.get("backdrop_path", ""), "original")
        if backdrop and not fanart:
            fanart = backdrop
        plot = r.get("overview", "")[:200]
        rating = r.get("vote_average", 0)
        label = "%s [%s]" % (title, year) if year else title
        if media == "movie":
            _add_item(label, "play_movie", "DefaultVideo.png", False,
                      {"title": title, "year": year, "tmdb_id": str(tid), "imdb_id": ""},
                      {"title": title, "year": int(year or 0), "plot": plot, "rating": rating},
                      {"thumb": poster, "fanart": backdrop})
        else:
            _add_item(label, "tv_browse_seasons", "DefaultTVShows.png", True,
                      {"tmdb_id": str(tid), "show_title": title},
                      {"title": title, "plot": plot, "rating": rating},
                      {"thumb": poster, "fanart": backdrop})
    if fanart:
        xbmcplugin.setPluginFanart(HANDLE, fanart)
    total_pages = data.get("total_pages", 1)
    if page < total_pages:
        _add_item("[B]Next Page >[/B]", "browse_tmdb_genre_list", "DefaultFolderBack.png", True,
                  {"genre_id": genre_id, "genre_name": genre_name, "media": media, "page": page + 1})
    xbmcplugin.endOfDirectory(HANDLE)


def tv_browse_seasons(tmdb_id, show_title, imdb_id=""):
    data = tmdb_fetch("/tv/%s" % tmdb_id)
    seasons = data.get("seasons", [])
    poster = tmdb_img(data.get("poster_path", ""))
    fanart = tmdb_img(data.get("backdrop_path", ""), "original")
    if fanart:
        xbmcplugin.setPluginFanart(HANDLE, fanart)
    for s in seasons:
        snum = s.get("season_number", 0)
        if snum == 0:
            continue
        eps = s.get("episode_count", 0)
        label = "Season %d [%d episodes]" % (snum, eps)
        _add_item(label, "tv_browse_episodes", "DefaultTVShows.png", True,
                  {"tmdb_id": tmdb_id, "season": str(snum), "show_title": show_title, "imdb_id": imdb_id},
                  {"title": "%s - S%d" % (show_title, snum), "tvshowtitle": show_title},
                  {"thumb": tmdb_img(s.get("poster_path", "") or poster), "fanart": fanart})
    xbmcplugin.endOfDirectory(HANDLE)


def tv_browse_episodes(tmdb_id, season, show_title, imdb_id=""):
    data = tmdb_fetch("/tv/%s/season/%s" % (tmdb_id, season))
    episodes = data.get("episodes", [])
    for ep in episodes:
        epnum = ep.get("episode_number", 0)
        epname = ep.get("name", "Episode %d" % epnum)
        label = "S%02dE%02d - %s" % (int(season), epnum, epname)
        _add_item(label, "play_episode", "DefaultTVShows.png", False,
                  {"show_title": show_title, "season": season, "show_imdb_id": imdb_id, "episode_num": str(epnum),
                   "tmdb_id": tmdb_id, "title": "S%02dE%02d" % (int(season), epnum)},
                  {"title": epname, "season": int(season), "episode": epnum, "tvshowtitle": show_title,
                   "plot": ep.get("overview", ""), "rating": ep.get("vote_average", 0)},
                  {"thumb": tmdb_img(ep.get("still_path", ""))})
    xbmcplugin.endOfDirectory(HANDLE)


def person_detail(person_id, person_name):
    data = tmdb_fetch("/person/%s" % person_id, {"append_to_response": "combined_credits"})
    if not data:
        xbmcplugin.endOfDirectory(HANDLE)
        return
    biog = data.get("biography", "")[:500]
    fanart = tmdb_img(data.get("profile_path", ""), "original")
    if fanart:
        xbmcplugin.setPluginFanart(HANDLE, fanart)
    credits = data.get("combined_credits", {}).get("cast", [])[:50]
    for c in credits:
        title = c.get("title") or c.get("name", "Unknown")
        mtype = "movie" if c.get("media_type") == "movie" else "tv"
        year = (c.get("release_date") or c.get("first_air_date") or "")[:4]
        label = "%s [%s] (%s)" % (title, year, mtype.upper())
        tid = c.get("id")
        if mtype == "movie":
            _add_item(label, "play_movie", "DefaultVideo.png", False,
                      {"title": title, "year": year, "tmdb_id": str(tid), "imdb_id": ""},
                      {"title": title, "year": int(year or 0), "plot": c.get("overview", "")[:200]})
        else:
            _add_item(label, "tv_browse_seasons", "DefaultTVShows.png", True,
                      {"tmdb_id": str(tid), "show_title": title})
    _add_item("[B]New Search[/B]", "search", "DefaultSearch.png")
    xbmcplugin.endOfDirectory(HANDLE)


def browse_tmdb_search(query=""):
    if not query:
        kb = xbmc.Keyboard("", "Search TMDB...")
        kb.doModal()
        if kb.isConfirmed() and kb.getText():
            query = kb.getText().strip()
        else:
            xbmcplugin.endOfDirectory(HANDLE)
            return
    data = tmdb_fetch("/search/multi", {"query": query})
    results = data.get("results", [])
    fanart = ""
    for r in results:
        mtype = r.get("media_type", "")
        if mtype not in ("movie", "tv", "person"):
            continue
        title = r.get("title") or r.get("name", "Unknown")
        year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        tid = r.get("id")
        poster = tmdb_img(r.get("poster_path", "") or r.get("profile_path", ""))
        backdrop = tmdb_img(r.get("backdrop_path", ""), "original")
        if backdrop and not fanart:
            fanart = backdrop
        label = "%s [%s]" % (title, year) if year else title
        label += " (%s)" % mtype.upper()
        if mtype == "person":
            _add_item(label, "person_detail", "DefaultActor.png", True,
                      {"person_id": str(tid), "person_name": title},
                      {"title": title, "plot": ""}, {"thumb": poster})
        elif mtype == "movie":
            _add_item(label, "play_movie", "DefaultVideo.png", False,
                      {"title": title, "year": year, "tmdb_id": str(tid)},
                      {"title": title, "year": int(year or 0), "plot": r.get("overview", "")[:200]},
                      {"thumb": poster, "fanart": backdrop})
        else:
            _add_item(label, "tv_browse_seasons", "DefaultTVShows.png", True,
                      {"tmdb_id": str(tid), "show_title": title},
                      {"title": title, "plot": r.get("overview", "")[:200]},
                      {"thumb": poster, "fanart": backdrop})
    if fanart:
        xbmcplugin.setPluginFanart(HANDLE, fanart)
    _add_item("[B]New Search[/B]", "tmdb_search", "DefaultSearch.png")
    xbmcplugin.endOfDirectory(HANDLE)


# --- Trakt ---

def trakt_auth():
    try:
        from resources.lib import trakt_api
        dc, uc, vu = trakt_api.get_device_code()
        if not dc:
            xbmcgui.Dialog().ok("StreamLord", "Failed to get Trakt device code")
            return
        xbmcgui.Dialog().ok("StreamLord", "Go to %s and enter code:\n\n%s" % (vu, uc))
        at, rt = trakt_api.poll_token(dc)
        if at:
            addon = xbmcaddon.Addon(ADDON)
            addon.setSetting('trakt_token', at)
            xbmcgui.Dialog().notification("StreamLord", "Trakt authorized!")
        else:
            xbmcgui.Dialog().ok("StreamLord", "Trakt authorization timed out")
    except Exception as e:
        xbmc.log("[StreamLord] trakt_auth error: %s" % str(e), xbmc.LOGERROR)


def browse_trakt_watchlist(media="movie"):
    try:
        from resources.lib import trakt_api
        if not trakt_api.is_authenticated():
            xbmcgui.Dialog().ok("StreamLord", "Authorize Trakt first in Settings")
            xbmcplugin.endOfDirectory(HANDLE)
            return
        items = trakt_api.get_watchlist(media)
        fanart = ""
        for item in items:
            title = item.get("title") or item.get("show", {}).get("title", "Unknown")
            year = item.get("year", "")
            if media == "show":
                tid = item.get("show", {}).get("ids", {}).get("tmdb", "")
            else:
                tid = item.get("movie", {}).get("ids", {}).get("tmdb", "")
            imdb = ""
            if media == "show":
                imdb = item.get("show", {}).get("ids", {}).get("imdb", "")
            else:
                imdb = item.get("movie", {}).get("ids", {}).get("imdb", "")
            label = "%s [%s]" % (title, year) if year else title
            if media == "movie":
                _add_item(label, "play_movie", "DefaultVideo.png", False,
                          {"title": title, "year": str(year), "tmdb_id": str(tid), "imdb_id": imdb},
                          {"title": title, "year": year})
            else:
                _add_item(label, "tv_browse_seasons", "DefaultTVShows.png", True,
                          {"tmdb_id": str(tid), "show_title": title, "imdb_id": imdb})
        xbmcplugin.endOfDirectory(HANDLE)
    except Exception as e:
        log("Trakt watchlist error: %s" % str(e), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(HANDLE)


# --- Live TV ---

def livetv_menu():
    try:
        from resources.lib import livetv
        channels = livetv.load_channels()
        groups = set()
        for c in channels:
            groups.add(c.get("group", "Other"))
        for g in sorted(groups):
            _add_item(g, "livetv_channels", "DefaultTVShows.png", True, {"group": g})
        xbmcplugin.endOfDirectory(HANDLE)
    except Exception as e:
        log("LiveTV error: %s" % str(e), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(HANDLE)


def livetv_channels(group):
    try:
        from resources.lib import livetv
        channels = livetv.load_channels()
        for c in channels:
            if c.get("group", "") == group:
                label = c.get("name", "Unknown")
                url = c.get("url", "")
                logo = c.get("logo", "")
                li = xbmcgui.ListItem(label=label)
                li.setArt({"thumb": logo, "icon": "DefaultTVShows.png"})
                li.setProperty("IsPlayable", "true")
                li.setInfo("video", {"title": label})
                xbmcplugin.addDirectoryItem(HANDLE, get_url(action="livetv_play", url=urllib.parse.quote(url), title=label), li, isFolder=False)
        xbmcplugin.endOfDirectory(HANDLE)
    except Exception as e:
        log("LiveTV channels error: %s" % str(e), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(HANDLE)


def livetv_play(url, title):
    try:
        li = xbmcgui.ListItem(path=url, label=title)
        li.setProperty("IsPlayable", "true")
        li.setMimeType("application/vnd.apple.mpegurl")
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
    except:
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


# --- Sports Search ---

def sports_search(query=""):
    if not query:
        kb = xbmc.Keyboard("", "Search Sports (e.g. UFC 300)...")
        kb.doModal()
        if kb.isConfirmed() and kb.getText():
            query = kb.getText().strip()
        else:
            xbmcplugin.endOfDirectory(HANDLE)
            return
    try:
        from resources.lib import torrentio as tio
        log("Sports search: %s" % query)
        sources = tio.get_movie_sources(query)
        for s in sources:
            bh = s.get("behaviorHints", {})
            ih = s.get("infoHash", "") or bh.get("infoHash", "")
            url = s.get("url", "")
            if not ih and ('playback' in url or 'exception' in url or 'configure' in url):
                continue
            name = s.get("title", query)
            label = "%s [%s]" % (name[:60], s.get("_quality", "?"))
            if s.get("seeders", 0):
                label += " [S:%s]" % s["seeders"]
            magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (ih, urllib.parse.quote(name)) if ih else url
            _add_item(label, "open_magnet_play", "DefaultVideo.png", False,
                      {"magnet": magnet, "title": name})
        xbmcplugin.endOfDirectory(HANDLE)
    except Exception as e:
        log("Sports search error: %s" % str(e), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(HANDLE)


# --- Open Magnet ---

def open_magnet():
    kb = xbmc.Keyboard("", "Paste a magnet link or info hash...")
    kb.doModal()
    if not kb.isConfirmed() or not kb.getText():
        xbmcplugin.endOfDirectory(HANDLE)
        return
    magnet = kb.getText().strip()
    if not magnet.startswith("magnet:") and len(magnet) == 40 and re.match(r'^[a-fA-F0-9]{40}$', magnet):
        magnet = "magnet:?xt=urn:btih:%s" % magnet
    if magnet.startswith("magnet:"):
        open_magnet_play(magnet, "Direct Magnet")
    else:
        xbmcgui.Dialog().ok("StreamLord", "Invalid magnet or hash")


def open_magnet_play(magnet, title):
    try:
        TRACKERS = "&tr=udp://tracker.opentrackr.org:1337/announce&tr=udp://open.stealth.si:80/announce&tr=udp://tracker.torrent.eu.org:451/announce"
        if TRACKERS not in magnet:
            magnet += TRACKERS
        for lid in ["plugin.video.lordplayer", "plugin.video.lordplayer.droid"]:
            if xbmc.getCondVisibility("System.HasAddon({})".format(lid)):
                break
        plugin_url = "plugin://%s/play_magnet?magnet=%s&buffer=true" % (lid, urllib.parse.quote(magnet, safe=""))
        li = xbmcgui.ListItem(path=plugin_url, label=title)
        li.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
    except:
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


# --- Surprise Me ---

def surprise_me(media="movie"):
    import random
    if media == "movie":
        path = "/movie/popular"
    else:
        path = "/tv/popular"
    data = tmdb_fetch(path, {"page": str(random.randint(1, 20))})
    results = data.get("results", [])
    if results:
        r = random.choice(results)
        title = r.get("title") or r.get("name", "Unknown")
        year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        tid = r.get("id")
        if media == "movie":
            _add_item(title, "play_movie", "DefaultVideo.png", False,
                      {"title": title, "year": year, "tmdb_id": str(tid), "imdb_id": ""},
                      {"title": title, "year": int(year or 0), "plot": r.get("overview", "")[:200]},
                      {"thumb": tmdb_img(r.get("poster_path", ""))})
        else:
            _add_item(title, "tv_browse_seasons", "DefaultTVShows.png", True,
                      {"tmdb_id": str(tid), "show_title": title})
    xbmcplugin.endOfDirectory(HANDLE)


# --- Trakt Auth in settings ---

def trakt_settings_auth():
    trakt_auth()
