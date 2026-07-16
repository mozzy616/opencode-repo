import sys
import urllib.parse
import urllib.request
import json
import os
import re
import subprocess
import time
import threading

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
_addon_profile = _addon.getAddonInfo("profile")

if not xbmcvfs.exists(_addon_profile):
    xbmcvfs.mkdirs(_addon_profile)

TPB_API = "https://apibay.org/q.php?q={q}&cat={cat}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}
ADULT_CAT = "500"
ITEMS_PER_PAGE = 25
SEARCH_TERMS = ["pov", "xxx", "facial", "interracial"]
THUMBS = [
    os.path.join(_addon_path, "resources", "thumb1.jpg"),
    os.path.join(_addon_path, "resources", "thumb2.jpg"),
    os.path.join(_addon_path, "resources", "thumb3.jpg"),
    os.path.join(_addon_path, "resources", "thumb4.jpg"),
]
LORDPLAYER_ID = "plugin.video.lordplayer"
MAGNET_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://tracker.trackerfix.com:80/announce",
    "udp://tracker.moeking.me:6969/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.dler.org:6969/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.coppersurfer.tk:6969/announce",
]

try:
    import ssl
    _ssl_context = ssl.create_default_context()
    _ssl_context.check_hostname = False
    _ssl_context.verify_mode = ssl.CERT_NONE
except Exception:
    _ssl_context = None

_CACHE_WIN = xbmcgui.Window(10000)


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("[TorrentX] " + str(msg), level)


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


def fetch_json(url, timeout=15):
    last_error = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            if _ssl_context:
                response = urllib.request.urlopen(req, timeout=timeout, context=_ssl_context)
            else:
                response = urllib.request.urlopen(req, timeout=timeout)
            data = response.read().decode("utf-8")
            result = json.loads(data)
            if not isinstance(result, list) or len(result) == 0:
                return []
            first = result[0]
            if isinstance(first, dict) and first.get("name") in ("No results returned", "Invalid query"):
                return []
            return result
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(1)
                continue
    log("API fetch failed: {}".format(last_error), xbmc.LOGERROR)
    return []


def size_to_string(size_bytes):
    try:
        size_bytes = int(size_bytes)
    except (ValueError, TypeError):
        return "Unknown"
    if size_bytes >= 1073741824:
        return "{:.2f} GB".format(size_bytes / 1073741824)
    elif size_bytes >= 1048576:
        return "{:.0f} MB".format(size_bytes / 1048576)
    elif size_bytes >= 1024:
        return "{:.0f} KB".format(size_bytes / 1024)
    else:
        return "{} B".format(size_bytes)


def build_magnet(info_hash, name):
    magnet = "magnet:?xt=urn:btih:{}&dn={}".format(
        info_hash.lower(),
        urllib.parse.quote(name)
    )
    for tracker in MAGNET_TRACKERS:
        magnet += "&tr=" + urllib.parse.quote(tracker)
    return magnet


def add_menu_item(name, query_params, thumb=None):
    url = build_url(query_params)
    li = xbmcgui.ListItem(name)
    if thumb:
        li.setArt({"thumb": thumb})
    li.setProperty("IsPlayable", "false")
    xbmcplugin.addDirectoryItem(_handle, url, li, isFolder=True)


def parse_torrent_name(name):
    meta = {}

    qual_match = re.search(r'\b(2160p|4K|1080p|720p|480p|HD|SD)\b', name, re.IGNORECASE)
    if qual_match:
        q = qual_match.group(1).upper()
        if q == "4K":
            q = "2160p"
        meta["resolution"] = q

    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', name)
    if year_match:
        y = int(year_match.group(1))
        if 2000 <= y <= 2026:
            meta["year"] = y

    parts = name.split(" - ", 1)
    if len(parts) == 2 and 3 <= len(parts[0]) <= 40:
        meta["studio"] = parts[0].strip()

    clean = re.sub(r'\[.*?\]|\(.*?\)', '', name)

    tags = r'\b(XXX|WEB-DL|WEBRip|BluRay|BRRip|HDRip|DVDRip|HEVC|x265|x264|MP4|AVI|MKV|S\d+E\d+|SD|SPLIT SCENES|COMPLETE|UNCENSORED|LEAKED)\b'
    for tag in re.findall(tags, clean, re.IGNORECASE):
        clean = re.sub(r'\b' + re.escape(tag) + r'\b', '', clean, flags=re.IGNORECASE)
    if qual_match:
        clean = re.sub(r'\b' + re.escape(qual_match.group(1)) + r'\b', '', clean, flags=re.IGNORECASE)
    if year_match:
        clean = re.sub(r'\b' + str(year_match.group(1)) + r'\b', '', clean)

    clean = re.sub(r'\s*[-–—]\s*', ' ', clean)
    clean = re.sub(r'[_\.]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    clean = re.sub(r'[,;]\s*$', '', clean)
    clean = re.sub(r'^\d+\s*', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()

    if not clean:
        clean = name
    meta["clean_title"] = clean.strip()

    return meta


def add_video_item(name, info_hash, seeders, leechers, size_bytes, added_date, uploader):
    magnet = build_magnet(info_hash, name)
    size_str = size_to_string(size_bytes)
    meta = parse_torrent_name(name)

    title = meta["clean_title"]
    if len(title) > 80:
        title = title[:77] + "..."

    year = meta.get("year", 0)

    plot_parts = []
    if meta.get("studio"):
        plot_parts.append("Studio: {}".format(meta["studio"]))
    if meta.get("resolution"):
        plot_parts.append("Quality: {}".format(meta["resolution"]))
    plot_parts.append("Size: {}".format(size_str))
    plot_parts.append("Seeds: {} | Leeches: {}".format(seeders, leechers))
    plot_parts.append("Uploader: {}".format(uploader))
    plot_parts.append("Added: {}".format(added_date))

    info_labels = {
        "title": title,
        "originaltitle": name,
        "plot": "\n".join(plot_parts),
        "size": int(size_bytes) if str(size_bytes).isdigit() else 0,
        "mediatype": "video",
    }
    if year:
        info_labels["year"] = year

    li = xbmcgui.ListItem(title)
    li.setInfo("video", info_labels)
    li.setProperty("IsPlayable", "false")

    thumb_index = hash(info_hash) % len(THUMBS)
    thumb_path = THUMBS[thumb_index]
    li.setArt({"thumb": thumb_path, "icon": thumb_path, "poster": thumb_path})

    submenu_url = build_url({
        "mode": "submenu",
        "magnet": magnet,
        "name": name,
        "info_hash": info_hash,
    })

    copy_url = build_url({"mode": "copy_magnet", "magnet": magnet})
    li.addContextMenuItems([
        ("[B]Copy Magnet Link[/B]", "RunPlugin({})".format(copy_url)),
    ], replaceItems=False)

    xbmcplugin.addDirectoryItem(_handle, submenu_url, li, isFolder=True)


def cache_save(key, data):
    try:
        _CACHE_WIN.setProperty("torrentx_" + key, json.dumps(data))
    except Exception:
        pass


def cache_load(key):
    try:
        raw = _CACHE_WIN.getProperty("torrentx_" + key)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


def cache_clear(key):
    try:
        _CACHE_WIN.clearProperty("torrentx_" + key)
    except Exception:
        pass


def sort_by_seeders(item):
    try:
        return int(item.get("seeders", 0))
    except (ValueError, TypeError):
        return 0


def tpb_search(query):
    encoded_query = urllib.parse.quote(query)
    url = TPB_API.format(q=encoded_query, cat=ADULT_CAT)
    return fetch_json(url)


def tpb_search_multi():
    all_items = []
    seen_hashes = set()
    results_lock = threading.Lock()

    def fetch_term(term):
        items = tpb_search(term)
        with results_lock:
            for item in items:
                h = item.get("info_hash", "")
                if h and h != "0000000000000000000000000000000000000000" and h not in seen_hashes:
                    seen_hashes.add(h)
                    all_items.append(item)

    threads = []
    for term in SEARCH_TERMS:
        t = threading.Thread(target=fetch_term, args=(term,))
        t.daemon = True
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=20)

    log("Multi-search found {} unique torrents".format(len(all_items)))
    return all_items


def show_listings(items, page, sort_popular=False, mode_name="new_videos"):
    xbmcplugin.setContent(_handle, "videos")

    if not items:
        xbmcgui.Dialog().notification(_addon_name, "No results found", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)
        return

    if sort_popular:
        items = sorted(items, key=sort_by_seeders, reverse=True)

    total_items = len(items)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(1, min(page, total_pages))

    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    page_items = items[start:end]

    for item in page_items:
        name = item.get("name", "Unknown")
        info_hash = item.get("info_hash", "")
        seeders = item.get("seeders", "0")
        leechers = item.get("leechers", "0")
        size_bytes = item.get("size", "0")
        added_date = item.get("added", "Unknown")
        uploader = item.get("username", "Unknown")

        if info_hash and name:
            add_video_item(name, info_hash, seeders, leechers, size_bytes, added_date, uploader)

    if page < total_pages:
        add_menu_item(
            "[B]Next Page ({} of {}) >>[/B]".format(page, total_pages),
            {"mode": "next_page", "page": str(page + 1), "from": mode_name},
            thumb="DefaultFolderBack.png"
        )

    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def new_videos(page=1):
    log("Loading New Videos, page {}".format(page))

    if page == 1:
        progress = xbmcgui.DialogProgress()
        progress.create(_addon_name, "Loading New Videos...")
        progress.update(50)
        items = tpb_search_multi()
        progress.update(100)
        progress.close()
        if items:
            cache_save("new_videos", items)
    else:
        items = cache_load("new_videos")
        if not items:
            new_videos(page=1)
            return

    show_listings(items, page, sort_popular=False, mode_name="new_videos")


def search_videos():
    search_term = xbmcgui.Dialog().input("Search for adult content", type=xbmcgui.INPUT_ALPHANUM)
    if not search_term:
        main_menu()
        return

    log("Searching for: {}".format(search_term))
    progress = xbmcgui.DialogProgress()
    progress.create(_addon_name, "Searching...")
    progress.update(20)

    all_items = []
    seen_hashes = set()
    results_lock = threading.Lock()

    queries = [search_term] + ["{} {}".format(search_term, t) for t in SEARCH_TERMS]

    def fetch_and_merge(query):
        items = tpb_search(query)
        if items:
            with results_lock:
                for item in items:
                    h = item.get("info_hash", "")
                    if h and h != "0000000000000000000000000000000000000000" and h not in seen_hashes:
                        seen_hashes.add(h)
                        all_items.append(item)

    threads = []
    active = 0
    for q in queries:
        t = threading.Thread(target=fetch_and_merge, args=(q,))
        t.daemon = True
        t.start()
        threads.append(t)
        active += 1

    for t in threads:
        t.join(timeout=15)

    progress.update(80)

    if not all_items:
        items = tpb_search(search_term)
        if not items:
            items = tpb_search("xxx")
        all_items = items

    log("Search found {} unique results".format(len(all_items) if isinstance(all_items, list) else 0))
    progress.update(100)
    progress.close()

    if all_items:
        cache_save("search", all_items)

    show_listings(all_items, 1, sort_popular=False, mode_name="search")


def search_results(page=1):
    log("Search results, page {}".format(page))

    if page == 1:
        search_videos()
        return

    items = cache_load("search")
    if not items:
        main_menu()
        return

    show_listings(items, page, sort_popular=False, mode_name="search")


def add_playable_item(name, query_params, thumb=None):
    url = build_url(query_params)
    li = xbmcgui.ListItem(name)
    if thumb:
        li.setArt({"thumb": thumb})
    li.setProperty("IsPlayable", "true")
    xbmcplugin.addDirectoryItem(_handle, url, li, isFolder=False)


def show_play_menu(magnet_url, name, info_hash):
    xbmcplugin.setContent(_handle, "videos")

    title = name
    if len(title) > 80:
        title = title[:77] + "..."

    add_playable_item(
        "[B][COLOR gold]Play via Lordplayer[/COLOR][/B]",
        {"mode": "play", "magnet": magnet_url, "name": name},
        thumb="DefaultVideoPlay.png"
    )
    add_menu_item(
        "[B][COLOR deepskyblue]Download via Lordplayer[/COLOR][/B]",
        {"mode": "download", "magnet": magnet_url, "name": name},
        thumb="DefaultVideo.png"
    )

    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def play_video(magnet_url, name):
    log("Resolving playback via Lordplayer: {}".format(name))

    safe_magnet = urllib.parse.quote(magnet_url, safe="")
    lordplayer_url = "plugin://{}/play_magnet?magnet={}&buffer=true".format(
        LORDPLAYER_ID, safe_magnet
    )

    li = xbmcgui.ListItem(path=lordplayer_url, label=name)
    li.setProperty("IsPlayable", "true")
    xbmcplugin.setResolvedUrl(_handle, True, li)


def download_video(magnet_url, name):
    log("Download via Lordplayer: {}".format(name))

    try:
        params = {
            "uri": magnet_url,
            "ignore_duplicate": "true",
            "download": "true"
        }
        url = "http://127.0.0.1:61235/add/magnet?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method="POST")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        log("Added magnet to torrest: {}".format(data))
        xbmcgui.Dialog().notification(
            _addon_name,
            "Added to Lordplayer for download",
            xbmcgui.NOTIFICATION_INFO, 4000
        )
    except Exception as e:
        log("Download error: {}".format(e), xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            _addon_name,
            "Failed. Is Lordplayer running?",
            xbmcgui.NOTIFICATION_ERROR, 5000
        )

    xbmcplugin.setContent(_handle, "videos")
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def copy_magnet(magnet_url):
    try:
        subprocess.run(
            ["cmd.exe", "/c", "echo {}|clip".format(magnet_url)],
            shell=True, check=False,
            capture_output=True
        )
        xbmcgui.Dialog().notification(
            _addon_name, "Magnet link copied to clipboard",
            xbmcgui.NOTIFICATION_INFO, 3000
        )
    except Exception:
        try:
            xbmcgui.Dialog().textviewer(_addon_name + " - Magnet Link", magnet_url)
        except Exception:
            xbmcgui.Dialog().ok(_addon_name, "Magnet Link:", magnet_url[:500])


def main_menu():
    xbmcplugin.setContent(_handle, "videos")

    cache_clear("new_videos")
    cache_clear("search")

    add_menu_item(
        "[B][COLOR gold]New Videos[/COLOR][/B]",
        {"mode": "new_videos"},
        thumb="DefaultRecentlyAddedEpisodes.png"
    )
    add_menu_item(
        "[B][COLOR deepskyblue]Search[/COLOR][/B]",
        {"mode": "search"},
        thumb="DefaultAddonVideo.png"
    )

    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def router(params):
    mode = params.get("mode", "main")
    page = int(params.get("page", "1"))

    if mode == "main":
        main_menu()
    elif mode == "new_videos":
        new_videos(page)
    elif mode == "search":
        search_videos()
    elif mode == "search_results":
        search_results(page)
    elif mode == "submenu":
        magnet = params.get("magnet", "")
        name = params.get("name", "Unknown")
        info_hash = params.get("info_hash", "")
        show_play_menu(magnet, name, info_hash)
    elif mode == "play":
        magnet = params.get("magnet", "")
        name = params.get("name", "Unknown")
        play_video(magnet, name)
    elif mode == "download":
        magnet = params.get("magnet", "")
        name = params.get("name", "Unknown")
        download_video(magnet, name)
    elif mode == "copy_magnet":
        magnet = params.get("magnet", "")
        copy_magnet(magnet)
    elif mode == "next_page":
        from_mode = params.get("from", "new_videos")
        if from_mode == "search":
            search_results(page)
        else:
            new_videos(page)
    else:
        main_menu()


if __name__ == "__main__":
    params = get_params()
    log("Params: {}".format(params))
    router(params)
