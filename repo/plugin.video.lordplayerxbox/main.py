# -*- coding: utf-8 -*-

import sys, os, urllib.parse, urllib.request, json, time, hashlib
import xbmc, xbmcgui, xbmcplugin, xbmcaddon, xbmcvfs

HANDLE = int(sys.argv[1])
ADDON = xbmcaddon.Addon()

def log(msg):
    xbmc.log("[LordPlayerXbox] %s" % msg, xbmc.LOGINFO)

def _get_json(url, headers=None):
    try:
        h = {"User-Agent": "Kodi/21"}
        if headers: h.update(headers)
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        log("HTTP %s: %s" % (url[:60], str(e)[:100]))
        return None

def _post(url, data, headers=None):
    try:
        h = {"User-Agent": "Kodi/21", "Content-Type": "application/x-www-form-urlencoded"}
        if headers: h.update(headers)
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=body, headers=h)
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        log("HTTP %s: %s" % (url[:60], str(e)[:100]))
        return None

def auth_headers():
    token = ADDON.getSetting("rd_token") or ""
    if not token:
        return None
    return {"Authorization": "Bearer " + token}

def get_info_hash(magnet):
    import re
    m = re.search(r"btih:([a-fA-F0-9]{40})", magnet)
    return m.group(1).lower() if m else None

def rd_cached_stream(magnet):
    info_hash = get_info_hash(magnet)
    if not info_hash:
        return None
    auth = auth_headers()
    if not auth:
        return None

    # Check instant availability (cached torrents)
    avail = _get_json("https://api.real-debrid.com/rest/1.0/torrents/instantAvailability/%s" % info_hash, auth)
    if avail and info_hash in avail:
        # Return first available file from best quality variant
        variants = avail[info_hash].get("rd", [])
        if variants:
            files = variants[0].values() if variants else []
            for f_list in [files] + [list(v.values()) for v in variants]:
                for f in (f_list if isinstance(f_list, list) else []):
                    if isinstance(f, dict) and f.get("filename"):
                        # Unrestrict
                        dl = _post("https://api.real-debrid.com/rest/1.0/unrestrict/link",
                                   {"link": "https://real-debrid.com/d/%s/%s" % (info_hash, f.get("filename",""))},
                                   auth)
                        if dl and dl.get("download"):
                            log("RD cached: %s" % f.get("filename",""))
                            return dl["download"]
            # Try first file from first variant
            for v in variants:
                for fid, finfo in v.items():
                    dl = _post("https://api.real-debrid.com/rest/1.0/unrestrict/link",
                               {"link": "https://real-debrid.com/d/%s/%s" % (info_hash, finfo.get("filename",""))},
                               auth)
                    if dl and dl.get("download"):
                        return dl["download"]
                    break
                break

    # Not cached - add magnet and wait for download
    add = _post("https://api.real-debrid.com/rest/1.0/torrents/addMagnet", {"magnet": magnet}, auth)
    if not add or "id" not in add:
        log("RD addMagnet failed: %s" % str(add)[:100])
        return None

    tid = add["id"]
    log("RD torrent id=%s, waiting..." % tid)

    for attempt in range(60):
        time.sleep(5)
        info = _get_json("https://api.real-debrid.com/rest/1.0/torrents/info/%s" % tid, auth)
        if not info:
            continue
        status = info.get("status", "")
        if status == "waiting_files_selection":
            files = info.get("files", [])
            ids = ",".join(str(f["id"]) for f in files
                          if any(f.get("path","").lower().endswith(e)
                                 for e in (".mp4",".mkv",".avi",".ts")))
            if not ids and files:
                ids = str(files[0]["id"])
            if ids:
                _post("https://api.real-debrid.com/rest/1.0/torrents/selectFiles/%s" % tid,
                      {"files": ids}, auth)
        elif status == "downloaded":
            links = info.get("links", [])
            for link in links:
                dl = _post("https://api.real-debrid.com/rest/1.0/unrestrict/link",
                           {"link": link}, auth)
                if dl and dl.get("download"):
                    log("RD ready after %ds" % ((attempt+1)*5))
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
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    auth = auth_headers()
    if not auth:
        xbmcgui.Dialog().ok("LordPlayer Xbox",
                             "Real-Debrid token not set.",
                             "Go to addon settings and enter",
                             "your API token from real-debrid.com/api")
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    p = xbmcgui.DialogProgress()
    p.create("LordPlayer Xbox", "Checking Real-Debrid cache...")
    url = rd_cached_stream(magnet)
    p.close()

    if url:
        li = xbmcgui.ListItem(path=url)
        li.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
    else:
        xbmcgui.Dialog().ok("LordPlayer Xbox",
                             "Torrent could not be streamed.",
                             "It may not be cached on RD, is dead,",
                             "or requires a paid RD subscription.")
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())

def router(paramstring):
    params = dict(urllib.parse.parse_qsl(paramstring.lstrip("?")))
    if params.get("action", "play_magnet") == "play_magnet":
        play_magnet(paramstring)
    elif params.get("action") == "settings":
        ADDON.openSettings()
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
    else:
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)

if __name__ == "__main__":
    router(sys.argv[2])
