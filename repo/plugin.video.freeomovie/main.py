import xbmcgui, xbmcplugin, xbmc, xbmcvfs, sys
import re, os, time, urllib.request, urllib.parse

HANDLE = int(sys.argv[1])
URL = sys.argv[0]
PARAMS = sys.argv[2]
BASE = "https://www.freeomovie.to"
UA = "Mozilla/5.0"

# Load resolveurl
try:
    for mod, sub in [("script.module.six","lib"),("script.module.kodi-six","libs"),("script.module.resolveurl","lib")]:
        p = xbmcvfs.translatePath("special://home/addons/%s/%s" % (mod,sub))
        if p not in sys.path: sys.path.insert(0, p)
    import resolveurl
    HAS_RESOLVE = True
except:
    HAS_RESOLVE = False

def fetch(u):
    try:
        r = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        xbmc.log("[Freeomovie] fetch: %s" % e, xbmc.LOGERROR)
        return ""

def get_url(**kw):
    return "%s?%s" % (URL, urllib.parse.urlencode(kw))

def parse(p):
    d = {}
    if p and p.startswith("?"): p = p[1:]
    if p:
        for part in p.split("&"):
            if "=" in part: k, v = part.split("=", 1); d[k] = urllib.parse.unquote(v)
    return d

def menu():
    for l, a in [("[B]Latest[/B]", "latest"), ("[B]Categories[/B]", "cats"), ("[B]Search[/B]", "search")]:
        li = xbmcgui.ListItem(l); li.setArt({"icon": "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(mode=a), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_videos(page_url, page=1):
    if page > 1: page_url += "page/%d/" % page
    h = fetch(page_url)
    if not h:
        xbmcplugin.endOfDirectory(HANDLE); return

    # Extract video items from grid
    items = re.findall(r'<a href="(https://www\.freeomovie\.to/[^"]+?)"[^>]*title="([^"]*)"', h)
    seen = set()
    for link, title in items:
        if link in seen or "/page/" in link or "/category/" in link: continue
        seen.add(link)
        thumb = ""
        tm = re.search(r'%s.*?src="([^"]+)"' % re.escape(link.split("/")[-2]), h[:h.find(link)+1000], re.DOTALL)
        if not tm: tm = re.search(r'%s.*?data-src="([^"]+)"' % re.escape(link.split("/")[-2]), h, re.DOTALL)
        if tm: thumb = tm.group(1)
        dur = ""; q = ""
        dm = re.search(r'<span[^>]*class="duration[^"]*"[^>]*>([^<]+)<', h)
        if dm: dur = dm.group(1)
        li = xbmcgui.ListItem(title.strip())
        li.setInfo("video", {"title": title.strip()})
        if thumb: li.setArt({"thumb": thumb, "icon": "DefaultVideo.png"})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(mode="play", url=link, title=title), li, isFolder=False)

    # Next page
    if re.search(r'rel="next" href="([^"]+)"', h):
        li = xbmcgui.ListItem("[B]Next Page >[/B]")
        xbmcplugin.addDirectoryItem(HANDLE, get_url(mode="list", page_url=page_url, page=page+1), li, isFolder=True)
    xbmcplugin.setContent(HANDLE, "videos")
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)

def list_categories():
    h = fetch(BASE)
    if not h:
        xbmcplugin.endOfDirectory(HANDLE); return
    cats = re.findall(r'href="(https://www\.freeomovie\.to/category/[^"]+)"[^>]*>([^<]+)<', h)
    seen = set()
    for link, name in cats:
        if link in seen: continue
        seen.add(link)
        li = xbmcgui.ListItem(name.strip()); li.setArt({"icon": "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(mode="list", page_url=link), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def do_search():
    kb = xbmc.Keyboard("", "Search Freeomovie...")
    kb.doModal()
    if kb.isConfirmed() and kb.getText():
        q = kb.getText().strip()
        list_videos(BASE + "/?s=%s&" % urllib.parse.quote(q, safe=''))

def play_video(purl, title):
    h = fetch(purl)
    if not h:
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem()); return

    # Find all video source URLs
    sources = []
    # Direct URLs in the page content
    for s in re.findall(r'https?://[^\s"\'<>\[\]\(\)]+\.(?:mp4|m3u8)[^\s"\'<>\[\]\(\)]*', h):
        if s not in sources: sources.append(s)
    # Embed URLs (doodstream, voe.sx, mixdrop, playmogo, player4me, etc.)
    for s in re.findall(r'https?://(?:doodstream\.com|voe\.sx|mixdrop|playmogo|player4me|mxdrop|streamtape|streamwish|vidmoly|vidara|luluvid|luluvdo|lulustream|streamhide|vidoza)\.\S+/[^\s"\'<>\[\]\(\)]+', h):
        if s not in sources: sources.append(s)

    if not sources:
        xbmcgui.Dialog().notification("Freeomovie", "No sources found", xbmcgui.NOTIFICATION_ERROR, 3000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem()); return

    # Ask play or download
    idx = xbmcgui.Dialog().select(title[:50], ["Play"] + ["Download: %s" % s[:40] for s in sources])
    if idx < 0:
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem()); return

    if idx == 0:
        # Play - try resolveurl for each source
        for src in sources:
            if HAS_RESOLVE:
                try:
                    hmf = resolveurl.HostedMediaFile(url=src, include_disabled=True, include_universal=False)
                    if hmf.valid_url():
                        resolved = hmf.resolve()
                        if resolved and resolved != src and not resolved.startswith("plugin://"):
                            li = xbmcgui.ListItem(path=resolved, label=title)
                            li.setProperty("IsPlayable", "true")
                            if ".m3u8" in resolved: li.setMimeType("application/vnd.apple.mpegurl")
                            else: li.setMimeType("video/mp4")
                            li.setContentLookup(False)
                            xbmcplugin.setResolvedUrl(HANDLE, True, li)
                            return
                except: pass
            # Fallback: direct play
            li = xbmcgui.ListItem(path=src, label=title)
            li.setProperty("IsPlayable", "true")
            if ".m3u8" in src: li.setMimeType("application/vnd.apple.mpegurl")
            else: li.setMimeType("video/mp4")
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(HANDLE, True, li)
            return
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
    else:
        # Download - resolve embed URL first to get direct video URL
        dl_url = sources[idx - 1]
        if HAS_RESOLVE:
            try:
                hmf = resolveurl.HostedMediaFile(url=dl_url, include_disabled=True, include_universal=False)
                if hmf.valid_url():
                    resolved = hmf.resolve()
                    if resolved and resolved != dl_url and not resolved.startswith("plugin://"):
                        dl_url = resolved
            except: pass

        dest = xbmcgui.Dialog().browse(0, "Choose download folder", "files", "", False, True,
                                       xbmcvfs.translatePath("special://home/downloads/"))
        if dest:
            safe = re.sub(r'[<>:"/\\|?*]', '', title)[:100]
            ext = ".mp4" if ".mp4" in dl_url else ".mkv" if ".mkv" in dl_url else ".mp4"
            out = os.path.join(dest, safe + ext)
            prog = xbmcgui.DialogProgress()
            prog.create("Freeomovie", "Downloading...")
            try:
                req = urllib.request.Request(dl_url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=600) as srcf:
                    total = int(srcf.headers.get("Content-Length", 0))
                    with open(out, "wb") as f:
                        wrote = 0
                        while not prog.iscanceled():
                            chunk = srcf.read(65536)
                            if not chunk: break
                            f.write(chunk); wrote += len(chunk)
                            if total: prog.update(int(wrote*100/total), "%d/%d MB" % (wrote//1048576, total//1048576))
                prog.close()
                xbmcgui.Dialog().notification("Done", safe + ext, xbmcgui.NOTIFICATION_INFO, 5000)
            except Exception as e:
                prog.close(); xbmcgui.Dialog().ok("Error", str(e))
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())

def main():
    p = parse(PARAMS)
    m = p.get("mode", "")
    if m == "latest": list_videos(BASE + "/")
    elif m == "list": list_videos(p.get("page_url", ""), int(p.get("page", "1")))
    elif m == "cats": list_categories()
    elif m == "search": do_search()
    elif m == "play": play_video(p.get("url", ""), p.get("title", ""))
    else: menu()

if __name__ == "__main__": main()
