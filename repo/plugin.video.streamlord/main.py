def auth_rd_device():
    import time, xbmcaddon
    client_id = "X245A4XAIBGVM"
    try:
        url = "https://api.real-debrid.com/oauth/v2/device/code?client_id=%s&new_credentials=yes" % client_id
        req = urllib.request.Request(url, headers={"User-Agent": "Kodi/21"})
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
    except Exception as e:
        xbmcgui.Dialog().ok("Error", "Could not connect to RD. " + str(e))
        return

    device_code = result.get("device_code", "")
    user_code = result.get("user_code", "")
    direct_url = result.get("direct_verification_url", "https://real-debrid.com/device")

    xbmcgui.Dialog().ok("Authorize Real-Debrid",
                         "1. Open: %s" % direct_url,
                         "2. Enter code: %s" % user_code,
                         "",
                         "Press OK when done.")

    for attempt in range(60):
        xbmc.sleep(2000)
        try:
            poll_url = "https://api.real-debrid.com/oauth/v2/device/credentials?client_id=%s&code=%s" % (client_id, device_code)
            req = urllib.request.Request(poll_url, headers={"User-Agent": "Kodi/21"})
            with urllib.request.urlopen(req, timeout=15) as r:
                creds = json.loads(r.read())
            if creds.get("client_secret"):
                # Exchange for actual access token
                token = _exchange_rd_token(creds.get("client_id", client_id), creds["client_secret"], device_code)
                if not token:
                    token = creds["client_secret"]
                xbmcaddon.Addon('plugin.video.streamlord').setSetting('rd_token', token)
                try:
                    cache = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.streamlord/rd.txt")
                    os.makedirs(os.path.dirname(cache), exist_ok=True)
                    with open(cache, "w") as f:
                        f.write(token)
                except:
                    pass
                xbmcgui.Dialog().ok("Success!", "Real-Debrid linked!")
                return
        except:
            pass
    xbmcgui.Dialog().ok("Timeout", "Authorization timed out. Try again.")
    xbmcplugin.endOfDirectory(HANDLE, updateListing=True)

def _exchange_rd_token(client_id, client_secret, device_code):
    """Exchange OAuth creds for REST API access token."""
    try:
        url = "https://api.real-debrid.com/oauth/v2/token"
        data = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "code": device_code,
            "grant_type": "http://oauth.net/grant_type/device/1.0"
        }).encode()
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/x-www-form-urlencoded",
                                              "User-Agent": "Kodi/21"})
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
            if result.get("access_token"):
                return result["access_token"]
            if result.get("token"):
                return result["token"]
    except:
        pass
    return None