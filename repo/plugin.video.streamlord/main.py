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
        li.setArt({"thumb": item["thumb"], "icon": "DefaultVideo.png"})
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
        li.setArt({"thumb": item["thumb"], "icon": "DefaultTVShows.png"})
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
        li.setArt({"thumb": item["thumb"], "icon": "DefaultVideo.png"})
        action = "tvshow_detail" if item["type"] == "tvshow" else "movie_detail"
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action=action, slug=item["slug"], link=item["link"]), li, isFolder=True)
    max_page = extract_pagination(html)
    if page < max_page and page < 50:
        li = xbmcgui.ListItem("[B]Next Page >[/B]")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="genre", genre=genre, page=page+1), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def get_embed_url(mid):
    # Try multiple server selectors
    for l_val in [2, 1, 3]:
        url = "%s/embed/get?action=movie_embed&mid=%s&l=%s" % (BASE, mid, l_val)
        result = fetch_json(url)
        if result:
            for key in sorted(result.keys()):
                val = result[key]
                if isinstance(val, str) and ("http" in val or "//" in val) and "/embed/" in val:
                    return val
    return None

def get_embed_url_by_imdb(imdb_id, is_tv=False):
    """Return list of candidate embed URLs from alternative sources using IMDB ID"""
    tmpls = []
    if is_tv:
        tmpls = [
            "https://vidsrc.to/embed/tv/%s",
            "https://www.2embed.cc/embedtv/%s",
        ]
    else:
        tmpls = [
            "https://vidsrc.to/embed/movie/%s",
            "https://www.2embed.cc/embed/%s",
        ]
    candidates = []
    for tmpl in tmpls:
        url = tmpl % imdb_id
        raw = fetch_raw(url, ref="https://streamlord.to")
        if raw:
            html = raw.decode("utf-8", errors="replace")
            if re.search(r'(iframe|video|source|m3u8|player.*file)', html, re.IGNORECASE):
                candidates.append(url)
    return candidates

def get_episode_embed_url(eid):
    for l_val in [2, 1, 3]:
        url = "%s/embed/get?action=episode_embed&eid=%s&l=%s" % (BASE, eid, l_val)
        result = fetch_json(url)
        if result:
            for key in sorted(result.keys()):
                val = result[key]
                if isinstance(val, str) and ("http" in val or "//" in val) and "/embed/" in val:
                    return val
    return None

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
    if not imdb_id and mid:
        embed_url = get_embed_url(mid)
        if embed_url:
            imdb_m = re.search(r'imdb=tt(\d+)', embed_url)
            if imdb_m:
                imdb_id = "tt" + imdb_m.group(1)
    label = title
    if year:
        label += " [%s]" % year
    if rating:
        label += " [IMDb: %s]" % rating
    li = xbmcgui.ListItem(label=label)
    li.setInfo("video", {"title": title, "plot": desc, "year": year, "genre": ", ".join(genres[:5])})
    li.setArt({"thumb": thumb, "icon": "DefaultVideo.png"})
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
    if not imdb_id:
        embed_m = re.search(r'id="episode-(\d+)"', html)
        eid = embed_m.group(1) if embed_m else ""
        if eid:
            embed_url = get_episode_embed_url(eid)
            if embed_url:
                imdb_m = re.search(r'imdb=tt(\d+)', embed_url)
                if imdb_m:
                    imdb_id = "tt" + imdb_m.group(1)
    seasons = re.findall(r'id="season(\d+)"', html)
    for season in seasons:
        label = "Season %s" % season
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": "%s - Season %s" % (title, season)})
        li.setArt({"thumb": thumb, "icon": "DefaultTVShows.png"})
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
    episodes = re.findall(r'<a href="(/tvshow/[^"]+/episode-(\d+))"[^>]*>(.*?)</a>', content, re.DOTALL)
    for ep_link, ep_id, ep_name in episodes:
        ep_name = re.sub(r'<[^>]+>', '', ep_name).strip()
        ep_num_m = re.search(r'(\d+)', ep_name)
        episode_num = ep_num_m.group(1) if ep_num_m else ep_id
        li = xbmcgui.ListItem(label=ep_name)
        li.setInfo("video", {"title": ep_name, "tvshowtitle": show_title, "episode": int(episode_num)})
        li.setArt({"thumb": thumb, "icon": "DefaultTVShows.png"})
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
        return data.get("seasons", []), data.get("name", ""), data.get("poster_path", "")
    except:
        return [], "", ""

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
    for r in results:
        mtype = r.get("media_type", "")
        if mtype not in ("movie", "tv"):
            continue
        title = r.get("title") or r.get("name", "Unknown")
        year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        tid = r.get("id")
        thumb = _tmdb_img(r.get("poster_path", ""))
        items.append((tid, title, year, mtype, thumb))

    if not items:
        xbmcgui.Dialog().notification("StreamLord", "No results found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for tid, title, year, mtype, thumb in items:
        label = title
        if year:
            label += " [%s]" % year
        label += " (%s)" % mtype.upper()
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": title, "year": year})
        li.setArt({"thumb": thumb, "icon": "DefaultVideo.png" if mtype == "movie" else "DefaultTVShows.png"})
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
    seasons, show_name, poster = _tmdb_tv(tmdb_id)
    if not seasons:
        xbmcgui.Dialog().notification("StreamLord", "No seasons found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    thumb = _tmdb_img(poster)
    for s in seasons:
        snum = s.get("season_number", 0)
        if snum == 0:
            continue
        eps = s.get("episode_count", 0)
        label = "Season %d [%d episodes]" % (snum, eps)
        li = xbmcgui.ListItem(label=label)
        li.setArt({"thumb": thumb, "icon": "DefaultTVShows.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search_streamlord", browse_tmdb=tmdb_id,
            browse_season=str(snum)), li, isFolder=True)
    li = xbmcgui.ListItem("[B]New Search[/B]")
    li.setArt({"icon": "DefaultSearch.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search_streamlord"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _sl_browse_episodes(tmdb_id, season_num):
    episodes = _tmdb_episodes(tmdb_id, season_num)
    _, show_name, _ = _tmdb_tv(tmdb_id)
    if not episodes:
        xbmcgui.Dialog().notification("StreamLord", "No episodes found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    for ep in episodes:
        epnum = ep.get("episode_number", 0)
        epname = ep.get("name", "Episode %d" % epnum)
        label = "S%02dE%02d - %s" % (int(season_num), epnum, epname)
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": epname, "tvshowtitle": show_name})
        li.setArt({"icon": "DefaultTVShows.png"})
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
    for r in results:
        mtype = r.get("media_type", "")
        if mtype not in ("movie", "tv"):
            continue
        title = r.get("title") or r.get("name", "Unknown")
        year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        tid = r.get("id")
        thumb = _tmdb_img(r.get("poster_path", ""))
        items.append((tid, title, year, mtype, thumb))

    if not items:
        xbmcgui.Dialog().notification("StreamLord", "No results found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for tid, title, year, mtype, thumb in items:
        label = title
        if year:
            label += " [%s]" % year
        label += " (%s)" % mtype.upper()
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": title, "year": year})
        li.setArt({"thumb": thumb, "icon": "DefaultVideo.png" if mtype == "movie" else "DefaultTVShows.png"})
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
    seasons, show_name, poster = _tmdb_tv(tmdb_id)
    if not seasons:
        xbmcgui.Dialog().notification("StreamLord", "No seasons found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    thumb = _tmdb_img(poster)
    for s in seasons:
        snum = s.get("season_number", 0)
        if snum == 0:
            continue
        eps = s.get("episode_count", 0)
        label = "Season %d [%d episodes]" % (snum, eps)
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": "%s - S%d" % (show_name, snum)})
        li.setArt({"thumb": thumb, "icon": "DefaultTVShows.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search", browse_tmdb=tmdb_id,
            browse_season=str(snum)), li, isFolder=True)
    li = xbmcgui.ListItem("[B]New Search[/B]")
    li.setArt({"icon": "DefaultSearch.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _browse_episodes(tmdb_id, season_num):
    episodes = _tmdb_episodes(tmdb_id, season_num)
    _, show_name, _ = _tmdb_tv(tmdb_id)
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

    for ep in episodes:
        epnum = ep.get("episode_number", 0)
        epname = ep.get("name", "Episode %d" % epnum)
        label = "S%02dE%02d - %s" % (int(season_num), epnum, epname)
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": epname, "season": int(season_num), "episode": epnum,
                             "tvshowtitle": show_name})
        li.setArt({"icon": "DefaultTVShows.png"})
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

def _tr(method, path, params=None):
    url = "http://127.0.0.1:61235" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))

def rd_unrestrict(magnet, rd_token, prog=None):
    """Use Real-Debrid API to convert magnet to direct stream URL."""
    import re, hashlib
    try:
        def _rd_get(path, token):
            url = "https://api.real-debrid.com/rest/1.0/" + path
            req = urllib.request.Request(url,
                                         headers={"Authorization": "Bearer " + token,
                                                  "User-Agent": "Kodi/21"})
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    return json.loads(r.read().decode("utf-8", errors="replace"))
            except urllib.error.HTTPError as e:
                xbmc.log("[StreamLord] RD GET %s = %d %s" % (path, e.code, str(e)[:100]), xbmc.LOGERROR)
                raise
        def _rd_post(path, data, token):
            url = "https://api.real-debrid.com/rest/1.0/" + path
            body = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(url, data=body,
                                         headers={"Authorization": "Bearer " + token,
                                                  "User-Agent": "Kodi/21",
                                                  "Content-Type": "application/x-www-form-urlencoded"})
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    return json.loads(r.read().decode("utf-8", errors="replace"))
            except urllib.error.HTTPError as e:
                xbmc.log("[StreamLord] RD POST %s = %d %s" % (path, e.code, str(e)[:100]), xbmc.LOGERROR)
                raise

        m = re.search(r"btih:([a-fA-F0-9]{40})", magnet)
        if not m:
            return None
        info_hash = m.group(1).lower()

        # Check instant availability first
        if prog:
            prog.update(0, "Checking RD cache...")
        avail = _rd_get("torrents/instantAvailability/%s" % info_hash, rd_token)
        if avail and info_hash in avail:
            variants = avail[info_hash].get("rd", [])
            if variants:
                for v in variants:
                    for fid, finfo in v.items():
                        dl = _rd_post("unrestrict/link",
                                      {"link": "https://real-debrid.com/d/%s/%s" % (info_hash, finfo.get("filename", fid))},
                                      rd_token)
                        if dl and dl.get("download"):
                            if prog: prog.update(100, "Cached! Playing...")
                            return dl["download"]
                        break
                    break

        # Not cached — add magnet and wait
        if prog:
            prog.update(5, "Adding to RD...")
        add = _rd_post("torrents/addMagnet", {"magnet": magnet}, rd_token)
        if not add or "id" not in add:
            raise Exception("RD addMagnet failed: %s" % str(add)[:100])
        tid = add["id"]

        for attempt in range(120):
            xbmc.sleep(3000)
            if prog and prog.iscanceled():
                return None
            info = _rd_get("torrents/info/%s" % tid, rd_token)
            if not info:
                continue
            st = info.get("status", "")
            pct = info.get("progress", 0)
            if prog:
                prog.update(int(pct), "RD: %s %d%%" % (st, pct))
            if st == "waiting_files_selection":
                files = info.get("files", [])
                ids = ",".join(str(f["id"]) for f in files
                              if any(f.get("path","").lower().endswith(e)
                                     for e in (".mp4",".mkv",".avi",".ts")))
                if not ids and files:
                    ids = str(files[0]["id"])
                if ids:
                    _rd_post("torrents/selectFiles/%s" % tid, {"files": ids}, rd_token)
            elif st == "downloaded":
                for link in info.get("links", []):
                    dl = _rd_post("unrestrict/link", {"link": link}, rd_token)
                    if dl and dl.get("download"):
                        if prog: prog.update(100, "Playing!")
                        return dl["download"]
                return None
            elif st in ("magnet_error", "error", "virus", "dead"):
                return None
        return None
    except Exception as e:
        xbmcgui.Dialog().ok("RD Error", str(e)[:200])
        xbmc.log("[StreamLord] RD unrestrict error: %s" % str(e), xbmc.LOGERROR)
        return None

def play_via_LordPlayer(magnet, title):
    try:
        if not magnet.startswith("magnet:"):
            return False
        if TRACKERS not in magnet:
            magnet += TRACKERS

        rd_token = _get_rd_token()
        # Always use RD if token is set (for Xbox)
        if rd_token:
            if not rd_token:
                xbmcgui.Dialog().ok("StreamLord", "RD token not set. Add it in StreamLord settings.")
                return False
            xbmc.log("[StreamLord] Using RD for Xbox playback", xbmc.LOGINFO)
            prog = xbmcgui.DialogProgress()
            prog.create("StreamLord RD", "Checking Real-Debrid cache...")
            url = rd_unrestrict(magnet, rd_token, prog)
            prog.close()
            if url:
                li = xbmcgui.ListItem(path=url, label=title)
                li.setProperty("IsPlayable", "true")
                xbmcplugin.setResolvedUrl(HANDLE, True, li)
                return True
            xbmcgui.Dialog().ok("StreamLord", "Torrent not streamable via RD. May not be cached.")
            return False
        else:
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

def fetch_raw(url, ref=None):
    try:
        hdrs = {"User-Agent": USER_AGENT}
        if ref:
            hdrs["Referer"] = ref
        req = urllib.request.Request(url, headers=hdrs)
        with opener.open(req, timeout=15) as resp:
            return resp.read()
    except:
        return b""

def resolve_vidsrc(html):
    video_url = None
    patterns = [
        r'file:\s*["\']([^"\']+)["\']',
        r'link:\s*["\']([^"\']+)["\']',
        r'src:\s*["\']([^"\']+\.(?:mp4|m3u8)[^"\']*)["\']',
        r'<source[^>]*src=["\']([^"\']+)["\']',
        r'<video[^>]*src=["\']([^"\']+)["\']',
        r'(https?://[^"\']*\/videos\/[^"\']+)',
        r'(https?://[^"\']+\.(?:mp4|m3u8)[^"\']*)',
        r'"url":"([^"]+\.(?:mp4|m3u8)[^"]+)"',
        r'"videoUrl":"([^"]+)"',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            video_url = m.group(1).replace("\\/", "/").replace("&amp;", "&")
            if video_url.startswith("//"):
                video_url = "https:" + video_url
            break
    return video_url

def resolve_embed_chain(url):
    final_url = url
    ref = BASE
    for _ in range(5):
        raw = fetch_raw(url, ref=ref)
        if not raw:
            return None, final_url
        html = raw.decode("utf-8", errors="replace")
        if not html:
            return None, final_url
        # Try to find direct video URL on this page before following iframes
        vurl = resolve_vidsrc(html)
        if vurl:
            xbmc.log("[StreamLord] Found video URL in chain at %s: %s" % (url[:60], vurl[:100]), xbmc.LOGINFO)
            return html, url
        # Try data-src first (used by 2embed, embed.su, etc.)
        m = re.search(r'<iframe[^>]*data-src=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE)
        if m:
            ref = url
            url = m.group(1).replace("&amp;", "&")
            final_url = url
            continue
        m = re.search(r'<iframe[^>]*src=["\'](//[^"\']+)["\']', html, re.IGNORECASE)
        if m:
            ref = url
            url = "https:" + m.group(1)
            final_url = url
            continue
        m = re.search(r'<iframe[^>]*src=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE)
        if m:
            ref = url
            url = m.group(1).replace("&amp;", "&")
            final_url = url
            continue
        return html, final_url
    return None, final_url

def resolve_with_resolveurl(url, title):
    import resolveurl
    for u in [url, url + "$$" + BASE]:
        hmf = resolveurl.HostedMediaFile(u)
        if hmf:
            try:
                resolved = hmf.resolve()
            except:
                continue
            if resolved:
                xbmc.log("[StreamLord] resolveurl resolved: %s" % str(resolved)[:100], xbmc.LOGINFO)
                rurl = resolved if isinstance(resolved, str) else resolved.get('url', '')
                if rurl:
                    if "ok.ru" in url and "Referer" not in rurl:
                        sep = "&" if "|" in rurl else "|"
                        rurl += "%sReferer=https://www.ok.ru/" % sep
                        xbmc.log("[StreamLord] Added Referer for OK.ru stream", xbmc.LOGINFO)
                    li = xbmcgui.ListItem(path=rurl, label=title)
                    li.setProperty("IsPlayable", "true")
                    xbmcplugin.setResolvedUrl(HANDLE, True, li)
                    return

def play_movie(mid, title, watch_link="", imdb_id="", year=""):
    all_sources = []
    embed_source = None

    if mid:
        embed_url = get_embed_url(mid)
        if embed_url:
            embed_source = embed_url

    if not embed_source and imdb_id:
        candidates = get_embed_url_by_imdb(imdb_id, is_tv=False)
        if candidates:
            embed_source = candidates[0]

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
                        all_sources.append(('torrent', q, seed, s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), s.get('debrid', False)))
        except Exception as e:
            xbmc.log("[StreamLord] Movie scraper error: %s" % str(e), xbmc.LOGWARNING)

    if not all_sources and title:
        xbmc.log("[StreamLord] CocoScrapers returned nothing, trying TPB for %s" % title, xbmc.LOGINFO)
        tpb = search_tpb(title + (" " + year if year else ""))
        for s in tpb:
            all_sources.append(('torrent', s.get('quality', 'SD'), s.get('seeders', 0), s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), s.get('debrid', False)))

    deduped = []
    seen = set()
    for s in all_sources:
        h = s[4]
        if h and h not in seen:
            seen.add(h)
            deduped.append(s)

    deduped.sort(key=lambda s: (QUALITY_ORDER.get(s[1], 99), -(int(s[2]) if s[2] else 0)))

    # Batch-check RD cache
    rd_cached = set()
    rd_token = _get_rd_token()
    if rd_token:
        hashes = [s[4] for s in deduped if s[4] and len(s[4]) == 40]
        if hashes:
            try:
                hash_list = "/" + "/".join(hashes[:50])
                req = urllib.request.Request(
                    "https://api.real-debrid.com/rest/1.0/torrents/instantAvailability" + hash_list,
                    headers={"Authorization": "Bearer " + rd_token, "User-Agent": "Kodi/21"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    avail = json.loads(r.read())
                for h in hashes:
                    if h in avail and avail[h].get("rd"):
                        rd_cached.add(h)
            except:
                pass

    items = []
    for s in deduped:
        name = s[6] if len(s) > 6 else ""
        label = "%s %s" % (s[1], s[5]) if s[5] else s[1]
        if s[2]:
            label += " [S:%s]" % s[2]
        if s[4] in rd_cached:
            label += " *** RD CACHED ***"
        elif len(s) > 7 and s[7]:
            label += " [RD]"
        if name:
            label = "%s - %s" % (name[:60], label)
        items.append(label)

    embed_idx = -1
    if embed_source:
        embed_idx = len(items)
        items.append("[B]StreamLord Web[/B]")

    if len(items) == 0:
        if embed_source and play_embed_video(embed_source, title):
            return
        if imdb_id:
            for alt_url in get_embed_url_by_imdb(imdb_id, is_tv=False):
                if play_embed_video(alt_url, title):
                    return
        xbmcplugin.endOfDirectory(HANDLE)
        xbmcgui.Dialog().ok("StreamLord", "No sources found for\n%s" % title)
        return

    if len(items) == 1 and embed_idx == -1:
        chosen_idx = 0
    else:
        chosen_idx = xbmcgui.Dialog().select("Select source - %s" % title, items)

    if chosen_idx < 0:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    if chosen_idx == embed_idx:
        if play_embed_video(embed_source, title):
            return
        if imdb_id:
            for alt_url in get_embed_url_by_imdb(imdb_id, is_tv=False):
                if play_embed_video(alt_url, title):
                    return
        xbmcgui.Dialog().ok("StreamLord", "Embed source not playable.\nTry opening in browser:\n%s" % embed_source)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    chosen = deduped[chosen_idx]
    xbmc.log("[StreamLord] Trying %s %s" % (chosen[1], chosen[3][:50]), xbmc.LOGINFO)
    if chosen[2] == 0 and not (len(chosen) > 7 and chosen[7]) and not xbmcgui.Dialog().yesno("StreamLord", "0 seeders - may not play.\nTry anyway?"):
        xbmcplugin.endOfDirectory(HANDLE)
        return
    action = xbmcgui.Dialog().select("Choose action", ["Play", "Download"])
    if action == 0:
        if play_via_LordPlayer(chosen[3], title):
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

    # Build patterns to filter for exact episode
    s_int = int(season_num) if season_num.isdigit() else 0
    e_int = int(ep_num) if ep_num.isdigit() else 0
    exact_pattern = re.compile(r'[Ss]%02d[Ee]%02d|[Ss]%d[Ee]%02d' % (s_int, e_int, s_int, e_int), re.IGNORECASE) if s_int else re.compile(re.escape("S%sE%s" % (season_num, ep_num)), re.IGNORECASE)

    all_sources = []
    embed_source = None

    if eid:
        embed_url = get_episode_embed_url(eid)
        if embed_url:
            embed_source = embed_url

    if not embed_source and show_imdb_id:
        embed_url = get_embed_url_by_imdb(show_imdb_id, is_tv=True)
        if embed_url:
            embed_source = embed_url

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
                        all_sources.append(('torrent', q, seed, s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), s.get('debrid', False)))
        except Exception as e:
            xbmc.log("[StreamLord] Episode scraper error: %s" % str(e), xbmc.LOGWARNING)

    if not all_sources and show_title:
        q = "%s S%02dE%02d" % (show_title, s_int, e_int)
        xbmc.log("[StreamLord] CocoScrapers returned nothing, trying TPB for %s" % q, xbmc.LOGINFO)
        tpb = search_tpb(q)
        for s in tpb:
            name = s.get('name', '')
            # Filter TPB results to match exact episode pattern
            if exact_pattern.search(name) or len(tpb) <= 1:
                all_sources.append(('torrent', s.get('quality', 'SD'), s.get('seeders', 0), s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), s.get('debrid', False)))

    deduped = []
    seen = set()
    for s in all_sources:
        h = s[4]
        if h and h not in seen:
            seen.add(h)
            deduped.append(s)

    deduped.sort(key=lambda s: (QUALITY_ORDER.get(s[1], 99), -(int(s[2]) if s[2] else 0)))

    # Batch-check RD cache
    rd_cached = set()
    rd_token = _get_rd_token()
    if rd_token:
        hashes = [s[4] for s in deduped if s[4] and len(s[4]) == 40]
        if hashes:
            try:
                hash_list = "/" + "/".join(hashes[:50])
                req = urllib.request.Request(
                    "https://api.real-debrid.com/rest/1.0/torrents/instantAvailability" + hash_list,
                    headers={"Authorization": "Bearer " + rd_token, "User-Agent": "Kodi/21"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    avail = json.loads(r.read())
                for h in hashes:
                    if h in avail and avail[h].get("rd"):
                        rd_cached.add(h)
            except:
                pass

    items = []
    for s in deduped:
        name = s[6] if len(s) > 6 else ""
        label = "%s %s" % (s[1], s[5]) if s[5] else s[1]
        if s[2]:
            label += " [S:%s]" % s[2]
        if s[4] in rd_cached:
            label += " *** RD CACHED ***"
        elif len(s) > 7 and s[7]:
            label += " [RD]"
        if name:
            label = "%s - %s" % (name[:60], label)
        items.append(label)

    embed_idx = -1
    if embed_source:
        embed_idx = len(items)
        items.append("[B]StreamLord Web[/B]")

    if len(items) == 0:
        if embed_source and play_embed_video(embed_source, full_title):
            return
        if show_imdb_id:
            for alt_url in get_embed_url_by_imdb(show_imdb_id, is_tv=True):
                if play_embed_video(alt_url, full_title):
                    return
        li = xbmcgui.ListItem(path=link)
        xbmcplugin.setResolvedUrl(HANDLE, False, li)
        xbmcgui.Dialog().ok("StreamLord", "No sources found for\n%s" % full_title)
        return

    if len(items) == 1 and embed_idx == -1:
        chosen_idx = 0
    else:
        chosen_idx = xbmcgui.Dialog().select("Select source - %s" % full_title, items)

    if chosen_idx < 0:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    if chosen_idx == embed_idx:
        if play_embed_video(embed_source, full_title):
            return
        if show_imdb_id:
            for alt_url in get_embed_url_by_imdb(show_imdb_id, is_tv=True):
                if play_embed_video(alt_url, full_title):
                    return
        xbmcgui.Dialog().ok("StreamLord", "Embed source not playable.\nTry opening in browser:\n%s" % embed_source)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    chosen = deduped[chosen_idx]
    xbmc.log("[StreamLord] Trying %s %s" % (chosen[1], chosen[3][:50]), xbmc.LOGINFO)
    if chosen[2] == 0 and not (len(chosen) > 7 and chosen[7]) and not xbmcgui.Dialog().yesno("StreamLord", "0 seeders - may not play.\nTry anyway?"):
        xbmcplugin.endOfDirectory(HANDLE)
        return
    action = xbmcgui.Dialog().select("Choose action", ["Play", "Download"])
    if action == 0:
        if play_via_LordPlayer(chosen[3], full_title):
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
    d = xbmcgui.Dialog()
    if d.yesno("StreamLord v1.0.5", "Authorize Real-Debrid easily?", "", "Use your phone to link RD - no typing!"):
        auth_rd_device()
    else:
        xbmcaddon.Addon('plugin.video.streamlord').openSettings()
    xbmcplugin.endOfDirectory(HANDLE, updateListing=True)

def auth_rd_device():
    import time, xbmcaddon
    client_id = "X245A4XAIBGVM"
    try:
        url = "https://api.real-debrid.com/oauth/v2/device/code?client_id=%s&new_credentials=yes" % client_id
        req = urllib.request.Request(url, headers={"User-Agent": "Kodi/21"})
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
    except Exception as e:
        xbmcgui.Dialog().ok("Error", "Could not connect to RD. " + str(e))
        return

    device_code = result.get("device_code", "")
    user_code = result.get("user_code", "")
    direct_url = result.get("direct_verification_url", "https://real-debrid.com/device")

    xbmcgui.Dialog().ok("Authorize Real-Debrid",
                         "Open: %s\nEnter code: %s" % (direct_url, user_code))

    for attempt in range(60):
        xbmc.sleep(2000)
        try:
            poll_url = "https://api.real-debrid.com/oauth/v2/device/credentials?client_id=%s&code=%s" % (client_id, device_code)
            req = urllib.request.Request(poll_url, headers={"User-Agent": "Kodi/21"})
            with urllib.request.urlopen(req, timeout=15) as r:
                creds = json.loads(r.read())
            if creds.get("client_secret"):
                api_token = creds["client_secret"]
                xbmcaddon.Addon('plugin.video.streamlord').setSetting('rd_token', api_token)
                try:
                    cache = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.streamlord/rd.txt")
                    os.makedirs(os.path.dirname(cache), exist_ok=True)
                    with open(cache, "w") as f:
                        f.write(api_token)
                except:
                    pass
                xbmcgui.Dialog().ok("Success!", "Real-Debrid linked!")
                return
        except:
            pass
    xbmcgui.Dialog().ok("Timeout", "Authorization timed out. Try again.")
    xbmcplugin.endOfDirectory(HANDLE, updateListing=True)

def _exchange_rd_token(client_id, client_secret):
    return None

def _rd_token():
    try:
        import xbmcaddon
        return xbmcaddon.Addon('plugin.video.streamlord').getSetting('rd_token').strip()
    except:
        return ""
    return None
    try:
        import xbmcaddon
        return xbmcaddon.Addon('plugin.video.streamlord').getSetting('rd_token').strip()
    except:
        return ""

def _get_rd_token():
    # Check settings first, then file backup, try alt token
    token = _rd_token()
    if token:
        return token
    cache = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.streamlord/rd.txt")
    try:
        with open(cache) as f:
            token = f.read().strip()
            if token:
                return token
    except:
        pass
    # Try alt token from OAuth
    try:
        import xbmcaddon
        alt = xbmcaddon.Addon('plugin.video.streamlord').getSetting('rd_token_alt').strip()
        if alt:
            return alt
    except:
        pass
    return ""

def handle_download(magnet, title):
    dest = xbmcgui.Dialog().browse(0, "Choose download folder", "files", "", False, True, _get_download_path())
    if not dest:
        xbmc.log("[StreamLord] Download cancelled by user", xbmc.LOGINFO)
        return
    xbmc.log("[StreamLord] Download selected: %s" % dest, xbmc.LOGINFO)
    choices = ["Download via LordPlayer"]
    if _rd_token():
        choices.append("Download via Real-Debrid")
    pick = xbmcgui.Dialog().select("Download method", choices)
    if pick == 0:
        download_via_LordPlayer(magnet, title, dest)
    elif pick == 1 and _rd_token():
        download_via_rd(magnet, title, dest)

def download_via_rd(magnet, title, dest):
    try:
        import threading
        token = _rd_token()
        if not token:
            xbmcgui.Dialog().ok("StreamLord", "Real-Debrid not configured.\nSet RD token in Settings.")
            return
        if TRACKERS not in magnet:
            magnet += TRACKERS
        hdr = {"Authorization": "Bearer " + token, "User-Agent": USER_AGENT}
        req = urllib.request.Request("https://api.real-debrid.com/rest/1.0/torrents/addMagnet",
                                     data=urllib.parse.urlencode({"magnet": magnet}).encode(),
                                     headers=hdr)
        with urllib.request.urlopen(req, timeout=30) as r:
            rd = json.loads(r.read())
        tid = rd["id"]
        xbmc.log("[StreamLord] RD torrent added: %s" % tid, xbmc.LOGINFO)
        for _ in range(90):
            req = urllib.request.Request("https://api.real-debrid.com/rest/1.0/torrents/info/%s" % tid, headers=hdr)
            with urllib.request.urlopen(req, timeout=15) as r:
                info = json.loads(r.read())
            status = info.get("status")
            if status == "magnet_conversion":
                xbmc.sleep(2000)
                continue
            if status in ("downloading", "downloaded"):
                break
            if status == "waiting_files_selection":
                req = urllib.request.Request("https://api.real-debrid.com/rest/1.0/torrents/selectFiles/%s" % tid,
                                             data=urllib.parse.urlencode({"files": "all"}).encode(),
                                             headers=hdr)
                urllib.request.urlopen(req, timeout=15)
                continue
            xbmc.sleep(2000)
        prog = xbmcgui.DialogProgress()
        prog.create("StreamLord - RD Processing")
        while not prog.iscanceled():
            req = urllib.request.Request("https://api.real-debrid.com/rest/1.0/torrents/info/%s" % tid, headers=hdr)
            with urllib.request.urlopen(req, timeout=15) as r:
                info = json.loads(r.read())
            cur = info.get("progress", 0)
            prog.update(int(cur), "%d%%" % int(cur))
            if info.get("status") == "downloaded" or cur >= 100:
                break
            xbmc.sleep(3000)
        prog.close()
        links = [l for l in info.get("links", [])]
        if not links:
            xbmcgui.Dialog().ok("StreamLord", "No files from RD")
            return
        cancel = threading.Event()
        monitor = xbmc.Monitor()
        for link in links:
            req = urllib.request.Request("https://api.real-debrid.com/rest/1.0/unrestrict/link",
                                         data=urllib.parse.urlencode({"link": link}).encode(),
                                         headers=hdr)
            with urllib.request.urlopen(req, timeout=30) as r:
                ul = json.loads(r.read())
            dl_url = ul.get("download")
            filename = ul.get("filename", "video.mp4")
            if not dl_url:
                continue
            out = os.path.join(dest, filename)
            xbmc.log("[StreamLord] RD downloading: %s -> %s" % (dl_url[:80], out), xbmc.LOGINFO)
            dl_prog = xbmcgui.DialogProgress()
            dl_prog.create("StreamLord - Saving %s" % filename)
            result = {"ok": False, "err": ""}
            def run_dl():
                try:
                    dl_req = urllib.request.Request(dl_url, headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(dl_req, timeout=300) as src:
                        total = int(src.headers.get("Content-Length", 0))
                        wrote = 0
                        with open(out, "wb") as f:
                            while not cancel.is_set():
                                chunk = src.read(65536)
                                if not chunk:
                                    break
                                f.write(chunk)
                                wrote += len(chunk)
                                if total:
                                    pct = int(wrote / total * 100)
                                    dl_prog.update(pct, "%d / %d MB" % (wrote // 1048576, total // 1048576))
                    result["ok"] = True
                except Exception as ex:
                    result["err"] = str(ex)
            t = threading.Thread(target=run_dl, daemon=True)
            t.start()
            while t.is_alive():
                if dl_prog.iscanceled():
                    cancel.set()
                if monitor.waitForAbort(1):
                    break
            dl_prog.close()
            if result["err"]:
                xbmcgui.Dialog().ok("RD Download Error", result["err"])
                return
            if not result["ok"]:
                xbmcgui.Dialog().notification("Download Cancelled", filename, xbmcgui.NOTIFICATION_WARNING, 3000)
                return
        xbmcgui.Dialog().notification("Download Complete", filename, xbmcgui.NOTIFICATION_INFO, 5000)
    except urllib.error.HTTPError as e:
        msg = str(e)
        if e.code == 451:
            msg = "Torrent blocked by Real-Debrid (copyright).\nTry a different source."
        xbmc.log("[StreamLord] RD download error: %s" % msg, xbmc.LOGERROR)
        xbmcgui.Dialog().ok("RD Download Error", msg)
    except Exception as e:
        import traceback
        xbmc.log("[StreamLord] RD download error: %s\n%s" % (str(e), traceback.format_exc()), xbmc.LOGERROR)
        xbmcgui.Dialog().ok("RD Download Error", str(e))

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
    for r in results:
        mtype = r.get("media_type", "")
        if mtype not in ("movie", "tv"):
            continue
        title = r.get("title") or r.get("name", "Unknown")
        year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        tid = r.get("id")
        thumb = _tmdb_img(r.get("poster_path", ""))
        items.append((tid, title, year, mtype, thumb))

    if not items:
        xbmcgui.Dialog().notification("StreamLord", "No results found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for tid, title, year, mtype, thumb in items:
        label = title
        if year:
            label += " [%s]" % year
        label += " (%s)" % mtype.upper()
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": title, "year": year})
        li.setArt({"thumb": thumb, "icon": "DefaultVideo.png" if mtype == "movie" else "DefaultTVShows.png"})
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
    seasons, show_name, poster = _tmdb_tv(tmdb_id)
    if not seasons:
        xbmcgui.Dialog().notification("StreamLord", "No seasons found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    thumb = _tmdb_img(poster)
    for s in seasons:
        snum = s.get("season_number", 0)
        if snum == 0:
            continue
        eps = s.get("episode_count", 0)
        label = "Season %d [%d episodes]" % (snum, eps)
        li = xbmcgui.ListItem(label=label)
        li.setArt({"thumb": thumb, "icon": "DefaultTVShows.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="tpb_search", browse_tmdb=tmdb_id,
            browse_season=str(snum)), li, isFolder=True)
    li = xbmcgui.ListItem("[B]New Search[/B]")
    li.setArt({"icon": "DefaultSearch.png"})
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="tpb_search"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _tpb_browse_episodes(tmdb_id, season_num):
    episodes = _tmdb_episodes(tmdb_id, season_num)
    _, show_name, _ = _tmdb_tv(tmdb_id)
    if not episodes:
        xbmcgui.Dialog().notification("StreamLord", "No episodes found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    for ep in episodes:
        epnum = ep.get("episode_number", 0)
        epname = ep.get("name", "Episode %d" % epnum)
        label = "S%02dE%02d - %s" % (int(season_num), epnum, epname)
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": epname, "tvshowtitle": show_name})
        li.setArt({"icon": "DefaultTVShows.png"})
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
    action = xbmcgui.Dialog().select("Choose action", ["Play", "Download"])
    if action == 0:
        play_via_LordPlayer(magnet, label)
    elif action == 1:
        handle_download(magnet, label)

def show_menu():
    items = [
        ("[B]Search All Torrents[/B]", "search", "DefaultSearch.png"),
        ("[B]TPB Search[/B]", "tpb_search", "DefaultSearch.png"),
        ("[B]Search StreamLord[/B]", "search_streamlord", "DefaultSearch.png"),
        ("[B]Hot Movies[/B]", "movies", "DefaultMovies.png"),
        ("[B]TV Series[/B]", "tvseries", "DefaultTVShows.png"),
        ("[B]Top IMDb[/B]", "top_imdb", "DefaultVideo.png"),
        ("[B]Genres[/B]", "genres", "DefaultVideo.png"),
        ("[B]LordPlayer[/B]", "lordplayer", "DefaultAddon.png"),
        ("[B]Authorize Real-Debrid[/B]", "rd_auth", "DefaultAddon.png"),
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
        li.setArt({"icon": "DefaultVideo.png"})
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
        li.setArt({"thumb": item["thumb"], "icon": "DefaultVideo.png"})
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
        li.setArt({"icon": "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="fight_category", cat_slug=slug), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def fight_category(cat_slug, page=1):
    import watchwrestling as ww
    posts, has_next = ww.list_category(cat_slug, page)
    for post in posts:
        li = xbmcgui.ListItem(label=post["title"])
        li.setArt({"thumb": post["thumb"], "icon": "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="fight_post", url=post["link"]), li, isFolder=True)
    if has_next:
        li = xbmcgui.ListItem("[B]Next Page >[/B]")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="fight_category", cat_slug=cat_slug, page=page+1), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def fight_post(url):
    import watchwrestling as ww
    detail = ww.get_post_detail(url)
    search_title = ww.clean_title(detail["title"])
    # Torrent search option (primary)
    li = xbmcgui.ListItem(label="[B]Search Torrents: %s[/B]" % search_title)
    li.setArt({"icon": "DefaultVideo.png"})
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
            li.setInfo("video", {"title": detail["title"], "plot": detail["desc"]})
            li.setArt({"thumb": detail["thumb"], "icon": "DefaultVideo.png"})
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
            all_sources.append(('torrent', q, seed, s.get('url', ''), s.get('hash', ''), s.get('size', ''), s.get('name', ''), s.get('debrid', False)))
    ss = sorted(all_sources, key=lambda s: (QUALITY_ORDER.get(s[1], 99), -(int(s[2]) if s[2] else 0)))
    slist = []
    for s in ss:
        name = s[6] if len(s) > 6 else ""
        short = name[:60] + ".." if len(name) > 62 else name
        lbl = "%s %s" % (s[1], s[5]) if s[5] else s[1]
        if s[2]:
            lbl += " [S:%s]" % s[2]
        if len(s) > 7 and s[7]:
            lbl += " [RD]"
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
        try:
            import resolveurl
            xbmc.log("[StreamLord] resolveurl imported OK", xbmc.LOGINFO)
            hmf = resolveurl.HostedMediaFile(resolved["url"])
            if hmf:
                r = hmf.resolve()
                if r:
                    rurl = r if isinstance(r, str) else r.get("url", "")
                    if rurl:
                        li = xbmcgui.ListItem(path=rurl, label=title)
                        li.setProperty("IsPlayable", "true")
                        xbmcplugin.setResolvedUrl(HANDLE, True, li)
                        return
        except Exception as e:
            xbmc.log("[StreamLord] resolveurl error: %s" % str(e), xbmc.LOGERROR)
        xbmcgui.Dialog().ok("StreamLord", "Could not resolve video.\nTry a different link on this post.")
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
        elif a == "rd_auth":
            auth_rd_device()
            xbmcplugin.endOfDirectory(HANDLE)
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
        else:
            show_menu()
    except Exception as e:
        tb = traceback.format_exc()
        xbmc.log("[StreamLord] CRASH: %s\n%s" % (str(e), tb), xbmc.LOGFATAL)
        xbmcgui.Dialog().ok("StreamLord Error", str(e))
        xbmcplugin.endOfDirectory(HANDLE)

if __name__ == "__main__":
    main()
