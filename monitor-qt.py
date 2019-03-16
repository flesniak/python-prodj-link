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
parser.add_argument('--color-preview', action='store_true', help='Show NXS2 colored preview waveforms')
parser.add_argument('--color-waveform', action='store_true', help='Show NXS2 colored big waveforms')
parser.add_argument('-c', '--color', action='store_true', help='Shortcut for --colored-preview and --color-waveform')
args = parser.parse_args()

default_loglevel=0
default_loglevel=logging.DEBUG
#default_loglevel=logging.INFO
#default_loglevel=logging.WARNING

logging.basicConfig(level=default_loglevel, format='%(levelname)s: %(message)s')

prodj = ProDj(enable_pdb=args.enable_pdb)
app = QApplication([])
gui = Gui(prodj, show_color_waveform=args.color_waveform or args.color, show_color_preview=args.color_preview or args.color)

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
