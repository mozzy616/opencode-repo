import json
import time
import urllib.request
import urllib.error
import urllib.parse

import xbmc

from resources.lib.kodi_utils import log, get_setting

AD_API = "https://api.alldebrid.com/v4"
AGENT = "plugin.video.rdflix"


def _token():
    return get_setting("ad_token", "")


def _fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except Exception as e:
        log("AD fetch error: %s" % str(e), xbmc.LOGWARNING)
        return None


def _url(path, params=None):
    token = _token()
    if not token:
        return None
    if not params:
        params = {}
    params["agent"] = AGENT
    params["apikey"] = token
    qs = urllib.parse.urlencode(params)
    return "%s/%s?%s" % (AD_API, path, qs)


def get_user():
    u = _url("user")
    if not u:
        return None
    return _fetch(u)


def add_magnet(magnet):
    u = _url("magnet/upload", {"magnet": magnet})
    if not u:
        return None
    resp = _fetch(u)
    if resp and resp.get("status") == "success":
        data = resp.get("data", {})
        return data.get("id")
    return None


def magnet_status(magnet_id):
    u = _url("magnet/status", {"id": str(magnet_id)})
    if not u:
        return None
    return _fetch(u)


def unrestrict_link(link):
    u = _url("link/unlock", {"link": link})
    if not u:
        return None
    resp = _fetch(u)
    if resp and resp.get("status") == "success":
        data = resp.get("data", {})
        if data.get("link"):
            return {"download": data["link"], "filename": data.get("filename", "")}
    return None


def resolve_magnet(magnet, title=""):
    token = _token()
    if not token:
        return None

    magnet_id = add_magnet(magnet)
    if not magnet_id:
        return None

    for _ in range(20):
        status = magnet_status(magnet_id)
        if not status:
            time.sleep(1)
            continue
        data = status.get("data", {})
        magnets = data.get("magnets", [])
        if not magnets:
            time.sleep(1)
            continue

        m = magnets[0]
        st = m.get("status", "")

        if st == "Ready":
            links = m.get("links", [])
            if links:
                dl = unrestrict_link(links[0].get("link", ""))
                if dl:
                    return dl
            break

        if st in ("Error", "Dead"):
            break

        time.sleep(1)

    return None
