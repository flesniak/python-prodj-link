#!/usr/bin/env python3

import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette
from PyQt5.QtCore import Qt
import signal
import argparse

from prodj import ProDj
from gui import Gui


parser = argparse.ArgumentParser(description='Python ProDJ Link')
parser.add_argument('--disable-pdb', dest='enable_pdb', action='store_false', help='Disable PDB provider')
parser.add_argument('--nxs2-blue', dest='nxs2_blue', action='store_true', help='Show NXS2 blue waveform previews')
parser.add_argument('--nxs2-color ', dest='nxs2_color', action='store_true', help='Show NXS2 color waveforms')
args = parser.parse_args()

print(args.nxs2_color)

default_loglevel=0
default_loglevel=logging.DEBUG
#default_loglevel=logging.INFO
#default_loglevel=logging.WARNING

logging.basicConfig(level=default_loglevel, format='%(levelname)s: %(message)s')

prodj = ProDj(enable_pdb=args.enable_pdb)
app = QApplication([])
gui = Gui(prodj, show_color_waveform=args.nxs2_color, show_nxs2_waveform=args.nxs2_blue)

pal = app.palette()
pal.setColor(QPalette.Window, Qt.black)
pal.setColor(QPalette.Base, Qt.black)
pal.setColor(QPalette.Button, Qt.black)
pal.setColor(QPalette.WindowText, Qt.white)
pal.setColor(QPalette.Text, Qt.white)
pal.setColor(QPalette.ButtonText, Qt.white)
pal.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.gray)
app.setPalette(pal)

signal.signal(signal.SIGINT, lambda s,f: app.quit())

prodj.set_client_keepalive_callback(gui.keepalive_callback)
prodj.set_client_change_callback(gui.client_change_callback)
prodj.set_media_change_callback(gui.media_callback)
prodj.start()
prodj.vcdj_set_player_number(5)
prodj.vcdj_enable()

app.exec()
logging.info("Shutting down...")
prodj.stop()
