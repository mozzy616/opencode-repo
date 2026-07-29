import xbmcgui
import os

_DIM = '0xBB000000'
_MUTED = '0xFFAAAAAA'


class GameInfoDialog(xbmcgui.WindowDialog):

    def __init__(self, game, thumb_path, fanart_path):
        super().__init__()
        sw = xbmcgui.getScreenWidth()
        sh = xbmcgui.getScreenHeight()

        bg = ''
        if thumb_path and os.path.isfile(thumb_path):
            bg = thumb_path
        elif fanart_path and os.path.isfile(fanart_path):
            bg = fanart_path
        if bg:
            self._bg = xbmcgui.ControlImage(0, 0, sw, sh, bg)
            self._bg.setColorDiffuse(_DIM)
        else:
            self._bg = xbmcgui.ControlImage(0, 0, sw, sh, '0xFF0D0D1A')
        self.addControl(self._bg)

        lx = 60
        ly = 50
        lw = sw - 120

        info = game.get('cached_meta', {})
        title = info.get('title') or game.get('title', '')
        self._title = xbmcgui.ControlLabel(lx, ly, lw, 45, title, font='font30_title')
        self.addControl(self._title)

        year = info.get('released', '')[:4] if info.get('released') else ''
        genre = ', '.join(info.get('genres', [])) if info.get('genres') else ''
        dev = ', '.join(info.get('developers', [])) if info.get('developers') else ''
        rating = f"{info.get('rating', '')}/10" if info.get('rating') else ''
        meta_parts = [p for p in [year, genre, dev, rating] if p]
        meta_str = '  |  '.join(meta_parts) if meta_parts else ''
        self._meta = xbmcgui.ControlLabel(lx, ly + 55, lw, 28, meta_str, font='font12', textColor=_MUTED)
        self.addControl(self._meta)

        desc_y = ly + 100
        desc_h = sh - desc_y - 100
        desc = info.get('description', '') or 'No description available.'
        self._desc = xbmcgui.ControlTextBox(lx, desc_y, lw, desc_h)
        self._desc.setText(desc)
        self.addControl(self._desc)

        if len(desc) > 200:
            self._desc.autoScroll(5000, 1000, -1)

        btn_w = 170
        gap = 15
        total = btn_w * 3 + gap * 2
        bx = (sw - total) // 2
        by = sh - 55

        self._launch = xbmcgui.ControlButton(bx, by, btn_w, 42, 'Launch')
        self.addControl(self._launch)
        self._delete = xbmcgui.ControlButton(bx + btn_w + gap, by, btn_w, 42, 'Delete')
        self.addControl(self._delete)
        self._close = xbmcgui.ControlButton(bx + (btn_w + gap) * 2, by, btn_w, 42, 'Close')
        self.addControl(self._close)

        self._launch_id = -1
        self._delete_id = -1
        self._close_id = -1
        self._probe_ids()

        self.setFocus(self._launch)

    def _probe_ids(self):
        for pid in range(3000, 3010):
            try:
                ctrl = self.getControl(pid)
                if hasattr(ctrl, 'getLabel'):
                    label = ctrl.getLabel()
                    if label == 'Launch':
                        self._launch_id = pid
                    elif label == 'Delete':
                        self._delete_id = pid
                    elif label == 'Close':
                        self._close_id = pid
            except:
                pass

    def onAction(self, action):
        aid = action.getId()
        if aid in (7, 100):
            self._pick(self.getFocusId())
        elif aid == 4:
            self._desc.scroll(0)
        elif aid == 5:
            self._desc.scroll(9999)
        elif aid in (9, 10, 92, 117):
            self.close()

    def onClick(self, cid):
        self._pick(cid)

    def _pick(self, cid):
        if cid == self._launch_id:
            self._result = 'launch'
        elif cid == self._delete_id:
            self._result = 'delete'
        elif cid == self._close_id:
            self._result = 'close'
        else:
            return
        self.close()

    def getResult(self):
        return getattr(self, '_result', None)
