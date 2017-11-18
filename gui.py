import logging
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QSizePolicy, QHBoxLayout, QVBoxLayout, QWidget
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtCore import pyqtSignal, Qt, QSize
import sys
import math
from threading import Lock

from gui_browser import Browser, printableField
from waveform_gl import GLWaveformWidget

class ClickableLabel(QLabel):
  clicked = pyqtSignal()
  def mousePressEvent(self, event):
    self.clicked.emit()

class PreviewWaveformWidget(QWidget):
  redraw_signal = pyqtSignal()

  def __init__(self, parent):
    super().__init__(parent)
    self.pixmap_width = 400
    self.pixmap_height = 34
    self.setMinimumSize(self.pixmap_width, self.pixmap_height)
    self.data = None
    self.pixmap = None
    self.pixmap_lock = Lock()
    self.position = 0 # relative, between 0 and 1
    self.redraw_signal.connect(self.update)

  def clear(self):
    self.setData(None)

  def setData(self, data):
    with self.pixmap_lock:
      self.data = data
      self.pixmap = self.drawPreviewWaveformPixmap()
    self.redraw_signal.emit()

  def sizeHint(self):
    return QSize(self.pixmap_width, self.pixmap_height)

  def heightForWidth(self, width):
    return width*self.pixmap_height//self.pixmap_width

  def setPosition(self, relative):
    if relative != self.position:
      self.position = relative
      self.redraw_signal.emit()

  def paintEvent(self, e):
    painter = QPainter()
    painter.begin(self)
    with self.pixmap_lock:
      if self.pixmap is not None:
        scaled_pixmap = self.pixmap.scaled(self.size(), Qt.KeepAspectRatio)
        painter.drawPixmap(0, 0, scaled_pixmap)
        painter.fillRect(self.position*scaled_pixmap.width(), 0, 2, scaled_pixmap.height(), Qt.red)
    painter.end()

  def drawPreviewWaveformPixmap(self):
    if self.data is None:
      return None
    pixmap = QPixmap(self.pixmap_width, self.pixmap_height)
    pixmap.fill(Qt.black)
    painter = QPainter()
    painter.begin(pixmap)
    painter.setBrush(Qt.SolidPattern)
    if self.data and len(self.data) >= self.pixmap_width*2:
      for x in range(0, self.pixmap_width):
        height = self.data[2*x] # only seen from 2..23
        whiteness = self.data[2*x+1]+1 # only seen from 1..6
        painter.setPen(QColor(36*whiteness, 36*whiteness, 255))
        painter.drawLine(x, 31, x, 31-height)
    # base line
    painter.setPen(Qt.white)
    painter.drawLine(0,33,399,33)
    painter.end()
    return pixmap

class BeatBarWidget(QWidget):
  def __init__(self, parent):
    super().__init__(parent)
    self.setMinimumSize(100, 12)
    self.beat = 0

  def setBeat(self, beat):
    if beat != self.beat:
      self.beat = beat
      self.update()

  def paintEvent(self, e):
    painter = QPainter()
    painter.begin(self)
    painter.setBrush(Qt.SolidPattern)
    painter.setPen(Qt.yellow)
    box_gap = 6
    box_width = (self.size().width()-1-3*box_gap)//4
    box_height = self.size().height()-1
    for x in range(0,4):
      draw_x = x*(box_width+box_gap)
      painter.drawRect(draw_x, 0, box_width, box_height)
      if x == self.beat-1:
        painter.fillRect(draw_x, 0, box_width, box_height, Qt.yellow)
    painter.end()

class PlayerWidget(QFrame):
  def __init__(self, player_number, parent):
    super().__init__(parent)
    self.setFrameStyle(QFrame.Box | QFrame.Plain)
    self.labels = {}
    self.browse_dialog = None
    self.time_mode_remain = False

    # metadata and player info
    self.labels["title"] = QLabel(self)
    self.labels["title"].setStyleSheet("QLabel { color: white; font: bold 16pt; }")
    self.labels["title"].setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    self.labels["artist"] = QLabel(self)
    self.labels["artist"].setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    self.labels["album"] = QLabel(self)
    self.labels["album"].setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    self.labels["info"] = QLabel(self)
    self.labels["info"].setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    # artwork and player number
    self.labels["player_number"] = QLabel(self)
    self.labels["player_number"].setStyleSheet("QLabel { font: bold 12pt; qproperty-alignment: AlignCenter; background-color: white; color: black; }")
    self.setPlayerNumber(player_number)

    self.labels["artwork"] = QLabel(self)
    self.pixmap_empty = QPixmap(80,80)
    self.pixmap_empty.fill(QColor(40,40,40))
    self.labels["artwork"].setPixmap(self.pixmap_empty)

    # buttons below time/beat bar
    self.browse_button = QPushButton("BROWSE", self)
    self.browse_button.setFlat(True)
    self.browse_button.setStyleSheet("QPushButton { color: white; font: 10px; background-color: black; padding: 1px; border-style: outset; border-radius: 2px; border-width: 1px; border-color: gray; }")
    self.download_button = QPushButton("DLOAD", self)
    self.download_button.setFlat(True)
    self.download_button.setStyleSheet("QPushButton { color: white; font: 10px; background-color: black; padding: 1px; border-style: outset; border-radius: 2px; border-width: 1px; border-color: gray; }")

    self.labels["play_state"] = QLabel(self)
    self.labels["play_state"].setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    buttons_layout = QHBoxLayout()
    buttons_layout.addWidget(self.browse_button)
    buttons_layout.addWidget(self.download_button)
    buttons_layout.addWidget(self.labels["play_state"])
    buttons_layout.setStretch(2, 1)
    buttons_layout.setSpacing(3)

    self.browse_button.clicked.connect(self.openBrowseDialog)
    self.download_button.clicked.connect(self.downloadTrack)

    # time and beat bar
    self.elapsed_label = ClickableLabel("ELAPSED", self)
    self.elapsed_label.setStyleSheet("QLabel:disabled { color: gray; }")
    self.remain_label = ClickableLabel("REMAIN", self)
    self.remain_label.setStyleSheet("QLabel:disabled { color: gray; }")
    self.remain_label.setEnabled(False)
    self.time = ClickableLabel(self)
    self.time.setStyleSheet("QLabel { font: 32px; qproperty-alignment: AlignRight; }")
    self.time.setMaximumHeight(32)
    self.total_time_label = QLabel("TOTAL", self)
    self.total_time = QLabel(self)
    self.total_time.setStyleSheet("QLabel { font: 32px; qproperty-alignment: AlignRight; }")
    self.total_time.setMaximumHeight(32)
    self.beat_bar = BeatBarWidget(self)

    time_layout = QGridLayout()
    time_layout.addWidget(self.elapsed_label, 0, 0)
    time_layout.addWidget(self.remain_label, 1, 0)
    time_layout.addWidget(self.time, 0, 1, 2, 1)
    time_layout.addWidget(self.total_time_label, 2, 0)
    time_layout.addWidget(self.total_time, 2, 1, 2, 1)
    time_layout.addWidget(self.beat_bar, 4, 0, 1, 2)
    time_layout.addLayout(buttons_layout, 5, 0, 1, 2)
    time_layout.setHorizontalSpacing(0)

    self.elapsed_label.clicked.connect(self.toggleTimeMode)
    self.remain_label.clicked.connect(self.toggleTimeMode)
    self.time.clicked.connect(self.toggleTimeMode)

    # waveform widgets
    self.waveform = GLWaveformWidget(self)
    self.waveform.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.preview_waveform = PreviewWaveformWidget(self)
    qsp = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    qsp.setHeightForWidth(True)
    self.preview_waveform.setSizePolicy(qsp)

    # BPM / Pitch / Master display
    bpm_label = QLabel("BPM", self)
    bpm_label.setContentsMargins(4,0,4,0)
    bpm_label.setStyleSheet("QLabel { color: white; font: bold 8pt; qproperty-alignment: AlignLeft; }")
    self.labels["bpm"] = QLabel(self)
    self.labels["bpm"].setContentsMargins(4,0,4,0)
    self.labels["bpm"].setStyleSheet("QLabel { color: white; font: bold 16pt; qproperty-alignment: AlignRight; }")
    self.labels["pitch"] = QLabel("+80.00%", self)
    self.labels["pitch"].setContentsMargins(4,0,4,0)
    self.labels["pitch"].setStyleSheet("QLabel { color: white; font: bold 14pt; qproperty-alignment: AlignRight; }")
    self.labels["pitch"].show() # makes the widget calculate its current size
    self.labels["pitch"].setMinimumSize(self.labels["pitch"].size()) # to prevent jumping in size when changing pitch
    self.labels["master"] = QLabel("MASTER", self)
    self.labels["master"].setStyleSheet("QLabel { font: bold; qproperty-alignment: AlignCenter; background-color: green; color: black; } QLabel:disabled { background-color: gray; }")
    self.labels["sync"] = QLabel("SYNC", self)
    self.labels["sync"].setStyleSheet("QLabel { font: bold; qproperty-alignment: AlignCenter; background-color: blue; color: black; } QLabel:disabled { background-color: gray; }")

    bpm_box = QFrame(self)
    bpm_box.setFrameStyle(QFrame.Box | QFrame.Plain)
    speed_layout = QVBoxLayout(bpm_box)
    speed_layout.addWidget(bpm_label)
    speed_layout.addWidget(self.labels["bpm"])
    speed_layout.addWidget(self.labels["pitch"])
    speed_layout.addWidget(self.labels["master"])
    speed_layout.addWidget(self.labels["sync"])
    speed_layout.setSpacing(0)
    speed_layout.setContentsMargins(0,0,0,0)

    # main layout
    layout = QGridLayout(self)
    layout.addWidget(self.labels["player_number"], 0, 0)
    layout.addWidget(self.labels["artwork"], 1, 0, 3, 1)
    layout.addWidget(self.labels["title"], 0, 1)
    layout.addWidget(self.labels["artist"], 1, 1)
    layout.addWidget(self.labels["album"], 2, 1)
    layout.addWidget(self.labels["info"], 3, 1)
    layout.addLayout(time_layout, 0, 2, 4, 1)
    layout.addWidget(bpm_box, 0, 3, 4, 1)
    layout.addWidget(self.waveform, 4, 0, 1, 4)
    layout.addWidget(self.preview_waveform, 5, 0, 1, 4)
    layout.setColumnStretch(1, 2)

    self.reset()

  def unload(self):
    self.setMetadata("Not loaded", "", "")
    self.setArtwork(None)
    self.setTime(None)
    self.setTotalTime(None)
    self.beat_bar.setBeat(0)
    self.waveform.clear()
    self.preview_waveform.clear()

  def reset(self):
    self.unload()
    self.labels["info"].setText("No player connected")
    self.setSpeed("")
    self.setMaster(False)
    self.setSync(False)
    self.track_id = 0 # track id of displayed metadata, waveform etc from dbclient queries

  def setPlayerNumber(self, player_number):
    self.player_number = player_number
    self.labels["player_number"].setText("PLAYER {}".format(self.player_number))
    if self.browse_dialog is not None:
      self.browse_dialog.setPlayerNumber(player_number)

  def setMaster(self, master):
    self.labels["master"].setEnabled(master)

  def setSync(self, sync):
    self.labels["sync"].setEnabled(sync)

  def setPlayerInfo(self, model, ip_addr, fw=""):
    self.labels["info"].setText("{} {} {}".format(model, fw, ip_addr))

  def setSpeed(self, bpm, pitch=None):
    if pitch is None:
      pitch = 1
    self.labels["pitch"].setText("{:+.2f}%".format((pitch-1)*100))
    if isinstance(bpm, str):
      self.labels["bpm"].setText("--.--")
    else:
      pitched_bpm = bpm*pitch
      self.labels["bpm"].setText("{:.2f}".format(pitched_bpm))

  def setMetadata(self, title, artist, album):
    self.labels["title"].setText(title)
    self.labels["artist"].setText(artist)
    self.labels["album"].setText(album)

  def setArtwork(self, data):
    if data is None:
      self.labels["artwork"].setPixmap(self.pixmap_empty)
    else:
      p = QPixmap()
      p.loadFromData(data)
      self.labels["artwork"].setPixmap(p)

  def setTime(self, seconds, total=None):
    if seconds is not None:
      if total is not None and self.time_mode_remain:
        seconds = total-seconds
      self.time.setText("{}{:02d}:{:02d}".format("" if self.time_mode_remain==False else "-", int(seconds//60), int(seconds)%60))
    else:
      self.time.setText("00:00")

  def setTotalTime(self, seconds):
    if seconds is not None:
      self.total_time.setText("{:02d}:{:02d}".format(int(seconds//60), int(seconds)%60))
    else:
      self.total_time.setText("00:00")

  def setPlayState(self, state):
    self.labels["play_state"].setText(printableField(state))

  def toggleTimeMode(self):
    self.time_mode_remain = not self.time_mode_remain
    self.elapsed_label.setEnabled(not self.time_mode_remain)
    self.remain_label.setEnabled(self.time_mode_remain)

  def openBrowseDialog(self):
    if self.browse_dialog is None:
      self.browse_dialog = Browser(self.parent().prodj, self.player_number)
    self.browse_dialog.show()

  def downloadTrack(self):
    logging.info("Gui: Player %d track download requested", self.player_number)
    c = self.parent().prodj.cl.getClient(self.player_number)
    if c is None:
      logging.error("Gui: Download failed, player %d unknown", self.player_number)
      return
    self.parent().prodj.dbc.get_mount_info(c.loaded_player_number, c.loaded_slot,
      c.track_id, self.parent().prodj.nfs.enqueue_download_from_mount_info)

  # make browser dialog close when player window disappears
  def hideEvent(self, event):
    if self.browse_dialog is not None:
      self.browse_dialog.close()
    event.accept()

class Gui(QWidget):
  keepalive_signal = pyqtSignal(int)
  client_change_signal = pyqtSignal(int)

  def __init__(self, prodj):
    super().__init__()
    self.prodj = prodj
    self.setWindowTitle('Pioneer ProDJ Link Monitor')

    self.setAutoFillBackground(True)

    self.keepalive_signal.connect(self.keepalive_slot)
    self.client_change_signal.connect(self.client_change_slot)

    self.players = {}
    self.layout = QGridLayout(self)
    # "xy" = player 1 + 2 in the first row
    # "yx" = player 1 + 2 in the first column
    self.layout_mode = "xy"
    self.create_player(0)

    self.show()

  def get_layout_coordinates(self, player_number):
    if player_number == 0:
      return 0, 0
    if self.layout_mode == "xy":
      return (player_number-1)//2, (player_number-1)%2
    elif self.layout_mode == "yx":
      return (player_number-1)%2, (player_number-1)//2
    else:
      raise Exception("Unknown Gui layout mode {}".format(str(layout_mode)))

  def create_player(self, player_number):
    if player_number in self.players:
      return
    if len(self.players) == 1 and 0 in self.players:
      logging.debug("Gui: reassigning default player 0 to player %d", player_number)
      self.players[0].setPlayerNumber(player_number)
      self.layout.removeWidget(self.players[0])
      self.players = {player_number: self.players[0]}
    else:
      logging.info("Gui: Creating player {}".format(player_number))
      self.players[player_number] = PlayerWidget(player_number, self)
    self.players[player_number].show()
    self.layout.addWidget(self.players[player_number], *self.get_layout_coordinates(player_number))

  def remove_player(self, player_number):
    if not player_number in self.players:
      return
    self.layout.removeWidget(self.players[player_number])
    if len(self.players) == 1:
      logging.info("All players gone, resetting last player to 0")
      self.players = {0: self.players[player_number]}
      self.players[0].setPlayerNumber(0)
      self.players[0].reset()
      self.layout.addWidget(self.players[0], *self.get_layout_coordinates(0))
    else:
      self.players[player_number].hide()
      self.players[player_number].deleteLater()
      del self.players[player_number]
    logging.info("Gui: Removed player {}".format(player_number))

  # has to be called using a signal, otherwise windows are created standalone
  def keepalive_callback(self, player_number):
    self.keepalive_signal.emit(player_number)

  def keepalive_slot(self, player_number):
    if player_number not in range(1,5):
      return
    if not player_number in self.players: # on new keepalive, create player
      self.create_player(player_number)
    c = self.prodj.cl.getClient(player_number)
    self.players[player_number].setPlayerInfo(c.model, c.ip_addr)

  def client_change_callback(self, player_number):
    self.client_change_signal.emit(player_number)

  def client_change_slot(self, player_number):
    if not player_number in self.players:
      return
    c = self.prodj.cl.getClient(player_number)
    if c is None:
      self.remove_player(player_number)
      return
    self.players[player_number].setSpeed(c.bpm, c.pitch)
    self.players[player_number].setMaster("master" in c.state)
    self.players[player_number].setSync("sync" in c.state)
    self.players[player_number].beat_bar.setBeat(c.beat)
    self.players[player_number].waveform.setPosition(c.position, c.actual_pitch, c.play_state)
    self.players[player_number].setPlayState(c.play_state)
    if c.metadata is not None and "duration" in c.metadata:
      self.players[player_number].setTime(c.position, c.metadata["duration"])
      self.players[player_number].setTotalTime(c.metadata["duration"])
      if c.position is not None:
        self.players[player_number].preview_waveform.setPosition(c.position/c.metadata["duration"])
    else:
      self.players[player_number].setTime(c.position, None)
      self.players[player_number].setTotalTime(None)
    if len(c.fw) > 0:
      self.players[player_number].setPlayerInfo(c.model, c.ip_addr, c.fw)

    # track changed -> reload metadata
    if self.players[player_number].track_id != c.track_id:
      self.players[player_number].track_id = c.track_id # remember requested track id
      if c.track_id != 0:
        logging.info("Gui: track id of player %d changed to %d, requesting metadata", player_number, c.track_id)
        self.prodj.dbc.get_metadata(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbclient_callback)
        # we do not get artwork yet because we need metadata to know the artwork_id
        self.prodj.dbc.get_preview_waveform(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbclient_callback)
        self.prodj.dbc.get_beatgrid(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbclient_callback)
        self.prodj.dbc.get_waveform(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbclient_callback)
      else:
        logging.info("Gui: track id of player %d changed to %d, unloading", player_number, c.track_id)
        self.players[player_number].unload()

  def dbclient_callback(self, request, source_player_number, slot, item_id, reply):
    if request == "artwork":
      iterator = self.prodj.cl.clientsByLoadedTrackArtwork
    else:
      iterator = self.prodj.cl.clientsByLoadedTrack
    for client in iterator(source_player_number, slot, item_id):
      player_number = client.player_number if client is not None else None
      if not player_number in self.players or reply is None:
        continue
      logging.debug("Gui: dbclient_callback %s source player %d to widget player %d", request, source_player_number, player_number)
      if request == "metadata":
        if len(reply) == 0:
          logging.warning("Gui: empty metadata received")
          continue
        self.players[player_number].setMetadata(reply["title"], reply["artist"], reply["album"])
        with open("tracks.log", "a") as f:
          f.write("{} - {} ({})\n".format(reply["artist"], reply["title"], reply["album"]))
        if "artwork_id" in reply and reply["artwork_id"] != 0:
          self.prodj.dbc.get_artwork(source_player_number, slot, reply["artwork_id"], self.dbclient_callback)
        else:
          self.players[player_number].setArtwork(None)
      elif request == "artwork":
        self.players[player_number].setArtwork(reply)
      elif request == "waveform":
        self.players[player_number].waveform.setData(reply)
      elif request == "preview_waveform":
        self.players[player_number].preview_waveform.setData(reply)
      elif request == "beatgrid":
        self.players[player_number].waveform.setBeatgridData(reply)
      else:
        logging.warning("Gui: unhandled dbserver callback %s", request)

  def media_callback(self, cl, player_number, slot):
    if not player_number in self.players:
      return
    if self.players[player_number].browse_dialog is not None:
      logging.debug("Gui: refresh media signal to player %d slot %s", player_number, slot)
      self.players[player_number].browse_dialog.refreshMediaSignal.emit(slot)
