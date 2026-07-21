import json
import time
import urllib.request
import urllib.error
import urllib.parse

import xbmc
import xbmcgui

from resources.lib.constants import RD_API, RD_OAUTH, USER_AGENT, LOG_PREFIX
from resources.lib.kodi_utils import get_setting, log, notify


def _token():
    return get_setting("rd_token", "")


def _fetch(url, method="GET", data=None, auth_required=True):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if auth_required:
        token = _token()
        if not token:
            log("No RD token set", xbmc.LOGWARNING)
            return None
        headers["Authorization"] = "Bearer " + token

    encoded = None
    if data:
        if isinstance(data, dict):
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            encoded = urllib.parse.urlencode(data).encode("utf-8")
        elif isinstance(data, str):
            encoded = data.encode("utf-8")
        else:
            encoded = data

    try:
        req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except:
            pass
        log("HTTP %d %s body=%s" % (e.code, url.split("?")[0][-50:], body), xbmc.LOGWARNING)
        if e.code in (401, 403):
            notify("RDFlix", "RD token invalid. Check settings.", xbmcgui.NOTIFICATION_ERROR, 8000)
        return None
    except urllib.error.URLError as e:
        log("URL error: %s" % str(e), xbmc.LOGWARNING)
        return None
    except Exception as e:
        log("Fetch error: %s" % str(e), xbmc.LOGWARNING)
        return None


def _get(path, auth=True):
    return _fetch(RD_API + path, "GET", auth_required=auth)


def _post(path, data=None, auth=True):
    return _fetch(RD_API + path, "POST", data=data, auth_required=auth)


def _delete(path):
    return _fetch(RD_API + path, "DELETE")


def _oauth_fetch(url, data=None):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    encoded = urllib.parse.urlencode(data).encode("utf-8") if data else None
    try:
        req = urllib.request.Request(url, data=encoded, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except Exception as e:
        log("OAuth error: %s" % str(e), xbmc.LOGERROR)
        return None


def get_device_code():
    resp = _oauth_fetch(RD_OAUTH + "/device/code", {"client_id": "X245A4XAIBGVMW", "new_credentials": "yes"})
    if resp:
        return resp.get("device_code"), resp.get("user_code"), resp.get("verification_url")
    return None, None, None


def poll_device_auth(device_code):
    for attempt in range(60):
        resp = _oauth_fetch(RD_OAUTH + "/device/credentials", {"client_id": "X245A4XAIBGVMW", "code": device_code})
        if resp and "client_id" in resp:
            return resp.get("client_id"), resp.get("client_secret")
        if resp and resp.get("error") != "authorization_pending":
            return None, None
        time.sleep(5)
    return None, None


def get_token(client_id, client_secret):
    resp = _oauth_fetch(RD_OAUTH + "/token", {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": client_secret,
        "grant_type": "http://oauth.net/grant_type/device/1.0",
    })
    if resp and "access_token" in resp:
        return resp["access_token"], resp.get("refresh_token", "")
    return None, None


def get_user():
    return _get("/user")


def torrents(page=1, limit=50):
    return _get("/torrents?page=%d&limit=%d" % (page, limit))


def torrent_info(torrent_id):
    return _get("/torrents/info/" + str(torrent_id))


def add_magnet(magnet):
    resp = _post("/torrents/addMagnet", {"magnet": magnet})
    if resp and "id" in resp:
        log("Added magnet: id=%s" % resp["id"])
        return resp["id"]
    if resp and "error" in resp or (resp and "magnet_already_added" in str(resp).lower()):
        log("Add magnet already exists or error")
        return None
    return None


def select_files(torrent_id, file_ids):
    if isinstance(file_ids, list):
        file_ids = ",".join(str(f) for f in file_ids)
    return _post("/torrents/selectFiles/" + str(torrent_id), {"files": str(file_ids)})


def delete_torrent(torrent_id):
    return _delete("/torrents/delete/" + str(torrent_id))


def unrestrict_link(link):
    resp = _post("/unrestrict/link", {"link": link})
    if resp and "download" in resp:
        return resp
    return None


def instant_availability(hashes):
    if isinstance(hashes, str):
        hashes = [hashes]
    h = "/" + "/".join(h[:40].lower() for h in hashes)
    return _get("/torrents/instantAvailability" + h)


def traffic():
    return _get("/traffic")


def user_torrents_list():
    resp = _get("/torrents?limit=250")
    if resp:
        return resp
    return []


def find_cached_torrent(info_hash):
    info_hash = info_hash.lower().strip()[:40]
    existing = user_torrents_list()
    for t in existing:
        if t.get("hash", "").lower() == info_hash:
            if t.get("status") == "downloaded":
                return t
    return None


def get_largest_video_file(files):
    if not files:
        return None
    video_exts = (".mp4", ".mkv", ".avi", ".m4v", ".mov", ".webm", ".ts")
    videos = [f for f in files if f.get("path", "").lower().endswith(video_exts)]
    if not videos:
        videos = [f for f in files if f.get("path", "").lower().endswith((".rar", ".zip"))]
    if not videos:
        videos = files
    videos.sort(key=lambda f: f.get("bytes", 0), reverse=True)
    return videos[0]


def resolve_magnet(magnet, title=""):
    token = _token()
    if not token:
        log("No RD token", xbmc.LOGWARNING)
        return None

    info_hash = ""
    import re
    m = re.search(r"btih:([a-fA-F0-9]{40})", magnet)
    if m:
        info_hash = m.group(1).lower()

    if info_hash:
        cached = find_cached_torrent(info_hash)
        if cached:
            links = cached.get("links", [])
            video = get_largest_video_file(cached.get("files", []))
            if links:
                ul = unrestrict_link(links[0])
                if ul:
                    fn = video.get("path", title or "video.mp4") if video else (title or "video.mp4")
                    log("Resolved from cached torrent")
                    return {"url": ul["download"], "filename": fn}
            elif video and video.get("download"):
                ul = unrestrict_link(video["download"])
                if ul:
                    fn = video.get("path", title or "video.mp4")
                    log("Resolved from cached file")
                    return {"url": ul["download"], "filename": fn}

    torrent_id = add_magnet(magnet)
    if not torrent_id:
        log("Failed to add magnet", xbmc.LOGWARNING)
        return None

    for _ in range(15):
        info = torrent_info(torrent_id)
        if not info:
            time.sleep(1)
            continue

        status = info.get("status", "")
        log("Torrent status: %s" % status)

        if status == "magnet_conversion":
            time.sleep(2)
            continue

        if status == "waiting_files_selection":
            files = info.get("files", [])
            video = get_largest_video_file(files)
            if video:
                select_files(torrent_id, video["id"])
            else:
                select_files(torrent_id, "all")
            time.sleep(1)
            continue

        if status == "downloaded":
            links = info.get("links", [])
            video = get_largest_video_file(info.get("files", []))
            url = None
            if links:
                ul = unrestrict_link(links[0])
                if ul:
                    url = ul["download"]
            elif video and video.get("download"):
                ul = unrestrict_link(video["download"])
                if ul:
                    url = ul["download"]

            if url:
                fn = video.get("path", title or "video.mp4") if video else (title or "video.mp4")
                return {"url": url, "filename": fn}

        if status in ("magnet_error", "error", "virus", "dead"):
            delete_torrent(torrent_id)
            return None

        time.sleep(1)

    delete_torrent(torrent_id)
    return None
