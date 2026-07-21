import sys
import threading
import time
import re
import json
import urllib.request
import urllib.error

import xbmc
import xbmcvfs
import xbmcaddon

from resources.lib.constants import ADDON_ID, USER_AGENT, LOG_PREFIX, QUALITY_ORDER
from resources.lib.kodi_utils import log, get_setting

TRACKERS = "&tr=udp://tracker.opentrackr.org:1337/announce&tr=udp://open.stealth.si:80/announce&tr=udp://tracker.torrent.eu.org:451/announce"

TRY_COCO = False
COCO_PATH = xbmcvfs.translatePath("special://home/addons/script.module.cocoscrapers/lib")
if COCO_PATH not in sys.path:
    sys.path.insert(0, COCO_PATH)

try:
    import cocoscrapers
    from cocoscrapers.modules import client as cc_client
    TRY_COCO = True
    log("CocoScrapers loaded")
except Exception as e:
    log("CocoScrapers not available: %s" % str(e), xbmc.LOGWARNING)


_scrapers = None
_scrapers_lock = threading.Lock()
HOSTDICT = ['__all__']
SCRAPER_TIMEOUT = 10
GLOBAL_TIMEOUT = 30


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
    try:
        if TRY_COCO:
            resp = cc_client.request(url, timeout=timeout, flare=True)
            if resp:
                return resp
    except:
        pass
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    except:
        return None


class TPBScraper:
    def __init__(self):
        self.api = "https://apibay.org"

    def search(self, is_tv, imdb, title, year, tvshowtitle, season, episode):
        results = []
        if is_tv:
            s = int(season) if season else 1
            e = int(episode) if episode else 1
            query = "%s S%02dE%02d" % (tvshowtitle, s, e)
        else:
            query = imdb if imdb else "%s %s" % (title, year)

        try:
            url = "%s/q.php?q=%s" % (self.api, urllib.request.quote(query.replace(' ', '+')))
            resp = _try_request(url, timeout=8)
            if not resp:
                return results
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
                    'name': name,
                    'quality': _detect_quality(name),
                    'seeders': seeders,
                    'size': item.get('size', ''),
                })
        except Exception as e:
            log("TPB error: %s" % str(e), xbmc.LOGERROR)
        return results


class YTSScraper:
    def __init__(self):
        self.domains = ['yts.mx', 'yts.ag', 'yts.am']

    def search(self, imdb, title):
        results = []
        if not imdb and not title:
            return results
        for domain in self.domains:
            try:
                if imdb:
                    url = "https://%s/api/v2/list_movies.json?query_term=%s" % (domain, imdb)
                else:
                    url = "https://%s/api/v2/list_movies.json?query_term=%s" % (domain, urllib.request.quote(title))
                resp = _try_request(url, timeout=8)
                if not resp:
                    continue
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
                            'name': m['title'] + ' ' + quality,
                            'quality': quality,
                            'seeders': t.get('seeds', 0),
                            'size': t.get('size', ''),
                        })
                break
            except:
                continue
        return results


class TorrentsCSVScraper:
    """Torrents-CSV API scraper - returns JSON with info_hash directly."""

    def search(self, is_tv, imdb, title, year, tvshowtitle, season, episode):
        results = []
        if is_tv:
            s = int(season) if season else 1
            e = int(episode) if episode else 1
            query = "%s S%02dE%02d" % (tvshowtitle, s, e)
        else:
            query = "%s %s" % (title, year) if year else title

        try:
            url = "https://torrents-csv.com/service/search?q=%s&size=30" % urllib.request.quote(query)
            resp = _try_request(url, timeout=10)
            if not resp:
                return results

            data = json.loads(resp)
            torrents = data.get("torrents", [])
            if not isinstance(torrents, list):
                return results

            for item in torrents:
                name = item.get("name", "")
                info_hash = item.get("infohash", "")
                if not info_hash or not name:
                    continue
                seeders = item.get("seeders", 0)
                if isinstance(seeders, str):
                    try:
                        seeders = int(seeders)
                    except:
                        seeders = 0
                size_bytes = item.get("size_bytes", 0)
                size_str = ""
                if size_bytes:
                    if size_bytes >= 1073741824:
                        size_str = "%.1f GB" % (size_bytes / 1073741824)
                    elif size_bytes >= 1048576:
                        size_str = "%.0f MB" % (size_bytes / 1048576)
                    else:
                        size_str = "%.0f KB" % (size_bytes / 1024)

                magnet = "magnet:?xt=urn:btih:%s&dn=%s%s" % (info_hash, urllib.request.quote(name), TRACKERS)
                results.append({
                    'hash': info_hash,
                    'magnet': magnet,
                    'name': name,
                    'quality': _detect_quality(name),
                    'seeders': seeders,
                    'size': size_str,
                })
        except Exception as e:
            log("TorrentsCSV error: %s" % str(e), xbmc.LOGERROR)
        return results


class EZTVScraper:
    """EZTV API - TV show torrents by IMDB ID."""

    BASE_URL = "https://eztvx.to"

    def search(self, imdb, tvshowtitle, season, episode):
        results = []
        if not imdb:
            return results

        try:
            url = "%s/api/get-torrents?imdb_id=%s&limit=50" % (self.BASE_URL, imdb)
            resp = _try_request(url, timeout=10)
            if not resp:
                return results
            data = json.loads(resp)
            torrents = data.get("torrents", [])
            if not isinstance(torrents, list):
                return results

            s_int = int(season) if season else 0
            e_int = int(episode) if episode else 0

            for item in torrents:
                name = item.get("filename", item.get("title", ""))
                info_hash = item.get("hash", "")
                if not info_hash or not name:
                    continue

                item_season = str(item.get("season", ""))
                item_episode = str(item.get("episode", ""))

                if s_int > 0 and item_season and item_episode:
                    if str(s_int) != item_season or str(e_int) != item_episode:
                        continue

                seeders = item.get("seeds", 0)
                size_bytes = str(item.get("size_bytes", "0"))
                size_str = ""
                try:
                    sb = int(size_bytes)
                    if sb >= 1073741824:
                        size_str = "%.1f GB" % (sb / 1073741824)
                    elif sb >= 1048576:
                        size_str = "%.0f MB" % (sb / 1048576)
                except:
                    pass

                magnet = item.get("magnet_url", "")
                if not magnet and info_hash:
                    magnet = "magnet:?xt=urn:btih:%s&dn=%s%s" % (info_hash, urllib.request.quote(name), TRACKERS)

                results.append({
                    'hash': info_hash,
                    'magnet': magnet,
                    'name': name,
                    'quality': _detect_quality(name),
                    'seeders': seeders,
                    'size': size_str,
                })
        except Exception as e:
            log("EZTV error: %s" % str(e), xbmc.LOGERROR)
        return results


class KnabenScraper:
    """Knaben API - aggregate search across TPB, 1337x, Nyaa, etc."""

    BASE_URL = "https://api.knaben.org/v1"

    def search(self, is_tv, imdb, title, year, tvshowtitle, season, episode):
        results = []
        if is_tv:
            s = int(season) if season else 1
            e = int(episode) if episode else 1
            query = "%s S%02dE%02d" % (tvshowtitle, s, e)
            categories = [2000000]  # TV
        else:
            query = "%s %s" % (title, year) if year else title
            categories = [3000000]  # Movies

        try:
            body = json.dumps({
                "query": query,
                "categories": categories,
                "size": 30,
                "order_by": "seeders",
                "order_direction": "desc",
            }).encode("utf-8")

            req = urllib.request.Request(
                self.BASE_URL,
                data=body,
                headers={
                    "User-Agent": USER_AGENT,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))

            hits = data.get("hits", [])
            if not isinstance(hits, list):
                return results

            for item in hits:
                name = item.get("title", "")
                info_hash = item.get("hash", "")
                magnet = item.get("magnetUrl", "")
                if not info_hash and not magnet:
                    continue
                if not info_hash and magnet:
                    m = re.search(r"btih:([a-fA-F0-9]{40})", magnet)
                    if m:
                        info_hash = m.group(1)

                seeders = item.get("seeders", 0)
                size_bytes = item.get("bytes", 0) or 0
                size_str = ""
                if size_bytes:
                    if size_bytes >= 1073741824:
                        size_str = "%.1f GB" % (size_bytes / 1073741824)
                    elif size_bytes >= 1048576:
                        size_str = "%.0f MB" % (size_bytes / 1048576)

                if not magnet and info_hash:
                    magnet = "magnet:?xt=urn:btih:%s&dn=%s%s" % (info_hash, urllib.request.quote(name), TRACKERS)

                results.append({
                    'hash': info_hash,
                    'magnet': magnet,
                    'name': name,
                    'quality': _detect_quality(name),
                    'seeders': seeders,
                    'size': size_str,
                })
        except Exception as e:
            log("Knaben error: %s" % str(e), xbmc.LOGERROR)
        return results


def _load_coco_scrapers():
    global _scrapers
    if _scrapers is not None:
        return True
    with _scrapers_lock:
        if _scrapers is not None:
            return True
        scrapers = []
        if TRY_COCO:
            try:
                cocoscrapers.enabledCheck = lambda mn: True
                scrapers = cocoscrapers.sources(specified_folders=['torrents']) or []
                exclude = ['torrentio_cached', 'mediafusion_cached', 'comet']
                scrapers = [(n, s) for n, s in scrapers if n not in exclude]
                log("CocoScrapers: %d scrapers loaded" % len(scrapers))
            except Exception as e:
                log("CocoScrapers init failed: %s" % str(e), xbmc.LOGERROR)
        _scrapers = scrapers
        return len(_scrapers) > 0


def _collect_coco(imdb, title, year, tvshowtitle, season, episode, is_tv):
    if not _load_coco_scrapers():
        return []

    results = []
    lock = threading.Lock()

    data = {
        'imdb': imdb or '',
        'title': title or '',
        'year': year or '',
        'aliases': [],
    }
    if is_tv:
        data['tvshowtitle'] = tvshowtitle or ''
        data['season'] = str(season)
        data['episode'] = str(episode)

    thread_count = 0

    def run_scraper(scraper_class, name):
        nonlocal thread_count
        try:
            if is_tv:
                if getattr(scraper_class, 'hasEpisodes', True) == False:
                    return
            else:
                if getattr(scraper_class, 'hasMovies', True) == False:
                    return
            instance = scraper_class()
            srcs = instance.sources(data, HOSTDICT)
            if srcs:
                with lock:
                    for s in srcs:
                        results.append(s)
        except Exception as e:
            log("Scraper %s error: %s" % (name, str(e)), xbmc.LOGWARNING)

    threads = []
    for idx, (name, scraper_class) in enumerate(_scrapers):
        t = threading.Thread(target=run_scraper, args=(scraper_class, name), daemon=True)
        t.start()
        threads.append(t)
        thread_count += 1

    deadline = time.time() + GLOBAL_TIMEOUT
    for t in threads:
        remaining = max(0, deadline - time.time())
        t.join(min(remaining, SCRAPER_TIMEOUT))

    log("CocoScrapers: %d results from %d threads" % (len(results), thread_count))
    return results


def search_movie(imdb, title, year):
    all_results = []

    # 1. CocoScrapers
    coco_results = _collect_coco(imdb, title, year, '', '', '', False)
    for r in coco_results:
        h = r.get('hash', '') or ''
        all_results.append({
            'hash': h[:40].lower(),
            'magnet': r.get('magnet') or r.get('url', ''),
            'name': r.get('name', ''),
            'quality': r.get('quality', _detect_quality(r.get('name', ''))),
            'seeders': int(r.get('seeders', 0)),
            'size': str(r.get('size', '')),
            'debrid': r.get('debrid', False),
        })

    # 2. TPB
    tpb = TPBScraper()
    tpb_results = tpb.search(False, imdb, title, year, '', '', '')
    all_results.extend(tpb_results)

    # 3. YTS (movies only)
    yts = YTSScraper()
    yts_results = yts.search(imdb, title)
    all_results.extend(yts_results)

    # 4. TorrentsCSV
    csv_scraper = TorrentsCSVScraper()
    csv_results = csv_scraper.search(False, imdb, title, year, '', '', '')
    all_results.extend(csv_results)

    # 5. Knaben
    knaben = KnabenScraper()
    knaben_results = knaben.search(False, imdb, title, year, '', '', '')
    all_results.extend(knaben_results)

    # Deduplicate by hash
    seen = set()
    deduped = []
    for r in all_results:
        h = r.get('hash', '')
        if h and h not in seen:
            seen.add(h)
            deduped.append(r)
        elif not h:
            deduped.append(r)

    log("search_movie: %d total results" % len(deduped))
    return deduped


def search_episode(imdb, tvshowtitle, season, episode, year):
    all_results = []

    # 1. CocoScrapers
    coco_results = _collect_coco(imdb, '', year, tvshowtitle, season, episode, True)
    for r in coco_results:
        h = r.get('hash', '') or ''
        all_results.append({
            'hash': h[:40].lower(),
            'magnet': r.get('magnet') or r.get('url', ''),
            'name': r.get('name', ''),
            'quality': r.get('quality', _detect_quality(r.get('name', ''))),
            'seeders': int(r.get('seeders', 0)),
            'size': str(r.get('size', '')),
            'debrid': r.get('debrid', False),
        })

    # 2. TPB
    tpb = TPBScraper()
    tpb_results = tpb.search(True, imdb, '', year, tvshowtitle, season, episode)
    all_results.extend(tpb_results)

    # 3. TorrentsCSV
    csv_scraper = TorrentsCSVScraper()
    csv_results = csv_scraper.search(True, imdb, '', year, tvshowtitle, season, episode)
    all_results.extend(csv_results)

    # 4. EZTV (TV only, by IMDB ID)
    eztv = EZTVScraper()
    eztv_results = eztv.search(imdb, tvshowtitle, season, episode)
    all_results.extend(eztv_results)

    # 5. Knaben
    knaben = KnabenScraper()
    knaben_results = knaben.search(True, imdb, '', year, tvshowtitle, season, episode)
    all_results.extend(knaben_results)

    # Deduplicate by hash
    seen = set()
    deduped = []
    for r in all_results:
        h = r.get('hash', '')
        if h and h not in seen:
            seen.add(h)
            deduped.append(r)
        elif not h:
            deduped.append(r)

    log("search_episode: %d total results" % len(deduped))
    return deduped
