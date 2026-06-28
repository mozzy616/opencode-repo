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
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

_log_prefix = "[StreamLord RD]"

def log(msg, level=xbmc.LOGINFO):
    xbmc.log("%s %s" % (_log_prefix, msg), level)

def _get_rd_token():
    try:
        import xbmcaddon
        a = xbmcaddon.Addon('plugin.video.streamlord')
        return a.getSetting('rd_token').strip()
    except:
        return ""

def _rd_fetch(url, method="GET", data=None):
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

def resolve_torrent(info_hash, title=""):
    token = _get_rd_token()
    if not token:
        log("resolve_torrent: no token", xbmc.LOGWARNING)
        return None, None

    info_hash = info_hash.lower().strip()
    if len(info_hash) != 40:
        log("resolve_torrent: invalid hash length %d" % len(info_hash), xbmc.LOGWARNING)
        return None, None

    log("resolve_torrent: hash=%s title=%s" % (info_hash[:12], title[:50] if title else ""))

    dn = urllib.parse.quote(title or "video")
    magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash, dn)
    torrent_id = add_magnet(magnet)

    if not torrent_id:
        log("resolve_torrent: addMagnet failed, trying existing")
        existing = find_existing_by_hash(info_hash)
        if existing:
            torrent_id = existing.get("id")
            log("resolve_torrent: using existing id=%s status=%s" % (torrent_id, existing.get("status", "?")))
            if existing.get("status") == "downloaded":
                links = existing.get("links", [])
                best = get_largest_video(existing.get("files", []))
                if links:
                    dl = unrestrict_link(links[0]) or links[0]
                    fn = best.get("path", title or "video.mp4") if best else (title or "video.mp4")
                    log("resolve_torrent: SUCCESS from existing %s" % info_hash[:12])
                    return dl, fn
                elif best and best.get("download"):
                    dl = unrestrict_link(best["download"]) or best["download"]
                    fn = best.get("path", title or "video.mp4")
                    log("resolve_torrent: SUCCESS from existing (file) %s" % info_hash[:12])
                    return dl, fn
        if not torrent_id:
            log("resolve_torrent: FAILED - not in RD at all", xbmc.LOGINFO)
            return None, None

    # We have a torrent_id — wait for it to be ready
    for attempt in range(8):  # up to ~16 seconds
        info = get_torrent_info(torrent_id)
        if not info:
            time.sleep(2)
            continue
        status = info.get("status", "")
        log("resolve_torrent: poll status=%s" % status)

        if status == "magnet_conversion":
            time.sleep(2)
            continue

        if status == "waiting_files_selection":
            files = info.get("files", [])
            best = get_largest_video(files)
            if not best:
                log("resolve_torrent: no files to select", xbmc.LOGWARNING)
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
                files = info.get("files", [])
                best = get_largest_video(files)
            else:
                files = info.get("files", [])
                best = get_largest_video(files)
                if best:
                    download_url = best.get("download", "")
            if download_url:
                dl = unrestrict_link(download_url) or download_url
                fn = best.get("path", title or "video.mp4") if best else (title or "video.mp4")
                delete_torrent(torrent_id)
                log("resolve_torrent: SUCCESS %s -> %s" % (info_hash[:12], dl[:80]))
                return dl, fn

        if status in ("magnet_error", "error", "virus", "dead"):
            log("resolve_torrent: status=%s" % status, xbmc.LOGWARNING)
            delete_torrent(torrent_id)
            return None, None

        time.sleep(2)

    # Timed out — not cached
    log("resolve_torrent: not cached (poll timed out)", xbmc.LOGINFO)
    delete_torrent(torrent_id)
    return None, None

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
