import os
import json
import urllib.request
import xbmc


def log(msg):
    xbmc.log(f'[GameLauncher-Cache] {msg}', xbmc.LOGINFO)


class GameCache:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.meta_dir = os.path.join(cache_dir, 'metadata')
        self.art_dir = os.path.join(cache_dir, 'art')
        self.game_list_file = os.path.join(cache_dir, 'game_list.json')
        for d in [self.meta_dir, self.art_dir]:
            if not os.path.isdir(d):
                try:
                    os.makedirs(d)
                except:
                    pass

    def _safe_name(self, name):
        safe = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in name)
        return safe[:100].strip()

    def save_meta(self, game_name, data):
        safe = self._safe_name(game_name)
        filepath = os.path.join(self.meta_dir, f'{safe}.json')
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            log(f'Failed to save meta for {game_name}: {e}')
            return False

    def get_meta(self, game_name):
        safe = self._safe_name(game_name)
        filepath = os.path.join(self.meta_dir, f'{safe}.json')
        if not os.path.isfile(filepath):
            return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None

    def has_meta(self, game_name):
        safe = self._safe_name(game_name)
        return os.path.isfile(os.path.join(self.meta_dir, f'{safe}.json'))

    def get_art_path(self, game_name, art_type='thumb'):
        safe = self._safe_name(game_name)
        return os.path.join(self.art_dir, f'{safe}_{art_type}.jpg')

    def download_art(self, game_name, url):
        if not url:
            return None
        local_path = self.get_art_path(game_name)
        if os.path.isfile(local_path):
            return local_path
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Kodi/1.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                with open(local_path, 'wb') as f:
                    f.write(resp.read())
            log(f'Downloaded art: {game_name}')
            return local_path
        except Exception as e:
            log(f'Failed to download art for {game_name}: {e}')
            return None

    def download_all_art(self, games, progress=None):
        total = len(games)
        for idx, game in enumerate(games):
            title = game.get('title', '')
            if not title:
                continue
            if progress:
                progress.update(int((idx / total) * 100), f'Downloading art: {title}\n({idx + 1}/{total})')
                if progress.iscanceled():
                    break
            meta = self.get_meta(title)
            if not meta:
                continue
            thumb_url = meta.get('thumbnail') or meta.get('background', '')
            bg_url = meta.get('background') or meta.get('thumbnail', '')
            if thumb_url:
                local = self.download_art(title, thumb_url)
                if local:
                    meta['_thumb_local'] = local
            if bg_url and bg_url != thumb_url:
                local = self.download_art(title, bg_url)
                if local:
                    meta['_bg_local'] = local
            if thumb_url or bg_url:
                self.save_meta(title, meta)

    def save_game_list(self, games):
        try:
            with open(self.game_list_file, 'w', encoding='utf-8') as f:
                json.dump(games, f, indent=2)
            log(f'Saved {len(games)} games to cache')
            return True
        except Exception as e:
            log(f'Failed to save game list: {e}')
            return False

    def load_game_list(self):
        if not os.path.isfile(self.game_list_file):
            return []
        try:
            with open(self.game_list_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def has_cached_games(self):
        return os.path.isfile(self.game_list_file) and os.path.getsize(self.game_list_file) > 10

    def clear_all(self):
        try:
            for d in [self.meta_dir, self.art_dir]:
                if os.path.isdir(d):
                    import shutil
                    shutil.rmtree(d)
                    os.makedirs(d)
            if os.path.isfile(self.game_list_file):
                os.remove(self.game_list_file)
            log('Cache cleared')
            return True
        except Exception as e:
            log(f'Failed to clear cache: {e}')
            return False

    def clear_meta(self, game_name):
        safe = self._safe_name(game_name)
        for f in [f'{safe}.json', f'{safe}_thumb.jpg', f'{safe}_bg.jpg']:
            p = os.path.join(self.meta_dir if f.endswith('.json') else self.art_dir, f)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except:
                    pass

    def get_cached_count(self):
        if not os.path.isdir(self.meta_dir):
            return 0
        return len([f for f in os.listdir(self.meta_dir) if f.endswith('.json')])
