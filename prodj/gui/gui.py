import sys
import logging
import math
from threading import Lock
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QMenu, QPushButton, QSizePolicy, QHBoxLayout, QVBoxLayout, QWidget
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtCore import pyqtSignal, Qt, QSize

from .gui_browser import Browser, printableField
from .waveform_gl import GLWaveformWidget
from .preview_waveform_qt import PreviewWaveformWidget

class ClickableLabel(QLabel):
  clicked = pyqtSignal()
  def mousePressEvent(self, event):
    self.clicked.emit()

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
  time_mode_remain_changed_signal = pyqtSignal(bool)

  def __init__(self, player_number, parent):
    super().__init__(parent)
    self.setObjectName("PlayerFrame")
    self.setProperty("on_air", False)
    self.setStyleSheet("#PlayerFrame { border: 3px solid white; } #PlayerFrame[on_air=true] { border: 3px solid red; }")
    self.labels = {}
    self.browse_dialog = None
    self.time_mode_remain = False
    self.show_color_waveform = parent.show_color_waveform
    self.show_color_preview = parent.show_color_preview
    self.parent_gui = parent

    # metadata and player info
    self.labels["title"] = QLabel(self)
    self.labels["title"].setStyleSheet("QLabel { color: white; font: bold 16pt; }")
    self.labels["title"].setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    self.labels["artist"] = QLabel(self)
    self.labels["artist"].setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    self.labels["artist"].setStyleSheet("QLabel { color: white; }")
    self.labels["album"] = QLabel(self)
    self.labels["album"].setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    self.labels["album"].setStyleSheet("QLabel { color: white; }")
    self.labels["info"] = QLabel(self)
    self.labels["info"].setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    self.labels["info"].setStyleSheet("QLabel { color: white; }")

    # artwork and player number
    self.labels["player_number"] = QLabel(self)
    self.labels["player_number"].setStyleSheet("QLabel { font: bold 12pt; qproperty-alignment: AlignCenter; background-color: white; color: black; }")
    self.setPlayerNumber(player_number)

    self.labels["artwork"] = QLabel(self)
    self.pixmap_empty = QPixmap(80,80)
    self.pixmap_empty.fill(QColor(40,40,40))
    self.labels["artwork"].setPixmap(self.pixmap_empty)

    # menu button
    self.menu_button = QPushButton("MENU", self)
    self.menu_button.setFlat(True)
    self.menu_button.setStyleSheet("QPushButton { color: white; font: 10px; background-color: black; padding: 1px; border-style: outset; border-radius: 2px; border-width: 1px; border-color: gray; }")

    self.menu = QMenu(self.menu_button)
    action_browse = self.menu.addAction("Browse Media")
    action_browse.triggered.connect(self.openBrowseDialog)
    action_download = self.menu.addAction("Download track")
    action_download.triggered.connect(self.downloadTrack)
    action_start = self.menu.addAction("Start playback")
    action_start.triggered.connect(self.playbackStart)
    action_stop = self.menu.addAction("Stop playback")
    action_stop.triggered.connect(self.playbackStop)
    self.menu_button.setMenu(self.menu)

    self.labels["play_state"] = QLabel(self)
    self.labels["play_state"].setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    buttons_layout = QHBoxLayout()
    buttons_layout.addWidget(self.menu_button)
    buttons_layout.addWidget(self.labels["play_state"])
    buttons_layout.setStretch(1, 1)
    buttons_layout.setSpacing(3)

    # time and beat bar
    self.elapsed_label = ClickableLabel("ELAPSED", self)
    self.elapsed_label.setStyleSheet("QLabel { color: white; } QLabel:disabled { color: gray; }")
    self.remain_label = ClickableLabel("REMAIN", self)
    self.remain_label.setStyleSheet("QLabel { color: white; } QLabel:disabled { color: gray; }")
    self.remain_label.setEnabled(False)
    self.time = ClickableLabel(self)
    self.time.setStyleSheet("QLabel { color: white; font: 32px; qproperty-alignment: AlignRight; }")
    self.time.setMaximumHeight(32)
    self.total_time_label = QLabel("TOTAL", self)
    self.total_time = QLabel(self)
    self.total_time.setStyleSheet("QLabel { color: white; font: 32px; qproperty-alignment: AlignRight; }")
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
    self.time_mode_remain_changed_signal.connect(self.setTimeMode)

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
    self.labels["slot"] = QLabel("", self)
    self.labels["slot"].setContentsMargins(4,0,4,0)
    self.labels["slot"].setStyleSheet("QLabel { color: white; font: bold 8pt; qproperty-alignment: AlignLeft; }")
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

    speed_top_layout = QHBoxLayout()
    speed_top_layout.addWidget(bpm_label)
    speed_top_layout.addWidget(self.labels["slot"])
    speed_top_layout.setSpacing(1)

    bpm_box = QFrame(self)
    bpm_box.setFrameStyle(QFrame.Box | QFrame.Plain)
    speed_layout = QVBoxLayout(bpm_box)
    speed_layout.addLayout(speed_top_layout)
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
    self.track_id = 0

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
        seconds = total-seconds if total > seconds else 0
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

  def setSlotInfo(self, player, slot):
    self.labels["slot"].setText(f"{player} {slot.upper()}")

  def toggleTimeMode(self):
    self.time_mode_remain_changed_signal.emit(not self.time_mode_remain)

  def setTimeMode(self, time_mode_remain):
    self.time_mode_remain = time_mode_remain
    self.elapsed_label.setEnabled(not self.time_mode_remain)
    self.remain_label.setEnabled(self.time_mode_remain)

  def openBrowseDialog(self):
    if self.browse_dialog is None:
      self.browse_dialog = Browser(self.parent().prodj, self.player_number)
    self.browse_dialog.show()

  def downloadTrack(self):
    logging.info("Player %d track download requested", self.player_number)
    c = self.parent().prodj.cl.getClient(self.player_number)
    if c is None:
      logging.error("Download failed, player %d unknown", self.player_number)
      return
    self.parent().prodj.data.get_mount_info(c.loaded_player_number, c.loaded_slot,
      c.track_id, self.parent().prodj.nfs.enqueue_download_from_mount_info)

  def playbackStart(self):
    self.parent_gui.prodj.vcdj.command_fader_start_single(self.player_number, start=True)

  def playbackStop(self):
    self.parent_gui.prodj.vcdj.command_fader_start_single(self.player_number, start=False)

  # make browser dialog close when player window disappears
  def hideEvent(self, event):
    if self.browse_dialog is not None:
      self.browse_dialog.close()
    event.accept()

  def setOnAir(self, on_air):
    self.setProperty("on_air", on_air)
    self.style().unpolish(self);
    self.style().polish(self);
    self.update()

class Gui(QWidget):
  keepalive_signal = pyqtSignal(int)
  client_change_signal = pyqtSignal(int)

  def __init__(self, prodj, show_color_waveform=False, show_color_preview=False, arg_layout="xy"):
    super().__init__()
    self.prodj = prodj
    self.setWindowTitle('Pioneer ProDJ Link Monitor')

    self.setAutoFillBackground(True)

    self.keepalive_signal.connect(self.keepalive_slot)
    self.client_change_signal.connect(self.client_change_slot)

    self.show_color_waveform = show_color_waveform
    self.show_color_preview = show_color_preview

    self.players = {}
    self.layout = QGridLayout(self)
    # "xy" = player 1 + 2 in the first row
    # "yx" = player 1 + 2 in the first column
    # "xx" = player 1 + 4 in the first row
    # "yy" = player 2 + 3 in the first row
    # "row" = player 1 + 2 + 3 + 4 in a single row
    # "column" = = player 1 + 2 + 3 + 4 in a single column
    self.layout_mode = arg_layout
    self.layouts = {
      "xy": [(0,0), (0,1), (1,0), (1,1)],
      "yx": [(0,0), (1,0), (0,1), (1,1)],
      "xx": [(0,0), (1,0), (1,1), (0,1)],
      "yy": [(1,0), (0,0), (0,1), (1,1)],
      "row": [(0,0), (0,1), (0,2), (1,3)],
      "column": [(0,0), (1,0), (2,0), (3,0)]
    }
    self.create_player(0)

    self.show()

  def get_layout_coordinates(self, widget_number):
    if widget_number == 0:
      return 0,0
    if widget_number > 4:
      raise Exception("Unhandled widget number {}".format(widget_number))
    if not self.layout_mode in self.layouts:
      raise Exception("Unknown Gui layout mode {}".format(self.layout_mode))
    return self.layouts[self.layout_mode][widget_number-1]

  def update_player_layout(self):
    n = 1
    for player in sorted(self.players.values(), key=lambda x: x.player_number):
      x,y = self.get_layout_coordinates(n)
      if self.layout.itemAtPosition(x, y) != player:
        self.layout.removeWidget(player)
        self.layout.addWidget(player, x, y)
      n = n+1

  def connect_linked_player_controls(self, player_number):
    for pn, p in self.players.items():
      if pn != player_number:
        self.players[player_number].waveform.waveform_zoom_changed_signal.connect(p.waveform.setZoom, type = Qt.UniqueConnection | Qt.AutoConnection)
        p.waveform.waveform_zoom_changed_signal.connect(self.players[player_number].waveform.setZoom, type = Qt.UniqueConnection | Qt.AutoConnection)
        self.players[player_number].time_mode_remain_changed_signal.connect(p.setTimeMode, type = Qt.UniqueConnection | Qt.AutoConnection)
        p.time_mode_remain_changed_signal.connect(self.players[player_number].setTimeMode, type = Qt.UniqueConnection | Qt.AutoConnection)

  # return widget of a player or create it if it does not exist yet
  def create_player(self, player_number):
    if player_number in self.players:
      return self.players[player_number]
    if player_number not in range(0,5):
      return None
    if len(self.players) == 1 and 0 in self.players:
      logging.debug("reassigning default player 0 to player %d", player_number)
      self.players[0].setPlayerNumber(player_number)
      self.players = {player_number: self.players[0]}
    else:
      logging.info("Creating player {}".format(player_number))
      self.players[player_number] = PlayerWidget(player_number, self)
    self.connect_linked_player_controls(player_number)
    self.players[player_number].show()
    self.update_player_layout()
    return self.players[player_number]

  def remove_player(self, player_number):
    if not player_number in self.players:
      return
    player = self.players[player_number]
    if len(self.players) == 1:
      logging.info("All players gone, resetting last player to 0")
      self.players = {0: player}
      self.players[0].setPlayerNumber(0)
      self.players[0].reset()
    else:
      player.hide()
      player.deleteLater()
      del self.players[player_number]
    self.update_player_layout()
    logging.info("Removed player {}".format(player_number))

  # has to be called using a signal, otherwise windows are created standalone
  def keepalive_callback(self, player_number):
    self.keepalive_signal.emit(player_number)

  def keepalive_slot(self, player_number):
    player = self.create_player(player_number)
    c = self.prodj.cl.getClient(player_number)
    if c is not None and player is not None:
      player.setPlayerInfo(c.model, c.ip_addr)

  def client_change_callback(self, player_number):
    self.client_change_signal.emit(player_number)

  def client_change_slot(self, player_number):
    player = self.create_player(player_number)
    if player is None:
      return
    c = self.prodj.cl.getClient(player_number)
    if c is None:
      self.remove_player(player_number)
      return
    if c.type != "cdj":
      return
    player.setSpeed(c.bpm, c.pitch)
    player.setMaster("master" in c.state)
    player.setSync("sync" in c.state)
    player.beat_bar.setBeat(c.beat)
    player.waveform.setPosition(c.position, c.actual_pitch, c.play_state)
    player.setPlayState(c.play_state)
    player.setOnAir(c.on_air)
    player.setSlotInfo(c.loaded_player_number, c.loaded_slot)
    if c.metadata is not None and "duration" in c.metadata:
      player.setTime(c.position, c.metadata["duration"])
      player.setTotalTime(c.metadata["duration"])
      if c.position is not None:
        player.preview_waveform.setPosition(c.position/c.metadata["duration"])
    else:
      player.setTime(c.position, None)
      player.setTotalTime(None)
    if len(c.fw) > 0:
      player.setPlayerInfo(c.model, c.ip_addr, c.fw)

    # track changed -> reload metadata
    if player.track_id != c.track_id:
      player.track_id = c.track_id # remember requested track id
      if c.track_id != 0:
        if c.loaded_slot in ["sd", "usb"] and c.track_analyze_type == "rekordbox":
          logging.info("track id of player %d changed to %d, requesting metadata", player_number, c.track_id)
          self.prodj.data.get_metadata(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbclient_callback)
          if self.show_color_preview:
            self.prodj.data.get_color_preview_waveform(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbclient_callback)
          else:
            self.prodj.data.get_preview_waveform(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbclient_callback)
          if self.show_color_waveform:
            self.prodj.data.get_color_waveform(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbclient_callback)
          else:
            self.prodj.data.get_waveform(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbclient_callback)
          self.prodj.data.get_beatgrid(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbclient_callback)
          # we do not get artwork yet because we need metadata to know the artwork_id
        elif c.track_analyze_type == "file":
          logging.info("player %d loaded bare file %d, requesting info", player_number, c.track_id)
          self.prodj.data.get_track_info(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbclient_callback)
        elif c.track_analyze_type == "cd":
          logging.info("player %d loaded cd track %d", player_number, c.track_id)
          player.setMetadata(f"Track {c.track_id}", "CD", "")
          player.setArtwork(None) # no artwork for unanalyzed tracks
          player.waveform.clear()
          player.preview_waveform.clear()
        else:
          logging.warning("unable to handle track %d in player %d, no known metadata method", c.track_id, player_number)
          player.unload()
      else:
        logging.info("track id of player %d changed to %d, unloading", player_number, c.track_id)
        player.unload()

  def dbclient_callback(self, request, source_player_number, slot, item_id, reply):
    if request == "artwork":
      iterator = self.prodj.cl.clientsByLoadedTrackArtwork
    else:
      iterator = self.prodj.cl.clientsByLoadedTrack
    for client in iterator(source_player_number, slot, item_id):
      player_number = client.player_number if client is not None else None
      if not player_number in self.players or reply is None:
        continue
      player = self.players[player_number]
      logging.debug("dbclient_callback %s source player %d to widget player %d", request, source_player_number, player_number)
      if request == "metadata":
        if len(reply) == 0:
          logging.warning("empty metadata received")
          continue
        player.setMetadata(reply["title"], reply["artist"], reply["album"])
        if "artwork_id" in reply and reply["artwork_id"] != 0:
          self.prodj.data.get_artwork(source_player_number, slot, reply["artwork_id"], self.dbclient_callback)
        else:
          player.setArtwork(None)
      elif request == "artwork":
        player.setArtwork(reply)
      elif request == "waveform":
        player.waveform.setData(reply, False)
      elif request == "preview_waveform":
        player.preview_waveform.setData(reply)
      elif request == "color_waveform":
        player.waveform.setData(reply, True)
      elif request == "color_preview_waveform":
        player.preview_waveform.setData(reply, True)
      elif request == "beatgrid":
        player.waveform.setBeatgridData(reply)
      elif request == "track_info":
        player.setMetadata(reply["title"], reply["artist"], reply["album"])
        player.setArtwork(None) # no artwork for unanalyzed tracks
        player.waveform.clear()
        player.preview_waveform.clear()
      else:
        logging.warning("unhandled dbserver callback %s", request)

  def media_callback(self, cl, player_number, slot):
    if not player_number in self.players:
      return
    if self.players[player_number].browse_dialog is not None:
      logging.debug("refresh media signal to player %d slot %s", player_number, slot)
      self.players[player_number].browse_dialog.refreshMediaSignal.emit(slot)
