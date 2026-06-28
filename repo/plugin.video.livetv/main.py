import xbmcgui
import xbmcplugin
import xbmc
import xbmcaddon
import sys
import urllib.request
import urllib.error
import re

HANDLE = int(sys.argv[1])
URL = sys.argv[0]

ADDON = xbmcaddon.Addon('plugin.video.livetv')
M3U_URL = ADDON.getSetting('m3u_url').strip() or 'https://iptv-org.github.io/iptv/countries/us.m3u'
UA = ADDON.getSetting('user_agent').strip() or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

def get_url(**kwargs):
    return '{0}?{1}'.format(URL, urllib.parse.urlencode(kwargs))

def log(msg):
    xbmc.log('[LiveTV] %s' % msg, xbmc.LOGINFO)

def fetch_m3u():
    try:
        req = urllib.request.Request(M3U_URL, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode('utf-8', errors='replace')
        log('Fetched %d bytes from %s' % (len(raw), M3U_URL))
        return raw
    except Exception as e:
        log('Fetch error: %s' % str(e))
        xbmcgui.Dialog().ok('Live TV', 'Failed to fetch playlist:\n%s' % str(e))
        return None

def parse_m3u(raw):
    categories = {}
    lines = raw.splitlines()
    i = 0
    current_group = 'Other'
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            m = re.search(r'group-title="([^"]*)"', line)
            if m:
                current_group = m.group(1) or 'Other'
            tvg_logo = ''
            lm = re.search(r'tvg-logo="([^"]*)"', line)
            if lm:
                tvg_logo = lm.group(1)
            name = ''
            nm = re.search(r',(.+)', line)
            if nm:
                name = nm.group(1).strip()
            i += 1
            while i < len(lines) and (lines[i].strip() == '' or lines[i].strip().startswith('#EXTVLCOPT') or lines[i].strip().startswith('#KODIPROP')):
                i += 1
            if i < len(lines):
                url = lines[i].strip()
                if url and not url.startswith('#'):
                    if current_group not in categories:
                        categories[current_group] = []
                    categories[current_group].append({
                        'name': name or 'Unknown',
                        'url': url,
                        'logo': tvg_logo,
                    })
        i += 1
    log('Parsed %d categories, %d total channels' % (len(categories), sum(len(v) for v in categories.values())))
    return categories

def show_categories(categories):
    sorted_cats = sorted(categories.keys())
    items = []
    for cat in sorted_cats:
        count = len(categories[cat])
        li = xbmcgui.ListItem(label='%s  [COLOR=grey](%d)[/COLOR]' % (cat, count))
        li.setProperty('IsPlayable', 'false')
        items.append((get_url(action='category', name=cat), li, True))
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.endOfDirectory(HANDLE)

def show_channels(cat_name, channels):
    items = []
    for ch in channels:
        li = xbmcgui.ListItem(label=ch['name'])
        if ch['logo']:
            li.setArt({'thumb': ch['logo']})
        li.setProperty('IsPlayable', 'true')
        li.setMimeType('application/x-mpegURL')
        li.setContentLookup(False)
        is_hls = ch['url'].endswith('.m3u8') or '.m3u8' in ch['url']
        if is_hls:
            li.setProperty('inputstreamaddon', 'inputstream.adaptive')
            li.setProperty('inputstream.adaptive.manifest_type', 'hls')
        items.append((get_url(action='play', url=ch['url'], name=ch['name']), li, False))
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.endOfDirectory(HANDLE)

def play_channel(url, name):
    log('Playing: %s' % url[:100])
    li = xbmcgui.ListItem(path=url, label=name)
    li.setProperty('IsPlayable', 'true')
    li.setMimeType('application/x-mpegURL')
    li.setContentLookup(False)
    is_hls = url.endswith('.m3u8') or '.m3u8' in url
    if is_hls:
        li.setProperty('inputstreamaddon', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.manifest_type', 'hls')
    xbmcplugin.setResolvedUrl(HANDLE, True, li)

def main():
    try:
        p = dict(urllib.parse.parse_qsl(sys.argv[2].lstrip('?')))
        action = p.get('action', '')
        if action == 'category':
            cat_name = p.get('name', '')
            raw = fetch_m3u()
            if not raw:
                return
            categories = parse_m3u(raw)
            channels = categories.get(cat_name, [])
            if channels:
                show_channels(cat_name, channels)
            else:
                xbmcgui.Dialog().ok('Live TV', 'No channels found in "%s"' % cat_name)
        elif action == 'play':
            play_channel(p.get('url', ''), p.get('name', 'Channel'))
        else:
            raw = fetch_m3u()
            if not raw:
                xbmcplugin.endOfDirectory(HANDLE)
                return
            categories = parse_m3u(raw)
            if not categories:
                xbmcgui.Dialog().ok('Live TV', 'No channels found in playlist.\nCheck your M3U URL in settings.')
                xbmcplugin.endOfDirectory(HANDLE)
                return
            show_categories(categories)
    except Exception as e:
        import traceback
        log('CRASH: %s\n%s' % (str(e), traceback.format_exc()))
        xbmcgui.Dialog().ok('Live TV Error', str(e))
        xbmcplugin.endOfDirectory(HANDLE)

if __name__ == '__main__':
    main()
