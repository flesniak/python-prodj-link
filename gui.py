import logging
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QLCDNumber, QSizePolicy, QVBoxLayout, QWidget
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtCore import pyqtSignal, Qt, QSize
import sys
import math

from waveform_gl import GLWaveformWidget
from waveform_qt import WaveformWidget

class PreviewWaveformWidget(QWidget):
  def __init__(self, parent):
    super().__init__(parent)
    self.setMinimumSize(400, 34)
    self.data = None
    self.pixmap = None
    self.position = 0

  def setData(self, data):
    self.data = data
    self.pixmap = self.drawPreviewWaveformPixmap()
    self.update()

  def sizeHint(self):
    return QSize(400, 34)

  def heightForWidth(self, width):
    #logging.info("preview width {} height {}".format(width, int(width/400*34)))
    return int(width/400*34)

  def setPosition(self, relative):
    new_position = int(400*relative)
    if new_position != self.position:
      self.position = new_position
      self.update()

  def paintEvent(self, e):
    #logging.info("preview size {}".format(self.size()))
    painter = QPainter()
    painter.begin(self)
    if self.pixmap is not None:
      scaled_pixmap = self.pixmap.scaled(self.size(), Qt.KeepAspectRatio)
      painter.drawPixmap(0,0,scaled_pixmap)
      painter.fillRect(self.position, 0, 2, scaled_pixmap.height(), Qt.red)
    painter.end()

  def drawPreviewWaveformPixmap(self):
    if self.data is None:
      return None
    pixmap = QPixmap(400, 34)
    pixmap.fill(Qt.black)
    painter = QPainter()
    painter.begin(pixmap)
    painter.setBrush(Qt.SolidPattern)
    if self.data and len(self.data) >= 400*2:
      for x in range(0,400):
        height = self.data[2*x] # only seen from 2..23
        whiteness = self.data[2*x+1]+1 # only seen from 1..6
        painter.setPen(QColor(36*whiteness, 36*whiteness, 255))
        painter.drawLine(x,31,x,31-height)
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
    self.track_id = None # track id of displayed metadata, waveform etc from dbclient queries

    # metadata and player info
    self.labels["title"] = QLabel(self)
    self.labels["title"].setStyleSheet("QLabel { color: white; font: bold 16pt; }")
    self.labels["artist"] = QLabel(self)
    self.labels["album"] = QLabel(self)
    self.labels["info"] = QLabel(self)

    # artwork and player number
    self.labels["player_number"] = QLabel(self)
    self.labels["player_number"].setStyleSheet("QLabel { font: bold 14pt; qproperty-alignment: AlignCenter; background-color: white; color: black; }")
    self.setPlayerNumber(player_number)

    self.labels["artwork"] = QLabel(self)
    self.pixmap_empty = QPixmap(80,80)
    self.pixmap_empty.fill(QColor(40,40,40))
    self.labels["artwork"].setPixmap(self.pixmap_empty)

    # time and beat bar
    self.time = QLCDNumber(5, self)
    self.time.setSegmentStyle(QLCDNumber.Flat)
    self.time.setMinimumSize(160,10)
    self.beat_bar = BeatBarWidget(self)

    time_layout = QVBoxLayout()
    time_layout.addWidget(self.time)
    time_layout.addWidget(self.beat_bar)
    #time_layout.addStretch(1)
    time_layout.setStretch(0, 10)
    time_layout.setStretch(1, 2)

    # waveform widgets
    self.waveform = GLWaveformWidget(self)
    #self.waveform.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.preview_waveform = PreviewWaveformWidget(self)
    #self.preview_waveform.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    #qsp = QSizePolicy(QSizePolicy.Preferred,QSizePolicy.Minimum)
    #qsp.setHeightForWidth(True)
    #self.preview_waveform.setSizePolicy(qsp)

    # BPM / Pitch / Master display
    bpm_label = QLabel("BPM", self)
    bpm_label.setStyleSheet("QLabel { color: white; font: bold 8pt; qproperty-alignment: AlignLeft; }")
    self.labels["bpm"] = QLabel(self)
    self.labels["bpm"].setStyleSheet("QLabel { color: white; font: bold 16pt; qproperty-alignment: AlignRight; }")
    self.labels["pitch"] = QLabel("+10.00%", self)
    self.labels["pitch"].setStyleSheet("QLabel { color: white; font: bold 14pt; qproperty-alignment: AlignRight; }")
    self.labels["pitch"].show() # makes the widget calculate its current size
    self.labels["pitch"].setMinimumSize(self.labels["pitch"].size())
    self.labels["master"] = QLabel("MASTER", self) # stylesheet set by setMaster()

    bpm_box = QFrame(self)
    bpm_box.setFrameStyle(QFrame.Box | QFrame.Plain)
    speed_layout = QVBoxLayout(bpm_box)
    speed_layout.addWidget(bpm_label)
    speed_layout.addWidget(self.labels["bpm"])
    speed_layout.addWidget(self.labels["pitch"])
    speed_layout.addWidget(self.labels["master"])
    speed_layout.addStretch(1)
    speed_layout.setSpacing(0)

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
    layout.setRowStretch(4, 2)
    layout.setRowStretch(5, 2)
    layout.setColumnStretch(1, 2)
    #layout.setColumnStretch(2, 1)

    self.reset()

  def reset(self):
    self.labels["title"].setText("Not loaded")
    self.labels["artist"].setText("")
    self.labels["album"].setText("")
    self.labels["info"].setText("No player connected")
    self.setTime(None)
    self.setSpeed("")
    self.setMaster(False)

  def setPlayerNumber(self, player_number):
    self.player_number = player_number
    self.labels["player_number"].setText("Player {}".format(self.player_number))

  def setMaster(self, master):
    if master:
      self.labels["master"].setStyleSheet("QLabel { font: bold; qproperty-alignment: AlignCenter; background-color: green; color: black; }")
    else:
      self.labels["master"].setStyleSheet("QLabel { font: bold; qproperty-alignment: AlignCenter; background-color: green; color: black; }")

  def setPlayerInfo(self, model, ip_addr, fw=""):
    self.labels["info"].setText("{} {} {}".format(model, fw, ip_addr))

  def setSpeed(self, bpm, pitch=0):
    if isinstance(bpm, str):
      self.labels["bpm"].setText("--.--")
      self.labels["pitch"].setText("{:+.2f}%".format(0))
    else:
      pitched_bpm = bpm*pitch
      self.labels["bpm"].setText("{:.2f}".format(pitched_bpm))
      self.labels["pitch"].setText("{:+.2f}%".format((pitch-1)*100))

  def setMetadata(self, title, artist, album):
    self.labels["title"].setText(title)
    self.labels["artist"].setText(artist)
    self.labels["album"].setText(album)

  def setArtwork(self, data):
    p = QPixmap()
    p.loadFromData(data)
    self.labels["artwork"].setPixmap(p)

  def setTime(self, seconds):
    if seconds is not None:
      self.time.display("{:02d}:{:02d}".format(int(seconds//60), int(seconds)%60))
    else:
      self.time.display("--:--")

class Gui(QWidget):
  keepalive_signal = pyqtSignal(int)

  def __init__(self, prodj):
    super().__init__()
    self.prodj = prodj
    #self.resize(800, 600)
    self.setWindowTitle('Pioneer ProDJ Link Monitor')

    pal = self.palette()
    pal.setColor(self.foregroundRole(), Qt.white)
    pal.setColor(self.backgroundRole(), Qt.black)
    self.setPalette(pal)
    self.setAutoFillBackground(True)

    self.keepalive_signal.connect(self.keepalive_slot)

    self.players = {}
    self.layout = QGridLayout(self)
    self.create_player(0)

    self.show()

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
    if player_number == 0:
      self.layout.addWidget(self.players[0], 0, 0)
    else:
      self.layout.addWidget(self.players[player_number], (player_number-1)//2, (player_number-1)%2)

  def remove_player(self, player_number):
    if not player_number in self.players:
      return
    self.layout.removeWidget(self.players[player_number])
    del self.players[player_number]
    logging.info("Gui: Removed player {}".format(player_number))

  # has to be called using a signal, otherwise windows are created standalone
  def keepalive_slot(self, player_number):
    if player_number not in range(1,5):
      return
    if not player_number in self.players: # on new keepalive, create player
      self.create_player(player_number)
    c = self.prodj.cl.getClient(player_number)
    self.players[player_number].setPlayerInfo(c.model, c.ip_addr)

  def change_callback(self, clientlist, player_number):
    if not player_number in self.players:
      return
    c = clientlist.getClient(player_number)
    self.players[player_number].setSpeed(c.bpm, c.pitch)
    self.players[player_number].setMaster("master" in c.state)
    self.players[player_number].beat_bar.setBeat(c.beat)
    self.players[player_number].waveform.setPosition(c.position, c.actual_pitch, c.play_state)
    self.players[player_number].setTime(c.position)
    if c.metadata is not None and "duration" in c.metadata and c.position is not None:
      self.players[player_number].preview_waveform.setPosition(c.position/c.metadata["duration"])
    if len(c.fw) > 0:
      self.players[player_number].setPlayerInfo(c.model, c.ip_addr, c.fw)

    # track changed -> reload metadata
    if self.players[player_number].track_id != c.track_id and c.track_id != 0:
      logging.info("Gui: track id of player %d changed to %d, requesting metadata", player_number, c.track_id)
      self.players[player_number].track_id = c.track_id # remember requested track id
      self.prodj.dbs.get_metadata(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbserver_callback)
      # we do not get artwork yet because we need metadata to know the artwork_id
      self.prodj.dbs.get_preview_waveform(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbserver_callback)
      self.prodj.dbs.get_beatgrid(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbserver_callback)
      self.prodj.dbs.get_waveform(c.loaded_player_number, c.loaded_slot, c.track_id, self.dbserver_callback)

  def dbserver_callback(self, request, source_player_number, slot, item_id, reply):
    if request == "artwork":
      client = self.prodj.cl.getClientByLoadedTrackArtwork(source_player_number, slot, item_id)
    else:
      client = self.prodj.cl.getClientByLoadedTrack(source_player_number, slot, item_id)
    player_number = client.player_number if client is not None else None
    logging.debug("Gui: dbserver_callback %s source player %d to widget player %d",
      request, source_player_number, player_number)
    if not player_number in self.players or reply is None:
      return
    if request == "metadata":
      self.players[player_number].setMetadata(reply["title"], reply["artist"], reply["album"])
      if "artwork_id" in reply and reply["artwork_id"] != 0:
        self.prodj.dbs.get_artwork(source_player_number, slot, reply["artwork_id"], self.dbserver_callback)
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
