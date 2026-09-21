import json
import re
import time
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
import xbmc
import xbmcgui

RD_API = "https://api.real-debrid.com/rest/1.0"
RD_OAUTH = "https://api.real-debrid.com/oauth/v2"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

_log_prefix = "[StreamLord RD]"

def log(msg, level=xbmc.LOGINFO):
    xbmc.log("%s %s" % (_log_prefix, msg), level)

def _get_rd_token():
    try:
        import xbmcaddon
        rdf = xbmcaddon.Addon('plugin.video.rdflix')
        t = rdf.getSetting('rd_token').strip()
        if t:
            return t
    except:
        pass
    try:
        import xbmcaddon
        a = xbmcaddon.Addon('plugin.video.streamlord')
        return a.getSetting('rd_token').strip()
    except:
        return ""

def _get_credential(key):
    for addon_id in ("plugin.video.rdflix", "plugin.video.streamlord"):
        try:
            import xbmcaddon
            v = xbmcaddon.Addon(addon_id).getSetting(key).strip()
            if v:
                return v, addon_id
        except:
            pass
    return "", ""

def _refresh_rd_token():
    client_id, aid = _get_credential("rd_client_id")
    client_secret, _ = _get_credential("rd_client_secret")
    refresh, _ = _get_credential("rd_refresh_token")
    if not client_id or not client_secret or not refresh:
        return None
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": refresh,
        "grant_type": "http://oauth.net/grant_type/device/1.0",
    }).encode("utf-8")
    try:
        req = urllib.request.Request(RD_OAUTH + "/token", data=data, headers={
            "User-Agent": UA, "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode("utf-8", errors="replace"))
        if resp and resp.get("access_token"):
            import xbmcaddon
            a = xbmcaddon.Addon(aid)
            a.setSetting("rd_token", resp["access_token"])
            if resp.get("refresh_token"):
                a.setSetting("rd_refresh_token", resp["refresh_token"])
            log("RD token refreshed successfully")
            return resp["access_token"]
    except Exception as e:
        log("RD refresh error: %s" % str(e), xbmc.LOGWARNING)
    return None

def _rd_fetch(url, method="GET", data=None, _retry=True):
    token = _get_rd_token()
    headers = {
        "Authorization": "Bearer " + token,
        "User-Agent": UA,
        "Accept": "application/json",
    }
    if method == "POST" and data:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        if data and isinstance(data, dict):
            encoded = urllib.parse.urlencode(data).encode("utf-8")
        elif data:
            encoded = data.encode("utf-8") if isinstance(data, str) else data
        else:
            encoded = None
        req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
            log("%s %s -> %d bytes" % (method, url.split('/')[-1][:40], len(raw)))
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = ""
        try: body = e.read().decode("utf-8", errors="replace")[:500]
        except: pass
        log("%s %s HTTP %d body=%s" % (method, url.split('/')[-1][:40], e.code, body), xbmc.LOGWARNING)
        if e.code in (403, 401):
            is_dup = "magnet_already_added" in body or "already_added" in body
            if "bad_token" in body and _retry:
                log("RD token expired, refreshing")
                if _refresh_rd_token():
                    return _rd_fetch(url, method, data, _retry=False)
            if not is_dup:
                xbmcgui.Dialog().notification("Real-Debrid", "HTTP %d - check token at real-debrid.com/apitoken" % e.code, xbmcgui.NOTIFICATION_ERROR, 8000)
        return None
    except urllib.error.URLError as e:
        log("URL error %s: %s" % (url.split('/')[-1][:40], str(e)), xbmc.LOGWARNING)
        return None
    except Exception as e:
        log("error %s: %s" % (url.split('/')[-1][:40], str(e)), xbmc.LOGWARNING)
        return None

def _rd_request(method, path, data=None):
    token = _get_rd_token()
    if not token:
        log("no token set", xbmc.LOGWARNING)
        return None
    url = RD_API + path
    return _rd_fetch(url, method, data)

def add_magnet(magnet):
    log("addMagnet: %s..." % magnet[:80])
    resp = _rd_request("POST", "/torrents/addMagnet", {"magnet": magnet})
    if resp and "id" in resp:
        log("addMagnet success: id=%s status=%s" % (resp["id"], resp.get("status", "?")))
        return resp["id"]
    if resp and "error" in resp:
        log("addMagnet error: %s" % resp["error"], xbmc.LOGWARNING)
    return None

def get_torrent_info(torrent_id):
    return _rd_request("GET", "/torrents/info/" + str(torrent_id))

def select_file(torrent_id, file_id):
    log("selectFile: %s file=%s" % (torrent_id, file_id))
    return _rd_request("POST", "/torrents/selectFiles/" + str(torrent_id), {"files": str(file_id)})

def delete_torrent(torrent_id):
    log("delete: %s" % torrent_id)
    return _rd_request("DELETE", "/torrents/delete/" + str(torrent_id))

def list_torrents():
    log("listing existing torrents")
    return _rd_request("GET", "/torrents?page=1&limit=200")

def find_existing_by_hash(info_hash):
    target = info_hash.lower().strip()
    torrents = list_torrents()
    if not torrents:
        log("find_existing: no torrents in account or list failed")
        return None
    log("find_existing: searching %d torrents for hash %s" % (len(torrents), target[:12]))
    for t in torrents:
        if t.get("hash", "").lower() == target:
            log("find_existing: FOUND id=%s status=%s" % (t.get("id"), t.get("status", "?")))
            return t
    log("find_existing: hash %s not found in any existing torrent" % target[:12])
    return None

def get_largest_video(files):
    if not files:
        return None
    vids = [f for f in files if f.get("path", "").lower().endswith((".mp4", ".mkv", ".avi", ".m4v", ".mov", ".webm"))]
    vids = vids or files
    vids.sort(key=lambda f: f.get("bytes", 0), reverse=True)
    best = vids[0]
    log("largest_video: id=%s %s (%d bytes)" % (best.get("id"), best.get("path", "?"), best.get("bytes", 0)))
    return best

def resolve_magnet(magnet, title=""):
    """Resolve a magnet link via Real-Debrid (handles hex and base32 btih)."""
    token = _get_rd_token()
    if not token:
        log("resolve_magnet: no token", xbmc.LOGWARNING)
        return None, None

    m = re.search(r"btih:([a-zA-Z0-9]{32,60})", magnet, re.IGNORECASE)
    info_hash = m.group(1).lower() if m else ""
    log("resolve_magnet: hash=%s title=%s" % (info_hash[:12], title[:50] if title else ""))

    # Check existing torrents first (only works for standard 40-char hex hashes)
    if len(info_hash) == 40:
        existing = find_existing_by_hash(info_hash)
        if existing and existing.get("status") == "downloaded":
            links = existing.get("links", [])
            best = get_largest_video(existing.get("files", []))
            if links:
                dl = unrestrict_link(links[0])
                if dl:
                    fn = best.get("path", title or "video.mp4") if best else (title or "video.mp4")
                    log("resolve_magnet: SUCCESS from existing %s" % info_hash[:12])
                    return dl, fn
            elif best and best.get("download"):
                dl = unrestrict_link(best["download"])
                if dl:
                    fn = best.get("path", title or "video.mp4")
                    log("resolve_magnet: SUCCESS from existing (file) %s" % info_hash[:12])
                    return dl, fn

    torrent_id = add_magnet(magnet)
    if not torrent_id:
        log("resolve_magnet: FAILED - blocked by RD or not available", xbmc.LOGINFO)
        return None, None

    for attempt in range(8):
        info = get_torrent_info(torrent_id)
        if not info:
            time.sleep(2)
            continue
        status = info.get("status", "")
        log("resolve_magnet: poll status=%s" % status)

        if status == "magnet_conversion":
            time.sleep(2)
            continue

        if status == "waiting_files_selection":
            files = info.get("files", [])
            best = get_largest_video(files)
            if not best:
                log("resolve_magnet: no files to select", xbmc.LOGWARNING)
                delete_torrent(torrent_id)
                return None, None
            select_file(torrent_id, best["id"])
            time.sleep(2)
            continue

        if status == "downloaded":
            links = info.get("links", [])
            best = None
            download_url = ""
            if links:
                download_url = links[0]
                best = get_largest_video(info.get("files", []))
            else:
                best = get_largest_video(info.get("files", []))
                if best:
                    download_url = best.get("download", "")
            if download_url:
                dl = unrestrict_link(download_url) or download_url
                fn = best.get("path", title or "video.mp4") if best else (title or "video.mp4")
                delete_torrent(torrent_id)
                log("resolve_magnet: SUCCESS %s -> %s" % (info_hash[:12], dl[:80]))
                return dl, fn

        if status in ("magnet_error", "error", "virus", "dead"):
            log("resolve_magnet: status=%s" % status, xbmc.LOGWARNING)
            delete_torrent(torrent_id)
            return None, None

        time.sleep(2)

    log("resolve_magnet: not cached (poll timed out)", xbmc.LOGINFO)
    delete_torrent(torrent_id)
    return None, None


def resolve_torrent(info_hash, title=""):
    """Resolve a raw info hash via Real-Debrid."""
    info_hash = (info_hash or "").strip()
    dn = urllib.parse.quote(title or "video")
    magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash, dn)
    return resolve_magnet(magnet, title)

def unrestrict_link(link):
    resp = _rd_request("POST", "/unrestrict/link", {"link": link})
    if resp and "download" in resp:
        return resp["download"]
    return None

def download_file(url, dest_path, filename, title=""):
    import os
    out = os.path.join(dest_path, filename)
    try:
        progress = xbmcgui.DialogProgress()
        progress.create("StreamLord - RD Download", title or filename)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as src:
            total = int(src.headers.get("Content-Length", 0))
            wrote = 0
            with open(out, "wb") as f:
                while not progress.iscanceled():
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    wrote += len(chunk)
                    if total:
                        pct = int(wrote / total * 100)
                        progress.update(pct, "%d / %d MB" % (wrote // 1048576, total // 1048576))
        progress.close()
        if not progress.iscanceled():
            log("download complete: %s" % out)
            xbmcgui.Dialog().notification("Download Complete", filename, xbmcgui.NOTIFICATION_INFO, 5000)
            return True
    except Exception as e:
        log("download error: %s" % str(e), xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Download Error", str(e))
    return False


def is_available(hashes):
    return {}


def instant_availability(hashes):
    """Check which info hashes are cached on Real-Debrid (instant availability)."""
    if not hashes:
        return {}
    hashes = [h.lower().strip()[:40] for h in hashes if h]
    hashes = list(dict.fromkeys(hashes))[:100]
    if not hashes:
        return {}
    path = "/torrents/instantAvailability/" + "/".join(hashes)
    resp = _rd_request("GET", path)
    if isinstance(resp, dict):
        return resp
    return {}
