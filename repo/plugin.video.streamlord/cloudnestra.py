import re
import urllib.request
import xbmc

CLOUDNESTRA = "https://cloudnestra.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

SERVER_DOMAINS = {
    "v1": "cloudnestra.com",
    "v2": "cloudnestra.com",
    "v3": "cloudnestra.com",
    "v4": "cloudnestra.com",
    "v5": "cloudnestra.com",
}

def resolve(main_url, opener):
    try:
        prorcp_url = None

        if "cloudnestra.com/rcp/" in main_url:
            xbmc.log("[Cloudnestra] Starting from RCP URL", xbmc.LOGINFO)
            prorcp_url = _rcp_to_prorcp(main_url, opener)

        elif "cloudnestra.com" in main_url and "/prorcp/" in main_url:
            xbmc.log("[Cloudnestra] Starting from prorcp URL", xbmc.LOGINFO)
            prorcp_url = main_url

        elif "streamdb" in main_url:
            xbmc.log("[Cloudnestra] Starting from streamdb URL", xbmc.LOGINFO)
            prorcp_url = _streamdb_to_prorcp(main_url, opener)

        else:
            xbmc.log("[Cloudnestra] Unknown URL type: %s" % main_url[:80], xbmc.LOGWARNING)

        if not prorcp_url:
            xbmc.log("[Cloudnestra] Failed to reach prorcp page", xbmc.LOGWARNING)
            return None

        hls_url = _extract_hls(prorcp_url, opener)
        if hls_url:
            xbmc.log("[Cloudnestra] Resolved HLS: %s" % hls_url[:120], xbmc.LOGINFO)
        else:
            xbmc.log("[Cloudnestra] Failed to extract HLS from prorcp", xbmc.LOGWARNING)
        return hls_url

    except Exception as e:
        xbmc.log("[Cloudnestra] Error: %s" % str(e), xbmc.LOGERROR)
        return None


def resolve_prorcp_direct(prorcp_url, opener):
    return _extract_hls(prorcp_url, opener)


def prorcp_from_rcp_html(rcp_html, rcp_url=None):
    patterns = [
        r"src:\s*'(/prorcp/[^']+)'",
        r'src:\s*"(/prorcp/[^"]+)"',
        r"/prorcp/([a-zA-Z0-9_:]+)",
    ]
    for pat in patterns:
        m = re.search(pat, rcp_html)
        if m:
            path = m.group(1) if m.lastindex == 1 else m.group(0)
            if not path.startswith("/"):
                path = "/prorcp/" + path
            return CLOUDNESTRA + path
    if rcp_url and "/rcp/" in rcp_url:
        prorcp_url = rcp_url.replace("/rcp/", "/prorcp/")
        return prorcp_url
    return None


def _streamdb_to_prorcp(url, opener):
    html = _fetch(url, opener, ref="https://streamlord.to")
    if not html:
        return None

    m = re.search(r'<iframe[^>]*src=["\'](//[^"\']+)["\']', html, re.IGNORECASE)
    if not m:
        return None
    rcp_url = "https:" + m.group(1)
    return _rcp_to_prorcp(rcp_url, opener)


def _rcp_to_prorcp(url, opener):
    html = _fetch(url, opener, ref="https://streamlord.to")
    if not html:
        return None

    m = re.search(r"src:\s*'(/prorcp/[^']+)'", html)
    if m:
        return CLOUDNESTRA + m.group(1)

    m = re.search(r'<iframe[^>]*src=["\'](//[^"\']+)["\']', html, re.IGNORECASE)
    if m:
        return "https:" + m.group(1)

    prorcp_url = url.replace("/rcp/", "/prorcp/")
    return prorcp_url


def _try_turnstile_bypass(rcp_url, opener, embed_url=""):
    return None  # cloudnestra Turnstile is permanently broken (rcp_verify returns 404)


def _extract_hls(prorcp_url, opener):
    html = _fetch(prorcp_url, opener, ref=CLOUDNESTRA)
    if not html:
        return None

    m = re.search(r'Playerjs\(\{.*?file:\s*["\']([^"\']+)["\']', html, re.DOTALL)
    if not m:
        m = re.search(r'https?://[^"\'<>]+\.m3u8[^"\'<>]*', html)
        if not m:
            return None

    raw_url = m.group(1)
    first_url = raw_url.split(" or ")[0].strip()

    for var_name, domain in SERVER_DOMAINS.items():
        placeholder = "{%s}" % var_name
        if placeholder in first_url:
            first_url = first_url.replace(placeholder, domain)

    if "{v" in first_url:
        return None

    return first_url


def _fetch(url, opener, ref=None):
    try:
        hdrs = {"User-Agent": USER_AGENT}
        if ref:
            hdrs["Referer"] = ref
        req = urllib.request.Request(url, headers=hdrs)
        with opener.open(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return ""
