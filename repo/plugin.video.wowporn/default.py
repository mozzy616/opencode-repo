import sys
import urllib.parse
import urllib.request
import json
import re
import os

import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmc
import xbmcvfs

_handle = int(sys.argv[1])
_addon = xbmcaddon.Addon()
_addon_id = _addon.getAddonInfo("id")
_addon_name = _addon.getAddonInfo("name")
_addon_path = _addon.getAddonInfo("path")

BASE_URL = "https://wowporn.video"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

try:
    import ssl
    _ssl_context = ssl.create_default_context()
    _ssl_context.check_hostname = False
    _ssl_context.verify_mode = ssl.CERT_NONE
except Exception:
    _ssl_context = None


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("[WowPorn] " + str(msg), level)


def get_params():
    params = {}
    paramstring = sys.argv[2] if len(sys.argv) > 2 else ""
    if paramstring:
        if paramstring[0] == "?":
            paramstring = paramstring[1:]
        params = dict(urllib.parse.parse_qsl(paramstring))
    return params


def build_url(query_params):
    base = sys.argv[0]
    if query_params:
        return base + "?" + urllib.parse.urlencode(query_params)
    return base


def fetch_html(url, timeout=15):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            if _ssl_context:
                resp = urllib.request.urlopen(req, timeout=timeout, context=_ssl_context)
            else:
                resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            if attempt == 2:
                log("Fetch failed: {} - {}".format(url, e), xbmc.LOGERROR)
    return ""


def add_menu_item(name, query_params, thumb=None):
    url = build_url(query_params)
    li = xbmcgui.ListItem(name)
    if thumb:
        li.setArt({"thumb": thumb, "icon": thumb})
    li.setProperty("IsPlayable", "false")
    xbmcplugin.addDirectoryItem(_handle, url, li, isFolder=True)


def add_video_item(name, video_url, thumb_url, duration, views, href):
    title = name
    if len(title) > 80:
        title = title[:77] + "..."

    info_labels = {
        "title": title,
        "originaltitle": name,
        "plot": "Duration: {} | Views: {}".format(duration, views),
        "mediatype": "video",
    }

    li = xbmcgui.ListItem(title)
    li.setInfo("video", info_labels)
    li.setProperty("IsPlayable", "true")

    if thumb_url:
        if not thumb_url.startswith("http"):
            thumb_url = BASE_URL + thumb_url
        li.setArt({"thumb": thumb_url, "icon": thumb_url})

    play_url = build_url({"mode": "play", "url": urllib.parse.quote(href, safe="")})

    xbmcplugin.addDirectoryItem(_handle, play_url, li, isFolder=False)


def scrape_thumb(row_html):
    pic_match = re.search(r'<img[^>]*src="([^"]+)"', row_html)
    if not pic_match:
        pic_match = re.search(r'<img[^>]*data-src="([^"]+)"', row_html)
    if not pic_match:
        pic_match = re.search(r'data-src="([^"]+)"', row_html)
    thumb = pic_match.group(1) if pic_match else ""
    if thumb and not thumb.startswith("http"):
        thumb = BASE_URL + thumb
    return thumb


def scrape_video_list(html):
    results = []
    blocks = re.findall(r'<a class="thumb-link"[^>]*href="https://wowporn\.video(/video/[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)

    for href, inner in blocks:
        name_match = re.search(r'<span class="name">([^<]+)</span>', inner)
        time_match = re.search(r'<span class="time">.*?</i>\s*([^<]+)</span>', inner)
        view_match = re.search(r'<span class="view">.*?</i>\s*([^<]+)</span>', inner)

        if name_match:
            name = name_match.group(1).strip()
            name = re.sub(r'\s+', ' ', name)
            thumb = scrape_thumb(inner)
            duration = time_match.group(1).strip() if time_match else ""
            views = view_match.group(1).strip() if view_match else ""
            results.append((name, href, thumb, duration, views))

    return results


def scrape_categories(html):
    results = []
    blocks = re.findall(r'<a[^>]*href="https://wowporn\.video(/category/[^"]+)"[^>]*data-category-id[^>]*>(.*?)</a>', html, re.DOTALL)

    for slug, inner in blocks:
        name_match = re.search(r'<span class="name">([^<]+)</span>', inner)
        if name_match:
            name = name_match.group(1).strip()
            thumb = scrape_thumb(inner)
            results.append((name, slug, thumb))

    return results


def scrape_video_page(html):
    hls_match = re.search(r'content="(https://cdn[\w\d]+\.wowporn\.video/hls/[^"]+\.m3u8[^"]*)"', html)
    if not hls_match:
        hls_match = re.search(r'(https?://[^\s"]+\.m3u8[^\s"]*)', html)
    return hls_match.group(1) if hls_match else ""


def main_menu():
    xbmcplugin.setContent(_handle, "videos")

    add_menu_item(
        "[B][COLOR gold]Categories[/COLOR][/B]",
        {"mode": "categories"},
        thumb="DefaultCategories.png"
    )
    add_menu_item(
        "[B][COLOR lime]New Videos[/COLOR][/B]",
        {"mode": "new_videos"},
        thumb="DefaultRecentlyAddedEpisodes.png"
    )
    add_menu_item(
        "[B][COLOR orange]Top Videos[/COLOR][/B]",
        {"mode": "top_videos"},
        thumb="DefaultMusicVideos.png"
    )
    add_menu_item(
        "[B][COLOR deepskyblue]Search[/COLOR][/B]",
        {"mode": "search"},
        thumb="DefaultAddonVideo.png"
    )

    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def list_categories(page=1):
    xbmcplugin.setContent(_handle, "videos")
    log("Loading categories page {}".format(page))

    url = BASE_URL if page == 1 else "{}/{}".format(BASE_URL, page)
    html = fetch_html(url)

    cats = scrape_categories(html)

    for name, slug, thumb in cats:
        add_menu_item(
            name,
            {"mode": "category", "slug": slug, "name": name},
            thumb=BASE_URL + thumb if thumb and not thumb.startswith("http") else thumb
        )

    if page < 11:
        add_menu_item(
            "[B]Next Page >>[/B]",
            {"mode": "categories", "page": str(page + 1)},
            thumb="DefaultFolderBack.png"
        )

    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def list_category(slug, name, page=1):
    xbmcplugin.setContent(_handle, "videos")
    log("Loading category: {} page {}".format(slug, page))

    url = "{}{}".format(BASE_URL, slug)
    if page > 1:
        url = "{}{}/{}".format(BASE_URL, slug, page)
    html = fetch_html(url)

    videos = scrape_video_list(html)

    if not videos:
        xbmcgui.Dialog().notification(_addon_name, "No videos found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)
        return

    for name, href, thumb, duration, views in videos:
        if not href.startswith("http"):
            href = BASE_URL + href
        add_video_item(name, href, thumb, duration, views, href)

    add_menu_item(
        "[B]Next Page >>[/B]",
        {"mode": "category", "slug": slug, "name": name, "page": str(page + 1)},
        thumb="DefaultFolderBack.png"
    )

    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def list_new_videos(page=1):
    xbmcplugin.setContent(_handle, "videos")
    log("Loading new videos page {}".format(page))

    url = "{}/new".format(BASE_URL)
    if page > 1:
        url = "{}/new/{}".format(BASE_URL, page)
    html = fetch_html(url)

    videos = scrape_video_list(html)

    if not videos:
        xbmcgui.Dialog().notification(_addon_name, "No videos found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)
        return

    for name, href, thumb, duration, views in videos:
        if not href.startswith("http"):
            href = BASE_URL + href
        add_video_item(name, href, thumb, duration, views, href)

    add_menu_item(
        "[B]Next Page >>[/B]",
        {"mode": "new_videos", "page": str(page + 1)},
        thumb="DefaultFolderBack.png"
    )

    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def list_top_videos(page=1):
    xbmcplugin.setContent(_handle, "videos")
    log("Loading top videos page {}".format(page))

    url = "{}/videos".format(BASE_URL)
    if page > 1:
        url = "{}/videos/{}".format(BASE_URL, page)
    html = fetch_html(url)

    videos = scrape_video_list(html)

    if not videos:
        xbmcgui.Dialog().notification(_addon_name, "No videos found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)
        return

    for name, href, thumb, duration, views in videos:
        if not href.startswith("http"):
            href = BASE_URL + href
        add_video_item(name, href, thumb, duration, views, href)

    add_menu_item(
        "[B]Next Page >>[/B]",
        {"mode": "top_videos", "page": str(page + 1)},
        thumb="DefaultFolderBack.png"
    )

    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def search_videos():
    search_term = xbmcgui.Dialog().input("Search WowPorn", type=xbmcgui.INPUT_ALPHANUM)
    if not search_term:
        main_menu()
        return

    log("Searching for: {}".format(search_term))
    list_search_results(search_term, 1)


def list_search_results(query, page=1):
    xbmcplugin.setContent(_handle, "videos")
    log("Search results for '{}', page {}".format(query, page))

    encoded = urllib.parse.quote(query)
    url = "{}/search/{}?sort=date".format(BASE_URL, encoded)
    if page > 1:
        url = "{}/search/{}/{}?sort=date".format(BASE_URL, encoded, page)
    html = fetch_html(url)

    videos = scrape_video_list(html)

    if not videos:
        xbmcgui.Dialog().notification(_addon_name, "No results for: {}".format(query), xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)
        return

    for name, href, thumb, duration, views in videos:
        if not href.startswith("http"):
            href = BASE_URL + href
        add_video_item(name, href, thumb, duration, views, href)

    add_menu_item(
        "[B]Next Page >>[/B]",
        {"mode": "search_results", "query": query, "page": str(page + 1)},
        thumb="DefaultFolderBack.png"
    )

    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def play_video(page_url):
    log("Playing: {}".format(page_url))

    html = fetch_html(page_url)
    hls_url = scrape_video_page(html)

    if not hls_url:
        xbmcgui.Dialog().notification(_addon_name, "Could not find video stream", xbmcgui.NOTIFICATION_ERROR, 4000)
        return

    hls_url = hls_url.replace("&amp;", "&")
    log("HLS: " + hls_url[:120])

    headers = "User-Agent=" + urllib.parse.quote(HEADERS["User-Agent"])
    headers += "&Referer=" + urllib.parse.quote(page_url)
    headers += "&Origin=" + urllib.parse.quote(BASE_URL)

    li = xbmcgui.ListItem(path=hls_url)
    li.setProperty("IsPlayable", "true")
    li.setProperty("inputstream", "inputstream.adaptive")
    li.setProperty("inputstream.adaptive.manifest_headers", headers)
    li.setProperty("inputstream.adaptive.stream_headers", headers)
    li.setProperty("inputstream.adaptive.max_resolution", "480")
    li.setMimeType("application/vnd.apple.mpegurl")
    li.setContentLookup(False)

    xbmcplugin.setResolvedUrl(_handle, True, li)


def router(params):
    mode = params.get("mode", "main")

    if mode == "main":
        main_menu()
    elif mode == "categories":
        page = int(params.get("page", "1"))
        list_categories(page)
    elif mode == "category":
        slug = params.get("slug", "")
        name = params.get("name", "Category")
        page = int(params.get("page", "1"))
        list_category(slug, name, page)
    elif mode == "new_videos":
        page = int(params.get("page", "1"))
        list_new_videos(page)
    elif mode == "top_videos":
        page = int(params.get("page", "1"))
        list_top_videos(page)
    elif mode == "search":
        search_videos()
    elif mode == "search_results":
        query = params.get("query", "")
        page = int(params.get("page", "1"))
        list_search_results(query, page)
    elif mode == "play":
        url = params.get("url", "")
        if url:
            url = urllib.parse.unquote(url)
        play_video(url)
    else:
        main_menu()


if __name__ == "__main__":
    params = get_params()
    log("Params: {}".format(params))
    router(params)
