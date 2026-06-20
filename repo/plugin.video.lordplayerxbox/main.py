# -*- coding: utf-8 -*-

import sys
import urllib.parse
import urllib.request
import json
import time
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

HANDLE = int(sys.argv[1])
ADDON = xbmcaddon.Addon()

def log(msg):
    xbmc.log("[LordPlayerXbox] %s" % msg, xbmc.LOGINFO)

def get_setting(key, default=""):
    return ADDON.getSetting(key) or default

def build_magnet(info_hash, title="", trackers=None):
    if "magnet:" in (info_hash or ""):
        return info_hash
    magnet = "magnet:?xt=urn:btih:" + info_hash.lower()
    encoded_title = urllib.parse.quote(title) if title else ""
    if encoded_title:
        magnet += "&dn=" + encoded_title
    default_trackers = [
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://tracker.coppersurfer.tk:6969/announce",
        "udp://tracker.leechers-paradise.org:6969/announce",
        "udp://9.rarbg.to:2710/announce",
        "udp://tracker.internetwarriors.net:1337/announce",
        "http://tracker.openbittorrent.com:80/announce",
    ]
    for t in (trackers or default_trackers):
        magnet += "&tr=" + urllib.parse.quote(t)
    return magnet

def _request(url, method="GET", data=None, headers=None, timeout=15):
    try:
        h = {"User-Agent": "Kodi/21"}
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        log("API error %s: %s" % (url, str(e)))
        return None


# ---- Seedr.cc play (requires free account) ----
def seedr_auth():
    user = get_setting("seedr_user")
    pwd = get_setting("seedr_pass")
    if not user or not pwd:
        return None
    cache = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.lordplayerxbox/seedr_token.txt")
    # Check cached token
    try:
        with open(cache) as f:
            token = f.read().strip()
            if token:
                return token
    except:
        pass
    # Login
    result = _request("https://www.seedr.cc/api/auth/login",
                      data=urllib.parse.urlencode({"username": user, "password": pwd}).encode(),
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    if result and result.get("access_token"):
        token = result["access_token"]
        try:
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(cache, "w") as f:
                f.write(token)
        except:
            pass
        return token
    return None

def seedr_add_torrent(token, magnet):
    return _request("https://www.seedr.cc/api/folder",
                    method="POST",
                    data=urllib.parse.urlencode({"magnet": magnet, "folder_id": 0}).encode(),
                    headers={"Content-Type": "application/x-www-form-urlencoded",
                             "Authorization": "Bearer " + token})

def seedr_list_folder(token, folder_id):
    return _request("https://www.seedr.cc/api/folder/" + str(folder_id),
                    headers={"Authorization": "Bearer " + token})

def seedr_get_stream(token, magnet):
    log("Seedr: adding torrent...")
    add_result = seedr_add_torrent(token, magnet)
    if not add_result:
        return None
    folder_id = add_result.get("id") or add_result.get("folder_id", 0)
    log("Seedr: folder_id=%s" % folder_id)
    # Wait for download
    for attempt in range(30):
        time.sleep(5)
        folder = seedr_list_folder(token, folder_id)
        if not folder:
            continue
        files = folder.get("files", [])
        for f in files:
            if f.get("play_video") or f.get("stream_url"):
                url = f.get("play_video") or f.get("stream_url")
                log("Seedr: got stream URL")
                return url
        progress = folder.get("progress", 0)
        log("Seedr: progress=%d%%" % progress)
        if progress >= 100 or folder.get("download_url"):
            # Try fetch any streamable file
            for f in files:
                url = f.get("play_video") or f.get("download_url")
                if url and any(ext in str(url).lower() for ext in [".mp4", ".mkv", ".avi", ".m3u8", ".ts"]):
                    return url
            if files and files[0].get("download_url"):
                return files[0]["download_url"]
            break
    return None


# ---- YTS.mx direct (movies only) ----
def yts_direct(info_hash):
    try:
        url = "https://yts.mx/api/v2/movie_details.json?imdb_id=" + info_hash
        data = _request(url)
        if not data:
            return None
        movie = data.get("data", {}).get("movie", {})
        for t in movie.get("torrents", []):
            if t.get("hash", "").lower() == info_hash.lower():
                return t.get("url")
    except:
        pass
    return None


# ---- Main playback ----
def play_magnet(paramstring):
    params = dict(urllib.parse.parse_qsl(paramstring.lstrip("?")))
    magnet = params.get("magnet", "")
    title = params.get("title", "")
    log("play_magnet: %s" % (magnet or "NONE")[:80])

    if not magnet:
        xbmcgui.Dialog().ok("Error", "No magnet provided")
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    # Try Seedr.cc first
    token = seedr_auth()
    if token:
        url = seedr_get_stream(token, magnet)
        if url:
            li = xbmcgui.ListItem(path=url)
            if ".m3u8" in url.lower():
                li.setProperty("inputstream", "inputstream.adaptive")
                li.setProperty("inputstream.adaptive.manifest_type", "hls")
            li.setProperty("IsPlayable", "true")
            xbmcplugin.setResolvedUrl(HANDLE, True, li)
            return
        log("Seedr failed to get stream")
    else:
        log("Seedr not configured - set username/password in addon settings")
        log("Free account: https://www.seedr.cc")

    xbmcgui.Dialog().ok("LordPlayer Xbox",
                         "Could not stream this torrent.",
                         "For best results, add a free Seedr.cc account",
                         "in the addon settings.")
    xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


def router(paramstring):
    params = dict(urllib.parse.parse_qsl(paramstring.lstrip("?")))
    action = params.get("action", "play_magnet")
    if action == "play_magnet":
        play_magnet(paramstring)
    elif action == "settings":
        ADDON.openSettings()
    else:
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)

if __name__ == "__main__":
    router(sys.argv[2])
