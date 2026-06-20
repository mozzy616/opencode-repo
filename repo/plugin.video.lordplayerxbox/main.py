# -*- coding: utf-8 -*-

import sys
import os
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

def _request(url, method="GET", data=None, headers=None, timeout=30):
    try:
        h = {"User-Agent": "Kodi/21", "Accept": "application/json"}
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            if body:
                return json.loads(body)
            return {}
    except Exception as e:
        log("API error %s: %s" % (url.split("?")[0], str(e)))
        return None

def seedr_auth():
    user = ADDON.getSetting("seedr_user") or ""
    pwd = ADDON.getSetting("seedr_pass") or ""
    if not user or not pwd:
        log("Seedr: no credentials set")
        return None
    cache = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.lordplayerxbox/token.txt")
    try:
        with open(cache) as f:
            token = f.read().strip()
            if token:
                log("Seedr: using cached token")
                return token
    except:
        pass
    result = _request("https://www.seedr.cc/auth/login",
                      method="POST",
                      data=urllib.parse.urlencode({"username": user, "password": pwd}).encode(),
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    if result and result.get("access_token"):
        token = result["access_token"]
        log("Seedr: login OK")
        try:
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(cache, "w") as f:
                f.write(token)
        except:
            pass
        return token
    log("Seedr: login failed: %s" % str(result)[:100])
    return None

def seedr_upload(token, magnet):
    r = _request("https://www.seedr.cc/api/folder",
                 method="POST",
                 data=urllib.parse.urlencode({"magnet": magnet}).encode(),
                 headers={"Content-Type": "application/x-www-form-urlencoded",
                          "Authorization": "Bearer " + token})
    if r:
        log("Seedr upload: %s" % str(r)[:100])
    return r

def seedr_folder(token, folder_id):
    return _request("https://www.seedr.cc/api/folder/" + str(folder_id),
                    headers={"Authorization": "Bearer " + token})

def seedr_get_stream(token, magnet):
    log("Seedr: uploading...")
    add = seedr_upload(token, magnet)
    if not add:
        return None
    fid = add.get("id") or add.get("folder_id", 0)
    if not fid:
        log("Seedr: no folder id in response")
        return None
    log("Seedr: folder=%s, waiting for download..." % fid)
    for i in range(60):
        time.sleep(3)
        f = seedr_folder(token, fid)
        if not f:
            continue
        files = f.get("files", [])
        for file in files:
            url = file.get("play_video") or file.get("stream_url") or file.get("download_url")
            if url:
                log("Seedr: got URL at attempt %d" % i)
                return url
        pct = f.get("progress", 0)
        if i % 10 == 0:
            log("Seedr: progress=%d%%" % pct)
        if pct >= 100:
            for file in files:
                url = file.get("play_video") or file.get("download_url")
                if url:
                    return url
            return None
    return None

def play_magnet(paramstring):
    params = dict(urllib.parse.parse_qsl(paramstring.lstrip("?")))
    magnet = params.get("magnet", "")
    log("play_magnet: %s" % magnet[:80])

    if not magnet:
        xbmcgui.Dialog().ok("Error", "No magnet provided")
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

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

    xbmcgui.Dialog().ok("LordPlayer Xbox",
                         "Could not stream torrent.",
                         "Make sure your free Seedr.cc account",
                         "credentials are set in addon settings.")
    xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())

def router(paramstring):
    params = dict(urllib.parse.parse_qsl(paramstring.lstrip("?")))
    action = params.get("action", "play_magnet")
    if action == "play_magnet":
        play_magnet(paramstring)
    elif action == "settings":
        ADDON.openSettings()
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
    else:
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)

if __name__ == "__main__":
    router(sys.argv[2])
