import subprocess
import os
import xbmc
import xbmcgui


def log(msg):
    xbmc.log(f'[GameLauncher-Launcher] {msg}', xbmc.LOGINFO)


class GameLauncher:
    def __init__(self, addon):
        self.addon = addon

    def get_launch_method(self):
        try:
            return int(self.addon.getSetting('launch_method'))
        except:
            return 0

    def should_minimize(self):
        return self.addon.getSetting('close_kodi') == 'true'

    def launch(self, filepath):
        if not os.path.isfile(filepath):
            xbmcgui.Dialog().ok('Game Launcher', f'File not found:\n{filepath}')
            return

        method = self.get_launch_method()
        minimize = self.should_minimize()

        game_dir = os.path.dirname(filepath)

        if minimize:
            xbmc.executebuiltin('Minimize()')

        try:
            if method == 2 or os.path.splitext(filepath)[1].lower() == '.lnk':
                os.startfile(filepath)
                log(f'Launched via startfile: {filepath}')
            else:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 1
                proc = subprocess.Popen(
                    [filepath],
                    cwd=game_dir,
                    startupinfo=startupinfo,
                    close_fds=False
                )
                log(f'Launched: {filepath} (cwd={game_dir}, pid={proc.pid})')

        except Exception as e:
            log(f'Launch failed: {e}')
            try:
                os.startfile(filepath)
                log(f'Fallback startfile succeeded: {filepath}')
            except Exception as e2:
                xbmcgui.Dialog().ok('Game Launcher', f'Failed to launch:\n{filepath}\n\nError: {e2}')
