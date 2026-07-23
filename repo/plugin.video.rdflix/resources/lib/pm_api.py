import json
import time
import urllib.request
import urllib.error
import urllib.parse

import xbmc

from resources.lib.kodi_utils import log, get_setting

PM_API = "https://www.premiumize.me/api"


def _token():
    return get_setting("pm_token", "")


def _fetch(url, data=None):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        encoded = None
        if data:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            encoded = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=encoded, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except Exception as e:
        log("PM fetch error: %s" % str(e), xbmc.LOGWARNING)
        return None


def _url(path, params=None):
    token = _token()
    if not token:
        return None
    if not params:
        params = {}
    params["apikey"] = token
    qs = urllib.parse.urlencode(params)
    return "%s/%s?%s" % (PM_API, path, qs)


def get_user():
    u = _url("account/info")
    if not u:
        return None
    resp = _fetch(u)
    if resp and resp.get("status") == "success":
        return resp
    return None


def add_magnet(magnet):
    u = _url("transfer/create", {"src": magnet})
    if not u:
        return None
    resp = _fetch(u)
    if resp and resp.get("status") == "success":
        return resp.get("id")
    return None


def list_transfers():
    u = _url("transfer/list")
    if not u:
        return None
    resp = _fetch(u)
    if resp and resp.get("status") == "success":
        return resp.get("transfers", [])
    return []


def resolve_magnet(magnet, title=""):
    token = _token()
    if not token:
        return None

    transfer_id = add_magnet(magnet)
    if not transfer_id:
        return None

    for _ in range(30):
        transfers = list_transfers()
        if not transfers:
            time.sleep(2)
            continue

        for t in transfers:
            if t.get("id") == transfer_id or t.get("src", "").lower() == magnet.lower():
                status = t.get("status", "")
                if status == "finished":
                    link = t.get("link", "")
                    if link:
                        return {"download": link, "filename": t.get("name", title)}
                    return None
                if status in ("error", "timeout"):
                    return None
        time.sleep(2)

    return None
