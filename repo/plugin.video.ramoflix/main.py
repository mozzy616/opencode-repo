# -*- coding: utf-8 -*-
import sys, re, json, urllib.parse, urllib.request
import xbmcgui, xbmcplugin, xbmc

HANDLE = int(sys.argv[1])
BASE = "https://ramoflix.net"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def get_url(**kw):
    return "{}?{}".format(sys.argv[0], urllib.parse.urlencode(kw))

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        xbmc.log("[RamoFlix] fetch error: %s" % str(e), xbmc.LOGERROR)
        return ""

def parse_params(p):
    d = {}
    if p.startswith("?"): p = p[1:]
    for pair in p.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            d[k] = urllib.parse.unquote_plus(v)
    return d

def list_categories():
    cats = [
        ("Movies", "/category/movies/"),
        ("TV Shows", "/category/tv-series/"),
        ("--- Genres ---", ""),
        ("Action", "/category/action/"),
        ("Adventure", "/category/adventure/"),
        ("Animation", "/category/animation/"),
        ("Comedy", "/category/comedy/"),
        ("Crime", "/category/crime/"),
        ("Documentary", "/category/documentary/"),
        ("Drama", "/category/drama/"),
        ("Family", "/category/family/"),
        ("Fantasy", "/category/fantasy/"),
        ("History", "/category/history/"),
        ("Horror", "/category/horror/"),
        ("Mystery", "/category/mystery/"),
        ("Romance", "/category/romance/"),
        ("Science Fiction", "/category/science-fiction/"),
        ("Thriller", "/category/thriller/"),
        ("War", "/category/war/"),
        ("Western", "/category/western/"),
        ("--- Search ---", ""),
        ("[B]Search[/B]", "search"),
    ]
    for label, path in cats:
        if not label:
            continue
        if path == "search":
            li = xbmcgui.ListItem(label)
            li.setArt({"icon": "DefaultAddonsSearch.png"})
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action="search"), li, isFolder=True)
        elif path:
            li = xbmcgui.ListItem(label)
            li.setArt({"icon": "DefaultVideo.png"})
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action="list", url=BASE + path, page="1"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def search():
    kb = xbmc.Keyboard("", "Search RamoFlix...")
    kb.doModal()
    if kb.isConfirmed() and kb.getText():
        q = kb.getText().strip()
        url = BASE + "/?s=" + urllib.parse.quote(q)
        list_posts(url)

def list_posts(url):
    url = urllib.parse.unquote(url)
    html = fetch(url)
    if not html:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    items = re.findall(r'<div id="post-(\d+)"[^>]*class="item[^"]*".*?<a href="([^"]*)"[^>]*>.*?<img[^>]*data-src="([^"]*)"[^>]*alt="([^"]*)".*?<a[^>]*>\4</a>', html, re.DOTALL)
    if not items:
        # Alternative pattern
        items = re.findall(r'<div id="post-(\d+)"[^>]*class="item[^"]*".*?<a href="([^"]*)"[^>]*>.*?<img[^>]*src="[^"]*" data-src="([^"]*)"[^>]*alt="([^"]*)".*?</a>.*?<a[^>]*>\4</a>', html, re.DOTALL)

    for pid, link, thumb, title in items:
        li = xbmcgui.ListItem(label=title)
        if thumb:
            li.setArt({"thumb": thumb, "poster": thumb})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="watch", url=link), li, isFolder=True)

    # Pagination
    next_m = re.search(r'<a class="[^"]*next[^"]*" href="([^"]*)"', html)
    if next_m:
        li = xbmcgui.ListItem("[B]Next Page >[/B]")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="list", url=next_m.group(1), page="0"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def watch(url):
    url = urllib.parse.unquote(url)
    html = fetch(url)
    if not html:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Extract Servers JS object
    servers_js = re.search(r'var Servers = ({.*?});', html, re.DOTALL)
    data = {}
    if servers_js:
        try:
            js = servers_js.group(1)
            # Parse key-value pairs: "key":"value"
            for m in re.finditer(r'"([^"]+)"\s*:\s*"([^"]*)"', js):
                data[m.group(1)] = m.group(2)
        except:
            pass

    # Get title and TMDB info
    title_m = re.search(r'<h1[^>]*>([^<]*)</h1>', html)
    title = title_m.group(1).strip() if title_m else "Unknown"
    year_m = re.search(r'\((\d{4})\)', title)
    year = year_m.group(1) if year_m else ""

    # Server definitions with URLs and names
    servers = []
    server_names = {
        "embedru": "Vidsrc",
        "vidlink": "Videasy",
        "superembed": "Vidfast",
        "vidsrc": "111movies",
        "vidsrc2": "Vidzee",
        "movieclub": "Vidsrc.wtf",
    }
    for key, name in server_names.items():
        if key in data and data[key]:
            url = data[key].replace("\\/", "/")
            servers.append((name, url))

    if not servers:
        xbmcgui.Dialog().notification("RamoFlix", "No servers found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    thumb = data.get("image", "")
    if thumb and not thumb.startswith("http"):
        thumb = "https:" + thumb
    thumb = thumb.replace("\\/", "/")

    for sname, surl in servers:
        label = "%s - %s" % (title, sname)
        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": title, "mediatype": "movie"})
        if year:
            li.setInfo("video", {"year": int(year)})
        if thumb:
            li.setArt({"thumb": thumb})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="play", url=surl, title=label), li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)

def play_video(url, title):
    url = urllib.parse.unquote(url)
    title = urllib.parse.unquote(title)

    # Try resolveurl
    try:
        import resolveurl
        resolved = resolveurl.resolve(url)
        if resolved:
            li = xbmcgui.ListItem(path=resolved, label=title)
            li.setProperty("IsPlayable", "true")
            if ".m3u8" in resolved:
                li.setProperty("inputstreamaddon", "inputstream.adaptive")
                li.setProperty("inputstream.adaptive.manifest_type", "hls")
            xbmcplugin.setResolvedUrl(HANDLE, True, li)
            return
    except:
        pass

    # Direct play
    li = xbmcgui.ListItem(path=url, label=title)
    li.setProperty("IsPlayable", "true")
    if ".m3u8" in url:
        li.setProperty("inputstreamaddon", "inputstream.adaptive")
        li.setProperty("inputstream.adaptive.manifest_type", "hls")
    xbmcplugin.setResolvedUrl(HANDLE, True, li)

def main():
    p = parse_params(sys.argv[2])
    a = p.get("action", "")
    if a == "list":
        list_posts(p.get("url", ""))
    elif a == "search":
        search()
    elif a == "watch":
        watch(p.get("url", ""))
    elif a == "play":
        play_video(p.get("url", ""), p.get("title", ""))
    else:
        list_categories()

if __name__ == "__main__":
    main()
