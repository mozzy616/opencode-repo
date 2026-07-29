import os
import urllib.request
import urllib.parse
import json
import time
import threading
import xbmc
import xbmcgui


def log(msg):
    xbmc.log(f'[GameLauncher-Meta] {msg}', xbmc.LOGINFO)


class MetadataFetcher:
    BASE_URL = 'https://api.rawg.io/api'

    def __init__(self, addon, cache):
        self.addon = addon
        self.cache = cache
        self.api_key = addon.getSetting('rawg_key')
        self.session = None

    def _request(self, endpoint, params=None):
        if not self.api_key:
            return None
        url = f'{self.BASE_URL}{endpoint}'
        if params is None:
            params = {}
        params['key'] = self.api_key
        url += '?' + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'KodiGameLauncher/1.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                log('Rate limited, waiting...')
                time.sleep(2)
                return self._request(endpoint, params)
            log(f'HTTP {e.code} for {url}')
            return None
        except Exception as e:
            log(f'Request failed: {e}')
            return None

    def search_game(self, game_name):
        data = self._request('/games', {
            'search': game_name,
            'page_size': 1,
            'search_precise': False,
        })
        if data and data.get('results'):
            return data['results'][0]
        return None

    def get_game_details(self, game_id):
        return self._request(f'/games/{game_id}')

    def get_game_screenshots(self, game_id):
        data = self._request(f'/games/{game_id}/screenshots')
        if data and data.get('results'):
            return data['results']
        return []

    def fetch_all(self, games, progress=None):
        if not self.api_key:
            log('No RAWG API key configured')
            return

        total = len(games)
        for idx, game in enumerate(games):
            title = game.get('title', '')
            if not title:
                continue

            if progress:
                progress.update(int((idx / total) * 100),
                                f'Fetching: {title}\n({idx + 1}/{total})')
                if progress.iscanceled():
                    break

            if self.cache.has_meta(title):
                continue

            try:
                result = self.search_game(title)
                if not result:
                    log(f'No result for: {title}')
                    self.cache.save_meta(title, {'name': title})
                    continue

                game_id = result.get('id')
                details = self.get_game_details(game_id)
                if not details:
                    self.cache.save_meta(title, {'name': result.get('name', title)})
                    continue

                screenshots = self.get_game_screenshots(game_id)

                meta = {
                    'name': details.get('name', title),
                    'description': details.get('description_raw', ''),
                    'released': details.get('released', ''),
                    'rating': details.get('rating', 0),
                    'metacritic': details.get('metacritic', 0),
                    'genres': [g['name'] for g in details.get('genres', [])],
                    'developers': [d['name'] for d in details.get('developers', [])],
                    'publishers': [p['name'] for p in details.get('publishers', [])],
                    'platforms': [p['platform']['name'] for p in details.get('platforms', [])],
                    'thumbnail': '',
                    'background': '',
                    'banner': '',
                    'poster': '',
                }

                if details.get('background_image'):
                    meta['background'] = details['background_image']
                    meta['fanart'] = details['background_image']

                if screenshots:
                    meta['thumbnail'] = screenshots[0].get('image', '')
                    if not meta['background']:
                        meta['background'] = screenshots[0].get('image', '')

                if details.get('background_image_additional'):
                    meta['poster'] = details.get('background_image_additional', '')

                if result.get('short_screenshots'):
                    for ss in result['short_screenshots']:
                        if ss.get('image'):
                            meta['thumbnail'] = ss['image']
                            break

                if not meta['thumbnail'] and details.get('background_image'):
                    meta['thumbnail'] = details['background_image']

                self.cache.save_meta(title, meta)
                log(f'Fetched metadata for: {title}')

            except Exception as e:
                log(f'Error fetching metadata for {title}: {e}')
                self.cache.save_meta(title, {'name': title})

            time.sleep(0.3)
