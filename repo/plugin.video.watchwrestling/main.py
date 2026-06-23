# -*- coding: utf-8 -*-
import xbmcgui
import xbmcplugin
import xbmc
import xbmcvfs
import sys
import os
import re
import base64
import urllib.parse
import urllib.request
from urllib.parse import urlparse

HANDLE = int(sys.argv[1])
URL = sys.argv[0]
PARAMS = sys.argv[2]

BASE = "https://watchwrestling.re"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def get_url(**kwargs):
    return "{}?{}".format(URL, urllib.parse.urlencode(kwargs))

def fetch(url, ref=None):
    try:
        headers = {"User-Agent": USER_AGENT}
        if ref:
            headers["Referer"] = ref
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        xbmc.log("[WatchWrestling] fetch error: %s" % str(e), xbmc.LOGERROR)
        return ""

def parse_params(params):
    p = {}
    if params.startswith("?"):
        params = params[1:]
    for pair in params.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            p[k] = urllib.parse.unquote_plus(v)
    return p

def decode_vision(encoded):
    """Decode Vision plugin base64-encoded URLs (triple encoded)"""
    try:
        decoded = encoded
        for _ in range(5):
            try:
                decoded = base64.b64decode(decoded).decode("utf-8")
                if decoded.startswith("http"):
                    return decoded
            except:
                break
    except:
        pass
    return ""

def list_categories():
    categories = [
        ("WWE", "https://watchwrestling.re/2026/wwe/", "DefaultVideo.png"),
        ("TNA iMPACT Wrestling", "https://watchwrestling.re/2026/tna-impact-wrestling/", "DefaultVideo.png"),
        ("AEW", "https://watchwrestling.re/2026/aew/", "DefaultVideo.png"),
        ("ROH", "https://watchwrestling.re/2026/roh/", "DefaultVideo.png"),
        ("NJPW", "https://watchwrestling.re/2026/njpw-wrestling-shows/", "DefaultVideo.png"),
        ("Stardom", "https://watchwrestling.re/2026/stardom/", "DefaultVideo.png"),
        ("UFC", "https://watchwrestling.re/2026/ufc/", "DefaultVideo.png"),
        ("MMA", "https://watchwrestling.re/2026/mma/", "DefaultVideo.png"),
        ("Bellator", "https://watchwrestling.re/2026/bellator/", "DefaultVideo.png"),
        ("Boxing", "https://watchwrestling.re/2026/boxing/", "DefaultVideo.png"),
        ("NWA Powerrr", "https://watchwrestling.re/2026/nwa-powerrr/", "DefaultVideo.png"),
        ("GCW", "https://watchwrestling.re/2026/gcw/", "DefaultVideo.png"),
        ("[B]WWE Raw[/B]", "https://watchwrestling.re/2026/wwe/wwe-raw/", "DefaultVideo.png"),
        ("[B]WWE SmackDown[/B]", "https://watchwrestling.re/2026/wwe/wwe-smackdown/", "DefaultVideo.png"),
        ("[B]WWE NXT[/B]", "https://watchwrestling.re/2026/wwe/wwe-nxt/", "DefaultVideo.png"),
        ("WWE Pay Per View", "https://watchwrestling.re/2026/wwe/pay-per-view/", "DefaultVideo.png"),
    ]
    for label, url, icon in categories:
        li = xbmcgui.ListItem(label)
        li.setArt({"icon": icon})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="list_posts", url=url, page="1"), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_posts(url, page=1):
    if page > 1:
        url = url.rstrip("/") + "/page/%d/" % int(page)
    html = fetch(url)
    if not html:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Extract posts
    items = re.findall(r'<div id="post-(\d+)"[^>]*class="item cf item-post[^"]*"(.*?)</h2>', html, re.DOTALL)
    for post_id, block in items:
        # Find the link and image
        link_m = re.search(r'<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"', block)
        img_m = re.search(r'<img[^>]*src="([^"]*)"', block)
        summary_m = re.search(r'<p class="entry-summary">(.*?)</p>', block)
        if not link_m:
            continue
        post_url = link_m.group(1)
        title = link_m.group(2)
        thumb = img_m.group(1) if img_m else ""
        summary = summary_m.group(1).strip() if summary_m else ""
        li = xbmcgui.ListItem(label=title)
        if summary:
            li.setInfo("video", {"title": title, "plot": summary})
        if thumb:
            li.setArt({"thumb": thumb})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="post_detail", url=post_url), li, isFolder=True)

    # Pagination
    if page < 50:
        next_m = re.search(r'<a class="next" href="[^"]*page/(\d+)/"', html)
        if next_m:
            next_page = int(next_m.group(1))
            li = xbmcgui.ListItem("[B]Next Page >[/B]")
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action="list_posts", url=url, page=str(next_page)), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def post_detail(url):
    html = fetch(url)
    if not html:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Extract meta
    title_m = re.search(r'<h1 class="entry-title">(.*?)</h1>', html)
    thumb_m = re.search(r'<div id="thumb" class="rich-content">.*?<img[^>]*src="([^"]*)"', html, re.DOTALL)
    cat_m = re.search(r'rel="category tag">([^<]*)<', html)
    title = title_m.group(1).strip() if title_m else "Unknown"
    thumb = thumb_m.group(1) if thumb_m else ""

    # Extract video links with Vision buttons
    # Find all <a data-src="..." with labels
    parts = re.findall(r'<span[^>]*>([^<]*)</span>.*?<br>(.*?)<br><br>', html, re.DOTALL)
    
    # Also find standalone vision buttons
    vision_links = re.findall(r'<a[^>]*data-src="([^"]*)"[^>]*>(.*?)</a>', html)
    
    if vision_links:
        # Group by section labels
        sections = re.findall(r'<span[^>]*>([^<]*)</span>\s*<br>\s*((?:<a[^>]*data-src="[^"]*"[^>]*>.*?</a>\s*<br>\s*)+)', html, re.DOTALL)
        
        if sections:
            for section_label, section_links in sections:
                links_in_section = re.findall(r'<a[^>]*data-src="([^"]*)"[^>]*>(.*?)</a>', section_links)
                for encoded, label in links_in_section:
                    video_url = decode_vision(encoded)
                    if not video_url:
                        continue
                    display = "%s - %s" % (section_label.strip(), label.strip())
                    li = xbmcgui.ListItem(label=display)
                    li.setInfo("video", {"title": display})
                    if thumb:
                        li.setArt({"thumb": thumb})
                    li.setProperty("IsPlayable", "true")
                    li.setPath(video_url)
                    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="resolve_video", url=video_url, title=display), li, isFolder=False)
        else:
            # Single links without sections
            for encoded, label in vision_links:
                video_url = decode_vision(encoded)
                if not video_url:
                    continue
                li = xbmcgui.ListItem(label=label.strip())
                li.setInfo("video", {"title": label.strip()})
                if thumb:
                    li.setArt({"thumb": thumb})
                li.setProperty("IsPlayable", "true")
                li.setPath(video_url)
                xbmcplugin.addDirectoryItem(HANDLE, get_url(action="resolve_video", url=video_url, title=label.strip()), li, isFolder=False)
    elif not vision_links:
        xbmcgui.Dialog().notification("Watch Wrestling", "No video links found", xbmcgui.NOTIFICATION_INFO, 3000)

    xbmcplugin.endOfDirectory(HANDLE)

def fetch_embed(url):
    """Fetch Cloudflare-protected embed page and extract video/iframe URL"""
    html = ""

    # Try browser engine via FlareSolverr
    try:
        import sys
        engine_path = xbmcvfs.translatePath("special://home/addons/service.browserengine/resources/lib")
        if engine_path not in sys.path:
            sys.path.insert(0, engine_path)
        from browserengine import get_engine
        engine = get_engine()
        if engine.ready:
            html = engine.fetch(url, referer=BASE, timeout=60000)
        else:
            html = engine._fallback_fetch(url, referer=BASE)
        if html:
            xbmc.log("[WatchWrestling] Got %d bytes from %s" % (len(html), "FlareSolverr" if engine.ready else "fallback"), xbmc.LOGINFO)
    except Exception as e:
        xbmc.log("[WatchWrestling] Browser engine error: %s" % str(e), xbmc.LOGERROR)

    # Fallback cloudscraper
    if not html or 'window.location.href' in html:
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(url, headers={"Referer": BASE}, timeout=15)
            html = resp.text
        except:
            pass

    # Final fallback
    if not html:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Referer": BASE})
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="replace")
        except:
            return None, None

    # Check for redirect spam
    if 'window.location.href' in html and 'djt2.com/' in html and len(html) < 3000:
        xbmc.log("[WatchWrestling] Got redirect spam, FlareSolverr may be needed", xbmc.LOGWARNING)

    urls = extract_media_urls(html)
    xbmc.log("[WatchWrestling] Extracted %d media URLs" % len(urls), xbmc.LOGINFO)
    if not urls and len(html) > 100:
        # Save full HTML for debugging
        try:
            debug_path = xbmcvfs.translatePath("special://home/userdata/addon_data/plugin.video.watchwrestling/debug.html")
            os.makedirs(os.path.dirname(debug_path), exist_ok=True)
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(html)
            xbmc.log("[WatchWrestling] Saved debug HTML to %s (%d bytes)" % (debug_path, len(html)), xbmc.LOGINFO)
        except:
            pass
    return urls, html

    # Look for iframe
    iframe_m = re.search(r'<iframe[^>]*src="([^"]*)"', html)
    if iframe_m:
        return iframe_m.group(1), html

    # Look for direct video URL
    for pat in [r'src="(https?://[^"]*\.m3u8[^"]*)"', r'src="(https?://[^"]*\.mp4[^"]*)"',
                r'(https?://[^"\'\s]+/manifest[^"\'\s]*\.m3u8[^"\'\s]*)',
                r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)',
                r'(https?://[^"\'\s]+\.mp4[^"\'\s]*)']:
        m = re.search(pat, html)
        if m:
            return m.group(1), html

    return None, html

def extract_media_urls(html):
    """Extract video/embed URLs from embed page HTML"""
    urls = []
    # Standard iframes
    for pat in [
        r'<iframe[^>]*src="((?:https?:)?//[^"]*)"',
        r"<iframe[^>]*src='((?:https?:)?//[^']*)'",
    ]:
        for m in re.finditer(pat, html):
            src = m.group(1)
            if src.startswith("//"):
                src = "https:" + src
            if any(exclude in src.lower() for exclude in ["javascript:", "ads", "cloudflare", "a-ads", "cmp.", "google", "gstatic", "doubleclick", "prebid", "smilewanted", "onetag", "omnitag"]):
                continue
            if not src.startswith("http"):
                continue
            urls.append(src)
    
    # JavaScript video players   
    for pat in [
        r'(?:file|src|source|video|video_url|videoUrl|streamUrl|url)\s*[:=]\s*[\'"](https?://[^\'"]+(?:\.m3u8|\.mp4|\.ts|/manifest)[^\'"]*)[\'"]',
        r'[\'"]((?:https?:)?//[^\'"]*dailymotion[^\'"]*\d+)[\'"]',
        r'[\'"]((?:https?:)?//[^\'"]*dood[^\'"]*(?:/e/|/d/)[^\'"]*)[\'"]',
        r'[\'"]((?:https?:)?//[^\'"]*streamtape[^\'"]*/v/[^\'"]*)[\'"]',
        r'[\'"]((?:https?:)?//[^\'"]*voe\.sx[^\'"]*)[\'"]',
        r'[\'"]((?:https?:)?//[^\'"]*ok\.ru[^\'"]*)[\'"]',
    ]:
        for m in re.finditer(pat, html, re.IGNORECASE):
            u = m.group(1)
            if u.startswith("//"):
                u = "https:" + u
            if u.startswith("http") and u not in urls:
                urls.append(u)

    # Look for base64 encoded URLs or eval-based embeds
    for pat in [r'eval\(.*?\)', r'atob\([\'"]([^\'"]+)[\'"]\)']:
        for m in re.finditer(pat, html):
            # Try to decode base64 strings
            try:
                decoded = base64.b64decode(m.group(1)).decode('utf-8')
                if 'http' in decoded:
                    urls.append(decoded)
            except:
                pass
    
    return urls

def resolve_video(url, title):
    # Try resolveurl first
    try:
        resolved = try_resolveurl(url)
        if resolved:
            play_url(resolved, title)
            return
    except:
        pass

    # Fetch embed page via browser engine
    media_urls, html = fetch_embed(url)
    
    # Follow iframe chain iteratively
    seen = {url}
    queue = media_urls or []
    depth = 0
    xbmc.log("[WatchWrestling] Starting chain with %d URLs" % len(queue), xbmc.LOGINFO)
    for i, qurl in enumerate(queue[:5]):
        xbmc.log("[WatchWrestling] Queue[%d] = %s" % (i, qurl[:120]), xbmc.LOGINFO)
    while queue and depth < 4:
        embed_url = queue.pop(0)
        if embed_url in seen:
            continue
        seen.add(embed_url)
        
        # Already a media file
        if '.m3u8' in embed_url or '.mp4' in embed_url:
            play_url(embed_url, title)
            return
        
        # Try resolveurl
        try:
            resolved = try_resolveurl(embed_url)
            if resolved:
                play_url(resolved, title)
                return
        except:
            pass
        
        # Follow one level deeper
        if any(x in embed_url for x in ['php', '.php', 'embed', 'blog.djt2', 'djshashi', 'dailymotion', 'dood', 'stream', 'play']):
            nested_urls, _ = fetch_embed(embed_url)
            if nested_urls:
                for nu in nested_urls:
                    if nu not in seen:
                        queue.append(nu)
                depth += 1
                xbmc.log("[WatchWrestling] Depth %d: queue size %d" % (depth, len(queue)), xbmc.LOGINFO)

    xbmc.log("[WatchWrestling] No playable URL found after %d levels" % depth, xbmc.LOGINFO)
    xbmcgui.Dialog().notification("Watch Wrestling", "Could not extract video", xbmcgui.NOTIFICATION_INFO, 3000)

def play_url(url, title):
    li = xbmcgui.ListItem(path=url, label=title)
    li.setProperty("IsPlayable", "true")
    if ".m3u8" in url:
        li.setProperty("inputstreamaddon", "inputstream.adaptive")
        li.setProperty("inputstream.adaptive.manifest_type", "hls")
    elif ".mp4" in url:
        li.setProperty("HTTPUserAgent", USER_AGENT)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)

def try_resolveurl(url):
    try:
        import resolveurl
        return resolveurl.resolve(url)
    except:
        pass
    return None

def main():
    p = parse_params(PARAMS)
    a = p.get("action", "")
    if a == "list_posts":
        list_posts(urllib.parse.unquote(p.get("url", "")), int(p.get("page", "1")))
    elif a == "post_detail":
        post_detail(urllib.parse.unquote(p.get("url", "")))
    elif a == "resolve_video":
        resolve_video(urllib.parse.unquote(p.get("url", "")), urllib.parse.unquote(p.get("title", "")))
    else:
        list_categories()

if __name__ == "__main__":
    main()
