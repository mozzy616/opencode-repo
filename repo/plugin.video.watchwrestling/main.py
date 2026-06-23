# -*- coding: utf-8 -*-
import xbmcgui
import xbmcplugin
import xbmc
import sys
import re
import base64
import urllib.parse
import urllib.request
from urllib.parse import urlparse
import xbmcgui
import xbmcplugin
import xbmc

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
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="list_posts", url=urllib.parse.quote(url, safe=""), page="1"), li, isFolder=True)
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
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action="post_detail", url=urllib.parse.quote(post_url, safe="")), li, isFolder=True)

    # Pagination
    if page < 50:
        next_m = re.search(r'<a class="next" href="[^"]*page/(\d+)/"', html)
        if next_m:
            next_page = int(next_m.group(1))
            li = xbmcgui.ListItem("[B]Next Page >[/B]")
            xbmcplugin.addDirectoryItem(HANDLE, get_url(action="list_posts", url=urllib.parse.quote(url, safe=""), page=str(next_page)), li, isFolder=True)
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
                    xbmcplugin.addDirectoryItem(HANDLE, get_url(action="resolve_video", url=urllib.parse.quote(video_url, safe=""), title=urllib.parse.quote(display, safe="")), li, isFolder=False)
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
                xbmcplugin.addDirectoryItem(HANDLE, get_url(action="resolve_video", url=urllib.parse.quote(video_url, safe=""), title=urllib.parse.quote(label.strip(), safe="")), li, isFolder=False)
    elif not vision_links:
        xbmcgui.Dialog().notification("Watch Wrestling", "No video links found", xbmcgui.NOTIFICATION_INFO, 3000)

    xbmcplugin.endOfDirectory(HANDLE)

def fetch_embed(url):
    """Fetch Cloudflare-protected embed page and extract video/iframe URL"""
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, headers={"Referer": BASE}, timeout=15)
        html = resp.text
    except:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Referer": BASE})
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="replace")
        except:
            return None, None

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

def resolve_video(url, title):
    try:
        resolved = try_resolveurl(url)
        if resolved:
            li = xbmcgui.ListItem(path=resolved, label=title)
            li.setProperty("IsPlayable", "true")
            if ".m3u8" in resolved:
                li.setProperty("inputstreamaddon", "inputstream.adaptive")
                li.setProperty("inputstream.adaptive.manifest_type", "hls")
            xbmcplugin.setResolvedUrl(HANDLE, True, li)
            return
    except:
        pass

    # Try to fetch the embed page (Cloudflare bypass)
    embed_url, html = fetch_embed(url)
    if embed_url:
        if not embed_url.startswith("http"):
            if embed_url.startswith("//"):
                embed_url = "https:" + embed_url
            elif embed_url.startswith("/"):
                parsed = urlparse(url)
                embed_url = "%s://%s%s" % (parsed.scheme, parsed.netloc, embed_url)
        
        # Try resolveurl on the embed URL
        try:
            resolved = try_resolveurl(embed_url)
            if resolved:
                li = xbmcgui.ListItem(path=resolved, label=title)
                li.setProperty("IsPlayable", "true")
                if ".m3u8" in resolved:
                    li.setProperty("inputstreamaddon", "inputstream.adaptive")
                    li.setProperty("inputstream.adaptive.manifest_type", "hls")
                xbmcplugin.setResolvedUrl(HANDLE, True, li)
                return
        except:
            pass

        # Try following iframe chain
        for _ in range(3):
            nested_url, _ = fetch_embed(embed_url)
            if nested_url:
                try:
                    resolved = try_resolveurl(nested_url)
                    if resolved:
                        li = xbmcgui.ListItem(path=resolved, label=title)
                        li.setProperty("IsPlayable", "true")
                        if ".m3u8" in resolved:
                            li.setProperty("inputstreamaddon", "inputstream.adaptive")
                            li.setProperty("inputstream.adaptive.manifest_type", "hls")
                        xbmcplugin.setResolvedUrl(HANDLE, True, li)
                        return
                except:
                    pass
                embed_url = nested_url
            else:
                break

    # Direct play
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
