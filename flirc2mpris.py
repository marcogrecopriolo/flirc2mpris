#!/usr/bin/python3
#
#    Copyright (C) 2023
#    Marco Greco <marcogrecopriolo@gmail.com>
#
#    This file is part of the flirc2mpris IR media player remote control utility
#
#    flirc2mpris is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 2 of the License.
#
#    flirc2mpris is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with flirc2mpris; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os
import sys
import time
import evdev
from evdev import ecodes
import mpris2
from plyer import notification
import configparser

device = "/dev/input/by-id/usb-flirc.tv_flirc-if01-event-kbd"
volumeInterval = 0.1
uri = ""
configFile = "flirc2mpris.conf"

# the mpris players iterator is reopened every time it is needed
# handling the exceptions due to players that have disappeared is more effort than it's worth

def loadPlayer(uri):
    try:
        return mpris2.Player(dbus_interface_info={'dbus_uri': uri})        
    except:
        return None

def volumeUp(player):
    volume = player.Volume + volumeInterval
    if volume <= 1.0:
        player.Volume = volume

def volumeDown(player):
    volume = player.Volume - volumeInterval
    if volume >= 0.0:
        player.Volume = volume

def random(player):
    try:
        random = player.Shuffle
        player.Shuffle = not random
    except:
        pass

def loop(player):
    try:
        loop = player.LoopStatus
        if loop == "None":
            loop = "Playlist"
        else:
            loop = "None"
        player.LoopStatus = loop
    except:
        pass

# unused - panics on clementine, not implemented in most other players
def loadPlaylist(player):
    global uri

    try:
        pls = mpris2.Playlists(dbus_interface_info={'dbus_uri': uri})
        pls.ActivatePlaylist("default")
    except:
        return

def nextPlayer(player):
    global uri

    found = False
    for u in mpris2.get_players_uri():
        if found:
            uri = u
            notify(uri)
            return
        if u == uri:
            found = True
    
    try:
        uri = next(mpris2.get_players_uri())
        notify(uri)
    except:
        uri = ""
        print("no player found")

def findPlayer(identity):
    global uri

    playerList = mpris2.get_players_uri()
    for uri in playerList:
        player2 = mpris2.MediaPlayer2(dbus_interface_info={'dbus_uri': uri})        
        if player2.Identity == identity:
            notify(uri)
            return True
    return False

def notify(uri):
    player2 = mpris2.MediaPlayer2(dbus_interface_info={'dbus_uri': uri})        
    notification.notify(
        app_name = "flirc remote",
        message = "media player switched to " +player2.Identity,
        timeout = 3,
        toast = False
    )

methodMappings = {
    "KEY_NEXTSONG": "Next",
    "KEY_PREVIOUSSONG": "Previous",
    "KEY_PLAYPAUSE": "PlayPause",
    "KEY_PAUSE": "Pause",
    "KEY_PLAY": "Play",
    "KEY_STOP": "Stop",
    "KEY_STOPCD": "Stop",
}

funcMappings = {
    "KEY_VOLUMEUP": volumeUp,
    "KEY_VOLUMEDOWN": volumeDown,
    "KEY_RIGHT": nextPlayer,
    "KEY_F12": random,
    "KEY_F11": loop,
}

playerMappings = {}
commandMappings = {}

class players:
    def __init__(self, app, identity):
        self.app = app
        self.identity = identity

def handle(event: evdev.KeyEvent):
    global uri

    if event.keystate != evdev.KeyEvent.key_down:
        return
    print(event)

# start a player    
    playerApp = playerMappings.get(event.keycode)
    if playerApp:
        if uri != "":
            try:
                player2 = mpris2.MediaPlayer2(dbus_interface_info={'dbus_uri': uri})        
                if player2 and player2.Identity == playerApp.identity:
                    print("found it")
                    return
            except:
                pass
        if findPlayer(playerApp.identity):
            return
        os.system(playerApp.app + " 1>/dev/null 2>/dev/null &")
        for i in range(10):
            if findPlayer(playerApp.identity):
                return
            time.sleep(1)
        return

    commandApp = commandMappings.get(event.keycode)
    if commandApp:
        os.system(commandApp.app + " 1>/dev/null 2>/dev/null &")
        return

# load a player if none is available
    if uri == "":
        try:
            playerList = mpris2.get_players_uri()
            uri = next(playerList)
        except StopIteration:
            print("No media player found")
            return

# try method and function mappings
    player = loadPlayer(uri)
    if not player:
        return
    methodName = methodMappings.get(event.keycode)
    if methodName:
        method = getattr(player, methodName)
        method()
        return
    funcName = funcMappings.get(event.keycode)
    if funcName:
        funcName(player)
        return

# parse config
config = configparser.ConfigParser()
try:
    path = os.environ.get("HOME")
    if path != "":
        path = path + "/.config/" + configFile
    else:
        path = configFile
    config.read(path)
    general = config["general"]
    try:
        volumeInterval = float(general["volumeInterval"])
        print("volume interval", volumeInterval)
    except:
        print("no volume")
    try:
        device = general["device"]
        print("remote device", device)
    except:
        print("no device")

    for section in config.sections():
        if section.startswith("player."):
            try:
                s = config[section]
                key = s["key"]
                app = s["app"]
                identity = s["identity"]
                playerMappings[key] = players(app, identity)
                print(key, identity)
            except:
                print("error parsing", section)
        if section.startswith("command."):
            try:
                s = config[section]
                key = s["key"]
                app = s["app"]
                commandMappings[key] = app
                print(key, section[len("command."):])
            except:
                print("error parsing", section)
except:
    print("error parsing config file")
    sys.exit(1)

# main loop
try:
    dev = evdev.InputDevice(device)
except:
    print("device not found")
    sys.exit(2)

try:
    for event in dev.read_loop():
        if event.type != ecodes.EV_KEY:
            continue
        keyEvent = evdev.categorize(event)
        handle(keyEvent)
except KeyboardInterrupt:
    dev.close()
    print("")
