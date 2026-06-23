# -*- coding: utf-8 -*-
"""
Browser Engine client module for Kodi addons.
Provides Cloudflare bypass and JavaScript-powered page fetching through FlareSolverr.
"""
import json
import time
import urllib.parse
import urllib.request
import xbmc
import xbmcvfs

PORT = 8191
BASE_URL = "http://127.0.0.1:%d" % PORT

class BrowserEngine:
    def __init__(self):
        self.timeout = 60000
        self.ready = False
        self._check_ready()

    def _check_ready(self):
        try:
            req = urllib.request.Request(BASE_URL + "/v1", method="GET")
            with urllib.request.urlopen(req, timeout=3) as r:
                self.ready = r.status == 200
        except:
            self.ready = False

    def fetch(self, url, referer=None, timeout=30000, wait_for_selector=None):
        if not self.ready:
            xbmc.log("[BrowserEngine] FlareSolverr not ready, using fallback", xbmc.LOGWARNING)
            return self._fallback_fetch(url, referer)

        data = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": timeout,
            "returnOnlyCookies": False,
        }
        if referer:
            data["headers"] = {"Referer": referer}
        if wait_for_selector:
            data["cmd"] = "request.get"
            data["waitForSelector"] = wait_for_selector

        try:
            req = urllib.request.Request(
                BASE_URL + "/v1",
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=max(30, timeout // 1000 + 10)) as r:
                resp = json.loads(r.read().decode("utf-8"))
                if resp.get("status") == "ok":
                    solution = resp.get("solution", {})
                    html = solution.get("response", "")
                    url = solution.get("url", url)
                    return html
                else:
                    xbmc.log("[BrowserEngine] FlareSolverr error: %s" % resp.get("message", ""), xbmc.LOGERROR)
        except Exception as e:
            xbmc.log("[BrowserEngine] FlareSolverr fetch error: %s" % str(e), xbmc.LOGERROR)
        return ""

    def _fallback_fetch(self, url, referer=None):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            if referer:
                headers["Referer"] = referer
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            xbmc.log("[BrowserEngine] Fallback fetch error: %s" % str(e), xbmc.LOGERROR)
            return ""

    def get_cookies(self, url):
        if not self.ready:
            return {}
        data = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 10000,
            "returnOnlyCookies": True,
        }
        try:
            req = urllib.request.Request(
                BASE_URL + "/v1",
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read().decode("utf-8"))
                if resp.get("status") == "ok":
                    solution = resp.get("solution", {})
                    return {c["name"]: c["value"] for c in solution.get("cookies", [])}
        except:
            pass
        return {}

def get_engine():
    return BrowserEngine()
