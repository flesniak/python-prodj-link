#!/usr/bin/env python3

import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette
from PyQt5.QtCore import Qt
import signal
import argparse

from prodj.core.prodj import ProDj
from prodj.gui.gui import Gui

def arg_size(value):
  number = int(value)
  if number < 1000 or number > 60000:
    raise argparse.ArgumentTypeError("%s is not between 1000 and 60000".format(value))
  return number

def arg_layout(value):
  if value not in ["xy", "yx", "xx", "yy", "row", "column"]:
    raise argparse.ArgumentTypeError("%s is not a value from the list xy, yx, xx, yy, row or column".format(value))
  return value

parser = argparse.ArgumentParser(description='Python ProDJ Link')
provider_group = parser.add_mutually_exclusive_group()
provider_group.add_argument('--disable-pdb', dest='enable_pdb', action='store_false', help='Disable PDB provider')
provider_group.add_argument('--disable-dbc', dest='enable_dbc', action='store_false', help='Disable DBClient provider')
parser.add_argument('--color-preview', action='store_true', help='Show NXS2 colored preview waveforms')
parser.add_argument('--color-waveform', action='store_true', help='Show NXS2 colored big waveforms')
parser.add_argument('-c', '--color', action='store_true', help='Shortcut for --color-preview and --color-waveform')
parser.add_argument('-q', '--quiet', action='store_const', dest='loglevel', const=logging.WARNING, help='Only display warning messages', default=logging.INFO)
parser.add_argument('-d', '--debug', action='store_const', dest='loglevel', const=logging.DEBUG, help='Display verbose debugging information')
parser.add_argument('--dump-packets', action='store_const', dest='loglevel', const=0, help='Dump packet fields for debugging', default=logging.INFO)
parser.add_argument('--chunk-size', dest='chunk_size', help='Chunk size of NFS downloads (high values may be faster but fail on some networks)', type=arg_size, default=None)
parser.add_argument('-f', '--fullscreen', action='store_true', help='Start with fullscreen window')
parser.add_argument('-l', '--layout', dest='layout', help='Display layout, values are xy (default), yx, xx, yy, row or column', type=arg_layout, default="xy")

args = parser.parse_args()

logging.basicConfig(level=args.loglevel, format='%(levelname)-7s %(module)s: %(message)s')

prodj = ProDj()
prodj.data.pdb_enabled = args.enable_pdb
prodj.data.dbc_enabled = args.enable_dbc
if args.chunk_size is not None:
  prodj.nfs.setDownloadChunkSize(args.chunk_size)
app = QApplication([])
gui = Gui(prodj, show_color_waveform=args.color_waveform or args.color, show_color_preview=args.color_preview or args.color, arg_layout=args.layout)
if args.fullscreen:
  gui.setWindowState(Qt.WindowFullScreen | Qt.WindowMaximized | Qt.WindowActive)

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
