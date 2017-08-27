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
app = QApplication([])
gui = Gui(prodj)

signal.signal(signal.SIGINT, lambda s,f: app.quit())

prodj.set_client_keepalive_callback(lambda cl,n: gui.keepalive_signal.emit(n))
prodj.set_client_change_callback(gui.change_callback)
prodj.start()
prodj.vcdj_set_player_number(5)
prodj.vcdj_enable()

app.exec()
logging.info("Shutting down...")
prodj.stop()
