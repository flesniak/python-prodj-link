import logging
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QLCDNumber, QSizePolicy, QVBoxLayout, QWidget
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtCore import pyqtSignal, Qt, QSize
import sys

class WaveformWidget(QWidget):
  def __init__(self, parent):
    super().__init__(parent)
    self.setMinimumSize(3*150, 65)
    self.data = None
    self.offset = 0 # frames = pixels of waveform
    self.position_marker = 0.5
    self.setFrameCount(150*10)
    #self.setPositionMarkerOffset(0.5)
    self.startTimer(40)

  def setFrameCount(self, frames): # frames-to-show -> 150*10 = 10 seconds
    self.frames = frames
    self.setPositionMarkerOffset(self.position_marker)

  def setPositionMarkerOffset(self, relative): # relative location of position marker
    self.position_marker = relative
    self.position_marker_offset = int(relative*self.frames)

  def paintEvent(self, e):
    painter = QPainter()
    painter.begin(self)
    pixmap = self.drawWaveformPixmap()
    if pixmap:
      scaled_pixmap = pixmap.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
      painter.drawPixmap(0,0,scaled_pixmap)
    painter.end()

  def drawWaveformPixmap(self):
    pixmap = QPixmap(self.frames, 65)
    # background
    pixmap.fill(Qt.black)
    painter = QPainter()
    painter.begin(pixmap)
    painter.setBrush(Qt.SolidPattern)
    # vertical orientation line
    painter.setPen(Qt.white)
    painter.drawLine(0,32,self.frames,32)
    # waveform data
    if self.data and len(self.data) >= self.offset+self.frames:
      for draw_x in range(0, self.frames):
        data_x = self.offset+draw_x-self.position_marker_offset
        if data_x < 0:
          continue
        height = self.data[data_x] & 0x1f
        whiteness = self.data[data_x] >> 5
        painter.setPen(QColor(36*whiteness, 36*whiteness, 255))
        painter.drawLine(draw_x,32-height,draw_x,32+height)
    # position marker
    painter.fillRect(self.position_marker_offset, 0, 4, 65, Qt.red)
    painter.end()
    return pixmap

  def timerEvent(self, event):
    self.offset += int(142*0.04)
    self.update()

class PreviewWaveformWidget(QWidget):
  def __init__(self, parent):
    super().__init__(parent)
    self.setMinimumSize(400, 34)
    p = self.palette()
    self.setAutoFillBackground(True)
    p.setColor(self.backgroundRole(), Qt.black)
    self.setPalette(p)
    self.data = None
    self.position = 0

  def sizeHint(self):
    return QSize(400, 34)

  def heightForWidth(self, width):
    logging.info("preview width {} height {}".format(width, int(width/400*34)))
    return int(width/400*34)

  def setProgress(self, relative):
    new_position = int(400*relative)
    if new_position != self.position:
      self.position = new_position
      self.update()

  def paintEvent(self, e):
    logging.info("preview size {}".format(self.size()))
    painter = QPainter()
    painter.begin(self)
    pixmap = self.drawPreviewWaveformPixmap()
    if pixmap:
      scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatio)
      painter.drawPixmap(0,0,scaled_pixmap)
    painter.end()

  def drawPreviewWaveformPixmap(self):
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

    # metadata and player info
    self.labels["title"] = QLabel(self)
    self.labels["title"].setStyleSheet("QLabel { font: bold 16pt; qproperty-alignment: AlignCenter; }")
    self.labels["artist"] = QLabel(self)
    self.labels["album"] = QLabel(self)
    self.labels["info"] = QLabel(self)
    font = self.labels["title"].font()
    font.setBold(1)
    font.setPointSize(16)
    #self.labels["title"].setFont(font)

    # artwork and player number
    self.labels["player_number"] = QLabel(self)
    self.labels["player_number"].setStyleSheet("QLabel { font: bold 14pt; qproperty-alignment: AlignCenter; background-color : white; color : black; }")
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
    self.waveform = WaveformWidget(self)
    self.waveform.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.preview_waveform = PreviewWaveformWidget(self)
    #self.preview_waveform.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    qsp = QSizePolicy(QSizePolicy.Preferred,QSizePolicy.Minimum)
    qsp.setHeightForWidth(True)
    self.preview_waveform.setSizePolicy(qsp)

    # BPM / Pitch / Master display
    bpm_label = QLabel("BPM", self)
    bpm_label.setStyleSheet("QLabel { font: bold 8pt; qproperty-alignment: AlignLeft; }")
    self.labels["bpm"] = QLabel(self)
    self.labels["bpm"].setStyleSheet("QLabel { font: bold 16pt; qproperty-alignment: AlignRight; }")
    #self.labels["bpm"].setFont(font)
    self.labels["pitch"] = QLabel("+10.00%", self)
    self.labels["pitch"].setStyleSheet("QLabel { font: bold 14pt; qproperty-alignment: AlignRight; }")
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
    self.time.display("--:--")
    self.setSpeed("")
    self.setMaster(False)

  def setPlayerNumber(self, player_number):
    self.player_number = player_number
    self.labels["player_number"].setText(str(self.player_number))

  def setMaster(self, master):
    if master:
      self.labels["master"].setStyleSheet("QLabel { font: bold; qproperty-alignment: AlignCenter; background-color : green; color : black; }")
    else:
      self.labels["master"].setStyleSheet("QLabel { font: bold; qproperty-alignment: AlignCenter; background-color : green; color : black; }")

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

class Gui(QWidget):
  keepalive_signal = pyqtSignal(int)
  change_signal = pyqtSignal(int)
  metadata_signal = pyqtSignal(int)

  def __init__(self, clientlist):
    super().__init__()
    self.clientlist = clientlist
    #self.resize(800, 600)
    self.setWindowTitle('Pioneer ProDJ Link Monitor')
    p = self.palette()
    p.setColor(self.backgroundRole(), Qt.black)
    self.setPalette(p)
    self.setAutoFillBackground(True)

    self.keepalive_signal.connect(self.keepalive_callback)
    self.change_signal.connect(self.change_callback)
    self.metadata_signal.connect(self.metadata_callback)

    self.players = {}
    self.layout = QGridLayout(self)
    self.create_player(1)

    self.show()

  def create_player(self, player_number):
    if player_number in self.players:
      return
    self.players[player_number] = PlayerWidget("Player {}".format(player_number), self)
    self.layout.addWidget(self.players[player_number], (player_number-1)//2, (player_number-1)%2)
    self.players[player_number].show()
    logging.info("Gui: Created player {}".format(player_number))

  def remove_player(self, player_number):
    if not player_number in self.players:
      return
    self.layout.removeWidget(self.players[player_number])
    del self.players[player_number]
    logging.info("Gui: Removed player {}".format(player_number))

  def keepalive_callback(self, player_number):
    if not player_number in self.players: # on new keepalive, create player
      self.create_player(player_number)
    c = self.clientlist.getClient(player_number)
    self.players[player_number].setPlayerInfo(c.model, c.ip_addr)

  def change_callback(self, player_number):
    if not player_number in self.players:
      return
    c = self.clientlist.getClient(player_number)
    self.players[player_number].setSpeed(c.bpm, c.pitch)
    self.players[player_number].setMaster("master" in c.state)
    self.players[player_number].beat_bar.setBeat(c.beat)
    if len(c.fw) > 0:
      self.players[player_number].setPlayerInfo(c.model, c.ip_addr, c.fw)

  def metadata_callback(self, player_number):
    if not player_number in self.players:
      return
    md = self.clientlist.getClient(player_number).metadata
    self.players[player_number].setMetadata(md["title"], md["artist"], md["album"])
