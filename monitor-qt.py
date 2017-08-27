#!/usr/bin/python3

import logging
import time
from PyQt5.QtWidgets import QApplication
import signal

from prodj import ProDj
from gui import Gui

default_loglevel=0
default_loglevel=logging.DEBUG
#default_loglevel=logging.INFO
#default_loglevel=logging.WARNING

logging.basicConfig(level=default_loglevel, format='%(levelname)s: %(message)s')

prodj = ProDj()

signal.signal(signal.SIGINT, signal.SIG_DFL)
app = QApplication([])
gui = Gui(prodj)

prodj.set_client_keepalive_callback(lambda cl,n: gui.keepalive_signal.emit(n))
prodj.set_client_change_callback(gui.change_callback)
prodj.start()
prodj.vcdj_set_player_number(5)
prodj.vcdj_enable()

with open("preview_waveform.bin", "rb") as f:
  gui.players[1].preview_waveform.data = f.read(800)

with open("waveform.bin", "rb") as f:
  f.seek(20)
  gui.players[1].waveform.data = f.read()

#gui.show()

app.exec()
logging.info("Shutting down...")
prodj.stop()
