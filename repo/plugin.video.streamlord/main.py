import xbmcgui
import xbmcplugin
import xbmc
import xbmcvfs
import xbmcaddon
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

HANDLE = int(sys.argv[1])
URL = sys.argv[0]
PARAMS = sys.argv[2]

BASE = "https://streamlord.to"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
QUALITY_ORDER = {'4K': 0, '1080p': 1, '720p': 2, 'SD': 3, 'SCR': 4, 'CAM': 5}

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
    html = fetch(url)
    items = extract_listings(html)
    if not items:
        xbmcgui.Dialog().notification("StreamLord", "No results on StreamLord", xbmcgui.NOTIFICATION_INFO, 3000)
        return

    pattern = re.compile(r'[Ss]%02d[Ee]%02d' % (int(season), int(episode)), re.IGNORECASE)
    matching = []
    for item in items:
        if pattern.search(item["title"]) or "season %s" % season in item["title"].lower():
            matching.append(item)

    if not matching:
        matching = items

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

# --- Torrent playback ---
TRACKERS = "&tr=udp://tracker.opentrackr.org:1337/announce&tr=udp://open.stealth.si:80/announce&tr=udp://tracker.torrent.eu.org:451/announce"

def _tr(method, path, params=None):
    url = "http://127.0.0.1:61235" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))

def play_via_LordPlayer(magnet, title):
    try:
        if not magnet.startswith("magnet:"):
            return False
        if TRACKERS not in magnet:
            magnet += TRACKERS
        player_id = "plugin.video.lordplayer"
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

def _try_torrest_serve(magnet, title):
    info = _prebuffer_torrest(magnet)
    if info:
        serve = info["serve"]
        if play_via_serve_url(serve, title):
            return True
    return False

def _play_rd_url(url, title):
    try:
        xbmc.log("[StreamLord] RD Play: %s" % url[:100], xbmc.LOGINFO)
        li = xbmcgui.ListItem(path=url, label=title)
        li.setProperty("IsPlayable", "true")
        li.setMimeType("video/x-matroska")
        li.setContentLookup(False)
        li.setProperty("inputstreamaddon", "inputstream.adaptive")
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
        return True
    except Exception as e:
        xbmc.log("[StreamLord] _play_rd_url error: %s" % str(e), xbmc.LOGERROR)
        return False

def _rd_download(url, filename, title):
    import resources.lib.rd_resolver as rd
    dest = xbmcgui.Dialog().browse(0, "Choose download folder", "files", "", False, True, _get_download_path())
    if not dest:
        return
    rd.download_file(url, dest, filename, title)

def _fetch_rd_hashes():
    try:
        token = xbmcaddon.Addon('plugin.video.streamlord').getSetting('rd_token').strip()
        if not token:
            return set()
        import resources.lib.rd_resolver as rd
        known = set()
        torrents = rd.list_torrents()
        if torrents:
            known.update(t.get("hash", "").lower() for t in torrents if t.get("hash"))
        return known
    except:
        return set()


def _try_rd_resolve(info_hash, title):
    if not info_hash or len(info_hash) != 40:
        return None, None
    try:
        from resources.lib import rd_resolver
        return rd_resolver.resolve_torrent(info_hash, title)
    except:
        return None, None

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
        while player.isPlaying() and not monitor.abortRequested():
            if total > 0:
                remaining = int(total - player.getTime())
                if remaining <= 240:
                    break
            monitor.waitForAbort(1)
        if not player.isPlaying():
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


def play_movie(mid, title, watch_link="", imdb_id="", year=""):
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
                        debrid = s.get('debrid', False)
                        all_sources.append(('torrent', q, seed, s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), debrid))
        except Exception as e:
            xbmc.log("[StreamLord] Movie scraper error: %s" % str(e), xbmc.LOGWARNING)

    if not all_sources and title:
        xbmc.log("[StreamLord] CocoScrapers returned nothing, trying TPB for %s" % title, xbmc.LOGINFO)
        tpb = search_tpb(title + (" " + year if year else ""))
        for s in tpb:
            all_sources.append(('torrent', s.get('quality', 'SD'), s.get('seeders', 0), s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), False))

    deduped = []
    seen = set()
    for s in all_sources:
        h = s[4]
        if h and h not in seen:
            seen.add(h)
            deduped.append(s)

    rd_hashes = _fetch_rd_hashes()
    xbmc.log("[StreamLord] RD existing torrents: %d hashes" % len(rd_hashes), xbmc.LOGINFO)

    def is_rd_known(s):
        if len(s) > 7 and s[7]:
            return True
        return s[4].lower() in rd_hashes if s[4] else False

    deduped.sort(key=lambda s: (0 if is_rd_known(s) else 1, QUALITY_ORDER.get(s[1], 99), -(int(s[2]) if s[2] else 0)))

    items = []
    for s in deduped:
        name = s[6] if len(s) > 6 else ""
        known = is_rd_known(s)
        label = "%s %s" % (s[1], s[5]) if s[5] else s[1]
        if s[2]:
            label += " [S:%s]" % s[2]
        if known:
            label = "[B][COLOR cyan]RD-CACHED[/COLOR][/B] %s" % label
        if name:
            label = "%s - %s" % (name[:60], label)
        items.append(label)

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
    xbmc.log("[StreamLord] Trying %s %s" % (chosen[1], chosen[3][:50]), xbmc.LOGINFO)

    # Always try RD first for any torrent
    info_hash = chosen[4] if len(chosen) > 4 else ""
    rd_url, rd_fname = _try_rd_resolve(info_hash, title)

    if rd_url:
        xbmc.log("[StreamLord] RD resolved!", xbmc.LOGINFO)
        rd_actions = ["Play via RD (Instant)", "Download via RD", "Play via LordPlayer", "Download via LordPlayer"]
        rd_idx = xbmcgui.Dialog().select("Real-Debrid - %s" % title, rd_actions)
        if rd_idx == 0:
            _play_rd_url(rd_url, title)
            return
        elif rd_idx == 1:
            _rd_download(rd_url, rd_fname, title)
            xbmcplugin.endOfDirectory(HANDLE)
            return
        elif rd_idx == 2:
            if play_via_LordPlayer(chosen[3], title):
                return
            if _try_torrest_serve(chosen[3], title):
                return
            xbmcplugin.endOfDirectory(HANDLE)
            xbmcgui.Dialog().ok("StreamLord", "Torrent failed to play.\n%s" % title)
            return
        elif rd_idx == 3:
            handle_download(chosen[3], title)
            xbmcplugin.endOfDirectory(HANDLE)
            return
        else:
            xbmcplugin.endOfDirectory(HANDLE)
            return

    # RD failed or no hash — fall through to LordPlayer
    if chosen[2] == 0 and not xbmcgui.Dialog().yesno("StreamLord", "0 seeders - may not play.\nTry anyway?"):
        xbmcplugin.endOfDirectory(HANDLE)
        return
    action = xbmcgui.Dialog().select("Choose action", ["Play", "Download"])
    if action == 0:
        if play_via_LordPlayer(chosen[3], title):
            return
        if _try_torrest_serve(chosen[3], title):
            return
    elif action == 1:
        handle_download(chosen[3], title)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    xbmcplugin.endOfDirectory(HANDLE)
    xbmcgui.Dialog().ok("StreamLord", "Torrent failed to play.\n%s" % title)

def play_episode(eid, title, link, show_title, season, show_imdb_id="", episode_num=""):
    full_title = "%s - %s" % (show_title, title) if show_title else title
    season_num = re.search(r'\d+', season).group() if re.search(r'\d+', season) else season
    ep_num = episode_num or re.search(r'(\d+)', title) if not episode_num else episode_num
    if isinstance(ep_num, re.Match):
        ep_num = ep_num.group(1) if ep_num else eid

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
                    if key not in used and (exact_pattern.search(name) or not name or len(results) <= 3):
                        used.add(key)
                        q = s.get('quality', '?')
                        seed = s.get('seeders', 0)
                        debrid = s.get('debrid', False)
                        all_sources.append(('torrent', q, seed, s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), debrid))
        except Exception as e:
            xbmc.log("[StreamLord] Episode scraper error: %s" % str(e), xbmc.LOGWARNING)

    if not all_sources and show_title:
        q = "%s S%02dE%02d" % (show_title, s_int, e_int)
        xbmc.log("[StreamLord] CocoScrapers returned nothing, trying TPB for %s" % q, xbmc.LOGINFO)
        tpb = search_tpb(q)
        for s in tpb:
            name = s.get('name', '')
            if exact_pattern.search(name) or len(tpb) <= 1:
                all_sources.append(('torrent', s.get('quality', 'SD'), s.get('seeders', 0), s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), False))

    deduped = []
    seen = set()
    for s in all_sources:
        h = s[4]
        if h and h not in seen:
            seen.add(h)
            deduped.append(s)

    rd_hashes = _fetch_rd_hashes()
    xbmc.log("[StreamLord] RD existing torrents: %d hashes" % len(rd_hashes), xbmc.LOGINFO)

    def is_rd_known(s):
        if len(s) > 7 and s[7]:
            return True
        return s[4].lower() in rd_hashes if s[4] else False

    deduped.sort(key=lambda s: (0 if is_rd_known(s) else 1, QUALITY_ORDER.get(s[1], 99), -(int(s[2]) if s[2] else 0)))

    items = []
    for s in deduped:
        name = s[6] if len(s) > 6 else ""
        known = is_rd_known(s)
        label = "%s %s" % (s[1], s[5]) if s[5] else s[1]
        if s[2]:
            label += " [S:%s]" % s[2]
        if known:
            label = "[B][COLOR cyan]RD-CACHED[/COLOR][/B] %s" % label
        if name:
            label = "%s - %s" % (name[:60], label)
        items.append(label)

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

    # Always try RD first for any torrent
    info_hash = chosen[4] if len(chosen) > 4 else ""
    rd_url, rd_fname = _try_rd_resolve(info_hash, full_title)

    if rd_url:
        xbmc.log("[StreamLord] RD resolved episode!", xbmc.LOGINFO)
        rd_actions = ["Play via RD (Instant)", "Download via RD", "Play via LordPlayer", "Download via LordPlayer"]
        rd_idx = xbmcgui.Dialog().select("Real-Debrid - %s" % full_title, rd_actions)
        if rd_idx == 0:
            _play_rd_url(rd_url, full_title)
            return
        elif rd_idx == 1:
            _rd_download(rd_url, rd_fname, full_title)
            xbmcplugin.endOfDirectory(HANDLE)
            return
        elif rd_idx == 2:
            if play_via_LordPlayer(chosen[3], full_title):
                xbmc.log("[StreamLord] Calling _autoplay_monitor S%02dE%02d imdb=%s" % (s_int, e_int, show_imdb_id), xbmc.LOGINFO)
                _autoplay_monitor(show_imdb_id, season_num, ep_num, show_title)
                xbmc.log("[StreamLord] _autoplay_monitor returned", xbmc.LOGINFO)
                return
            if _try_torrest_serve(chosen[3], full_title):
                xbmc.log("[StreamLord] Calling _autoplay_monitor S%02dE%02d (LordPlayer) imdb=%s" % (s_int, e_int, show_imdb_id), xbmc.LOGINFO)
                _autoplay_monitor(show_imdb_id, season_num, ep_num, show_title)
                return
            xbmcplugin.endOfDirectory(HANDLE)
            xbmcgui.Dialog().ok("StreamLord", "Torrent failed to play.\n%s" % full_title)
            return
        elif rd_idx == 3:
            handle_download(chosen[3], full_title)
            xbmcplugin.endOfDirectory(HANDLE)
            return
        else:
            xbmcplugin.endOfDirectory(HANDLE)
            return

    # RD failed or no hash — fall through to LordPlayer
    if chosen[2] == 0 and not xbmcgui.Dialog().yesno("StreamLord", "0 seeders - may not play.\nTry anyway?"):
        xbmcplugin.endOfDirectory(HANDLE)
        return
    action = xbmcgui.Dialog().select("Choose action", ["Play", "Download"])
    if action == 0:
        if play_via_LordPlayer(chosen[3], full_title):
            xbmc.log("[StreamLord] Calling _autoplay_monitor S%02dE%02d imdb=%s" % (s_int, e_int, show_imdb_id), xbmc.LOGINFO)
            _autoplay_monitor(show_imdb_id, season_num, ep_num, show_title)
            xbmc.log("[StreamLord] _autoplay_monitor returned", xbmc.LOGINFO)
            return
        if _try_torrest_serve(chosen[3], full_title):
            xbmc.log("[StreamLord] Calling _autoplay_monitor S%02dE%02d (LordPlayer)" % (s_int, e_int), xbmc.LOGINFO)
            _autoplay_monitor(show_imdb_id, season_num, ep_num, show_title)
            return
    elif action == 1:
        handle_download(chosen[3], full_title)
        xbmcplugin.endOfDirectory(HANDLE)
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
    sources = []
    used = set()
    for s in results:
        key = s.get('hash') or s.get('url', '')
        if key not in used:
            used.add(key)
            q = s.get('quality', '?')
            seed = s.get('seeders', 0)
            sources.append(('torrent', q, seed, s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), False))
    rd_hashes = _fetch_rd_hashes()
    xbmc.log("[StreamLord] TPB RD existing torrents: %d hashes" % len(rd_hashes), xbmc.LOGINFO)

    def is_rd_known(s):
        return s[4].lower() in rd_hashes if s[4] else False

    sources.sort(key=lambda s: (0 if is_rd_known(s) else 1, qo.get(s[1], 99), -(int(s[2]) if s[2] else 0)))
    slist = []
    for s in sources:
        name = s[6] if len(s) > 6 else ""
        short = name[:60] + ".." if len(name) > 62 else name
        lbl = "%s %s" % (s[1], s[5]) if s[5] else s[1]
        if s[2]:
            lbl += " [S:%s]" % s[2]
        if is_rd_known(s):
            lbl = "[B][COLOR cyan]RD-CACHED[/COLOR][/B] %s" % lbl
        if short:
            lbl = "%s - %s" % (short, lbl)
        slist.append(lbl)
    idx = xbmcgui.Dialog().select("TPB: %s" % label, slist)
    if idx < 0:
        return
    chosen = sources[idx]
    magnet = chosen[3]
    if not magnet.startswith("magnet:"):
        xbmcgui.Dialog().ok("StreamLord", "Not a magnet link.")
        return
    if chosen[2] == 0 and not is_rd_known(chosen) and not xbmcgui.Dialog().yesno("StreamLord", "0 seeders. Try anyway?"):
        return
    info_hash = chosen[4] if len(chosen) > 4 else ""
    rd_url, rd_fname = _try_rd_resolve(info_hash, label)
    if rd_url:
        xbmc.log("[StreamLord] TPB RD resolved!", xbmc.LOGINFO)
        rd_actions = ["Play via RD (Instant)", "Download via RD", "Play via LordPlayer", "Download via LordPlayer"]
        rd_idx = xbmcgui.Dialog().select("Real-Debrid - %s" % label, rd_actions)
        if rd_idx == 0:
            _play_rd_url(rd_url, label)
            return
        elif rd_idx == 1:
            _rd_download(rd_url, rd_fname, label)
            return
        elif rd_idx == 2:
            pass
        elif rd_idx == 3:
            handle_download(magnet, label)
            return
        else:
            return
    action = xbmcgui.Dialog().select("Choose action", ["Play", "Download"])
    if action == 0:
        play_via_LordPlayer(magnet, label)
    elif action == 1:
        handle_download(magnet, label)

def show_menu():
    items = [
        ("[B]Search All Torrents[/B]", "search", "DefaultAddonsSearch.png"),
        ("[B]Hot Movies[/B]", "movies", "DefaultMovies.png"),
        ("[B]TV Series[/B]", "tvseries", "DefaultTVShows.png"),
        ("[B]Top IMDb[/B]", "top_imdb", "DefaultVideo.png"),
        ("[B]Genres[/B]", "genres", "DefaultVideo.png"),
        ("[B]LordPlayer[/B]", "lordplayer", "DefaultAddon.png"),
        ("[B]Settings[/B]", "settings", "DefaultAddon.png"),
    ]
    for label, action, icon in items:
        li = xbmcgui.ListItem(label)
        li.setArt({"icon": icon, "thumb": icon})
        if action == "lordplayer":
            xbmcplugin.addDirectoryItem(HANDLE, "plugin://plugin.video.lordplayer/", li, isFolder=True)
        else:
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action=action), li, isFolder=True)
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
    li = xbmcgui.ListItem(label="[B]Search Torrents: %s[/B]" % search_title)
    li.setInfo("video", {"title": "Search Torrents: %s" % search_title, "plot": detail.get("desc", "")})
    li.setArt({"thumb": thumb, "fanart": fanart_url, "icon": "DefaultVideo.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="fight_torrent_search", title=search_title), li, isFolder=False)
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
    results = search_tpb(query)
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
            all_sources.append(('torrent', q, seed, s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), s.get('debrid', False)))
    rd_hashes = _fetch_rd_hashes()
    xbmc.log("[StreamLord] Fight RD existing torrents: %d hashes" % len(rd_hashes), xbmc.LOGINFO)

    def is_rd_known(s):
        if len(s) > 7 and s[7]:
            return True
        return s[4].lower() in rd_hashes if s[4] else False

    ss = sorted(all_sources, key=lambda s: (0 if is_rd_known(s) else 1, QUALITY_ORDER.get(s[1], 99), -(int(s[2]) if s[2] else 0)))
    slist = []
    for s in ss:
        name = s[6] if len(s) > 6 else ""
        short = name[:60] + ".." if len(name) > 62 else name
        lbl = "%s %s" % (s[1], s[5]) if s[5] else s[1]
        if s[2]:
            lbl += " [S:%s]" % s[2]
        if is_rd_known(s):
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
    if chosen[2] == 0 and not is_rd_known(chosen) and not xbmcgui.Dialog().yesno("StreamLord", "0 seeders - may not play.\nTry anyway?"):
        xbmcplugin.endOfDirectory(HANDLE)
        return
    info_hash = chosen[4] if len(chosen) > 4 else ""
    rd_url, rd_fname = _try_rd_resolve(info_hash, query)
    if rd_url:
        xbmc.log("[StreamLord] Fight RD resolved!", xbmc.LOGINFO)
        rd_actions = ["Play via RD (Instant)", "Download via RD", "Play via LordPlayer", "Download via LordPlayer"]
        rd_idx = xbmcgui.Dialog().select("Real-Debrid - %s" % query, rd_actions)
        if rd_idx == 0:
            _play_rd_url(rd_url, query)
            return
        elif rd_idx == 1:
            _rd_download(rd_url, rd_fname, query)
            return
        elif rd_idx == 2:
            pass
        elif rd_idx == 3:
            handle_download(magnet, query)
            return
        else:
            return
    play_via_LordPlayer(magnet, query)

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
            play_movie(p.get("mid", ""), p.get("title", ""), p.get("watch_link", ""), p.get("imdb_id", ""), p.get("year", ""))
        elif a == "play_episode":
            play_episode(p.get("eid", ""), p.get("title", ""), p.get("link", ""), p.get("show_title", ""), p.get("season", "1"), p.get("show_imdb_id", ""), p.get("episode_num", ""))
        elif a == "tpb_search":
            search_tpb_menu(p.get("query", ""), p.get("browse_tmdb", ""), p.get("browse_season", ""))
        elif a == "tpb_play_movie":
            tpb_play_movie(p.get("title", ""), p.get("year", ""))
        elif a == "tpb_play_episode":
            tpb_play_episode(p.get("show_title", ""), p.get("season", ""), p.get("episode", ""))
        elif a == "fight_category":
            fight_category(p.get("cat_slug", ""), int(p.get("page", "1")))
        elif a == "fight_post":
            fight_post(p.get("url", ""))
        elif a == "fight_play":
            fight_play(p.get("video_url", ""), p.get("title", ""))
        elif a == "fight_torrent_search":
            fight_torrent_search(p.get("title", ""))
        else:
            show_menu()
    except Exception as e:
        tb = traceback.format_exc()
        xbmc.log("[StreamLord] CRASH: %s\n%s" % (str(e), tb), xbmc.LOGFATAL)
        xbmcgui.Dialog().ok("StreamLord Error", str(e))
        xbmcplugin.endOfDirectory(HANDLE)

if __name__ == "__main__":
    main()
