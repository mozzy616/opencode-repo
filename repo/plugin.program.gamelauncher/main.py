import sys
import os
import json
import urllib.parse
import traceback
import threading
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'lib'))
from gameinfo_dialog import GameInfoDialog

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_PATH = ADDON.getAddonInfo('path')

HANDLE = -1
URL = ''
PARAMS = ''
try:
    HANDLE = int(sys.argv[1])
    URL = sys.argv[0]
    PARAMS = sys.argv[2]
except:
    pass

ICON = os.path.join(ADDON_PATH, 'icon.png')
FANART = os.path.join(ADDON_PATH, 'fanart.jpg')
CACHE_DIR = os.path.join(ADDON_PATH, '.cache')

if not os.path.isdir(CACHE_DIR):
    try:
        os.makedirs(CACHE_DIR)
    except:
        pass

from resources.lib.scanner import GameScanner
from resources.lib.metadata import MetadataFetcher
from resources.lib.cache import GameCache
from resources.lib.launcher import GameLauncher

cache = GameCache(CACHE_DIR)
scanner = GameScanner(ADDON, cache)
metadata = MetadataFetcher(ADDON, cache)
launcher = GameLauncher(ADDON)

_scanning = False


def log(msg):
    xbmc.log(f'[GameLauncher] {msg}', xbmc.LOGINFO)


def get_url(**kwargs):
    return URL + '?' + '&'.join([f'{k}={urllib.parse.quote(str(v))}' for k, v in kwargs.items()])


def end_directory(succeeded=True):
    xbmcplugin.setContent(HANDLE, 'games')
    xbmcplugin.endOfDirectory(HANDLE, succeeded)


def add_item(label, url, is_folder=True, art=None, info=None, properties=None, path=''):
    li = xbmcgui.ListItem(label=label, path=path if path and is_folder else '')
    default_art = {'icon': ICON, 'fanart': FANART}
    if art:
        default_art.update(art)
    li.setArt(default_art)
    if info:
        li.setInfo('game', info)
    if properties:
        for k, v in properties.items():
            li.setProperty(k, str(v))
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)
    return li


def show_main_menu():
    scan_on_start = ADDON.getSetting('scan_on_start') == 'true'
    has_cache = cache.has_cached_games()

    if scan_on_start and not has_cache:
        do_scan(main_menu=True)
        return

    add_item('[B]All Games[/B]', get_url(action='all_games'), is_folder=True,
             art={'icon': ICON, 'fanart': FANART})
    add_item('[B]Rescan Directories[/B]', get_url(action='scan'), is_folder=False,
             art={'icon': ICON, 'fanart': FANART})
    add_item('[B]Search Games[/B]', get_url(action='search'), is_folder=False,
             art={'icon': ICON, 'fanart': FANART})
    end_directory()


def get_game_dirs():
    dirs = []
    for key in ['game_dir', 'game_dir_2', 'game_dir_3', 'game_dir_4', 'game_dir_5']:
        d = ADDON.getSetting(key).strip()
        if d and os.path.isdir(d):
            dirs.append(d)
    return dirs


def do_scan(main_menu=False):
    global _scanning
    if _scanning:
        return
    _scanning = True

    try:
        progress = xbmcgui.DialogProgress()
        progress.create(ADDON_NAME, 'Scanning for games...')

        dirs = get_game_dirs()
        if not dirs:
            progress.close()
            _scanning = False
            xbmcgui.Dialog().ok(ADDON_NAME, 'No game directories configured.\nSet them in addon settings.')
            if not main_menu:
                show_main_menu()
            return

        found_games = scanner.scan_dirs(dirs, progress)
        progress.close()

        if not found_games:
            _scanning = False
            xbmcgui.Dialog().ok(ADDON_NAME, 'No games found in the configured directories.\nConfigure game directories in addon settings and try again.')
            if not main_menu:
                show_main_menu()
            return

        enable_metadata = ADDON.getSetting('enable_metadata') == 'true'
        if enable_metadata and ADDON.getSetting('rawg_key'):
            meta_progress = xbmcgui.DialogProgress()
            meta_progress.create(ADDON_NAME, 'Fetching game metadata...\nThis may take a while.')
            metadata.fetch_all(found_games, meta_progress)
            meta_progress.close()

        cache.save_game_list(found_games)
        _scanning = False
        xbmcgui.Dialog().notification(ADDON_NAME, f'Found {len(found_games)} games')

        if enable_metadata and ADDON.getSetting('rawg_key'):
            art_progress = xbmcgui.DialogProgress()
            art_progress.create(ADDON_NAME, 'Downloading artwork...')
            cache.download_all_art(found_games, art_progress)
            art_progress.close()

        if not main_menu:
            show_main_menu()

    except Exception as e:
        _scanning = False
        log(f'Scan error: {e}\n{traceback.format_exc()}')
        xbmcgui.Dialog().ok(ADDON_NAME, f'Scan failed: {str(e)}')
        if not main_menu:
            show_main_menu()


def show_all_games():
    games = cache.load_game_list()
    if not games:
        xbmcgui.Dialog().ok(ADDON_NAME, 'No games found. Scan directories first.')
        end_directory(False)
        return

    for game in games:
        filepath = game.get('filepath', '')
        title = game.get('title', os.path.splitext(os.path.basename(filepath))[0])
        subdir = game.get('subdir', '')
        size = game.get('size', 0)

        art = {'icon': ICON, 'fanart': FANART}
        cached_meta = cache.get_meta(title)

        display_title = title
        if cached_meta:
            local_thumb = cached_meta.get('_thumb_local') or cached_meta.get('thumbnail', '')
            local_bg = cached_meta.get('_bg_local') or cached_meta.get('background', '')
            if local_thumb and os.path.isfile(str(local_thumb)):
                art['thumb'] = local_thumb
                art['icon'] = local_thumb
            elif cached_meta.get('thumbnail'):
                art['thumb'] = cached_meta['thumbnail']
                art['icon'] = cached_meta['thumbnail']
            if local_bg and os.path.isfile(str(local_bg)):
                art['fanart'] = local_bg
            elif cached_meta.get('background'):
                art['fanart'] = cached_meta['background']
            if cached_meta.get('banner'):
                art['banner'] = cached_meta['banner']
            if cached_meta.get('poster'):
                art['poster'] = cached_meta['poster']
            if ADDON.getSetting('prefer_steam_names') != 'true':
                display_title = cached_meta.get('name', title)

        label = display_title
        if subdir:
            label = f'{display_title}  [COLOR=grey]({subdir})[/COLOR]'

        li = xbmcgui.ListItem(label=label)
        li.setArt(art)
        log(f'Game: {title[:30]} meta={cached_meta is not None} thumb={"thumb" in art}')

        if cached_meta:
            tag = li.getGameInfoTag()
            tag.setTitle(display_title)
            if cached_meta.get('description'):
                li.setProperty('description', cached_meta['description'])
            try:
                for g in cached_meta.get('genres', []):
                    tag.addGenre(g)
            except:
                pass
            try:
                for d in cached_meta.get('developers', []):
                    tag.addStudio(d)
            except:
                pass
            try:
                if cached_meta.get('released'):
                    tag.setYear(int(cached_meta['released'][:4]))
            except:
                pass
            try:
                if cached_meta.get('rating'):
                    tag.setRating(float(cached_meta['rating']))
            except:
                pass

        context_items = [
            ('Game Info', f'RunPlugin({get_url(action="game_info", game=title)})'),
            ('Rename Game', f'RunPlugin({get_url(action="rename_game", game=title)})'),
            ('Delete from List', f'RunPlugin({get_url(action="delete_game", game=title)})'),
            ('Rescan Directories', f'RunPlugin({get_url(action="scan")})'),
        ]
        li.addContextMenuItems(context_items)

        xbmcplugin.addDirectoryItem(HANDLE, get_url(action='launch', game=title), li, isFolder=False)

    end_directory()


def format_size(size):
    try:
        size = int(size)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} TB'
    except:
        return ''


def launch_game(game_title):
    games = cache.load_game_list()
    game = None
    for g in games:
        if g.get('title') == game_title:
            game = g
            break

    if not game:
        xbmcgui.Dialog().ok(ADDON_NAME, f'Game not found: {game_title}')
        return

    filepath = game.get('filepath', '')
    if not os.path.isfile(filepath):
        xbmcgui.Dialog().ok(ADDON_NAME, f'Game file not found:\n{filepath}')
        return

    launcher.launch(filepath)


def search_games():
    kb = xbmc.Keyboard('', 'Search Games', False)
    kb.doModal()
    if not kb.isConfirmed():
        return
    query = kb.getText().strip().lower()
    if not query:
        return

    games = cache.load_game_list()
    results = []
    for g in games:
        title = g.get('title', '')
        cached = cache.get_meta(title)
        display = cached.get('name', title) if cached else title
        if query in title.lower() or query in display.lower():
            results.append((g, cached, display))

    if not results:
        xbmcgui.Dialog().notification(ADDON_NAME, f'No results for "{query}"', ICON, 3000)
        return

    xbmcplugin.setContent(HANDLE, 'games')
    for game, cached_meta, display_title in sorted(results, key=lambda x: x[2]):
        filepath = game.get('filepath', '')
        title = game.get('title', '')
        art = {}
        if cached_meta:
            if cached_meta.get('thumbnail'):
                art['thumb'] = cached_meta['thumbnail']
            if cached_meta.get('background'):
                art['fanart'] = cached_meta['background']

        label = display_title
        add_item(label, get_url(action='launch', game=title), is_folder=False,
                 art=art)

    end_directory()


def clear_cache_action():
    confirmed = xbmcgui.Dialog().yesno(ADDON_NAME, 'Clear All Data and Start Fresh?\nThis will delete game list, thumbnails, descriptions, and artwork.\n\nYou will need to rescan after.')
    if not confirmed:
        end_directory()
        return
    cache.clear_all()
    xbmcgui.Dialog().notification(ADDON_NAME, 'All data cleared. Rescan to rebuild.', ICON, 5000)
    end_directory()


def delete_game_action(game_title):
    games = cache.load_game_list()
    removed = [g for g in games if g.get('title') != game_title]
    if len(removed) < len(games):
        cache.save_game_list(removed)
        cache.clear_meta(game_title)
        xbmcgui.Dialog().notification(ADDON_NAME, f'Removed: {game_title}', ICON, 3000)
    else:
        xbmcgui.Dialog().notification(ADDON_NAME, f'Not found: {game_title}', ICON, 3000)
    end_directory()


def rename_game_action(game_title):
    games = cache.load_game_list()
    game = None
    for g in games:
        if g.get('title') == game_title:
            game = g
            break
    if not game:
        end_directory()
        return

    new_name = xbmcgui.Dialog().input('Rename Game', game_title, type=xbmcgui.INPUT_ALPHANUM)
    if not new_name or new_name == game_title:
        end_directory()
        return

    game['title'] = new_name
    game['orig_title'] = new_name
    cache.save_game_list(games)
    cache.clear_meta(game_title)
    cache.clear_meta(new_name)

    fetch_single_metadata(new_name)
    progress = xbmcgui.DialogProgress()
    progress.create(ADDON_NAME, f'Downloading artwork for: {new_name}')
    cache.download_all_art([game], progress)
    progress.close()

    xbmcgui.Dialog().notification(ADDON_NAME, f'Renamed: {game_title} → {new_name}', ICON, 3000)
    end_directory()


def fetch_single_metadata(game_name):
    from metadata import MetadataFetcher
    mf = MetadataFetcher(ADDON, cache)
    rawg_key = ADDON.getSetting('rawg_key')
    if not rawg_key:
        return
    game = {'title': game_name}
    mf.fetch_all([game])



def rescan_action():
    do_scan()


def show_game_info(game_title):
    games = cache.load_game_list()
    game = None
    for g in games:
        if g.get('title') == game_title:
            game = g
            break
    if not game:
        end_directory()
        return

    cached_meta = cache.get_meta(game_title) or {}
    thumb_path = cache.get_art_path(game_title, 'thumb')
    fanart_path = cache.get_art_path(game_title, 'bg')

    game['cached_meta'] = cached_meta

    dialog = GameInfoDialog(game, thumb_path, fanart_path)
    dialog.doModal()
    result = dialog.getResult()
    del dialog

    if result == 'launch':
        launch_game(game_title)
    elif result == 'delete':
        delete_game_action(game_title)
    else:
        end_directory()


def router(paramstring):
    params = {}
    if paramstring:
        paramstring = paramstring.lstrip('?')
        for pair in paramstring.split('&'):
            pair = pair.strip()
            if '=' in pair:
                k, v = pair.split('=', 1)
                params[k] = urllib.parse.unquote(v)

    action = params.get('action', '')
    if action == 'all_games':
        show_all_games()
    elif action == 'scan':
        do_scan()
    elif action == 'search':
        search_games()
    elif action == 'launch':
        launch_game(params.get('game', ''))
    elif action == 'clear_cache':
        clear_cache_action()
    elif action == 'rescan':
        rescan_action()
    elif action == 'delete_game':
        delete_game_action(params.get('game', ''))
    elif action == 'game_info':
        show_game_info(params.get('game', ''))
    elif action == 'rename_game':
        rename_game_action(params.get('game', ''))
    else:
        show_main_menu()


if __name__ == '__main__':
    try:
        log(f'PARAMS: {PARAMS} HANDLE: {HANDLE}')
        if HANDLE == -1 and not PARAMS:
            plugin_url = 'plugin://' + ADDON_ID + '/'
            xbmc.executebuiltin('Container.Update(' + plugin_url + ')')
        else:
            router(PARAMS)
    except Exception as e:
        tb = traceback.format_exc()
        log(f'CRASH: {e}\n{tb}')
        xbmcgui.Dialog().ok(ADDON_NAME, f'Error: {e}')
