import os
import re
import xbmc


def log(msg):
    xbmc.log(f'[GameLauncher-Scanner] {msg}', xbmc.LOGINFO)


SUPPORT_DIRS = ['bin', 'binaries', 'win32', 'win64', 'x86', 'x64',
                'redist', 'common', 'support', 'tools', 'engine',
                'build', 'builds', 'plugins', '3rdparty', 'thirdparty',
                'sentry', 'physx', 'dotnet', 'install', 'setup',
                'content', 'movie', 'video', 'debug', 'logs',
                'saves', 'save', 'profiles', 'config', 'crashdump']

JUNK_NAMES = ['unins', 'setup', 'install', 'redist', 'vc_redist', 'dotnet',
              'dxsetup', 'dxwebsetup', 'oalinst', 'physx', 'vcredist',
              'crashpad', 'unitycrash', 'crashhandler', 'crashdump',
              'eosauth', 'easyanticheat', 'easyanti', 'anticheat',
              'readme', 'autorun', 'gameoverlay', 'splash', 'logo',
              'updater', 'config', 'configur', 'settings',
              'snd2wav', 'sff2pcx', 'sff2png', 'sprmake', 'pcxclean',
              'ipxconfig', 'vselect', 'aircleaner', 'aireditw',
              'add004', 'sprmaker', 'sprmake2', '00stage', 'stage0',
              'aircleaner', 'stageviewer',
              'oalinst', 'openal', 'wrapper', 'server']

GAME_EXTS = ['.exe', '.lnk', '.bat', '.cmd', '.com', '.jar']


def norm(s):
    return re.sub(r'[\s\-_]+', '', s).lower()


def is_support_dir(dirname):
    return norm(dirname) in [norm(d) for d in SUPPORT_DIRS]


def is_junk_name(filename):
    name = os.path.splitext(filename)[0]
    n = norm(name)
    for junk in JUNK_NAMES:
        if junk in n:
            return True
    return False


class GameScanner:
    def __init__(self, addon, cache):
        self.addon = addon
        self.cache = cache

    def _setting(self, key, default):
        try:
            return self.addon.getSetting(key)
        except:
            return default

    def get_extensions(self):
        raw = self._setting('extensions', '.exe,.lnk,.bat,.cmd,.com,.jar')
        return [e.strip().lower() if e.startswith('.') else '.' + e.strip().lower()
                for e in raw.split(',') if e.strip()]

    def get_min_size(self):
        try:
            return int(self._setting('min_file_size', '512')) * 1024
        except:
            return 524288

    def is_recursive(self):
        return self._setting('recursive', 'true') == 'true'

    def clean_game_name(self, filename):
        name, _ = os.path.splitext(filename)
        name = re.sub(r'[_.]', ' ', name)
        name = re.sub(r'\s*[-]\s*Shortcut$', '', name, flags=re.I)
        name = re.sub(r'\s*\(.*?\)\s*$', '', name)
        name = re.sub(r'\s*\[.*?\]\s*$', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        name = re.sub(r'\sLauncher$', '', name, flags=re.I)
        name = re.sub(r'\sv?\d+[\.,]\d+(?:[\.,]\d+)?$', '', name)
        return name.strip()

    def score_exe(self, filename, dirpath):
        name, ext = os.path.splitext(filename)
        fullpath = os.path.join(dirpath, filename)
        size = os.path.getsize(fullpath)
        dirname = os.path.basename(dirpath)
        parent = os.path.basename(os.path.dirname(dirpath))
        n = norm(name)

        score = size / (1024 * 1024) * 2

        if norm(filename) == norm(dirname) or n == norm(dirname):
            score += 500
        if norm(filename).startswith(norm(dirname)) or norm(dirname).startswith(n):
            score += 300
        if parent and (norm(filename) == norm(parent) or n == norm(parent)):
            score += 200

        if ext.lower() == '.exe':
            score += 50
        elif ext.lower() == '.lnk':
            score += 20

        if 'win64' in n and 'shipping' in n:
            score += 80

        if 'server' in n or 'crash' in n or 'launcher' in n or 'helper' in n:
            score -= 200
        if 'handler' in n or 'bootstrapper' in n or 'manager' in n or 'worker' in n:
            score -= 150
        if 'loader' in n or 'patch' in n or 'service' in n:
            score -= 100

        return max(score, 0)

    def _scan_for_exes(self, directory, extensions, min_size):
        result = []
        try:
            entries = os.listdir(directory)
        except:
            return result

        for entry in entries:
            full = os.path.join(directory, entry)
            if os.path.isfile(full):
                _, ext = os.path.splitext(entry)
                if ext.lower() not in extensions:
                    continue
                if os.path.getsize(full) < min_size:
                    continue
                if is_junk_name(entry):
                    continue
                result.append(entry)
        return result

    def _gather_dirs(self, root, recursive):
        dirs = [root]
        if not recursive:
            return dirs
        try:
            for entry in os.listdir(root):
                full = os.path.join(root, entry)
                if os.path.isdir(full) and not is_support_dir(entry):
                    dirs.extend(self._gather_dirs(full, True))
        except:
            pass
        return list(set(dirs))

    def scan_dirs(self, dirs, progress=None):
        extensions = self.get_extensions()
        min_size = self.get_min_size()
        recursive = self.is_recursive()
        all_games = []

        for idx, directory in enumerate(dirs):
            if not os.path.isdir(directory):
                log(f'Skipping (not found): {directory}')
                continue
            if progress:
                progress.update(int((idx / len(dirs)) * 50), f'Scanning: {directory}')

            subdirs = self._gather_dirs(directory, recursive)

            for sd in subdirs:
                exes = self._scan_for_exes(sd, extensions, min_size)
                if exes:
                    best = max(exes, key=lambda f: self.score_exe(f, sd))
                    score = self.score_exe(best, sd)
                    name = self.clean_game_name(best)
                    rel = os.path.relpath(sd, directory)
                    subdir = '' if rel == '.' else rel
                    entry = {
                        'filepath': os.path.join(sd, best),
                        'filename': best,
                        'title': name,
                        'size': os.path.getsize(os.path.join(sd, best)),
                        'subdir': subdir,
                    }
                    all_games.append((sd, score, entry))
                    log(f'Game: {name} (score={score:.0f}) -> {best}')

        # Pick best per unique directory path
        best_map = {}
        for sd, score, entry in all_games:
            if sd not in best_map or score > best_map[sd][0]:
                best_map[sd] = (score, entry)

        results = sorted([e for _, e in best_map.values()], key=lambda x: x['title'].lower())

        # Dedup by filepath
        seen = set()
        deduped = []
        for g in results:
            if g['filepath'] not in seen:
                seen.add(g['filepath'])
                deduped.append(g)

        log(f'Final: {len(deduped)} games')
        return deduped
