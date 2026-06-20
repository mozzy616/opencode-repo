# -*- coding: utf-8 -*-

import sys, os, urllib.parse, urllib.request, json, time
import xbmc, xbmcgui, xbmcplugin, xbmcaddon, xbmcvfs

HANDLE = int(sys.argv[1])
ADDON = xbmcaddon.Addon()

def log(msg):
    xbmc.log("[LordPlayerXbox] %s" % msg, xbmc.LOGINFO)

def _request(url, method="GET", data=None, headers=None, timeout=15):
    try:
        h = {"User-Agent": "Kodi/21"}
        if headers: h.update(headers)
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        log("HTTP error: %s" % str(e)[:100])
        return None

def rd_unrestrict(magnet):
    token = ADDON.getSetting("rd_token") or ""
    if not token:
        return None
    # Submit magnet to RD
    r = _request("https://api.real-debrid.com/rest/1.0/torrents/addMagnet",
                 method="POST",
                 data=urllib.parse.urlencode({"magnet": magnet}).encode(),
                 headers={"Content-Type": "application/x-www-form-urlencoded",
                          "Authorization": "Bearer " + token})
    if not r or "id" not in r:
        log("RD add failed: %s" % str(r)[:100])
        return None
    tid = r["id"]
    log("RD torrent id=%s" % tid)

    # Get torrent info to select files
    for _ in range(30):
        time.sleep(3)
        info = _request("https://api.real-debrid.com/rest/1.0/torrents/info/%s" % tid,
                        headers={"Authorization": "Bearer " + token})
        if not info:
            continue
        status = info.get("status", "")
        files = info.get("files", [])
        if status == "waiting_files_selection":
            # Auto-select all video files
            ids = ",".join(str(f["id"]) for f in files
                          if any(f.get("path","").lower().endswith(e)
                                 for e in (".mp4",".mkv",".avi",".m3u8")))
            if not ids:
                ids = str(files[0]["id"]) if files else ""
            if ids:
                _request("https://api.real-debrid.com/rest/1.0/torrents/selectFiles/%s" % tid,
                        method="POST",
                        data=urllib.parse.urlencode({"files": ids}).encode(),
                        headers={"Content-Type": "application/x-www-form-urlencoded",
                                 "Authorization": "Bearer " + token})
        elif status == "downloaded":
            # Get unrestricted links
            links = []
            for f in files:
                dl = _request("https://api.real-debrid.com/rest/1.0/torrents/instantAvailability/%s" %
                             (info.get("hash","") or f.get("id","")),
                             headers={"Authorization": "Bearer " + token})
                if not dl:
                    continue
            # Try unrestricted link via file download
            for f in files:
                if f.get("selected",0) == 1:
                    dl = _request("https://api.real-debrid.com/rest/1.0/unrestrict/link",
                                 method="POST",
                                 data=urllib.parse.urlencode({"link": f.get("download","") or ""}).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded",
                                          "Authorization": "Bearer " + token})
                    if dl and dl.get("download"):
                        return dl["download"]
            # Fallback: get the download link from torrent info
            links = info.get("links", [])
            for link in links:
                dl = _request("https://api.real-debrid.com/rest/1.0/unrestrict/link",
                             method="POST",
                             data=urllib.parse.urlencode({"link": link}).encode(),
                             headers={"Content-Type": "application/x-www-form-urlencoded",
                                      "Authorization": "Bearer " + token})
                if dl and dl.get("download"):
                    return dl["download"]
            return None
        elif status in ("magnet_error", "error", "virus", "dead"):
            log("RD status: %s" % status)
            return None
    return None

def play_magnet(paramstring):
    params = dict(urllib.parse.parse_qsl(paramstring.lstrip("?")))
    magnet = params.get("magnet", "")
    log("Magnet: %s" % magnet[:80])

    if not magnet:
        xbmcgui.Dialog().ok("Error", "No magnet provided")
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    token = ADDON.getSetting("rd_token") or ""
    if not token:
        xbmcgui.Dialog().ok("LordPlayer Xbox",
                             "Real-Debrid API token not set.",
                             "Go to addon settings and add your",
                             "RD token from real-debrid.com/api")
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    p = xbmcgui.DialogProgress()
    p.create("LordPlayer Xbox", "Sending to Real-Debrid...")
    url = rd_unrestrict(magnet)
    p.close()

    if url:
        li = xbmcgui.ListItem(path=url)
        li.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
    else:
        xbmcgui.Dialog().ok("LordPlayer Xbox",
                             "Torrent failed to stream.",
                             "It may not be cached on RD yet,",
                             "or the torrent is dead/too new.")
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
