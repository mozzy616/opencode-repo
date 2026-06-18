import xbmcgui
import xbmcplugin
import xbmc
import xbmcvfs
import sys
import re
import json
import urllib.request
import urllib.parse
import http.cookiejar

HANDLE = int(sys.argv[1])
URL = sys.argv[0]
PARAMS = sys.argv[2]

BASE = "https://xxthots.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def get_url(**kwargs):
    return "{0}?{1}".format(URL, urllib.parse.urlencode(kwargs))

def parse_params(p):
    params = {}
    if p and p.startswith("?"):
        p = p[1:]
    if p:
        for part in p.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = urllib.parse.unquote(v)
    return params

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with opener.open(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        xbmc.log("[XXThots] fetch error: %s" % str(e), xbmc.LOGERROR)
        return ""

def show_menu():
    items = [
        ("[B]Latest Videos[/B]", "latest", ""),
        ("[B]Top Rated[/B]", "top_rated", ""),
        ("[B]Most Viewed[/B]", "most_viewed", ""),
        ("[B]Categories[/B]", "categories", ""),
        ("[B]Models[/B]", "models", ""),
        ("[B]Search[/B]", "search", ""),
    ]
    for label, action, icon in items:
        li = xbmcgui.ListItem(label)
        li.setArt({"icon": "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action=action), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def extract_videos(html):
    videos = []
    items = re.findall(r'<div class="thumb thumb_rel[^"]*"[^>]*>(.*?)</div>\s*</li>', html, re.DOTALL)
    if not items:
        items = re.findall(r'<div class="thumb[^"]*"[^>]*>.*?<a href="([^"]+)"[^>]*title="([^"]*)"', html, re.DOTALL)
        for url, title in items:
            videos.append({"url": url if url.startswith("http") else BASE + url, "title": title.strip()})
        return videos

    for item in items:
        link_m = re.search(r'<a href="([^"]+)"[^>]*title="([^"]*)"', item)
        if not link_m:
            continue
        link = link_m.group(1)
        title = link_m.group(2).strip()
        if not link.startswith("http"):
            link = BASE + link

        thumb = ""
        thumb_m = re.search(r'data-original="([^"]+)"', item)
        if thumb_m:
            thumb = thumb_m.group(1)

        quality = ""
        q_m = re.search(r'class="qualtiy">([^<]+)<', item)
        if q_m:
            quality = q_m.group(1)

        duration = ""
        d_m = re.search(r'class="time">([^<]+)<', item)
        if d_m:
            duration = d_m.group(1)

        views = ""
        v_m = re.search(r'icon-eye[^>]*>.*?</svg>\s*</i>\s*([\d.]+K?)', item, re.DOTALL)
        if v_m:
            views = v_m.group(1)

        rating = ""
        r_m = re.search(r'icon-like[^>]*>.*?</svg>\s*</i>\s*(\d+%)', item, re.DOTALL)
        if r_m:
            rating = r_m.group(1)

        videos.append({
            "url": link,
            "title": title,
            "thumb": thumb,
            "quality": quality,
            "duration": duration,
            "views": views,
            "rating": rating
        })
    return videos

def list_videos(url, page=1):
    if page > 1:
        sep = "&" if "?" in url else "?"
        url = url + "%spage%d" % (sep, page) if "latest-updates" not in url and "most-popular" not in url and "top-rated" not in url else url.rstrip("/") + "/page%d.html" % page

    html = fetch(url)
    if not html:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    videos = extract_videos(html)
    for v in videos:
        label = v["title"]
        if v.get("quality"):
            label = "[%s] %s" % (v["quality"], label)
        if v.get("duration"):
            label += " [%s]" % v["duration"]
        if v.get("views"):
            label += " | %s views" % v["views"]

        li = xbmcgui.ListItem(label=label)
        li.setInfo("video", {"title": v["title"]})
        if v.get("thumb"):
            li.setArt({"thumb": v["thumb"], "icon": "DefaultVideo.png"})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="play", url=v["url"], title=v["title"]), li, isFolder=False)

    li = xbmcgui.ListItem("[B]Next Page >[/B]")
    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="list", page_url=url, page=page+1), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_categories():
    html = fetch(BASE + "/categories/")
    if not html:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    cats = re.findall(r'<a href="(/categories/[^"]+)"[^>]*>.*?<span[^>]*>([^<]+)</span>.*?<span[^>]*>([\d,]+)', html, re.DOTALL)
    if not cats:
        cats = re.findall(r'<a href="(/categories/[^"]+)"[^>]*>([^<]+)</a>', html, re.DOTALL)

    for cat in cats:
        if len(cat) == 3:
            link, name, count = cat
            label = "%s [%s videos]" % (name.strip(), count.strip())
        else:
            link, name = cat
            label = name.strip()

        li = xbmcgui.ListItem(label)
        li.setArt({"icon": "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="list", page_url=BASE + link), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_models():
    html = fetch(BASE + "/models/")
    if not html:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    models = re.findall(r'<a href="(/models/[^"]+)"[^>]*class="[^"]*model[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)
    for link, content in models:
        name_match = re.search(r'<span[^>]*>([^<]+)</span>', content)
        name = name_match.group(1).strip() if name_match else link.split("/")[-1]
        count_match = re.search(r'<em>([^<]+)</em>', content)
        count = count_match.group(1).strip() if count_match else ""

        li = xbmcgui.ListItem(name if not count else "%s [%s]" % (name, count))
        li.setArt({"icon": "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="list", page_url=BASE + link), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def do_search(query=""):
    if not query:
        kb = xbmc.Keyboard("", "Search XXTHOTS...")
        kb.doModal()
        if kb.isConfirmed() and kb.getText():
            query = kb.getText().strip()
        else:
            xbmcplugin.endOfDirectory(HANDLE)
            return

    url = BASE + "/search/" + urllib.parse.quote(query, safe='') + "/"
    list_videos(url)

def play_video(url, title):
    html = fetch(url)
    if not html:
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    # Extract video URLs from flashvars
    video_urls = []
    m = re.search(r"video_url\s*:\s*'([^']+)'", html)
    if m:
        video_urls.append(("480p", m.group(1).replace("\\/", "/")))

    m = re.search(r'video_alt_url\s*:\s*\'([^\']+)\'', html)
    if m:
        video_urls.append(("720p", m.group(1).replace("\\/", "/")))

    if not video_urls:
        xbmcgui.Dialog().notification("XXThots", "No playable video found", xbmcgui.NOTIFICATION_ERROR, 3000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    # Pick best quality
    if len(video_urls) > 1:
        idx = xbmcgui.Dialog().select("Select quality", [q for q, _ in video_urls])
        if idx < 0:
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
            return
        play_url = video_urls[idx][1]
    else:
        play_url = video_urls[0][1]

    xbmc.log("[XXThots] Playing: %s" % play_url[:100], xbmc.LOGINFO)

    li = xbmcgui.ListItem(path=play_url, label=title)
    li.setProperty("IsPlayable", "true")
    li.setMimeType("video/mp4")
    li.setContentLookup(False)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)

def main():
    p = parse_params(PARAMS)
    action = p.get("action", "")

    if action == "latest":
        list_videos(BASE + "/latest-updates/")
    elif action == "top_rated":
        list_videos(BASE + "/top-rated/")
    elif action == "most_viewed":
        list_videos(BASE + "/most-popular/")
    elif action == "categories":
        list_categories()
    elif action == "models":
        list_models()
    elif action == "search":
        do_search(p.get("query", ""))
    elif action == "list":
        list_videos(p.get("page_url", ""), int(p.get("page", "1")))
    elif action == "play":
        play_video(p.get("url", ""), p.get("title", ""))
    else:
        show_menu()

if __name__ == "__main__":
    main()
