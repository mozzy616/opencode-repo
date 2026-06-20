import re
import html as _html
import json
import ssl
import http.cookiejar
import urllib.request
from urllib.parse import quote, urlencode
import xbmc

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
BASE = "https://watchwrestling.ae"

CATEGORIES = [
    ("WWE", "wwe53"),
    ("WWE Raw", "wwe-raw50"),
    ("WWE Smackdown", "wwe-smackdown52"),
    ("WWE Main Event", "main-events57"),
    ("WWE NXT", "wwe-nxt-show58"),
    ("WWE PPV", "wwe-ppv60"),
    ("WWE Total Divas", "wwe-totaldvas28"),
    ("AEW", "aew65"),
    ("ROH", "roh24"),
    ("IMPACT Wrestling", "impact-wrestlingss30"),
    ("UFC", "ufc41"),
    ("UFC PPV", "ufc-ppv"),
    ("NJPW", "njpw51"),
    ("Boxing", "boxing"),
    ("Other Wrestling", "other-wrestling30"),
]

def fetch(url, ref=None):
    try:
        hdrs = {"User-Agent": USER_AGENT}
        if ref:
            hdrs["Referer"] = ref
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except:
        return ""

def extract_posts(html):
    results = []
    blocks = re.finditer(r'<div[^>]*class="item[^"]*item-post[^"]*"[^>]*>.*?<h2[^>]*class="entry-title"[^>]*><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
    for m in blocks:
        link = m.group(1)
        title = _html.unescape(re.sub(r'<[^>]+>', '', m.group(2)).strip())
        thumb = ""
        clip_m = re.search(r'<a[^>]*class="clip-link"[^>]*href="[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"', html[m.start():m.end()], re.DOTALL)
        if clip_m:
            thumb = clip_m.group(1)
        if title and link and "watchwrestling.ae" in link:
            results.append({"title": title, "link": link, "thumb": thumb})
    if not results:
        for m in re.finditer(r'<h2[^>]*class="entry-title"[^>]*><a[^>]*href="(https?://watchwrestling\.ae/[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL):
            link = m.group(1)
            title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
            thumb = ""
            before = html[max(0, m.start()-1000):m.start()]
            clip_m = re.search(r'<img[^>]*src="([^"]+)"', before[::-1])
            if clip_m:
                thumb = clip_m.group(1)[::-1]
            else:
                clip_m = re.search(r'<img[^>]*src="([^"]+)"', before)
                if clip_m:
                    thumb = clip_m.group(1)
            if title and link:
                results.append({"title": title, "link": link, "thumb": thumb})
    seen = set()
    deduped = []
    for r in results:
        if r["link"] not in seen:
            seen.add(r["link"])
            deduped.append(r)
    return deduped

def has_next_page(html):
    return bool(re.search(r'<a[^>]*class="next"[^>]*href="[^"]*/page/', html))

def list_category(cat_slug, page=1):
    if page == 1:
        url = "%s/%s/" % (BASE, cat_slug)
    else:
        url = "%s/%s/page/%d/" % (BASE, cat_slug, page)
    html = fetch(url)
    posts = extract_posts(html)
    has_next = has_next_page(html)
    return posts, has_next

def extract_video_links(html):
    m = re.search(r'<textarea[^>]*id=["\']([A-Z0-9]+)["\'][^>]*>(.*?)</textarea>', html, re.DOTALL)
    if not m:
        return []
    textarea_content = m.group(2)
    groups = re.findall(r'<div[^>]*class=["\']episodeRepeater["\'][^>]*>.*?<h1>(.*?)</h1>(.*?)</div>', textarea_content, re.DOTALL)
    parts = []
    for label, links_html in groups:
        links = re.findall(r'href=["\'](https?://snaptik\.ae/read\.php[^"\']+)["\']', links_html)
        for l in links:
            parts.append({"url": l.replace("&amp;", "&"), "label": label.strip()})
    if not parts:
        links = re.findall(r'href=["\'](https?://snaptik\.ae/read\.php[^"\']+)["\']', textarea_content)
        for l in links:
            parts.append({"url": l.replace("&amp;", "&"), "label": ""})
    return parts

def get_post_detail(url):
    html = fetch(url)
    title_m = re.search(r'<h1 class="entry-title">(.*?)</h1>', html)
    title = _html.unescape(title_m.group(1)) if title_m else ""
    thumb_m = re.search(r'<img[^>]*class="size-full[^"]*"[^>]*src="([^"]+)"', html)
    thumb = thumb_m.group(1) if thumb_m else ""
    desc_m = re.search(r'<div class="entry-content[^"]* rich-content">(.*?)</div>', html, re.DOTALL)
    desc = ""
    if desc_m:
        desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()
        desc = _html.unescape(desc)[:500]
    videos = extract_video_links(html)
    return {"title": title, "thumb": thumb, "desc": desc, "videos": videos}

def resolve_dm(video_id):
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT if hasattr(ssl, 'PROTOCOL_TLS_CLIENT') else ssl.PROTOCOL_TLS)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        hdrs = {"User-Agent": USER_AGENT, "Referer": "https://www.dailymotion.com/", "Origin": "https://www.dailymotion.com"}
        url = "https://www.dailymotion.com/player/metadata/video/%s" % video_id
        xbmc.log("[WW] DM metadata: %s" % video_id, xbmc.LOGINFO)
        resp = urllib.request.urlopen(urllib.request.Request(url, headers=hdrs), context=ctx, timeout=10)
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
        quals = data.get("qualities", {})
        auto = quals.get("auto", [{}])[0]
        cdn_url = auto.get("url", "") if isinstance(auto, dict) else auto
        if not cdn_url:
            for quality in ["auto", "1080", "720", "480", "380", "240"]:
                streams = quals.get(quality, [])
                if streams:
                    s = streams[0]
                    cdn_url = s.get("url", "") if isinstance(s, dict) else s
                    if cdn_url:
                        break
        if not cdn_url:
            return None
        # Extract cookies from metadata response and pass to CDN request
        cookies = resp.headers.get_all("Set-Cookie") if hasattr(resp.headers, "get_all") else [resp.headers.get("Set-Cookie")]
        cookie_str = ""
        if cookies:
            parts = []
            for ch in cookies:
                if ch:
                    parts.append(ch.split(";")[0])
            cookie_str = "; ".join(parts)
        xbmc.log("[WW] DM cookies: %s" % cookie_str[:80], xbmc.LOGINFO)
        cdn_hdrs = dict(hdrs)
        if cookie_str:
            cdn_hdrs["Cookie"] = cookie_str
        cdn_resp = urllib.request.urlopen(urllib.request.Request(cdn_url, headers=cdn_hdrs), context=ctx, timeout=10)
        master = cdn_resp.read().decode("utf-8", errors="replace")
        xbmc.log("[WW] DM master: %d bytes" % len(master), xbmc.LOGINFO)
        # Rewrite master: embed audio URI into stream-inf lines
        audio_urls = {}
        for am in re.finditer(r'#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="([^"]+)".*URI="([^"]+)"', master):
            audio_urls[am.group(1)] = am.group(2).replace("\\/", "/")
        lines = master.split("\n")
        new_lines = []
        for line in lines:
            new_lines.append(line)
            if line.startswith("#EXT-X-STREAM-INF:") and "AUDIO=" in line:
                am = re.search(r'AUDIO="([^"]+)"', line)
                if am and am.group(1) in audio_urls:
                    new_lines.append('#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="%s",NAME="audio",DEFAULT=YES,URI="%s"' % (am.group(1), audio_urls[am.group(1)]))
        new_master = "\n".join(new_lines)
        import os, xbmcvfs
        tmp = xbmcvfs.translatePath("special://temp/dm_%s.m3u8" % video_id)
        tmp = tmp.replace("\\", "/")
        with open(tmp, "w") as f:
            f.write(new_master)
        tmp_url = "file:///" + tmp.lstrip("/")
        xbmc.log("[WW] DM local URL: %s" % tmp_url, xbmc.LOGINFO)
        return tmp_url
    except Exception as e:
        xbmc.log("[WW] resolve_dm error: %s" % str(e), xbmc.LOGERROR)
        import traceback
        xbmc.log("[WW] traceback: %s" % traceback.format_exc(), xbmc.LOGERROR)
        return None
        xbmc.log("[WW] CDN URL: %s..." % cdn_url[:80], xbmc.LOGINFO)
        ssl._create_default_https_context = orig
        xbmc.log("[WW] DM master playlist URL: %s..." % cdn_url[:80], xbmc.LOGINFO)
        return cdn_url
    except Exception as e:
        try: ssl._create_default_https_context = orig
        except: pass
        xbmc.log("[WW] resolve_dm error: %s" % str(e), xbmc.LOGERROR)
        import traceback
        xbmc.log("[WW] traceback: %s" % traceback.format_exc(), xbmc.LOGERROR)
        return None

def clean_title(title):
    t = re.sub(r'\s*[–-]+\s*\d+\w+\s+\w+\s+\d{4}$', '', title).strip()
    t = re.sub(r'\s*\[.*?\]\s*$', '', t).strip()
    return t

def resolve_video(url):
    try:
        hdrs = {"User-Agent": USER_AGENT, "Referer": BASE}
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8", errors="replace")
        iframe_m = re.search(r'<iframe[^>]*src=["\']([^"\']+)["\']', data)
        if iframe_m:
            iframe_url = iframe_m.group(1).replace("&amp;", "&")
            if iframe_url.startswith("//"):
                iframe_url = "https:" + iframe_url
            xbmc.log("[WW] iframe URL: %s" % iframe_url[:80], xbmc.LOGINFO)
            ireq = urllib.request.Request(iframe_url, headers={"User-Agent": USER_AGENT, "Referer": url})
            with urllib.request.urlopen(ireq, timeout=15) as iresp:
                idata = iresp.read().decode("utf-8", errors="replace")
            ok_m = re.search(r'((?:https?:)?//(?:www\.)?ok\.ru/videoembed/[^"\'<\s]+)', idata)
            if ok_m:
                url = ok_m.group(1)
                if url.startswith("//"):
                    url = "https:" + url
                # Extract video ID and use OK.ru API directly (bypass resolveurl)
                vid_match = re.search(r'/videoembed/(\d+)', url)
                if vid_match:
                    vid = vid_match.group(1)
                    try:
                        ck_hdrs = {"User-Agent": USER_AGENT, "Referer": iframe_url}
                        cri = urllib.request.Request("http://www.ok.ru/videoembed/%s" % vid, headers=ck_hdrs)
                        with urllib.request.urlopen(cri, timeout=8) as cr:
                            chtml = cr.read().decode("utf-8", errors="replace")
                        mid = re.search(r'data-movie-id="([^"]+)"', chtml)
                        if not mid or mid.group(1) == "null":
                            xbmc.log("[WW] OK.ru video %s not playable" % vid, xbmc.LOGINFO)
                            return None
                        # Try API directly for HLS manifest
                        import urllib.parse as _up, json as _json
                        api_url = "http://www.ok.ru/dk?cmd=videoPlayerMetadata"
                        api_data = _up.urlencode({"mid": mid.group(1)}).encode()
                        areq = urllib.request.Request(api_url, data=api_data, headers=ck_hdrs)
                        with urllib.request.urlopen(areq, timeout=10) as ar:
                            aresult = _json.loads(ar.read().decode("utf-8", errors="replace"))
                        hls_url = aresult.get("hlsManifestUrl", "")
                        if hls_url:
                            xbmc.log("[WW] OK.ru HLS: %s" % hls_url[:80], xbmc.LOGINFO)
                            return {"type": "okru_hls", "url": hls_url}
                    except:
                        xbmc.log("[WW] OK.ru API failed, fallback to resolveurl", xbmc.LOGINFO)
                return {"type": "okru", "url": url}
            # Fallback: try direct video URLs in iframe content
            for pat in [r'file:\s*["\']([^"\']+\.(?:mp4|m3u8)[^"\']*)["\']',
                        r'src:\s*["\']([^"\']+\.(?:mp4|m3u8)[^"\']*)["\']',
                        r'(https?://[^"\'<\s]+\.(?:mp4|m3u8)[^"\'<\s]*)']:
                vm = re.search(pat, idata, re.IGNORECASE)
                if vm:
                    durl = vm.group(1).replace("\\/", "/")
                    if durl.startswith("//"):
                        durl = "https:" + durl
                    xbmc.log("[WW] Direct URL found: %s" % durl[:80], xbmc.LOGINFO)
                    return {"type": "direct", "url": durl}
            # Fallback: try resolveurl on iframe URL
            xbmc.log("[WW] Trying resolveurl on iframe: %s" % iframe_url[:80], xbmc.LOGINFO)
            return {"type": "embed", "url": iframe_url}
    except:
        pass
    return None
