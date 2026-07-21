import sys
import xbmc

from resources.lib.kodi_utils import log
from resources.lib.router import router


if __name__ == "__main__":
    try:
        router(sys.argv[2])
    except Exception as e:
        import traceback
        log("Main error: %s" % str(e), xbmc.LOGERROR)
        log(traceback.format_exc(), xbmc.LOGERROR)
