import xbmcgui
import xbmcplugin
import xbmc
import xbmcaddon
import sys
import urllib.request
import urllib.error
import urllib.parse
import re
import xml.etree.ElementTree as ET

HANDLE = int(sys.argv[1])
URL = sys.argv[0]

ADDON = xbmcaddon.Addon('plugin.video.livetv')
SOURCE_TYPE = ADDON.getSetting('source_type').strip() or 'pluto'
M3U_URL = ADDON.getSetting('m3u_url').strip()
UA = ADDON.getSetting('user_agent').strip() or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
COUNTRY = ADDON.getSetting('country_code').strip().upper()

PLUTO_URL = 'https://i.mjh.nz/PlutoTV/us.xml'
PLUTO_STITCHER = 'https://service-stitcher.clusters.pluto.tv/v1/stitch/embed/hls/channel/{id}/master.m3u8?deviceId=channel&deviceModel=web&deviceVersion=1.0&appVersion=1.0&deviceType=rokuChannel&deviceMake=rokuChannel&deviceDNT=1&advertisingId=channel&embedPartner=rokuChannel&appName=rokuchannel&is_lat=1&bmodel=bm1&content=channel&platform=web&tags=ROKU_CONTENT_TAGS&coppa=false&content_type=livefeed&rdid=channel&genre=ROKU_ADS_CONTENT_GENRE&content_rating=ROKU_ADS_CONTENT_RATING&studio_id=viacom&channel_id=channel'

CATEGORY_KEYWORDS = [
    ('Movies', ['movie', 'film', 'cinema', 'thriller', 'horror', 'action', 'western', 'fantasy', 'flicks', 'cult']),
    ('Comedy', ['comedy', 'sitcom', 'funny', 'ridiculous', 'wild', 'laugh', 'sketch', 'fail', 'afv', 'mst3k']),
    ('Drama', ['drama', 'romance', 'love', 'dynasty', 'little house']),
    ('Crime', ['crime', 'mystery', 'detective', 'law', 'csi', 'cops', 'matlock', 'murder', 'blue bloods', 'swat', 'nash']),
    ('Sci-Fi & Fantasy', ['sci-fi', 'sci fi', 'star trek', 'stargate', 'twilight zone', 'x-files', 'doctor who', 'andromeda', 'battlestar', 'monsters']),
    ('News', ['news', 'cnn', 'bloomberg', 'reuters', 'abc news', 'cbs news', 'nbc news']),
    ('Classic TV', ['classic', 'retro', 'rewind', 'throwback', '70s', '80s', '90s', '00s', 'nostalgia', 'gunsmoke', 'bonanza', 'rifleman']),
    ('Reality', ['reality', 'game show', 'competition', 'survivor', 'bachelor']),
    ('Music', ['music', 'mtv', 'vma', 'concert']),
    ('Kids', ['kid', 'cartoon', 'family', 'disney', 'nick', 'pbs']),
    ('Sports', ['sport', 'nfl', 'nba', 'mlb', 'nhl', 'fight', 'wwe', 'aew', 'boxing', 'mma']),
]

def get_url(**kwargs):
    return '{0}?{1}'.format(URL, urllib.parse.urlencode(kwargs))

def log(msg):
    xbmc.log('[LiveTV] %s' % msg, xbmc.LOGINFO)

def _set_isa_props(li, url, headers=None):
    li.setProperty('inputstreamaddon', 'inputstream.adaptive')
    li.setProperty('inputstream.adaptive.manifest_type', 'hls')
    li.setProperty('inputstream.adaptive.max_buffer_size', '52428800')
    if headers:
        h = '&'.join('%s=%s' % (k, urllib.parse.quote(v)) for k, v in headers.items())
        li.setProperty('inputstream.adaptive.stream_headers', h)
    li.setMimeType('application/x-mpegURL')
    li.setContentLookup(False)
    li.setProperty('IsPlayable', 'true')

def fetch_url(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        log('Fetch error: %s' % str(e))
        xbmcgui.Dialog().ok('Live TV', 'Failed to fetch:\n%s' % str(e))
        return None

def get_pluto_channels():
    raw = fetch_url(PLUTO_URL)
    if not raw:
        return {}
    categories = {}
    root = ET.fromstring(raw)
    for ch in root.findall('channel'):
        cid = ch.get('id', '')
        dn = ch.find('display-name')
        name = dn.text.strip() if dn is not None else 'Unknown'
        icon = ch.find('icon')
        logo = icon.get('src', '') if icon is not None else ''
        stream_url = PLUTO_STITCHER.format(id=cid)
        cat = 'Other'
        name_lower = name.lower()
        for cat_name, keywords in CATEGORY_KEYWORDS:
            if any(k in name_lower for k in keywords):
                cat = cat_name
                break
        if cat == 'Other':
            if name.startswith('Pluto TV '):
                cat = name.replace('Pluto TV ', '').split()[0] if name.replace('Pluto TV ', '').strip() else 'Entertainment'
                cat = cat.capitalize()
            elif name.startswith('BET '):
                cat = 'BET'
            elif name.startswith('CBS '):
                cat = 'News'
            elif name.startswith('MTV '):
                cat = 'Music'
            else:
                cat = 'Entertainment'
        categories.setdefault(cat, []).append({
            'name': name,
            'url': stream_url,
            'logo': logo,
        })
    log('Pluto TV: %d categories, %d channels' % (len(categories), sum(len(v) for v in categories.values())))
    return categories

def fetch_m3u():
    raw = fetch_url(M3U_URL)
    return raw

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
            country = ''
            cm = re.search(r'tvg-country="([^"]*)"', line)
            if cm:
                country = cm.group(1).strip().upper()
            if COUNTRY and country and country != COUNTRY:
                i += 1
                while i < len(lines) and lines[i].strip() != '' and not lines[i].strip().startswith('#EXTINF:'):
                    i += 1
                continue
            tvg_logo = ''
            lm = re.search(r'tvg-logo="([^"]*)"', line)
            if lm:
                tvg_logo = lm.group(1)
            name = ''
            nm = re.search(r',(.+)', line)
            if nm:
                name = nm.group(1).strip()
            headers = {}
            i += 1
            while i < len(lines):
                opt = lines[i].strip()
                if opt == '':
                    i += 1
                    continue
                if opt.startswith('#EXTVLCOPT:http-user-agent='):
                    headers['User-Agent'] = opt.split('=', 1)[1]
                    i += 1
                    continue
                if opt.startswith('#EXTVLCOPT:http-referrer='):
                    headers['Referer'] = opt.split('=', 1)[1]
                    i += 1
                    continue
                if opt.startswith('#EXTVLCOPT') or opt.startswith('#KODIPROP'):
                    i += 1
                    continue
                break
            if i < len(lines):
                url = lines[i].strip()
                if url and not url.startswith('#'):
                    if current_group not in categories:
                        categories[current_group] = []
                    categories[current_group].append({
                        'name': name or 'Unknown',
                        'url': url,
                        'logo': tvg_logo,
                        'headers': headers,
                    })
        i += 1
    log('M3U parsed: %d categories, %d channels' % (len(categories), sum(len(v) for v in categories.values())))
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
        _set_isa_props(li, ch['url'], ch.get('headers'))
        items.append((get_url(action='play', url=ch['url'], name=ch['name']), li, False))
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.endOfDirectory(HANDLE)

def play_channel(url, name):
    log('Playing: %s' % url[:100])
    li = xbmcgui.ListItem(path=url, label=name)
    _set_isa_props(li, url)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)

def main():
    try:
        p = dict(urllib.parse.parse_qsl(sys.argv[2].lstrip('?')))
        action = p.get('action', '')
        if action == 'category':
            cat_name = p.get('name', '')
            if SOURCE_TYPE == 'pluto':
                categories = get_pluto_channels()
            else:
                raw = fetch_m3u()
                if not raw:
                    return
                categories = parse_m3u(raw)
            channels = categories.get(cat_name, [])
            if channels:
                show_channels(cat_name, channels)
            else:
                xbmcgui.Dialog().ok('Live TV', 'No channels in "%s"' % cat_name)
        elif action == 'play':
            play_channel(p.get('url', ''), p.get('name', 'Channel'))
        else:
            if SOURCE_TYPE == 'pluto':
                categories = get_pluto_channels()
            else:
                raw = fetch_m3u()
                if not raw:
                    xbmcplugin.endOfDirectory(HANDLE)
                    return
                categories = parse_m3u(raw)
            if not categories:
                msg = 'No channels found. Check your source setting.' if SOURCE_TYPE == 'pluto' else 'No channels found.\nCheck your M3U URL in settings.'
                xbmcgui.Dialog().ok('Live TV', msg)
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