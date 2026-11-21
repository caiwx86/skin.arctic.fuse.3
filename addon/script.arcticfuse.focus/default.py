# -*- coding: utf-8 -*-
"""Arctic Fuse 3 focus helper.

Called from the skin:
    RunScript(script.arcticfuse.focus, playlist, <container id>)
    RunScript(script.arcticfuse.focus, wall, <container id>)
"""
import json
import sys

import xbmc

ADDON_ID = 'script.arcticfuse.focus'


def log(message, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, message), level)


def info(label):
    try:
        return xbmc.getInfoLabel(label)
    except Exception:  # noqa: BLE001 - never break the UI for a focus helper
        return ''


def as_int(value, default=-1):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def jsonrpc(method, params):
    payload = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(payload))).get('result', {})
    except Exception as error:  # noqa: BLE001
        log('jsonrpc %s failed: %s' % (method, error), xbmc.LOGWARNING)
        return {}


def set_focus(control_id, index):
    if control_id <= 0 or index < 0:
        return
    xbmc.executebuiltin('SetFocus(%d,%d,absolute)' % (control_id, index))
    log('focused control %d at index %d' % (control_id, index))


def item_count(control_id):
    return as_int(info('Container(%d).NumItems' % control_id), 0)


def wait_for_items(control_id, monitor, timeout=3.0):
    elapsed = 0.0
    while elapsed < timeout:
        if item_count(control_id) > 0:
            return True
        if monitor.waitForAbort(0.1):
            return False
        elapsed += 0.1
    return item_count(control_id) > 0


def focus_playlist(control_id):
    """Focus the entry that is currently playing (PlaylistPosition is 1-based)."""
    monitor = xbmc.Monitor()
    if not wait_for_items(control_id, monitor):
        return
    if as_int(info('VideoPlayer.PlaylistLength'), 0) <= 1:
        return
    position = as_int(info('VideoPlayer.PlaylistPosition'), 0)
    if position <= 0:
        return
    if as_int(info('Container(%d).CurrentItem' % control_id), 0) == position:
        return
    set_focus(control_id, position - 1)


def playing_episode_id():
    item = jsonrpc('Player.GetItem', {
        'playerid': 1,
        'properties': ['title', 'season', 'episode', 'showtitle'],
    }).get('item', {})
    if item.get('type') == 'episode':
        return item.get('id')
    return None


def season_context(control_id):
    """Identify the show and season shown by the wall from one of its episodes."""
    dbid = as_int(info('Container(%d).ListItem.DBID' % control_id), -1)
    if dbid <= 0:
        return None, None
    details = jsonrpc('VideoLibrary.GetEpisodeDetails', {
        'episodeid': dbid,
        'properties': ['season', 'tvshowid'],
    }).get('episodedetails', {})
    return details.get('tvshowid'), details.get('season')


def pick_index(episodes, playing_id, last_played_id):
    ids = [episode.get('episodeid') for episode in episodes]
    if playing_id in ids:
        return ids.index(playing_id)
    if last_played_id in ids:
        return ids.index(last_played_id)
    return -1


def focus_wall(control_id):
    """Focus the playing (or last played) episode in a season wall."""
    monitor = xbmc.Monitor()
    if not wait_for_items(control_id, monitor):
        return
    tvshow_id, season = season_context(control_id)
    if tvshow_id is None or season is None:
        return

    episodes = jsonrpc('VideoLibrary.GetEpisodes', {
        'tvshowid': tvshow_id,
        'season': season,
        'properties': ['episode', 'lastplayed'],
        'sort': {'method': 'episode', 'order': 'ascending'},
    }).get('episodes', [])
    if not episodes:
        return

    latest = None
    for episode in episodes:
        played = episode.get('lastplayed') or ''
        if played and (latest is None or played > latest[1]):
            latest = (episode.get('episodeid'), played)
    last_played_id = latest[0] if latest else None

    index = pick_index(episodes, playing_episode_id(), last_played_id)
    if index < 0:
        return
    if as_int(info('Container(%d).CurrentItem' % control_id), 0) == index + 1:
        return
    set_focus(control_id, index)


def main():
    arguments = [argument.lower() for argument in sys.argv[1:]]
    if not arguments:
        return
    mode = arguments[0]
    control_id = as_int(arguments[1], -1) if len(arguments) > 1 else -1
    if mode == 'playlist':
        focus_playlist(control_id)
    elif mode == 'wall':
        focus_wall(control_id)
    else:
        log('unknown mode: %s' % mode, xbmc.LOGWARNING)


if __name__ == '__main__':
    main()
