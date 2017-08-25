#!/usr/bin/python3

import logging
import time
from PyQt5.QtWidgets import QApplication
import signal

from prodj import ProDj
from gui import Gui

default_loglevel=0
default_loglevel=logging.DEBUG
default_loglevel=logging.INFO
#default_loglevel=logging.WARNING

logging.basicConfig(level=default_loglevel, format='%(levelname)s: %(message)s')

p = ProDj()

signal.signal(signal.SIGINT, signal.SIG_DFL)
app = QApplication([])
gui = Gui(p.cl)

def keepalive_callback(cl, player_number):
  if player_number > 4:
    return
  gui.keepalive_signal.emit(player_number)

def change_callback(cl, player_number):
  if player_number > 4:
    return
  gui.change_signal.emit(player_number)

def metadata_callback(player_number, metadata):
  if player_number > 4:
    return
  gui.metadata_signal.emit(player_number)

p.set_client_keepalive_callback(keepalive_callback)
p.set_client_change_callback(change_callback)
p.set_metadata_change_callback(metadata_callback)
p.start()
p.vcdj_set_player_number(5)
p.vcdj_enable()

with open("preview_waveform.bin", "rb") as f:
  gui.players[1].preview_waveform.data = f.read(800)

with open("waveform.bin", "rb") as f:
  f.seek(20)
  gui.players[1].waveform.data = f.read()

#gui.show()

app.exec()
logging.info("Shutting down...")
p.stop()
