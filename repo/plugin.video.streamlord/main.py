import xbmcgui
import xbmcplugin
import xbmc
import xbmcvfs
import sys
import json
import re
import traceback
import urllib.parse
import urllib.request
import urllib.error
import os
import time
import http.cookiejar
from resources.lib import extras as ext

HANDLE = int(sys.argv[1])
URL = sys.argv[0]
PARAMS = sys.argv[2]

BASE = "https://streamlord.to"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
QUALITY_ORDER = {'4K': 0, '1080p': 1, '720p': 2, 'SD': 3, 'SCR': 4, 'CAM': 5}
CONTINUE_WATCHING_FILE = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.streamlord/continue_watching.json")

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def get_url(**kwargs):
    return "{0}?{1}".format(URL, urllib.parse.urlencode(kwargs))


def parse_params(param_string):
    params = {}
    if param_string:
        if param_string.startswith("?"):
            param_string = param_string[1:]
        for part in param_string.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = urllib.parse.unquote(v)
    return params

def fetch(url, ref=None):
    try:
        headers = {"User-Agent": USER_AGENT}
        if ref:
            headers["Referer"] = ref
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=10) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        xbmc.log("[StreamLord] fetch error: %s" % str(e), xbmc.LOGERROR)
        return ""

def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Referer": BASE, "X-Requested-With": "XMLHttpRequest"})
        with opener.open(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        xbmc.log("[StreamLord] JSON error: %s" % str(e), xbmc.LOGERROR)
        return {}

def extract_listings(html):
    results = []
    items = re.findall(r'<div class="ml-item">(.*?)</div>', html, re.DOTALL)
    for item in items:
        m = re.search(r'href="([^"]*)"', item)
        link = m.group(1) if m else ""
        if not link or link.startswith("#"):
            continue
        title_m = re.search(r'oldtitle="([^"]*)"', item)
        title_m2 = re.search(r'<h2>(.*?)</h2>', item)
        title = title_m.group(1) if title_m else (title_m2.group(1) if title_m2 else "Unknown")
        quality_m = re.search(r'<span class="mli-quality">([^<]*)</span>', item)
        quality = quality_m.group(1) if quality_m else ""
        thumb_m = re.search(r'data-original="([^"]*)"', item)
        thumb = thumb_m.group(1) if thumb_m else ""
        is_tv = "/tvshow/" in link
        results.append({
            "title": title,
            "link": link if link.startswith("http") else BASE + link,
            "quality": quality,
            "thumb": thumb if thumb.startswith("http") else BASE + thumb,
            "type": "tvshow" if is_tv else "movie",
            "slug": link.split("/")[-1] if link else ""
        })
    return results

def extract_pagination(html):
    pages = re.findall(r'\?page=(\d+)[^>]*>', html)
    max_page = 1
    for p in pages:
        try:
            max_page = max(max_page, int(p))
        except:
            pass
    return max_page

def list_movies(page=1):
    url = BASE + "/movies" if page == 1 else BASE + "/movies?page=%d" % page
    html = fetch(url)
    items = extract_listings(html)
    for item in items:
        li = xbmcgui.ListItem(label=item["title"])
        li.setInfo("video", {"title": item["title"]})
        li.setArt({"thumb": item["thumb"], "fanart": item["thumb"], "icon": "DefaultVideo.png"})
        _tmdb_enrich_item(li, item["title"], media_type="movie")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="movie_detail", slug=item["slug"], link=item["link"]), li, isFolder=True)
    max_page = extract_pagination(html)
    if page < max_page and page < 50:
        li = xbmcgui.ListItem("[B]Next Page >[/B]")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="movies", page=page+1), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_tvseries(page=1):
    url = BASE + "/series" if page == 1 else BASE + "/series?page=%d" % page
    html = fetch(url)
    items = extract_listings(html)
    for item in items:
        li = xbmcgui.ListItem(label=item["title"])
        li.setInfo("video", {"title": item["title"]})
        li.setArt({"thumb": item["thumb"], "fanart": item["thumb"], "icon": "DefaultTVShows.png"})
        _tmdb_enrich_item(li, item["title"], media_type="tv")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="tvshow_detail", slug=item["slug"], link=item["link"]), li, isFolder=True)
    max_page = extract_pagination(html)
    if page < max_page and page < 50:
        li = xbmcgui.ListItem("[B]Next Page >[/B]")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="tvseries", page=page+1), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_genre(genre="action", page=1):
    url = BASE + "/genre/%s" % genre
    if page > 1:
        url += "?page=%d" % page
    html = fetch(url)
    items = extract_listings(html)
    for item in items:
        li = xbmcgui.ListItem(label=item["title"])
        li.setInfo("video", {"title": item["title"]})
        li.setArt({"thumb": item["thumb"], "fanart": item["thumb"], "icon": "DefaultVideo.png"})
        action = "tvshow_detail" if item["type"] == "tvshow" else "movie_detail"
        _tmdb_enrich_item(li, item["title"], media_type=item.get("type", ""))
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action=action, slug=item["slug"], link=item["link"]), li, isFolder=True)
    max_page = extract_pagination(html)
    if page < max_page and page < 50:
        li = xbmcgui.ListItem("[B]Next Page >[/B]")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="genre", genre=genre, page=page+1), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def movie_detail(slug, link):
    html = fetch(link)
    title_m = re.search(r'<h3>(.*?)</h3>', html)
    title = title_m.group(1) if title_m else slug
    desc_m = re.search(r'<div class="desc">(.*?)</div>', html, re.DOTALL)
    desc = desc_m.group(1).strip() if desc_m else ""
    desc = re.sub(r'<[^>]+>', '', desc)
    year_m = re.search(r'Release:</strong>.*?(\d{4})', html)
    year = year_m.group(1) if year_m else ""
    rating_m = re.search(r'IMDb:</strong>\s*([\d.]+)', html)
    rating = rating_m.group(1) if rating_m else ""
    genres = [g for g in re.findall(r'rel="tag">([^<]+)</a>', html) if g not in ["Movies", "TV-Series"] and not re.match(r'^\d{4}$', g)]
    thumb_m = re.search(r'<img src="(/thumbs/[^"]+)"', html)
    thumb = BASE + thumb_m.group(1) if thumb_m else ""
    watch_m = re.search(r'href="(/watch/movie/[^"]+)"', html)
    watch_link = BASE + watch_m.group(1) if watch_m else ""
    mid_m = re.search(r'movie-id="(\d+)"', html)
    mid = mid_m.group(1) if mid_m else ""
    if not mid:
        mid_m = re.search(r'id:\s*"(\d+)"', html)
        mid = mid_m.group(1) if mid_m else ""
    imdb_id = ""
    for pat in [r'imdb["\']?\s*:\s*["\']?tt(\d+)', r'tt(\d{7,8})', r'imdb.*?tt(\d+)', r'Imdb:\s*(\d+)', r'data-imdb=["\']tt(\d+)', r'/thumbs/(\d+)\.jpg']:
        imdb_m = re.search(pat, html, re.IGNORECASE)
        if imdb_m:
            imdb_id = "tt" + imdb_m.group(1)
            break
    label = title
    if year:
        label += " [%s]" % year
    if rating:
        label += " [IMDb: %s]" % rating
    fanart_url = ""
    if imdb_id:
        tmdb_info = _tmdb_find_by_imdb(imdb_id)
        if tmdb_info:
            backdrop = tmdb_info.get("backdrop_path") or tmdb_info.get("poster_path", "")
            if backdrop:
                fanart_url = _tmdb_img(backdrop, "original")
    if not fanart_url and thumb:
        fanart_url = thumb
    if fanart_url:
        xbmcplugin.setPluginFanart(HANDLE, fanart_url)
    rating_f = float(rating) if rating else 0
    li = xbmcgui.ListItem(label=label)
    li.setInfo("video", {"title": title, "plot": desc, "year": year, "genre": ", ".join(genres[:5]), "rating": rating_f})
    li.setArt({"thumb": thumb, "fanart": fanart_url, "icon": "DefaultVideo.png"})
    li.setProperty("IsPlayable", "true")
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="play_movie", mid=mid, title=title, watch_link=watch_link, imdb_id=imdb_id, year=year), li, isFolder=False)
    xbmcplugin.endOfDirectory(HANDLE)

def tvshow_detail(slug, link):
    html = fetch(link)
    title_m = re.search(r'<h3>(.*?)</h3>', html)
    title = title_m.group(1) if title_m else slug
    if not title:
        title_m = re.search(r'class="page-header"[^>]*>\s*<h1>(.*?)</h1>', html, re.DOTALL)
        title = title_m.group(1) if title_m else slug
    desc_m = re.search(r'class="desc">(.*?)</div>', html, re.DOTALL)
    desc = desc_m.group(1).strip() if desc_m else ""
    desc = re.sub(r'<[^>]+>', '', desc)
    rating_m = re.search(r'IMDb:</strong>\s*([\d.]+)', html)
    rating = rating_m.group(1) if rating_m else ""
    thumb_m = re.search(r'<img src="(/thumbs/[^"]+)"', html)
    thumb = BASE + thumb_m.group(1) if thumb_m else ""
    imdb_id = ""
    for pat in [r'imdb["\']?\s*:\s*["\']?tt(\d+)', r'tt(\d{7,8})', r'imdb.*?tt(\d+)', r'Imdb:\s*(\d+)', r'data-imdb=["\']tt(\d+)', r'/thumbs/(\d+)\.jpg']:
        imdb_m = re.search(pat, html, re.IGNORECASE)
        if imdb_m:
            imdb_id = "tt" + imdb_m.group(1)
            break
    fanart_url = ""
    if imdb_id:
        tmdb_info = _tmdb_find_by_imdb(imdb_id)
        if tmdb_info:
            backdrop = tmdb_info.get("backdrop_path") or tmdb_info.get("poster_path", "")
            if backdrop:
                fanart_url = _tmdb_img(backdrop, "original")
    if not fanart_url and thumb:
        fanart_url = thumb
    if fanart_url:
        xbmcplugin.setPluginFanart(HANDLE, fanart_url)
    seasons = re.findall(r'id="season(\d+)"', html)
    for season in seasons:
        label = "Season %s" % season
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": "%s - Season %s" % (title, season)})
        li.setArt({"thumb": thumb, "fanart": fanart_url, "icon": "DefaultTVShows.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="season_episodes", link=link, season=season, show_title=title, thumb=thumb, show_imdb_id=imdb_id), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def season_episodes(link, season, show_title, thumb, show_imdb_id=""):
    html = fetch(link)
    pattern = r'<div class="tab-pane[^"]*"[^>]* id="season%s">(.*?)</div>\s*(?:<div class="tab-pane|</div>|$)' % season
    m = re.search(pattern, html, re.DOTALL)
    if not m:
        xbmcgui.Dialog().ok("Error", "Season not found")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    content = m.group(1)
    fanart_url = ""
    if show_imdb_id:
        tmdb_info = _tmdb_find_by_imdb(show_imdb_id)
        if tmdb_info:
            backdrop = tmdb_info.get("backdrop_path") or tmdb_info.get("poster_path", "")
            if backdrop:
                fanart_url = _tmdb_img(backdrop, "original")
    if not fanart_url and thumb:
        fanart_url = thumb
    if fanart_url:
        xbmcplugin.setPluginFanart(HANDLE, fanart_url)
    episodes = re.findall(r'<a href="(/tvshow/[^"]+/episode-(\d+))"[^>]*>(.*?)</a>', content, re.DOTALL)
    for ep_link, ep_id, ep_name in episodes:
        ep_name = re.sub(r'<[^>]+>', '', ep_name).strip()
        ep_num_m = re.search(r'(\d+)', ep_name)
        episode_num = ep_num_m.group(1) if ep_num_m else ep_id
        li = xbmcgui.ListItem(label=ep_name)
        li.setInfo("video", {"title": ep_name, "tvshowtitle": show_title, "episode": int(episode_num), "season": int(season)})
        li.setArt({"thumb": thumb, "fanart": fanart_url, "icon": "DefaultTVShows.png"})
        li.setProperty("IsPlayable", "true")
        full_link = BASE + ep_link if ep_link.startswith("/") else ep_link
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="play_episode", eid=ep_id, episode_num=episode_num, title=ep_name, link=full_link, show_title=show_title, season=season, show_imdb_id=show_imdb_id), li, isFolder=False)
    xbmcplugin.endOfDirectory(HANDLE)

def search_imdb_suggest(query):
    try:
        query_clean = query.strip().lower().replace(' ', '+')
        first = query_clean[0] if query_clean else 'a'
        url = "https://v2.sg.media-imdb.com/suggests/%s/%s.json" % (first, query_clean.split('+')[0])
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = r.read().decode("utf-8", errors="replace")
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            return []
        import json
        data = json.loads(m.group())
        return data.get('d', [])
    except:
        return []

TMDB_KEY = "84259f99204eeb7d45c7e3d8e36c6123"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p"

def _tmdb_img(path, size="w342"):
    return "%s/%s%s" % (IMAGE_BASE_URL, size, path) if path else ""

def _tmdb_search(query):
    try:
        url = "%s/search/multi?api_key=%s&language=en-US&query=%s&page=1" % (
            TMDB_BASE_URL, TMDB_KEY, urllib.parse.quote(query))
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8", errors="replace")).get("results", [])
    except Exception as e:
        xbmc.log("[StreamLord] TMDB search error: %s" % str(e), xbmc.LOGERROR)
        return []

def _tmdb_tv(tmdb_id):
    try:
        url = "%s/tv/%s?api_key=%s&language=en-US" % (TMDB_BASE_URL, tmdb_id, TMDB_KEY)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        return data.get("seasons", []), data.get("name", ""), data.get("poster_path", ""), data.get("backdrop_path", "")
    except:
        return [], "", "", ""

def _tmdb_enrich_item(li, title, year="", media_type=""):
    try:
        results = _tmdb_search(title)
        for r in results:
            mt = r.get("media_type", "")
            if mt not in ("movie", "tv"):
                continue
            if media_type and mt != media_type:
                continue
            backdrop = r.get("backdrop_path", "")
            if backdrop:
                li.setArt({"fanart": _tmdb_img(backdrop, "original")})
            plot = r.get("overview", "")
            rating = r.get("vote_average", 0)
            ryear = (r.get("release_date") or r.get("first_air_date") or "")[:4]
            info = {"plot": plot, "rating": rating}
            if ryear:
                info["year"] = ryear
            li.setInfo("video", info)
            break
    except:
        pass

def _tmdb_find_by_imdb(imdb_id):
    try:
        url = "%s/find/%s?api_key=%s&language=en-US&external_source=imdb_id" % (
            TMDB_BASE_URL, imdb_id, TMDB_KEY)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        results = data.get("tv_results", [])
        if results:
            return results[0]
        return None
    except:
        return None


def _tmdb_get_imdb_id(tmdb_id, media_type="movie"):
    try:
        url = "%s/%s/%s/external_ids?api_key=%s" % (TMDB_BASE_URL, media_type, tmdb_id, TMDB_KEY)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        return data.get("imdb_id", "")
    except:
        return ""

def _tmdb_episodes(tmdb_id, season_num):
    try:
        url = "%s/tv/%s/season/%s?api_key=%s&language=en-US" % (
            TMDB_BASE_URL, tmdb_id, season_num, TMDB_KEY)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8", errors="replace")).get("episodes", [])
    except:
        return []

def search_streamlord(query="", browse_tmdb="", browse_season=""):
    if browse_tmdb and not query:
        if browse_season:
            _sl_browse_episodes(browse_tmdb, browse_season)
        else:
            _sl_browse_seasons(browse_tmdb)
        return

    if not query:
        kb = xbmc.Keyboard("", "Search StreamLord...")
        kb.doModal()
        if kb.isConfirmed() and kb.getText():
            query = kb.getText().strip()
        else:
            xbmcplugin.endOfDirectory(HANDLE)
            return

    results = _tmdb_search(query)
    if not results:
        xbmcgui.Dialog().notification("StreamLord", "No results found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    items = []
    fanart_url = ""
    for r in results:
        mtype = r.get("media_type", "")
        if mtype not in ("movie", "tv"):
            continue
        title = r.get("title") or r.get("name", "Unknown")
        year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        tid = r.get("id")
        poster = r.get("poster_path", "")
        thumb = _tmdb_img(poster)
        backdrop = r.get("backdrop_path", "")
        if backdrop and not fanart_url:
            fanart_url = _tmdb_img(backdrop, "original")
        plot = r.get("overview", "")
        rating = r.get("vote_average", 0)
        items.append((tid, title, year, mtype, thumb, plot, rating))

    if not items:
        xbmcgui.Dialog().notification("StreamLord", "No results found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    if fanart_url:
        xbmcplugin.setPluginFanart(HANDLE, fanart_url)

    for tid, title, year, mtype, thumb, plot, rating in items:
        label = title
        if year:
            label += " [%s]" % year
        label += " (%s)" % mtype.upper()
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": title, "year": year, "plot": plot, "rating": rating})
        li.setArt({"thumb": thumb, "fanart": fanart_url, "icon": "DefaultVideo.png" if mtype == "movie" else "DefaultTVShows.png"})
        if mtype == "movie":
            li.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action="play_movie", mid="", title=title,
                watch_link="", imdb_id="", year=year, tmdb_id=str(tid)), li, isFolder=False)
        else:
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search_streamlord", browse_tmdb=str(tid)), li, isFolder=True)

    li = xbmcgui.ListItem("[B]New Search[/B]")
    li.setArt({"icon": "DefaultSearch.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search_streamlord"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _sl_browse_seasons(tmdb_id):
    seasons, show_name, poster, fanart = _tmdb_tv(tmdb_id)
    if not seasons:
        xbmcgui.Dialog().notification("StreamLord", "No seasons found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    fanart_url = _tmdb_img(fanart, "original")
    if fanart_url:
        xbmcplugin.setPluginFanart(HANDLE, fanart_url)
    for s in seasons:
        snum = s.get("season_number", 0)
        if snum == 0:
            continue
        eps = s.get("episode_count", 0)
        label = "Season %d [%d episodes]" % (snum, eps)
        li = xbmcgui.ListItem(label=label)
        s_poster = s.get("poster_path") or poster
        li.setInfo("video", {"title": "%s - S%d" % (show_name, snum), "tvshowtitle": show_name})
        li.setArt({"thumb": _tmdb_img(s_poster), "fanart": fanart_url, "icon": "DefaultTVShows.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search_streamlord", browse_tmdb=tmdb_id,
            browse_season=str(snum)), li, isFolder=True)
    li = xbmcgui.ListItem("[B]New Search[/B]")
    li.setArt({"icon": "DefaultSearch.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search_streamlord"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _sl_browse_episodes(tmdb_id, season_num):
    episodes = _tmdb_episodes(tmdb_id, season_num)
    _, show_name, poster, fanart = _tmdb_tv(tmdb_id)
    if not episodes:
        xbmcgui.Dialog().notification("StreamLord", "No episodes found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    fanart_url = _tmdb_img(fanart, "original")
    if fanart_url:
        xbmcplugin.setPluginFanart(HANDLE, fanart_url)
    for ep in episodes:
        epnum = ep.get("episode_number", 0)
        epname = ep.get("name", "Episode %d" % epnum)
        label = "S%02dE%02d - %s" % (int(season_num), epnum, epname)
        li = xbmcgui.ListItem(label=label)
        ep_still = ep.get("still_path") or poster
        li.setInfo("video", {"title": epname, "season": int(season_num), "episode": epnum,
                             "tvshowtitle": show_name, "plot": ep.get("overview", ""),
                             "aired": ep.get("air_date", ""), "rating": ep.get("vote_average", 0)})
        li.setArt({"thumb": _tmdb_img(ep_still), "fanart": fanart_url, "icon": "DefaultTVShows.png"})
        li.setProperty("IsPlayable", "true")
        # Search StreamLord site for this specific show + season + episode
        sl_query = urllib.parse.quote("%s s%02de%02d" % (show_name, int(season_num), epnum), safe='')
        sl_url = BASE + "/search/%s" % sl_query
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="streamlord_play",
            url=sl_url, show_title=show_name, season=str(season_num), episode=str(epnum)),
            li, isFolder=False)
    li = xbmcgui.ListItem("[B]Back to Seasons[/B]")
    li.setArt({"icon": "DefaultFolderBack.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search_streamlord", browse_tmdb=tmdb_id), li, isFolder=True)
    li = xbmcgui.ListItem("[B]New Search[/B]")
    li.setArt({"icon": "DefaultSearch.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search_streamlord"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def streamlord_play(url, show_title, season, episode):
    """Search StreamLord site for episode, extract embed/sources"""
    html = fetch(url)
    items = extract_listings(html)
    if not items:
        xbmcgui.Dialog().notification("StreamLord", "No results on StreamLord", xbmcgui.NOTIFICATION_INFO, 3000)
        return

    # Filter for matching season/episode
    pattern = re.compile(r'[Ss]%02d[Ee]%02d' % (int(season), int(episode)), re.IGNORECASE)
    matching = []
    for item in items:
        if pattern.search(item["title"]) or "season %s" % season in item["title"].lower():
            matching.append(item)

    if not matching:
        matching = items  # Show all if no exact match

    for item in matching[:10]:
        li = xbmcgui.ListItem(label=item["title"])
        li.setInfo("video", {"title": item["title"]})
        li.setArt({"thumb": item["thumb"], "icon": "DefaultTVShows.png"})
        li.setProperty("IsPlayable", "true")
        if item["type"] == "tvshow":
            xbmcplugin.addDirectoryItem(HANDLE,
                get_url(action="season_episodes", link=item["link"], season=season,
                       show_title=show_title, thumb=item["thumb"]), li, isFolder=True)
        else:
            xbmcplugin.addDirectoryItem(HANDLE,
                get_url(action="movie_detail", slug=item["slug"], link=item["link"]), li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def do_search(query="", browse_tmdb="", browse_season=""):
    if browse_tmdb and not query:
        if browse_season:
            _browse_episodes(browse_tmdb, browse_season)
        else:
            _browse_seasons(browse_tmdb)
        return

    if not query:
        kb = xbmc.Keyboard("", "Search All Torrent Sources...")
        kb.doModal()
        if kb.isConfirmed() and kb.getText():
            query = kb.getText().strip()
        else:
            xbmcplugin.endOfDirectory(HANDLE)
            return

    results = _tmdb_search(query)
    if not results:
        xbmcgui.Dialog().notification("StreamLord", "No results found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    items = []
    fanart_url = ""
    for r in results:
        mtype = r.get("media_type", "")
        if mtype not in ("movie", "tv"):
            continue
        title = r.get("title") or r.get("name", "Unknown")
        year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        tid = r.get("id")
        poster = r.get("poster_path", "")
        backdrop = r.get("backdrop_path", "")
        thumb = _tmdb_img(poster)
        if backdrop and not fanart_url:
            fanart_url = _tmdb_img(backdrop, "original")
        plot = r.get("overview", "")
        rating = r.get("vote_average", 0)
        items.append((tid, title, year, mtype, thumb, plot, rating))

    if not items:
        xbmcgui.Dialog().notification("StreamLord", "No results found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    if fanart_url:
        xbmcplugin.setPluginFanart(HANDLE, fanart_url)

    for tid, title, year, mtype, thumb, plot, rating in items:
        label = title
        if year:
            label += " [%s]" % year
        label += " (%s)" % mtype.upper()
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": title, "year": year, "plot": plot, "rating": rating})
        li.setArt({"thumb": thumb, "fanart": fanart_url, "icon": "DefaultVideo.png" if mtype == "movie" else "DefaultTVShows.png"})
        if mtype == "movie":
            li.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action="play_movie", mid="", title=title,
                watch_link="", imdb_id="", year=year, tmdb_id=str(tid)), li, isFolder=False)
        else:
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search", browse_tmdb=str(tid)), li, isFolder=True)

    li = xbmcgui.ListItem("[B]New Search[/B]")
    li.setArt({"icon": "DefaultSearch.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _browse_seasons(tmdb_id):
    seasons, show_name, poster, fanart = _tmdb_tv(tmdb_id)
    if not seasons:
        xbmcgui.Dialog().notification("StreamLord", "No seasons found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    fanart_url = _tmdb_img(fanart, "original")
    if fanart_url:
        xbmcplugin.setPluginFanart(HANDLE, fanart_url)
    for s in seasons:
        snum = s.get("season_number", 0)
        if snum == 0:
            continue
        eps = s.get("episode_count", 0)
        label = "Season %d [%d episodes]" % (snum, eps)
        li = xbmcgui.ListItem(label=label)
        s_poster = s.get("poster_path") or poster
        li.setInfo("video", {"title": "%s - S%d" % (show_name, snum), "tvshowtitle": show_name})
        li.setArt({"thumb": _tmdb_img(s_poster), "fanart": fanart_url, "icon": "DefaultTVShows.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search", browse_tmdb=tmdb_id,
            browse_season=str(snum)), li, isFolder=True)
    li = xbmcgui.ListItem("[B]New Search[/B]")
    li.setArt({"icon": "DefaultSearch.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _browse_episodes(tmdb_id, season_num):
    episodes = _tmdb_episodes(tmdb_id, season_num)
    _, show_name, poster, fanart = _tmdb_tv(tmdb_id)
    if not episodes:
        xbmcgui.Dialog().notification("StreamLord", "No episodes found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    try:
        url = "%s/tv/%s/external_ids?api_key=%s" % (TMDB_BASE_URL, tmdb_id, TMDB_KEY)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as r:
            ext = json.loads(r.read().decode("utf-8", errors="replace"))
        imdb_id = ext.get("imdb_id", "")
    except:
        imdb_id = ""

    fanart_url = _tmdb_img(fanart, "original")
    if fanart_url:
        xbmcplugin.setPluginFanart(HANDLE, fanart_url)

    for ep in episodes:
        epnum = ep.get("episode_number", 0)
        epname = ep.get("name", "Episode %d" % epnum)
        label = "S%02dE%02d - %s" % (int(season_num), epnum, epname)
        li = xbmcgui.ListItem(label=label)
        ep_still = ep.get("still_path") or poster
        li.setInfo("video", {"title": epname, "season": int(season_num), "episode": epnum,
                             "tvshowtitle": show_name, "plot": ep.get("overview", ""),
                             "aired": ep.get("air_date", ""), "rating": ep.get("vote_average", 0)})
        li.setArt({"thumb": _tmdb_img(ep_still), "fanart": fanart_url, "icon": "DefaultTVShows.png"})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="play_episode", eid="",
            title="S%02dE%02d" % (int(season_num), epnum), link="", show_title=show_name,
            season=str(season_num), show_imdb_id=imdb_id, episode_num=str(epnum)),
            li, isFolder=False)

    li = xbmcgui.ListItem("[B]Back to Seasons[/B]")
    li.setArt({"icon": "DefaultFolderBack.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search", browse_tmdb=tmdb_id), li, isFolder=True)
    li = xbmcgui.ListItem("[B]New Search[/B]")
    li.setArt({"icon": "DefaultSearch.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

# --- Torrent playback (uses LordPlayer plugin) ---
TRACKERS = "&tr=udp://tracker.opentrackr.org:1337/announce&tr=udp://open.stealth.si:80/announce&tr=udp://tracker.torrent.eu.org:451/announce"


def _is_season_pack(name):
    """Detect if a torrent name is a full season pack (not a single episode)."""
    name = name or ""
    has_season = bool(re.search(r'[Ss]\d{1,2}', name))
    has_episode = bool(re.search(r'[Ss]\d{1,2}[Ee]\d{1,2}', name))
    if not has_season or has_episode:
        return False
    pack_patterns = [
        r'[Ss]\d{1,2}\s*(complete|full|season|pack)',
        r'[Ss](eason)?\s*\d{1,2}\s*$',
    ]
    return any(re.search(p, name, re.IGNORECASE) for p in pack_patterns) or "complete" in name.lower() or "season" in name.lower()


def _browse_season_pack(magnet, info_hash, title):
    """Add season pack to RD via torrest, browse files."""
    import os
    if not magnet or not magnet.startswith("magnet:"):
        return False
    if TRACKERS not in magnet:
        magnet += TRACKERS
    try:
        d = _tr("POST", "/add/magnet", {"uri": magnet, "ignore_duplicate": "true", "download": "false"})
        th = d.get("info_hash", info_hash or "")
        if not th:
            return False
        for _ in range(30):
            st = _tr("GET", "/torrents/%s/status" % th)
            if st.get("has_metadata"):
                break
            xbmc.sleep(1000)
        files = _tr("GET", "/torrents/%s/files" % th)
        if not files:
            return False
        vids = [f for f in files if f.get("path", "").lower().endswith((".mp4", ".mkv", ".avi", ".m4v", ".mov", ".webm"))]
        if not vids:
            vids = files
        labels = []
        for f in vids:
            fname = f.get("path", "Unknown")
            size = f.get("size", 0)
            sz = ""
            if size >= 1073741824:
                sz = "%d GB" % (size // 1073741824)
            elif size >= 1048576:
                sz = "%d MB" % (size // 1048576)
            ep = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})', fname)
            if ep:
                labels.append("S%02dE%02d - %s [%s]" % (int(ep.group(1)), int(ep.group(2)), os.path.basename(fname), sz))
            else:
                labels.append("%s [%s]" % (os.path.basename(fname), sz))
        idx = xbmcgui.Dialog().select("Season Pack - %s" % title[:30], labels)
        if idx < 0:
            return False
        chosen = vids[idx]
        fid = chosen.get("id")
        if fid is not None:
            _tr("PUT", "/torrents/%s/files/%s/download" % (th, fid), {"buffer": "true"})
            serve = "http://127.0.0.1:61235/torrents/%s/files/%s/serve" % (th, fid)
            if play_http_url(serve, chosen.get("path", title)):
                return True
        return False
    except Exception as e:
        xbmc.log("[StreamLord] Season pack browse error: %s" % str(e), xbmc.LOGERROR)
        return False

def _tr(method, path, params=None):
    url = "http://127.0.0.1:61235" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))

def get_lordplayer_id():
    for lid in ["plugin.video.lordplayer", "plugin.video.lordplayer.droid"]:
        if xbmc.getCondVisibility("System.HasAddon({})".format(lid)):
            return lid
    return "plugin.video.lordplayer"


def play_via_LordPlayer(magnet, title):
    try:
        if not magnet.startswith("magnet:"):
            return False
        if TRACKERS not in magnet:
            magnet += TRACKERS
        player_id = get_lordplayer_id()
        plugin_url = "plugin://%s/play_magnet?magnet=%s&buffer=true" % (player_id, urllib.parse.quote(magnet, safe=''))
        xbmc.log("[StreamLord] Playing via %s" % player_id, xbmc.LOGINFO)
        li = xbmcgui.ListItem(path=plugin_url, label=title)
        li.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
        return True
    except Exception as e:
        xbmc.log("[StreamLord] play_via_LordPlayer error: %s" % str(e), xbmc.LOGERROR)
        return False

def play_via_serve_url(serve_url, title):
    try:
        xbmc.log("[StreamLord] Playing via serve URL: %s" % serve_url, xbmc.LOGINFO)
        li = xbmcgui.ListItem(path=serve_url, label=title)
        li.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
        return True
    except Exception as e:
        xbmc.log("[StreamLord] play_via_serve_url error: %s" % str(e), xbmc.LOGERROR)
        return False

def play_http_url(url, title):
    try:
        xbmc.log("[StreamLord] Playing HTTP URL: %s" % url, xbmc.LOGINFO)
        li = xbmcgui.ListItem(path=url, label=title)
        li.setProperty("IsPlayable", "true")
        xbmc.Player().play(url, li)
        return True
    except Exception as e:
        xbmc.log("[StreamLord] play_http_url error: %s" % str(e), xbmc.LOGERROR)
        return False

def _play_rd_url(url, title):
    """Play a Real-Debrid direct download link."""
    try:
        is_resolve = "resolve" in url and "torrentio" in url
        if not is_resolve and _is_dmca_video(url):
            xbmc.log("[StreamLord] RD URL is DMCA notice, rejecting")
            return False
        xbmc.log("[StreamLord] RD Play: %s" % url[:100], xbmc.LOGINFO)
        li = xbmcgui.ListItem(path=url, label=title)
        li.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
        return True
    except Exception as e:
        xbmc.log("[StreamLord] _play_rd_url error: %s" % str(e), xbmc.LOGERROR)
        return False

def _rd_download(url, filename, title):
    """Download via Real-Debrid direct link."""
    import resources.lib.rd_resolver as rd
    dest = xbmcgui.Dialog().browse(0, "Choose download folder", "files", "", False, True, _get_download_path())
    if not dest:
        return
    rd.download_file(url, dest, filename, title)

def _load_continue_watching():
    try:
        if not os.path.exists(CONTINUE_WATCHING_FILE):
            return []
        with open(CONTINUE_WATCHING_FILE, 'r') as f:
            return json.loads(f.read())
    except:
        return []


def _save_continue_watching(imdb_id, tmdb_id, title, season, episode, show_title, progress_pct):
    try:
        data = _load_continue_watching()
        key = "%s_%s_%s" % (imdb_id, season, episode) if season else imdb_id
        data = [d for d in data if d.get('key') != key]
        data.insert(0, {
            'key': key, 'imdb_id': imdb_id, 'tmdb_id': tmdb_id,
            'title': title, 'show_title': show_title, 'season': str(season or ''),
            'episode': str(episode or ''), 'progress': int(progress_pct),
            'time': int(time.time())
        })
        data = data[:50]
        os.makedirs(os.path.dirname(CONTINUE_WATCHING_FILE), exist_ok=True)
        with open(CONTINUE_WATCHING_FILE, 'w') as f:
            json.dump(data, f)
    except:
        pass


def _is_dmca_video(url):
    try:
        import urllib.request
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", USER_AGENT)
        with urllib.request.urlopen(req, timeout=8) as r:
            cl = r.headers.get("Content-Length", "0")
            size = int(cl) if cl else 0
            if 0 < size < 52428800:
                return True
    except:
        pass
    return False


def sl_device_auth():
    """Real-Debrid OAuth device authorization."""
    try:
        from resources.lib import rd_api
        device_code, user_code, verify_url = rd_api.get_device_code()
        if not device_code:
            xbmcgui.Dialog().ok("StreamLord", "Failed to get device code. Check connection.")
            return
        xbmcgui.Dialog().ok("StreamLord", "Go to this URL and enter code:\n\n%s\n\nCode: %s" % (verify_url, user_code))
        xbmcgui.Dialog().notification("StreamLord", "Authorizing device...")
        client_id, client_secret = rd_api.poll_device_auth(device_code)
        if client_id and client_secret:
            access_token, refresh_tok = rd_api.get_token(client_id, client_secret, device_code)
            if access_token:
                import xbmcaddon
                addon = xbmcaddon.Addon('plugin.video.streamlord')
                addon.setSetting('rd_token', access_token)
                addon.setSetting('rd_refresh_token', refresh_tok or '')
                addon.setSetting('rd_client_id', client_id)
                addon.setSetting('rd_client_secret', client_secret)
                xbmcgui.Dialog().notification("StreamLord", "Device authorized successfully!")
                user = rd_api.get_user()
                if user:
                    xbmcgui.Dialog().notification("StreamLord", "Logged in as: %s" % user.get("username", "Unknown"))
            else:
                rd_api.clear_auth()
                xbmcgui.Dialog().ok("StreamLord", "Token exchange failed. Please try again.")
        else:
            xbmcgui.Dialog().ok("StreamLord", "Device authorization failed or timed out.")
    except Exception as e:
        xbmc.log("[StreamLord] device_auth error: %s" % str(e), xbmc.LOGERROR)
        xbmcgui.Dialog().ok("StreamLord", "Auth error: %s" % str(e))


def _get_stremio_sources(is_tv, imdb_id, season=0, episode=0):
    """Fetch sources from torrentio + comet + mediafusion via RDFlix module."""
    try:
        from resources.lib import torrentio as tio
        if is_tv:
            return tio.get_episode_sources(imdb_id, season, episode)
        else:
            return tio.get_movie_sources(imdb_id)
    except Exception as e:
        xbmc.log("[StreamLord] Stremio sources error: %s" % str(e), xbmc.LOGERROR)
        return []


def _check_rd_cache(sources):
    token = ""
    try:
        import xbmcaddon
        token = xbmcaddon.Addon('plugin.video.streamlord').getSetting('rd_token').strip()
    except:
        pass
    if not token:
        return sources
    from resources.lib import rd_resolver
    hashes = []
    hash_to_idx = {}
    for idx, s in enumerate(sources):
        h = s[4]
        if h and len(h) == 40 and not (len(s) > 7 and s[7]):
            hl = h.lower()
            hashes.append(hl)
            hash_to_idx[hl] = idx
    if not hashes:
        return sources
    try:
        existing = rd_resolver.list_torrents()
        if existing:
            rd_hashes = set()
            for t in existing:
                th = (t.get("hash") or "").lower()[:40]
                if th and t.get("status") == "downloaded":
                    rd_hashes.add(th)
            count = 0
            for h in hashes:
                if h in rd_hashes:
                    idx = hash_to_idx[h]
                    s = list(sources[idx])
                    s[7] = True
                    sources[idx] = tuple(s)
                    count += 1
            xbmc.log("[StreamLord] RD cache check: %d cached from %d existing torrents" % (count, len(rd_hashes)), xbmc.LOGINFO)
    except Exception as e:
        xbmc.log("[StreamLord] RD cache check error: %s" % str(e), xbmc.LOGERROR)
    return sources
    token = ""
    try:
        import xbmcaddon
        token = xbmcaddon.Addon('plugin.video.streamlord').getSetting('rd_token').strip()
    except:
        pass
    if not token:
        return sources
    hashes = []
    hash_to_idx = {}
    for idx, s in enumerate(sources):
        h = s[4]
        if h and len(h) == 40:
            hl = h.lower()
            hashes.append(hl)
            hash_to_idx[hl] = idx
    if not hashes:
        return sources
    try:
        from resources.lib import rd_resolver
        cached = rd_resolver.is_available(hashes)
        if cached:
            count = 0
            for h in cached:
                hl = h.lower()
                if hl in hash_to_idx:
                    idx = hash_to_idx[hl]
                    s = list(sources[idx])
                    s[7] = True
                    sources[idx] = tuple(s)
                    count += 1
            xbmc.log("[StreamLord] RD cache check: %d/%d cached" % (count, len(hashes)), xbmc.LOGINFO)
    except Exception as e:
        xbmc.log("[StreamLord] RD cache check error: %s" % str(e), xbmc.LOGERROR)
    return sources

def _scrape_best_magnet(imdb_id, show_title, season, episode):
    try:
        s_int = int(season) if season else 0
        e_int = int(episode) if episode else 0
        pattern = re.compile(r'[Ss]%02d[Ee]%02d' % (s_int, e_int), re.IGNORECASE)
        import scraper_manager as sm
        sm.set_silent(True)
        results = sm.search_episode(imdb=imdb_id, tvshowtitle=show_title, title="S%02dE%02d" % (s_int, e_int), season=str(s_int), episode=str(e_int), year='')
        sm.set_silent(False)
        best = None
        for s in results:
            if pattern.search(s.get('name', '')) or not s.get('name'):
                magnet = s.get('url', '')
                if magnet and magnet.startswith('magnet:'):
                    seed = int(s.get('seeders', 0))
                    if not best or seed > best[0]:
                        best = (seed, magnet)
        if best:
            return best[1]
        if show_title:
            tpb = search_tpb("%s S%02dE%02d" % (show_title, s_int, e_int))
            for s in tpb:
                magnet = s.get('url', '')
                if magnet and magnet.startswith('magnet:'):
                    seed = int(s.get('seeders', 0))
                    if not best or seed > best[0]:
                        best = (seed, magnet)
            if best:
                return best[1]
    except Exception as e:
        xbmc.log("[StreamLord] _scrape_best_magnet error: %s" % str(e), xbmc.LOGERROR)
    return None

def _prebuffer_torrest(magnet):
    try:
        if TRACKERS not in magnet:
            magnet += TRACKERS
        d = _tr("POST", "/add/magnet", {"uri": magnet, "ignore_duplicate": "true"})
        info_hash = d["info_hash"]
        for _ in range(30):
            st = _tr("GET", "/torrents/%s/status" % info_hash)
            if st.get("has_metadata"):
                break
            xbmc.sleep(1000)
        files = _tr("GET", "/torrents/%s/files" % info_hash)
        vids = [f for f in files if f.get("path", "").lower().endswith((".mp4", ".mkv", ".avi", ".m4v"))]
        if not vids:
            return None
        fid = vids[0]["id"]
        try:
            _tr("PUT", "/torrents/%s/files/%s/download" % (info_hash, fid), {"buffer": "true"})
        except:
            pass
        serve = "http://127.0.0.1:61235/torrents/%s/files/%s/serve" % (info_hash, fid)
        return {"serve": serve, "hash": info_hash, "fid": fid}
    except Exception as e:
        xbmc.log("[StreamLord] _prebuffer_torrest error: %s" % str(e), xbmc.LOGERROR)
        return None

def _autoplay_monitor(imdb_id, season, episode, show_title):
    import xbmcaddon
    try:
        if xbmcaddon.Addon('plugin.video.streamlord').getSetting('autoplay_next') != 'true':
            xbmc.log("[StreamLord] Autoplay: setting is off", xbmc.LOGINFO)
            return
        xbmc.log("[StreamLord] Autoplay: starting monitor for S%02dE%02d" % (int(season or 0), int(episode or 0)), xbmc.LOGINFO)
        player = xbmc.Player()
        monitor = xbmc.Monitor()
        for _ in range(180):
            if player.isPlaying():
                break
            monitor.waitForAbort(1)
        if not player.isPlaying():
            xbmc.log("[StreamLord] Autoplay: playback never started after 180s", xbmc.LOGINFO)
            return
        if monitor.abortRequested():
            xbmc.log("[StreamLord] Autoplay: Kodi shutting down", xbmc.LOGINFO)
            return
        for _ in range(30):
            total = player.getTotalTime()
            if total > 60:
                break
            monitor.waitForAbort(1)
        xbmc.log("[StreamLord] Autoplay: total time=%ds" % total, xbmc.LOGINFO)
        s_int = int(season) if season else 0
        e_int = int(episode) if episode else 0
        next_s, next_e = s_int, e_int + 1
        reached_end = False
        while player.isPlaying() and not monitor.abortRequested():
            if total > 0:
                remaining = int(total - player.getTime())
                if remaining <= 240:
                    reached_end = True
                    break
            monitor.waitForAbort(1)
        if not player.isPlaying():
            if not reached_end:
                xbmc.log("[StreamLord] Autoplay: user pressed stop, aborting chain", xbmc.LOGINFO)
                return
            xbmc.log("[StreamLord] Autoplay: playback ended naturally", xbmc.LOGINFO)
        elif monitor.abortRequested():
            xbmc.log("[StreamLord] Autoplay: Kodi shutting down", xbmc.LOGINFO)
            return
        xbmc.log("[StreamLord] Autoplay: scraping next S%02dE%02d" % (next_s, next_e), xbmc.LOGINFO)
        magnet = _scrape_best_magnet(imdb_id, show_title, next_s, next_e)
        if not magnet and next_e != 1:
            next_s, next_e = s_int + 1, 1
            xbmc.log("[StreamLord] Autoplay: trying next season S%02dE%02d" % (next_s, next_e), xbmc.LOGINFO)
            magnet = _scrape_best_magnet(imdb_id, show_title, next_s, next_e)
        if not magnet:
            xbmc.log("[StreamLord] Autoplay: no magnet for next episode", xbmc.LOGINFO)
            return
        xbmc.log("[StreamLord] Autoplay: prebuffering magnet", xbmc.LOGINFO)
        info = _prebuffer_torrest(magnet)
        if not info:
            xbmc.log("[StreamLord] Autoplay: prebuffer failed", xbmc.LOGINFO)
            return
        serve = info["serve"]
        info_hash = info["hash"]
        for _ in range(120):
            st = _tr("GET", "/torrents/%s/status" % info_hash)
            dl = st.get("downloaded", 0) or 0
            if dl > 100 * 1024 * 1024:
                break
            tot = st.get("total_size", 0) or 0
            if tot > 0 and dl >= tot * 0.10:
                break
            xbmc.sleep(1000)
        while player.isPlaying() and not monitor.abortRequested():
            monitor.waitForAbort(1)
        if not monitor.abortRequested():
            xbmc.sleep(15000)
            xbmc.log("[StreamLord] Autoplay: final buffer wait done for S%02dE%02d" % (next_s, next_e), xbmc.LOGINFO)
            xbmc.log("[StreamLord] Autoplay: playing next S%02dE%02d via Player().play()" % (next_s, next_e), xbmc.LOGINFO)
            if play_http_url(serve, "%s S%02dE%02d" % (show_title, next_s, next_e)):
                _autoplay_monitor(imdb_id, next_s, next_e, show_title)
    except Exception as e:
        import traceback
        xbmc.log("[StreamLord] Autoplay CRASH: %s" % str(e), xbmc.LOGERROR)
        xbmc.log("[StreamLord] Autoplay traceback: %s" % traceback.format_exc(), xbmc.LOGERROR)

def download_via_LordPlayer(magnet, title, dest):
    try:
        if not magnet.startswith("magnet:"):
            xbmcgui.Dialog().ok("StreamLord", "Invalid magnet link")
            return False
        if TRACKERS not in magnet:
            magnet += TRACKERS
        d = _tr("POST", "/add/magnet", {"uri": magnet, "ignore_duplicate": "true", "download": "true"})
        info_hash = d["info_hash"]
        for _ in range(60):
            st = _tr("GET", "/torrents/%s/status" % info_hash)
            if st.get("has_metadata"):
                break
            xbmc.sleep(1000)
        progress = xbmcgui.DialogProgress()
        progress.create("StreamLord - Downloading")
        done = False
        while not progress.iscanceled():
            st = _tr("GET", "/torrents/%s/status" % info_hash)
            prog = st.get("progress", 0)
            pct = int(min(prog, 1.0) * 100)
            state_names = {0: "queued", 1: "checking", 2: "downloading", 3: "meta", 4: "finished", 5: "seeding", 6: "alloc", 7: "check fast"}
            sn = state_names.get(st.get("state", -1), str(st.get("state", "?")))
            progress.update(pct, "%d%% - %s" % (pct, sn))
            if prog >= 1.0:
                done = True
                break
            xbmc.sleep(2000)
        progress.close()
        if done:
            files = _tr("GET", "/torrents/%s/files" % info_hash)
            vids = [f for f in files if f.get("path", "").lower().endswith((".mp4", ".mkv", ".avi", ".m4v"))]
            if vids:
                fid = vids[0].get("id")
                if len(vids) > 1:
                    labels = [os.path.basename(f.get("path", "Unknown")) for f in vids]
                    pick = xbmcgui.Dialog().select("Select file", labels)
                    if pick >= 0:
                        fid = vids[pick].get("id")
                fname = os.path.basename(vids[0].get("path", "video.mp4"))
                serve = "http://127.0.0.1:61235/torrents/%s/files/%s/serve" % (info_hash, fid)
                out = os.path.join(dest, fname)
                dl_prog = xbmcgui.DialogProgress()
                dl_prog.create("StreamLord - Saving")
                req = urllib.request.Request(serve, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=300) as src:
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
                                dl_prog.update(int(wrote / total * 100), "%d / %d MB" % (wrote // 1048576, total // 1048576))
                dl_prog.close()
                xbmcgui.Dialog().notification("Download Complete", fname, xbmcgui.NOTIFICATION_INFO, 5000)
            return True
        return False
    except Exception as e:
        xbmc.log("[StreamLord] Download error: %s" % str(e), xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Download Error", str(e))
        return False
    xbmc.log("[StreamLord] Playing LordPlayer: %s" % url[:100], xbmc.LOGINFO)
    li = xbmcgui.ListItem(path=url, label=title)
    li.setProperty("IsPlayable", "true")
    if url.startswith("http"):
        li.setMimeType("video/x-matroska")
        li.setContentLookup(False)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)
    return True

def _get_download_path():
    try:
        import xbmcaddon
        a = xbmcaddon.Addon('plugin.video.streamlord')
        p = a.getSetting('download_path').strip()
        if p:
            return xbmcvfs.translatePath(p)
    except:
        pass
    return xbmcvfs.translatePath("special://home/userdata/downloads/")


def play_movie(mid, title, watch_link="", imdb_id="", year="", tmdb_id="", resume_pct="0"):
    if not imdb_id and tmdb_id:
        imdb_id = _tmdb_get_imdb_id(tmdb_id, "movie")
        xbmc.log("[StreamLord] Resolved tmdb_id=%s to imdb_id=%s" % (tmdb_id, imdb_id), xbmc.LOGINFO)

    all_sources = []

    if imdb_id:
        try:
            import scraper_manager as sm
            xbmc.log("[StreamLord] Searching CocoScrapers for movie %s" % imdb_id, xbmc.LOGINFO)
            results = sm.search_movie(imdb=imdb_id, title=title, year=year)
            if results:
                used = set()
                for s in results:
                    key = s.get('hash') or s.get('url', '')
                    if key not in used:
                        used.add(key)
                        q = s.get('quality', '?')
                        seed = s.get('seeders', 0)
                        all_sources.append(('torrent', q, seed, s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), s.get('debrid', False) or s.get('cached_checked', False)))
        except Exception as e:
            xbmc.log("[StreamLord] Movie scraper error: %s" % str(e), xbmc.LOGWARNING)

    if not all_sources and title:
        xbmc.log("[StreamLord] CocoScrapers returned nothing, trying TPB for %s" % title, xbmc.LOGINFO)
        tpb = search_tpb(title + (" " + year if year else ""))
        for s in tpb:
            all_sources.append(('torrent', s.get('quality', 'SD'), s.get('seeders', 0), s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), s.get('debrid', False) or s.get('cached_checked', False)))

    if imdb_id:
        try:
            stremio = _get_stremio_sources(False, imdb_id)
            for s in stremio:
                bh = s.get('behaviorHints', {})
                ih = s.get('infoHash', '') or bh.get('infoHash', '')
                url = s.get('url', '')
                if not ih and ('playback' in url or 'exception' in url or 'configure' in url or 'error' in url.lower()):
                    continue
                magnet = "magnet:?xt=urn:btih:%s&dn=%s%s" % (ih, urllib.parse.quote(s.get('title', title)), TRACKERS) if ih else url
                origin = s.get('_origin', '')
                label = origin or s.get('title', title)[:50]
                name_field = origin or s.get('title', '')
                has_hash = bool(ih and len(ih) >= 40)
                all_sources.append(('stremio', s.get('_quality', '?'), s.get('seeders', 0), magnet, ih, s.get('size', ''), name_field, True))
        except Exception as e:
            xbmc.log("[StreamLord] Stremio movie sources error: %s" % str(e), xbmc.LOGERROR)

    deduped = []
    seen = set()
    for s in all_sources:
        h = s[4]
        if h and h not in seen:
            seen.add(h)
            deduped.append(s)

    _check_rd_cache(deduped)

    deduped.sort(key=lambda s: (0 if (len(s) > 7 and s[7]) else 1, QUALITY_ORDER.get(s[1], 99), -(int(s[2]) if s[2] else 0)))

    items = []
    for s in deduped:
        name = s[6] if len(s) > 6 else ""
        is_debrid = len(s) > 7 and s[7]
        quality = s[1]
        seeders = s[2]
        size_str = (" [%s]" % s[5]) if s[5] else ""
        seed_str = (" [S:%s]" % seeders) if seeders else ""

        if is_debrid:
            tag = "[COLOR cyan][B]RD[/B][/COLOR]"
        elif _is_season_pack(name):
            tag = "[COLOR yellow][B]PACK[/B][/COLOR]"
        else:
            tag = "[COLOR orange][B]LP[/B][/COLOR]"

        if s[0] == 'stremio':
            fname = name or "Unknown"
            label = "%s %s %s%s%s" % (tag, quality, fname[:50], size_str, seed_str)
        else:
            label = "%s %s %s%s%s [Scraper]" % (tag, quality, (name or "Unknown")[:50], size_str, seed_str)

        items.append(label.strip())

    if len(items) == 0:
        xbmcplugin.endOfDirectory(HANDLE)
        xbmcgui.Dialog().ok("StreamLord", "No torrents found for\n%s" % title)
        return

    if len(items) == 1:
        chosen_idx = 0
    else:
        chosen_idx = xbmcgui.Dialog().select("Select torrent - %s" % title, items)

    if chosen_idx < 0:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    chosen = deduped[chosen_idx]
    xbmc.log("[StreamLord] Trying %s %s" % (chosen[1], chosen[3][:80]), xbmc.LOGINFO)
    
    is_debrid = len(chosen) > 7 and chosen[7]
    info_hash = chosen[4] if len(chosen) > 4 else ""
    magnet = chosen[3]
    name = chosen[6] if len(chosen) > 6 else ""

    if _is_season_pack(name) and magnet:
        if _browse_season_pack(magnet, info_hash, title):
            _save_resume(title, imdb_id, tmdb_id, resume_pct, 0, 0)
            return

    if is_debrid and magnet and "resolve" in magnet:
        if _play_rd_url(magnet, title):
            _save_resume(title, imdb_id, tmdb_id, resume_pct, 0, 0)
            return
        xbmcplugin.endOfDirectory(HANDLE)
        xbmcgui.Dialog().ok("StreamLord", "RD resolve URL failed.\n%s" % title)
        return

    # If RD cached with hash, try RD first, auto-fallback to LP
    if is_debrid and info_hash:
        from resources.lib import rd_resolver
        rd_url, rd_fname = rd_resolver.resolve_torrent(info_hash, title)
        if rd_url and rd_fname:
            if _play_rd_url(rd_url, title):
                _save_resume(title, imdb_id, tmdb_id, resume_pct, 0, 0)
                return
        # RD failed - auto fallback to LordPlayer
        xbmc.log("[StreamLord] RD failed, auto-falling back to LordPlayer", xbmc.LOGINFO)
    
    if play_via_LordPlayer(magnet, title):
        _save_resume(title, imdb_id, tmdb_id, resume_pct, 0, 0)
        return

    xbmcplugin.endOfDirectory(HANDLE)
    xbmcgui.Dialog().ok("StreamLord", "Torrent failed to play.\n%s" % title)

def play_episode(eid, title, link, show_title, season, show_imdb_id="", episode_num="", tmdb_id="", resume_pct="0"):
    if not show_imdb_id and tmdb_id:
        show_imdb_id = _tmdb_get_imdb_id(tmdb_id, "tv")
    full_title = "%s - %s" % (show_title, title) if show_title else title
    season_num = re.search(r'\d+', season).group() if re.search(r'\d+', season) else season
    ep_num = episode_num or re.search(r'(\d+)', title) if not episode_num else episode_num
    if isinstance(ep_num, re.Match):
        ep_num = ep_num.group(1) if ep_num else eid

    # Build patterns to filter for exact episode
    s_int = int(season_num) if season_num.isdigit() else 0
    e_int = int(ep_num) if ep_num.isdigit() else 0
    exact_pattern = re.compile(r'[Ss]%02d[Ee]%02d|[Ss]%d[Ee]%02d' % (s_int, e_int, s_int, e_int), re.IGNORECASE) if s_int else re.compile(re.escape("S%sE%s" % (season_num, ep_num)), re.IGNORECASE)

    all_sources = []

    if show_imdb_id:
        try:
            import scraper_manager as sm
            xbmc.log("[StreamLord] Searching CocoScrapers for episode %s S%sE%s" % (show_imdb_id, season_num, ep_num), xbmc.LOGINFO)
            results = sm.search_episode(imdb=show_imdb_id, tvshowtitle=show_title, title=title, season=season_num, episode=ep_num, year='')
            if results:
                used = set()
                for s in results:
                    key = s.get('hash') or s.get('url', '')
                    name = s.get('name', '')
                    # Filter CocoScrapers results for exact episode match too
                    if key not in used and (exact_pattern.search(name) or not name or len(results) <= 3):
                        used.add(key)
                        q = s.get('quality', '?')
                        seed = s.get('seeders', 0)
                        is_debrid = s.get('debrid', False) or s.get('cached_checked', False)
                        all_sources.append(('torrent', q, seed, s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), is_debrid))
        except Exception as e:
            xbmc.log("[StreamLord] Episode scraper error: %s" % str(e), xbmc.LOGWARNING)

    if not all_sources and show_title:
        q = "%s S%02dE%02d" % (show_title, s_int, e_int)
        xbmc.log("[StreamLord] CocoScrapers returned nothing, trying TPB for %s" % q, xbmc.LOGINFO)
        tpb = search_tpb(q)
        for s in tpb:
            name = s.get('name', '')
            if exact_pattern.search(name) or len(tpb) <= 1:
                all_sources.append(('torrent', s.get('quality', 'SD'), s.get('seeders', 0), s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), s.get('debrid', False) or s.get('cached_checked', False)))

    if show_imdb_id:
        try:
            stremio = _get_stremio_sources(True, show_imdb_id, s_int, e_int)
            for s in stremio:
                bh = s.get('behaviorHints', {})
                ih = s.get('infoHash', '') or bh.get('infoHash', '')
                url = s.get('url', '')
                if not ih and ('playback' in url or 'exception' in url or 'configure' in url or 'error' in url.lower()):
                    continue
                magnet = "magnet:?xt=urn:btih:%s&dn=%s%s" % (ih, urllib.parse.quote(s.get('title', title)), TRACKERS) if ih else url
                origin = s.get('_origin', '')
                name_field = origin or s.get('title', '')
                all_sources.append(('stremio', s.get('_quality', '?'), s.get('seeders', 0), magnet, ih, s.get('size', ''), name_field, True))
        except Exception as e:
            xbmc.log("[StreamLord] Stremio episode sources error: %s" % str(e), xbmc.LOGERROR)

    deduped = []
    seen = set()
    for s in all_sources:
        h = s[4]
        if h and h not in seen:
            seen.add(h)
            deduped.append(s)

    _check_rd_cache(deduped)

    deduped.sort(key=lambda s: (0 if (len(s) > 7 and s[7]) else 1, QUALITY_ORDER.get(s[1], 99), -(int(s[2]) if s[2] else 0)))

    items = []
    for s in deduped:
        name = s[6] if len(s) > 6 else ""
        is_debrid = len(s) > 7 and s[7]
        quality = s[1]
        seeders = s[2]
        size_str = (" [%s]" % s[5]) if s[5] else ""
        seed_str = (" [S:%s]" % seeders) if seeders else ""

        if is_debrid:
            tag = "[COLOR cyan][B]RD[/B][/COLOR]"
        elif _is_season_pack(name):
            tag = "[COLOR yellow][B]PACK[/B][/COLOR]"
        else:
            tag = "[COLOR orange][B]LP[/B][/COLOR]"

        if s[0] == 'stremio':
            fname = name or "Unknown"
            label = "%s %s %s%s%s" % (tag, quality, fname[:50], size_str, seed_str)
        else:
            label = "%s %s %s%s%s [Scraper]" % (tag, quality, (name or "Unknown")[:50], size_str, seed_str)

        items.append(label.strip())

    if len(items) == 0:
        li = xbmcgui.ListItem(path=link)
        xbmcplugin.setResolvedUrl(HANDLE, False, li)
        xbmcgui.Dialog().ok("StreamLord", "No torrents found for\n%s" % full_title)
        return

    if len(items) == 1:
        chosen_idx = 0
    else:
        chosen_idx = xbmcgui.Dialog().select("Select torrent - %s" % full_title, items)

    if chosen_idx < 0:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    chosen = deduped[chosen_idx]
    xbmc.log("[StreamLord] Trying %s %s" % (chosen[1], chosen[3][:80]), xbmc.LOGINFO)
    
    is_debrid = len(chosen) > 7 and chosen[7]
    info_hash = chosen[4] if len(chosen) > 4 else ""
    magnet = chosen[3]
    name = chosen[6] if len(chosen) > 6 else ""

    if _is_season_pack(name) and magnet:
        if _browse_season_pack(magnet, info_hash, full_title):
            _autoplay_monitor(show_imdb_id, season_num, ep_num, show_title)
            return

    if is_debrid and magnet and "resolve" in magnet:
        if _play_rd_url(magnet, full_title):
            _autoplay_monitor(show_imdb_id, season_num, ep_num, show_title)
            return
        xbmcplugin.endOfDirectory(HANDLE)
        xbmcgui.Dialog().ok("StreamLord", "RD resolve URL failed.\n%s" % full_title)
        return

    if is_debrid and info_hash:
        from resources.lib import rd_resolver
        rd_url, rd_fname = rd_resolver.resolve_torrent(info_hash, full_title)
        if rd_url and rd_fname:
            if _play_rd_url(rd_url, full_title):
                _autoplay_monitor(show_imdb_id, season_num, ep_num, show_title)
                return
        xbmc.log("[StreamLord] RD failed, auto-falling back to LordPlayer", xbmc.LOGINFO)

    if play_via_LordPlayer(magnet, full_title):
        _autoplay_monitor(show_imdb_id, season_num, ep_num, show_title)
        return

    xbmcplugin.endOfDirectory(HANDLE)
    xbmcgui.Dialog().ok("StreamLord", "Torrent failed to play.\n%s" % full_title)

# --- Settings & Download helpers ---

def show_settings():
    import xbmcaddon
    xbmcaddon.Addon('plugin.video.streamlord').openSettings()
    xbmcplugin.endOfDirectory(HANDLE, updateListing=True)

def handle_download(magnet, title):
    dest = xbmcgui.Dialog().browse(0, "Choose download folder", "files", "", False, True, _get_download_path())
    if not dest:
        xbmc.log("[StreamLord] Download cancelled by user", xbmc.LOGINFO)
        return
    xbmc.log("[StreamLord] Download selected: %s" % dest, xbmc.LOGINFO)
    download_via_LordPlayer(magnet, title, dest)

GENRES = ["action", "adventure", "animation", "comedy", "crime", "documentary", "drama", "family", "fantasy", "history", "horror", "music", "mystery", "romance", "sci-fi", "thriller", "war", "western"]

def search_tpb_menu(query="", browse_tmdb="", browse_season=""):
    if browse_tmdb and not query:
        if browse_season:
            _tpb_browse_episodes(browse_tmdb, browse_season)
        else:
            _tpb_browse_seasons(browse_tmdb)
        return

    if not query:
        kb = xbmcgui.Dialog().input("Search TPB for:", type=xbmcgui.INPUT_ALPHANUM)
        if not kb:
            xbmcplugin.endOfDirectory(HANDLE)
            return
        query = kb

    results = _tmdb_search(query)
    if not results:
        xbmcgui.Dialog().notification("StreamLord", "No results found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    items = []
    fanart_url = ""
    for r in results:
        mtype = r.get("media_type", "")
        if mtype not in ("movie", "tv"):
            continue
        title = r.get("title") or r.get("name", "Unknown")
        year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        tid = r.get("id")
        poster = r.get("poster_path", "")
        thumb = _tmdb_img(poster)
        backdrop = r.get("backdrop_path", "")
        if backdrop and not fanart_url:
            fanart_url = _tmdb_img(backdrop, "original")
        plot = r.get("overview", "")
        rating = r.get("vote_average", 0)
        items.append((tid, title, year, mtype, thumb, plot, rating))

    if not items:
        xbmcgui.Dialog().notification("StreamLord", "No results found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    if fanart_url:
        xbmcplugin.setPluginFanart(HANDLE, fanart_url)

    for tid, title, year, mtype, thumb, plot, rating in items:
        label = title
        if year:
            label += " [%s]" % year
        label += " (%s)" % mtype.upper()
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": title, "year": year, "plot": plot, "rating": rating})
        li.setArt({"thumb": thumb, "fanart": fanart_url, "icon": "DefaultVideo.png" if mtype == "movie" else "DefaultTVShows.png"})
        if mtype == "movie":
            li.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action="tpb_play_movie", title=title, year=year), li, isFolder=False)
        else:
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action="tpb_search", browse_tmdb=str(tid)), li, isFolder=True)

    li = xbmcgui.ListItem("[B]New Search[/B]")
    li.setArt({"icon": "DefaultSearch.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="tpb_search"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _tpb_browse_seasons(tmdb_id):
    seasons, show_name, poster, fanart = _tmdb_tv(tmdb_id)
    if not seasons:
        xbmcgui.Dialog().notification("StreamLord", "No seasons found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    fanart_url = _tmdb_img(fanart, "original")
    if fanart_url:
        xbmcplugin.setPluginFanart(HANDLE, fanart_url)
    for s in seasons:
        snum = s.get("season_number", 0)
        if snum == 0:
            continue
        eps = s.get("episode_count", 0)
        label = "Season %d [%d episodes]" % (snum, eps)
        li = xbmcgui.ListItem(label=label)
        s_poster = s.get("poster_path") or poster
        li.setInfo("video", {"title": "%s - S%d" % (show_name, snum), "tvshowtitle": show_name})
        li.setArt({"thumb": _tmdb_img(s_poster), "fanart": fanart_url, "icon": "DefaultTVShows.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="tpb_search", browse_tmdb=tmdb_id,
            browse_season=str(snum)), li, isFolder=True)
    li = xbmcgui.ListItem("[B]New Search[/B]")
    li.setArt({"icon": "DefaultSearch.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="tpb_search"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _tpb_browse_episodes(tmdb_id, season_num):
    episodes = _tmdb_episodes(tmdb_id, season_num)
    _, show_name, poster, fanart = _tmdb_tv(tmdb_id)
    if not episodes:
        xbmcgui.Dialog().notification("StreamLord", "No episodes found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    fanart_url = _tmdb_img(fanart, "original")
    if fanart_url:
        xbmcplugin.setPluginFanart(HANDLE, fanart_url)
    for ep in episodes:
        epnum = ep.get("episode_number", 0)
        epname = ep.get("name", "Episode %d" % epnum)
        label = "S%02dE%02d - %s" % (int(season_num), epnum, epname)
        li = xbmcgui.ListItem(label=label)
        ep_still = ep.get("still_path") or poster
        li.setInfo("video", {"title": epname, "season": int(season_num), "episode": epnum,
                             "tvshowtitle": show_name, "plot": ep.get("overview", ""),
                             "aired": ep.get("air_date", ""), "rating": ep.get("vote_average", 0)})
        li.setArt({"thumb": _tmdb_img(ep_still), "fanart": fanart_url, "icon": "DefaultTVShows.png"})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="tpb_play_episode",
            show_title=show_name, season=str(season_num), episode=str(epnum)),
            li, isFolder=False)
    li = xbmcgui.ListItem("[B]Back to Seasons[/B]")
    li.setArt({"icon": "DefaultFolderBack.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="tpb_search", browse_tmdb=tmdb_id), li, isFolder=True)
    li = xbmcgui.ListItem("[B]New Search[/B]")
    li.setArt({"icon": "DefaultSearch.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="tpb_search"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def tpb_play_movie(title, year):
    q = "%s %s" % (title, year) if year else title
    results = search_tpb(q)
    _show_tpb_results(results, q)


def tpb_play_episode(show_title, season, episode):
    q = "%s S%02dE%02d" % (show_title, int(season), int(episode))
    results = search_tpb(q)
    pattern = re.compile(r'[Ss]%02d[Ee]%02d' % (int(season), int(episode)), re.IGNORECASE)
    filtered = [s for s in results if pattern.search(s.get('name', ''))] if len(results) > 1 else results
    _show_tpb_results(filtered or results, q)


def _show_tpb_results(results, label):
    if not results:
        xbmcgui.Dialog().notification("StreamLord", "No results on TPB", xbmcgui.NOTIFICATION_INFO, 3000)
        return
    qo = {'4K': 0, '1080p': 1, '1080': 1, '720p': 2, '720': 2, 'SD': 3, 'SCR': 4, 'CAM': 5}
    ss = sorted(results, key=lambda s: (qo.get(s.get('quality', 'SD'), 99), -(int(s.get('seeders', 0)))))
    slist = []
    for s in ss:
        name = s.get('name', '')
        short = name[:60] + ".." if len(name) > 62 else name
        lbl = "%s %s" % (s.get('quality', '?'), s.get('size', '')) if s.get('size') else s.get('quality', '?')
        if s.get('seeders'):
            lbl += " [S:%s]" % s['seeders']
        if short:
            lbl = "%s - %s" % (short, lbl)
        slist.append(lbl)
    idx = xbmcgui.Dialog().select("TPB: %s" % label, slist)
    if idx < 0:
        return
    chosen = ss[idx]
    magnet = chosen.get('url', '') or chosen.get('magnet', '')
    if not magnet.startswith("magnet:"):
        xbmcgui.Dialog().ok("StreamLord", "Not a magnet link.")
        return
    if int(chosen.get('seeders', 0)) == 0 and not xbmcgui.Dialog().yesno("StreamLord", "0 seeders. Try anyway?"):
        return
    action = xbmcgui.Dialog().select("Choose action", ["Play via LordPlayer", "Download via LordPlayer"])
    if action == 0:
        play_via_LordPlayer(magnet, label)
    elif action == 1:
        handle_download(magnet, label)

def _save_resume(title, imdb_id, tmdb_id, resume_pct, season, episode):
    if imdb_id or tmdb_id:
        _save_continue_watching(imdb_id, tmdb_id, title, season, episode, title, resume_pct)


def _do_resume_seek(resume_pct):
    if int(float(resume_pct)) > 5:
        xbmc.sleep(2000)
        try:
            player = xbmc.Player()
            if player.isPlaying():
                total = player.getTotalTime()
                seek_to = int(total * float(resume_pct) / 100)
                player.seekTime(seek_to)
                xbmc.log("[StreamLord] Resumed at %ds" % seek_to, xbmc.LOGINFO)
        except:
            pass


def list_continue_watching():
    items = _load_continue_watching()
    if not items:
        xbmcgui.Dialog().notification("StreamLord", "Nothing in continue watching", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    for item in items:
        title = item.get('show_title') or item.get('title', 'Unknown')
        season = item.get('season', '')
        episode = item.get('episode', '')
        progress = item.get('progress', 0)
        label = title
        if season and episode:
            label = "%s S%02dE%02d" % (title, int(season or 0), int(episode or 0))
        label += " [%d%%]" % progress
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": title, "tvshowtitle": title if season else "", "season": int(season or 0), "episode": int(episode or 0)})
        li.setArt({"icon": "DefaultTVShows.png" if season else "DefaultVideo.png"})
        imdb_id = item.get('imdb_id', '')
        tmdb_id = item.get('tmdb_id', '')
        if season and episode:
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action="play_episode", eid="", title="S%02dE%02d" % (int(season or 0), int(episode or 0)),
                link="", show_title=title, season=season, show_imdb_id=imdb_id, episode_num=episode, tmdb_id=tmdb_id, resume_pct=str(progress)), li, isFolder=False)
        else:
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action="play_movie", mid="", title=title, watch_link="",
                imdb_id=imdb_id, year="", tmdb_id=tmdb_id, resume_pct=str(progress)), li, isFolder=False)
    xbmcplugin.endOfDirectory(HANDLE)


def show_menu():
    import xbmcaddon
    s = xbmcaddon.Addon('plugin.video.streamlord').getSetting
    
    items = []
    if s('show_tmdb_trending') != 'false':
        items.append(("[B]TMDB Trending Movies[/B]", "browse_tmdb", "DefaultMovies.png", {"category": "popular", "media": "movie"}))
        items.append(("[B]TMDB Trending TV[/B]", "browse_tmdb", "DefaultTVShows.png", {"category": "popular", "media": "tv"}))
    if s('show_tmdb_genres') != 'false':
        items.append(("[B]TMDB Movie Genres[/B]", "browse_tmdb_genres", "DefaultGenre.png", {"media": "movie"}))
        items.append(("[B]TMDB TV Genres[/B]", "browse_tmdb_genres", "DefaultGenre.png", {"media": "tv"}))
    if s('show_tmdb_search') != 'false':
        items.append(("[B]TMDB Search[/B]", "tmdb_search", "DefaultAddonsSearch.png"))
    if s('show_continue_watching') != 'false':
        items.append(("[B]Continue Watching[/B]", "continue_watching", "DefaultRecentlyAddedEpisodes.png"))
    if s('show_search_torrents') != 'false':
        items.append(("[B]Search All Torrents[/B]", "search", "DefaultAddonsSearch.png"))
    if s('show_streamlord_movies') != 'false':
        items.append(("[B]Streamlord Movies[/B]", "movies", "DefaultMovies.png"))
    if s('show_streamlord_tv') != 'false':
        items.append(("[B]Streamlord TV Series[/B]", "tvseries", "DefaultTVShows.png"))
    if s('show_trakt') != 'false':
        items.append(("[B]Trakt Watchlist Movies[/B]", "trakt_watchlist", "DefaultVideo.png", {"media": "movie"}))
        items.append(("[B]Trakt Watchlist TV[/B]", "trakt_watchlist", "DefaultTVShows.png", {"media": "show"}))
    if s('show_open_magnet') != 'false':
        items.append(("[B]Open Magnet[/B]", "open_magnet", "DefaultAddon.png"))
    items.append(("[B]LordPlayer[/B]", "lordplayer", "DefaultAddon.png"))
    items.append(("[B]Settings[/B]", "settings", "DefaultAddon.png"))
    for label, action, icon, *extra in items:
        params = extra[0] if extra else {}
        li = xbmcgui.ListItem(label)
        li.setArt({"icon": icon, "thumb": icon})
        if action == "lordplayer":
            xbmcplugin.addDirectoryItem(HANDLE, "plugin://{}/".format(get_lordplayer_id()), li, isFolder=True)
        else:
            p = get_url(action=action, **params)
            xbmcplugin.addDirectoryItem(HANDLE, p, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_genres():
    for genre in GENRES:
        li = xbmcgui.ListItem(genre.capitalize())
        li.setInfo("video", {"genre": genre.capitalize(), "title": genre.capitalize()})
        li.setArt({"thumb": "DefaultGenre.png", "icon": "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="genre", genre=genre), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_top_imdb(page=1):
    url = BASE + "/filter/movie/imdb/all/all/all/"
    if page > 1:
        url += "?page=%d" % page
    html = fetch(url)
    items = extract_listings(html)
    for item in items:
        li = xbmcgui.ListItem(label=item["title"])
        li.setInfo("video", {"title": item["title"]})
        li.setArt({"thumb": item["thumb"], "fanart": item["thumb"], "icon": "DefaultVideo.png"})
        _tmdb_enrich_item(li, item["title"], media_type="movie")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="movie_detail", slug=item["slug"], link=item["link"]), li, isFolder=True)
    max_page = extract_pagination(html)
    if page < max_page and page < 50:
        li = xbmcgui.ListItem("[B]Next Page >[/B]")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="top_imdb", page=page+1), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

# --- Fight Sports (watchwrestling.ae) ---

def fight_sports_menu():
    import watchwrestling as ww
    for label, slug in ww.CATEGORIES:
        li = xbmcgui.ListItem(label)
        li.setInfo("video", {"title": label})
        li.setArt({"thumb": "DefaultVideo.png", "icon": "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="fight_category", cat_slug=slug), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def fight_category(cat_slug, page=1):
    import watchwrestling as ww
    posts, has_next = ww.list_category(cat_slug, page)
    for post in posts:
        li = xbmcgui.ListItem(label=post["title"])
        li.setInfo("video", {"title": post["title"]})
        li.setArt({"thumb": post["thumb"], "fanart": post.get("thumb", ""), "icon": "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="fight_post", url=post["link"]), li, isFolder=True)
    if has_next:
        li = xbmcgui.ListItem("[B]Next Page >[/B]")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="fight_category", cat_slug=cat_slug, page=page+1), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def fight_post(url):
    import watchwrestling as ww
    detail = ww.get_post_detail(url)
    search_title = ww.clean_title(detail["title"])
    thumb = detail.get("thumb", "")
    fanart_url = thumb if thumb else ""
    if fanart_url:
        xbmcplugin.setPluginFanart(HANDLE, fanart_url)
    # Torrent search option (primary)
    li = xbmcgui.ListItem(label="[B]Search Torrents: %s[/B]" % search_title)
    li.setInfo("video", {"title": "Search Torrents: %s" % search_title, "plot": detail.get("desc", "")})
    li.setArt({"thumb": thumb, "fanart": fanart_url, "icon": "DefaultVideo.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="fight_torrent_search", title=search_title), li, isFolder=False)
    # Also list any embed video links as secondary options
    if detail["videos"]:
        li = xbmcgui.ListItem(label="--- Embed Links (less reliable) ---")
        li.setProperty("IsPlayable", "false")
        xbmcplugin.addDirectoryItem(HANDLE, '', li, isFolder=False)
        for idx, v in enumerate(detail["videos"]):
            label = v.get("label", "") or "Video %d" % (idx + 1)
            li = xbmcgui.ListItem(label=label)
            li.setProperty("IsPlayable", "true")
            li.setInfo("video", {"title": detail["title"], "plot": detail.get("desc", "")})
            li.setArt({"thumb": thumb, "fanart": fanart_url, "icon": "DefaultVideo.png"})
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action="fight_play", video_url=v["url"], title=detail["title"]), li, isFolder=False)
    xbmcplugin.endOfDirectory(HANDLE)

def search_tpb(query):
    """Direct TPB API search, returns list of result dicts"""
    import json
    results = []
    try:
        url = "https://apibay.org/q.php?q=%s" % urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        for item in data:
            if item.get('id', '0') == '0':
                continue
            name = item.get('name', '')
            info_hash = item.get('info_hash', '')
            if not info_hash:
                continue
            magnet = "magnet:?xt=urn:btih:%s&dn=%s%s" % (info_hash, name, TRACKERS)
            results.append({
                'hash': info_hash,
                'magnet': magnet,
                'url': magnet,
                'quality': '1080p' if '1080' in name else ('720p' if '720' in name else 'SD'),
                'seeders': int(item.get('seeders', 0)),
                'size': item.get('size', ''),
                'name': name,
            })
    except Exception as e:
        xbmc.log("[StreamLord] TPB search error: %s" % str(e), xbmc.LOGERROR)
    return results

def fight_torrent_search(show_title):
    import scraper_manager as sm
    kb = xbmcgui.Dialog().input("Search torrents for:", show_title, type=xbmcgui.INPUT_ALPHANUM)
    if not kb:
        xbmcplugin.endOfDirectory(HANDLE)
        return
    query = kb
    xbmc.log("[StreamLord] Searching torrents: %s" % query, xbmc.LOGINFO)
    # Try TPB directly first (works without IMDb)
    results = search_tpb(query)
    # Also try scraper_manager as fallback
    sm.init()
    ep_results = sm.search_episode('', query, '', '1', '1', '')
    mov_results = sm.search_movie('', query, '')
    results.extend(ep_results)
    results.extend(mov_results)
    if not results:
        xbmcgui.Dialog().ok("StreamLord", "No torrents found for\n%s\nTry a different search." % query)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    QUALITY_ORDER = {'4K': 0, '1080p': 1, '1080': 1, '720p': 2, '720': 2, 'SD': 3, 'SCR': 4, 'CAM': 5}
    all_sources = []
    used = set()
    for s in results:
        key = s.get('hash') or s.get('url', '')
        if key not in used:
            used.add(key)
            q = s.get('quality', '?')
            seed = s.get('seeders', 0)
            all_sources.append(('torrent', q, seed, s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), s.get('debrid', False) or s.get('cached_checked', False)))
    _check_rd_cache(all_sources)
    ss = sorted(all_sources, key=lambda s: (0 if (len(s) > 7 and s[7]) else 1, QUALITY_ORDER.get(s[1], 99), -(int(s[2]) if s[2] else 0)))
    slist = []
    for s in ss:
        name = s[6] if len(s) > 6 else ""
        short = name[:60] + ".." if len(name) > 62 else name
        lbl = "%s %s" % (s[1], s[5]) if s[5] else s[1]
        if s[2]:
            lbl += " [S:%s]" % s[2]
        if len(s) > 7 and s[7]:
            lbl = "[B][COLOR cyan]RD-CACHED[/COLOR][/B] %s" % lbl
        if short:
            lbl = "%s - %s" % (short, lbl)
        else:
            lbl = "%s %s [S:%s]" % (s[1], s[5], s[2])
        slist.append(lbl)
    idx = xbmcgui.Dialog().select("Select source - %s" % query, slist)
    if idx < 0:
        xbmcplugin.endOfDirectory(HANDLE)
        return
    chosen = ss[idx]
    magnet = chosen[3]
    if not magnet.startswith("magnet:"):
        xbmcgui.Dialog().ok("StreamLord", "Not a magnet link.\nTry a different source.")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    if chosen[2] == 0 and not (len(chosen) > 7 and chosen[7]) and not xbmcgui.Dialog().yesno("StreamLord", "0 seeders - may not play.\nTry anyway?"):
        xbmcplugin.endOfDirectory(HANDLE)
        return
    action = xbmcgui.Dialog().select("Choose action", ["Play via LordPlayer", "Download via LordPlayer"])
    if action == 0:
        play_via_LordPlayer(magnet, query)
    elif action == 1:
        handle_download(magnet, query)

def fight_play(video_url, title):
    import watchwrestling as ww
    xbmc.log("[StreamLord] Fight Sports resolving: %s" % video_url[:80], xbmc.LOGINFO)
    resolved = ww.resolve_video(video_url)
    if not resolved:
        xbmcgui.Dialog().ok("StreamLord", "Could not resolve video source.\nTry a different link.")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    xbmc.log("[StreamLord] Fight Sports resolved: %s -> %s" % (resolved["type"], resolved["url"][:80]), xbmc.LOGINFO)
    if resolved["type"] == "okru_hls":
        li = xbmcgui.ListItem(path=resolved["url"], label=title)
        li.setProperty("IsPlayable", "true")
        li.setProperty("inputstreamaddon", "inputstream.adaptive")
        li.setProperty("inputstream.adaptive.manifest_type", "hls")
        li.setProperty("inputstream.adaptive.manifest_headers", "Referer=https://www.ok.ru/&User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        li.setMimeType("application/vnd.apple.mpegurl")
        li.setContentLookup(False)
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
        return
    if resolved["type"] in ("okru", "embed"):
        xbmcgui.Dialog().ok("StreamLord", "Embed source not supported without resolveurl.\nTry a different link on this post.")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    if resolved["type"] == "direct":
        li = xbmcgui.ListItem(path=resolved["url"], label=title)
        li.setProperty("IsPlayable", "true")
        if ".m3u8" in resolved["url"]:
            li.setProperty("inputstreamaddon", "inputstream.adaptive")
            li.setProperty("inputstream.adaptive.manifest_type", "hls")
            li.setProperty("inputstream.adaptive.manifest_headers", "Referer=https://www.dailymotion.com&User-Agent=" + urllib.parse.quote(USER_AGENT))
            li.setProperty("inputstream.adaptive.stream_headers", "Referer=https://www.dailymotion.com&User-Agent=" + urllib.parse.quote(USER_AGENT))
        elif ".mp4" in resolved["url"]:
            li.setProperty("HTTPUserAgent", USER_AGENT)
            li.setProperty("HTTPReferer", "https://www.dailymotion.com")
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
        return
    xbmcgui.Dialog().ok("StreamLord", "Unsupported video type: %s" % resolved["type"])
    xbmcplugin.endOfDirectory(HANDLE)

def main():
    try:
        p = parse_params(PARAMS)
        a = p.get("action", "")
        if a == "movies":
            list_movies(int(p.get("page", "1")))
        elif a == "tvseries":
            list_tvseries(int(p.get("page", "1")))
        elif a == "genre":
            list_genre(p.get("genre", "action"), int(p.get("page", "1")))
        elif a == "genres":
            list_genres()
        elif a == "top_imdb":
            list_top_imdb(int(p.get("page", "1")))
        elif a == "search":
            do_search(p.get("query", ""), p.get("browse_tmdb", ""), p.get("browse_season", ""))
        elif a == "search_streamlord":
            search_streamlord(p.get("query", ""), p.get("browse_tmdb", ""), p.get("browse_season", ""))
        elif a == "streamlord_play":
            streamlord_play(p.get("url", ""), p.get("show_title", ""), p.get("season", "1"), p.get("episode", "1"))
        elif a == "settings":
            show_settings()
        elif a == "movie_detail":
            movie_detail(p.get("slug", ""), p.get("link", ""))
        elif a == "tvshow_detail":
            tvshow_detail(p.get("slug", ""), p.get("link", ""))
        elif a == "season_episodes":
            season_episodes(p.get("link", ""), p.get("season", "1"), p.get("show_title", ""), p.get("thumb", ""), p.get("show_imdb_id", ""))
        elif a == "play_movie":
            play_movie(p.get("mid", ""), p.get("title", ""), p.get("watch_link", ""), p.get("imdb_id", ""), p.get("year", ""), p.get("tmdb_id", ""), p.get("resume_pct", "0"))
        elif a == "play_episode":
            play_episode(p.get("eid", ""), p.get("title", ""), p.get("link", ""), p.get("show_title", ""), p.get("season", "1"), p.get("show_imdb_id", ""), p.get("episode_num", ""), p.get("tmdb_id", ""), p.get("resume_pct", "0"))
        elif a == "tpb_search":
            search_tpb_menu(p.get("query", ""), p.get("browse_tmdb", ""), p.get("browse_season", ""))
        elif a == "tpb_play_movie":
            tpb_play_movie(p.get("title", ""), p.get("year", ""))
        elif a == "tpb_play_episode":
            tpb_play_episode(p.get("show_title", ""), p.get("season", ""), p.get("episode", ""))
        elif a == "continue_watching":
            list_continue_watching()
        elif a == "browse_tmdb":
            ext.browse_tmdb(p.get("category", "popular"), p.get("media", "movie"), int(p.get("page", "1")))
        elif a == "browse_tmdb_genres":
            ext.browse_tmdb_genres(p.get("media", "movie"))
        elif a == "browse_tmdb_genre_list":
            ext.browse_tmdb_genre_list(p.get("genre_id", ""), p.get("genre_name", ""), p.get("media", "movie"), int(p.get("page", "1")))
        elif a == "tmdb_search":
            ext.browse_tmdb_search(p.get("query", ""))
        elif a == "tv_browse_seasons":
            ext.tv_browse_seasons(p.get("tmdb_id", ""), p.get("show_title", ""), p.get("imdb_id", ""))
        elif a == "tv_browse_episodes":
            ext.tv_browse_episodes(p.get("tmdb_id", ""), p.get("season", ""), p.get("show_title", ""), p.get("imdb_id", ""))
        elif a == "person_detail":
            ext.person_detail(p.get("person_id", ""), p.get("person_name", ""))
        elif a == "trakt_watchlist":
            ext.browse_trakt_watchlist(p.get("media", "movie"))
        elif a == "trakt_auth":
            ext.trakt_auth()
        elif a == "livetv_menu":
            ext.livetv_menu()
        elif a == "livetv_channels":
            ext.livetv_channels(p.get("group", ""))
        elif a == "livetv_play":
            ext.livetv_play(urllib.parse.unquote(p.get("url", "")), p.get("title", ""))
        elif a == "sports_search":
            ext.sports_search(p.get("query", ""))
        elif a == "open_magnet":
            ext.open_magnet()
        elif a == "open_magnet_play":
            ext.open_magnet_play(p.get("magnet", ""), p.get("title", "Magnet"))
        elif a == "surprise_me":
            ext.surprise_me(p.get("media", "movie"))
        elif a == "fight_category":
            fight_category(p.get("cat_slug", ""), int(p.get("page", "1")))
        elif a == "fight_post":
            fight_post(p.get("url", ""))
        elif a == "fight_play":
            fight_play(p.get("video_url", ""), p.get("title", ""))
        elif a == "fight_torrent_search":
            fight_torrent_search(p.get("title", ""))
        elif a == "device_auth":
            sl_device_auth()
        else:
            show_menu()
    except Exception as e:
        tb = traceback.format_exc()
        xbmc.log("[StreamLord] CRASH: %s\n%s" % (str(e), tb), xbmc.LOGFATAL)
        xbmcgui.Dialog().ok("StreamLord Error", str(e))
        xbmcplugin.endOfDirectory(HANDLE)

if __name__ == "__main__":
    main()
