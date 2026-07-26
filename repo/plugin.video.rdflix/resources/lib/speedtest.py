import time
import urllib.request

import xbmc

from resources.lib.kodi_utils import log, get_setting
from resources.lib.rd_api import get_user as rd_user
from resources.lib.ad_api import get_user as ad_user


def run_speed_test():
    """Test API response times for each configured debrid service."""
    results = []

    for name, token_key, test_fn in [
        ("Real-Debrid", "rd_token", rd_user),
        ("AllDebrid", "ad_token", ad_user),
        ("Premiumize", "pm_token", _test_pm),
    ]:
        token = get_setting(token_key, "")
        if not token:
            continue

        t0 = time.time()
        try:
            user = test_fn()
            t1 = time.time()
            ms = int((t1 - t0) * 1000)
            username = ""
            premium = False
            if user:
                username = user.get("username", user.get("email", ""))
                if name == "Real-Debrid":
                    premium = user.get("premium", 0) > 0
                elif name == "AllDebrid":
                    premium = user.get("data", user).get("user", {}).get("isPremium", False) if isinstance(user, dict) else False
            results.append({
                "name": name,
                "latency_ms": ms,
                "username": username,
                "premium": premium,
                "active": user is not None,
            })
        except Exception as e:
            results.append({
                "name": name,
                "latency_ms": 0,
                "username": "",
                "premium": False,
                "active": False,
                "error": str(e),
            })

    return results


def _test_pm():
    import json, urllib.request
    token = get_setting("pm_token", "")
    if not token:
        return None
    url = "https://www.premiumize.me/api/account/info?apikey=%s" % token
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read().decode("utf-8", errors="replace"))
            if resp.get("status") == "success":
                return {"username": resp.get("customer_id", ""), "premium": True}
    except:
        pass
    return None
