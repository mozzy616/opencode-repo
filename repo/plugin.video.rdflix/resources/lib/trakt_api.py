import json
import time
import urllib.request
import urllib.error
import urllib.parse

import xbmc

from resources.lib.kodi_utils import log, get_setting, set_setting, notify

TRAKT_API = "https://api.trakt.tv"
CLIENT_ID = "33ea6bfa2b06c9cfa3e408fc6b4cc30484f31b90733df3508fd09ce512f47982"
CLIENT_SECRET = "4a294afdab95894be977dc79c9715224dc87a4a88d74944507945ca58bf719b2"
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"


def _headers():
    token = get_setting("trakt_token", "")
    return {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": CLIENT_ID,
        "Authorization": "Bearer " + token,
    }


def _fetch(method, path, data=None):
    try:
        url = TRAKT_API + path
        body = json.dumps(data).encode("utf-8") if data else None
        hdrs = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "trakt-api-version": "2",
            "trakt-api-key": CLIENT_ID,
        }
        token = get_setting("trakt_token", "")
        if token:
            hdrs["Authorization"] = "Bearer " + token
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except Exception as e:
        log("Trakt fetch error: %s" % str(e), xbmc.LOGWARNING)
        return None


def get_device_code():
    url = TRAKT_API + "/oauth/device/code"
    data = json.dumps({
        "client_id": CLIENT_ID,
    }).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read().decode("utf-8", errors="replace"))
        return resp.get("device_code"), resp.get("user_code"), resp.get("verification_url")
    except Exception as e:
        log("Trakt device code error: %s" % str(e), xbmc.LOGERROR)
        return None, None, None


def poll_token(device_code):
    url = TRAKT_API + "/oauth/device/token"
    data = json.dumps({
        "code": device_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    for _ in range(120):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as r:
                resp = json.loads(r.read().decode("utf-8", errors="replace"))
            if "access_token" in resp:
                return resp["access_token"], resp.get("refresh_token", "")
            if resp.get("error") == "authorization_pending":
                time.sleep(3)
                continue
            return None, None
        except:
            time.sleep(3)
    return None, None


def scrobble_start(action, imdb_id, title, season=None, episode=None):
    token = get_setting("trakt_token", "")
    if not token:
        return

    data = {}
    if season and episode:
        data["show"] = {"ids": {"imdb": imdb_id}, "title": title}
        data["episode"] = {"season": int(season), "number": int(episode)}
    else:
        data["movie"] = {"ids": {"imdb": imdb_id}, "title": title}

    resp = _fetch("POST", "/scrobble/start", data)
    if resp:
        scrobble_id = resp.get("id", 0)
        return scrobble_id
    return None


def scrobble_stop(scrobble_id):
    token = get_setting("trakt_token", "")
    if not token or not scrobble_id:
        return

    return _fetch("POST", "/scrobble/stop", {
        "id": scrobble_id,
        "progress": 100,
    })


def is_authenticated():
    return bool(get_setting("trakt_token", ""))


def get_watchlist():
    token = get_setting("trakt_token", "")
    if not token:
        return []
    resp = _fetch("GET", "/users/me/watchlist?extended=full")
    if resp and isinstance(resp, list):
        items = []
        for item in resp:
            mtype = item.get("type", "")
            if mtype == "movie":
                movie = item.get("movie", {})
                items.append({
                    "type": "movie",
                    "title": movie.get("title", "Unknown"),
                    "year": movie.get("year", ""),
                    "tmdb_id": movie.get("ids", {}).get("tmdb", ""),
                    "imdb_id": movie.get("ids", {}).get("imdb", ""),
                    "overview": movie.get("overview", ""),
                    "rating": movie.get("rating", 0),
                })
            elif mtype == "show":
                show = item.get("show", {})
                items.append({
                    "type": "show",
                    "title": show.get("title", "Unknown"),
                    "year": show.get("year", ""),
                    "tmdb_id": show.get("ids", {}).get("tmdb", ""),
                    "imdb_id": show.get("ids", {}).get("imdb", ""),
                    "overview": show.get("overview", ""),
                    "rating": show.get("rating", 0),
                })
        return items
    return []
