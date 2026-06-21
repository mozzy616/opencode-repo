import sys
import threading
import time
import re
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon

COCO_PATH = xbmcvfs.translatePath("special://home/addons/script.module.cocoscrapers/lib")
if COCO_PATH not in sys.path:
    sys.path.insert(0, COCO_PATH)

HOSTDICT = ['__all__']
HOSTPRDICT = []
SCRAPER_TIMEOUT = 8
GLOBAL_TIMEOUT = 45

_scrapers = None
_scrapers_lock = threading.Lock()
QUALITY_ORDER = {'4K': 0, '1080p': 1, '1080p': 1, '720p': 2, 'SD': 3, 'SCR': 4, 'CAM': 5}
TRACKERS = "&tr=udp://tracker.opentrackr.org:1337/announce&tr=udp://open.stealth.si:80/announce&tr=udp://tracker.torrent.eu.org:451/announce"

_ADDON = None
_silent = False

def set_silent(val):
    global _silent
    _silent = val

def _get_setting(key):
    global _ADDON
    if _ADDON is None:
        _ADDON = xbmcaddon.Addon('plugin.video.streamlord')
    return _ADDON.getSetting(key).strip()

def _detect_quality(name):
    name = name.lower()
    if '2160' in name or '4k' in name or 'uhd' in name:
        return '4K'
    if '1080' in name:
        return '1080p'
    if '720' in name:
        return '720p'
    return 'SD'

def _try_request(url, timeout=10):
    """Try using cocoscrapers client.request for CF bypass, fall back to urllib"""
    try:
        from cocoscrapers.modules import client
        resp = client.request(url, timeout=timeout, flare=True)
        if resp:
            return resp
    except:
        pass
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    except:
        return None

# --- Custom built-in scraper: YTS ---
class yts:
    priority = 8
    pack_capable = False
    hasMovies = True
    hasEpisodes = False
    def __init__(self):
        self.domains = ['yts.mx', 'yts.ag', 'yts.am']
    def sources(self, data, hostDict):
        results = []
        imdb = data.get('imdb', '')
        title = data.get('title', '')
        if not imdb and not title:
            return results
        for domain in self.domains:
            try:
                if imdb:
                    url = "https://%s/api/v2/list_movies.json?query_term=%s" % (domain, imdb)
                else:
                    url = "https://%s/api/v2/list_movies.json?query_term=%s" % (domain, title.replace(' ', '+'))
                resp = _try_request(url, timeout=8)
                if not resp:
                    continue
                import json
                j = json.loads(resp)
                if j.get('status') != 'ok' or not j.get('data', {}).get('movies'):
                    continue
                for m in j['data']['movies']:
                    for t in m.get('torrents', []):
                        quality = t.get('quality', '720p')
                        magnet = "magnet:?xt=urn:btih:%s&dn=%s%s" % (t['hash'], m['title'], TRACKERS)
                        results.append({
                            'hash': t['hash'],
                            'magnet': magnet,
                            'url': magnet,
                            'quality': quality,
                            'seeders': t.get('seeds', 0),
                            'size': t.get('size', ''),
                            '_scraper': 'yts',
                        })
                break
            except:
                continue
        return results

# --- Custom built-in scraper: TPB (The Pirate Bay) ---
class tpb:
    priority = 6
    pack_capable = False
    hasMovies = True
    hasEpisodes = True
    def __init__(self):
        self.api = "https://apibay.org"
    def sources(self, data, hostDict):
        results = []
        is_tv = 'tvshowtitle' in data
        if is_tv:
            title = data.get('tvshowtitle', '')
            season = data.get('season', '1')
            episode = data.get('episode', '1')
            query = "%s S%02dE%02d" % (title, int(season), int(episode))
        else:
            title = data.get('title', '')
            year = data.get('year', '')
            imdb = data.get('imdb', '')
            query = imdb if imdb else "%s %s" % (title, year)
        try:
            url = "%s/q.php?q=%s" % (self.api, query.replace(' ', '+'))
            resp = _try_request(url, timeout=8)
            if not resp:
                return results
            import json
            items = json.loads(resp)
            if not isinstance(items, list):
                return results
            for item in items:
                if item.get('id', '0') == '0':
                    continue
                name = item.get('name', '')
                info_hash = item.get('info_hash', '')
                if not info_hash:
                    continue
                seeders = int(item.get('seeders', 0))
                magnet = "magnet:?xt=urn:btih:%s&dn=%s%s" % (info_hash, name, TRACKERS)
                results.append({
                    'hash': info_hash,
                    'magnet': magnet,
                    'url': magnet,
                    'quality': _detect_quality(name),
                    'seeders': seeders,
                    'size': item.get('size', ''),
                    '_scraper': 'tpb',
                })
        except:
            pass
        return results

# --- Custom built-in scraper: TorrentGalaxy (via galaxy API) ---
class torrentgalaxy_custom:
    priority = 5
    pack_capable = False
    hasMovies = True
    hasEpisodes = True
    def __init__(self):
        self.base = "https://torrentgalaxy.to"
    def sources(self, data, hostDict):
        results = []
        try:
            from cocoscrapers.modules import client
            from cocoscrapers.modules import dom_parser
        except:
            return results
        is_tv = 'tvshowtitle' in data
        if is_tv:
            title = data.get('tvshowtitle', '')
            season = data.get('season', '1')
            episode = data.get('episode', '1')
            query = "%s S%02dE%02d" % (title, int(season), int(episode))
        else:
            title = data.get('title', '')
            year = data.get('year', '')
            query = "%s %s" % (title, year)
        try:
            url = "%s/torrents.php?search=%s" % (self.base, query.replace(' ', '+'))
            html = client.request(url, timeout=10, flare=True)
            if not html:
                return results
            rows = dom_parser.parse_dom(html, 'div', {'class': 'tgxtable'})
            if not rows:
                rows = dom_parser.parse_dom(html, 'div', {'class': 'tgyborder'})
            if not rows:
                return results
            for row in rows[:20]:
                try:
                    links = dom_parser.parse_dom(row, 'a', req='href')
                    magnets = [l for l in links if 'magnet' in l.get('href', '').lower()]
                    if not magnets:
                        continue
                    magnet = magnets[0].get('href', '')
                    name = dom_parser.parse_dom(row, 'a', {'class': 'txlight'})
                    if not name:
                        name = dom_parser.parse_dom(row, 'a', {'class': 'tv'})
                    name = name[0].content if name else ''
                    info_hash = re.search(r'btih:([a-fA-F0-9]+)', magnet)
                    if not info_hash:
                        continue
                    h = info_hash.group(1).lower()
                    seed_str = dom_parser.parse_dom(row, 'span', {'class': 'seed'})
                    seed_str = seed_str or dom_parser.parse_dom(row, 'font', {'class': 'green'})
                    seeders = int(re.search(r'(\d+)', seed_str[0].content).group(1)) if seed_str else 0
                    size_spans = dom_parser.parse_dom(row, 'span')
                    size = size_spans[-1].content.strip() if size_spans else ''
                    results.append({
                        'hash': h,
                        'magnet': magnet,
                        'url': magnet,
                        'quality': _detect_quality(name),
                        'seeders': seeders,
                        'size': size,
                        '_scraper': 'torrentgalaxy',
                    })
                except:
                    continue
        except:
            pass
        return results

# --- Custom built-in scraper: Torrentio Debrid (Real-Debrid / AllDebrid / Premiumize) ---
class torrentio_debrid:
    priority = 7
    pack_capable = False
    hasMovies = True
    hasEpisodes = True
    def __init__(self):
        self.base = "https://torrentio.strem.fun"
        self.movie_url = "/%s=%s/stream/movie/%s.json"
        self.tv_url = "/%s=%s/stream/series/%s:%s:%s.json"
        self._services = [
            ('realdebrid', 'rd_token'),
            ('alldebrid', 'ad_token'),
            ('premiumize', 'pm_token'),
        ]
    def _fetch_json(self, url):
        try:
            from cocoscrapers.modules import client
            resp = client.request(url, timeout=10)
            if resp:
                import json
                return json.loads(resp)
        except:
            pass
        return None
    def _scrape(self, svc_name, token, data):
        results = []
        is_tv = 'tvshowtitle' in data
        imdb = data.get('imdb', '')
        if not imdb:
            return results
        try:
            if is_tv:
                season = data.get('season', '1')
                episode = data.get('episode', '1')
                url = "%s%s" % (self.base, self.tv_url % (svc_name, token, imdb, int(season), int(episode)))
            else:
                url = "%s%s" % (self.base, self.movie_url % (svc_name, token, imdb))
            j = self._fetch_json(url)
            if not j or 'streams' not in j:
                return results
            for s in j['streams']:
                try:
                    info_hash = s.get('infoHash', '')
                    if not info_hash:
                        if 'url' in s:
                            parts = s['url'].split('/')
                            for p in parts:
                                if len(p) == 40 and all(c in '0123456789abcdef' for c in p.lower()):
                                    info_hash = p.lower()
                                    break
                    if not info_hash:
                        continue
                    title_line = s.get('title', '')
                    name = title_line.split('\n')[0] if '\n' in title_line else title_line
                    seeders = 0
                    import re as _re
                    m = _re.search(r'👤\s*(\d+)', title_line)
                    if m:
                        seeders = int(m.group(1))
                    size = ''
                    m2 = _re.search(r'💾\s*([\d.,]+\s*(?:GB|GiB|Gb|MB|MiB|Mb))', title_line)
                    if m2:
                        size = m2.group(1)
                    magnet = "magnet:?xt=urn:btih:%s&dn=%s%s" % (info_hash, name, TRACKERS)
                    results.append({
                        'hash': info_hash,
                        'magnet': magnet,
                        'url': magnet,
                        'quality': _detect_quality(name),
                        'seeders': seeders,
                        'size': size,
                        'name': name,
                        'debrid': True,
                        'cached_checked': 'true',
                        '_scraper': 'torrentio_%s' % svc_name,
                    })
                except:
                    continue
        except:
            pass
        return results
    def sources(self, data, hostDict):
        all_results = []
        for svc_name, setting_key in self._services:
            token = _get_setting(setting_key)
            if token:
                all_results.extend(self._scrape(svc_name, token, data))
        return all_results


def init():
    global _scrapers
    if _scrapers is not None:
        return True
    with _scrapers_lock:
        if _scrapers is not None:
            return True
        scrapers = []
        try:
            import cocoscrapers
            cocoscrapers.enabledCheck = lambda mn: True
            scrapers = cocoscrapers.sources(specified_folders=['torrents']) or []
            xbmc.log("[StreamLord] CocoScrapers: %d torrent scrapers loaded" % len(scrapers), xbmc.LOGINFO)
            # Exclude CocoScrapers debrid scrapers — we use our own (torrentio_debrid)
            exclude = ['torrentio_cached', 'mediafusion_cached', 'comet']
            scrapers = [(n, s) for n, s in scrapers if n not in exclude]
            xbmc.log("[StreamLord] After excluding debrid scrapers: %d" % len(scrapers), xbmc.LOGINFO)
        except Exception as e:
            xbmc.log("[StreamLord] CocoScrapers init failed: %s" % str(e), xbmc.LOGERROR)

        custom_scrapers = [
            ('yts', yts),
            ('tpb', tpb),
            ('torrentgalaxy_custom', torrentgalaxy_custom),
            ('torrentio_debrid', torrentio_debrid),
        ]
        scrapers.extend(custom_scrapers)
        _scrapers = scrapers
        xbmc.log("[StreamLord] Total scrapers (CocoScrapers + custom): %d" % len(_scrapers), xbmc.LOGINFO)
        return len(_scrapers) > 0

def collect_results_movie(progress, imdb, title, year):
    results = []
    threads = []
    lock = threading.Lock()
    total = len(_scrapers)
    data = {'imdb': imdb, 'title': title, 'year': year, 'aliases': []}

    class ScraperRunner(threading.Thread):
        def __init__(self, scraper, name, idx):
            threading.Thread.__init__(self, daemon=True)
            self.scraper = scraper
            self.name = name
            self.idx = idx
        def run(self):
            try:
                if getattr(self.scraper, 'hasMovies', True) == False:
                    return
                xbmc.log("[StreamLord]   scraper %s starting..." % self.name, xbmc.LOGINFO)
                instance = self.scraper()
                srcs = instance.sources(data, HOSTDICT)
                xbmc.log("[StreamLord]   scraper %s returned %d results" % (self.name, len(srcs) if srcs else 0), xbmc.LOGINFO)
                if not srcs:
                    return
                with lock:
                    for s in srcs:
                        s['_scraper'] = self.name
                        results.append(s)
            except Exception as e:
                xbmc.log("[StreamLord]   scraper %s error: %s" % (self.name, str(e)), xbmc.LOGERROR)
            finally:
                if progress:
                    with lock:
                        try:
                            pct = int((min(self.idx + 1, total) / float(total)) * 100)
                            progress.update(pct, "Scraping: %s" % self.name[:20])
                        except:
                            pass

    for idx, (name, scraper) in enumerate(_scrapers):
        t = ScraperRunner(scraper, name, idx)
        t.start()
        threads.append(t)

    deadline = time.time() + GLOBAL_TIMEOUT
    for t in threads:
        if progress and progress.iscanceled():
            break
        remaining = max(0, deadline - time.time())
        t.join(min(remaining, SCRAPER_TIMEOUT))

    return results

def collect_results_episode(progress, imdb, tvshowtitle, title, season, episode, year):
    results = []
    threads = []
    lock = threading.Lock()
    total = len(_scrapers)
    data = {'imdb': imdb, 'tvshowtitle': tvshowtitle, 'title': title, 'season': str(season), 'episode': str(episode), 'year': year, 'aliases': []}

    class ScraperRunner(threading.Thread):
        def __init__(self, scraper, name, idx):
            threading.Thread.__init__(self, daemon=True)
            self.scraper = scraper
            self.name = name
            self.idx = idx
        def run(self):
            try:
                if getattr(self.scraper, 'hasEpisodes', True) == False:
                    return
                xbmc.log("[StreamLord]   scraper %s starting..." % self.name, xbmc.LOGINFO)
                instance = self.scraper()
                srcs = instance.sources(data, HOSTDICT)
                xbmc.log("[StreamLord]   scraper %s returned %d results" % (self.name, len(srcs) if srcs else 0), xbmc.LOGINFO)
                if not srcs:
                    return
                with lock:
                    for s in srcs:
                        s['_scraper'] = self.name
                        results.append(s)
            except Exception as e:
                xbmc.log("[StreamLord]   scraper %s error: %s" % (self.name, str(e)), xbmc.LOGERROR)
            finally:
                if progress:
                    with lock:
                        try:
                            pct = int((min(self.idx + 1, total) / float(total)) * 100)
                            progress.update(pct, "Scraping: %s" % self.name[:20])
                        except:
                            pass

    for idx, (name, scraper) in enumerate(_scrapers):
        t = ScraperRunner(scraper, name, idx)
        t.start()
        threads.append(t)

    deadline = time.time() + GLOBAL_TIMEOUT
    for t in threads:
        if progress and progress.iscanceled():
            break
        remaining = max(0, deadline - time.time())
        t.join(min(remaining, SCRAPER_TIMEOUT))

    return results

def search_movie(imdb, title, year):
    if not init():
        return []
    progress = None
    if not _silent:
        progress = xbmcgui.DialogProgress()
        progress.create("StreamLord", "Searching %d scrapers..." % len(_scrapers))
    try:
        res = collect_results_movie(progress, imdb=imdb, title=title, year=year)
        xbmc.log("[StreamLord] Movie scraper results: %d total" % len(res), xbmc.LOGINFO)
        for r in res:
            q = r.get('quality', '?')
            h = r.get('hash', '')[:12]
            s = r.get('seeders', '?')
            u = r.get('url', '')[:60]
            xbmc.log("[StreamLord]   [%s] hash=%s seeds=%s url=%s" % (q, h, s, u), xbmc.LOGINFO)
        return res
    finally:
        if progress:
            try: progress.close()
            except: pass

def search_episode(imdb, tvshowtitle, title, season, episode, year):
    if not init():
        return []
    progress = None
    if not _silent:
        progress = xbmcgui.DialogProgress()
        progress.create("StreamLord", "Searching %d scrapers..." % len(_scrapers))
    try:
        res = collect_results_episode(progress, imdb=imdb, tvshowtitle=tvshowtitle, title=title, season=str(season), episode=str(episode), year=year)
        xbmc.log("[StreamLord] Episode scraper results: %d total" % len(res), xbmc.LOGINFO)
        for r in res:
            q = r.get('quality', '?')
            h = r.get('hash', '')[:12]
            s = r.get('seeders', '?')
            u = r.get('url', '')[:60]
            xbmc.log("[StreamLord]   [%s] hash=%s seeds=%s url=%s" % (q, h, s, u), xbmc.LOGINFO)
        return res
    finally:
        if progress:
            try: progress.close()
            except: pass
