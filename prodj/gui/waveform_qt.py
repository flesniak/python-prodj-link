import logging

from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtCore import Qt

class WaveformWidget(QWidget):
  def __init__(self, parent):
    super().__init__(parent)
    self.waveform_height = 75
    self.waveform_center = self.waveform_height//2
    self.waveform_px_per_s = 150
    self.setMinimumSize(3*self.waveform_px_per_s, self.waveform_height)
    self.waveform_data = None
    self.beatgrid_data = None
    self.pixmap = None
    self.offset = 0 # frames = pixels of waveform
    self.pitch = 0
    self.position_marker = 0.5
    self.setFrameCount(self.waveform_px_per_s*10)
    #self.setPositionMarkerOffset(0.5)
    self.update_interval = 0.04
    self.startTimer(self.update_interval*1000)

  def setData(self, data):
    self.pixmap = None
    self.waveform_data = data[20:]
    self.renderWaveformPixmap()
    self.update()

  def setBeatgridData(self, beatgrid_data):
    self.beatgrid_data = beatgrid_data
    if self.waveform_data:
      self.renderWaveformPixmap()
      self.update()

  def setFrameCount(self, frames): # frames-to-show -> 150*10 = 10 seconds
    self.frames = frames
    self.setPositionMarkerOffset(self.position_marker)

  def setPositionMarkerOffset(self, relative): # relative location of position marker
    self.position_marker = relative
    self.position_marker_offset = int(relative*self.frames)

  # FIXME state dependant pitch
  def setPosition(self, position, pitch=1, state="playing"):
    # logging.debug("setPosition {} pitch {}".format(position, pitch))
    if position is not None and pitch is not None:
      self.offset = int(self.waveform_px_per_s*position)
      self.pitch = pitch
    else:
      self.offset = 0
      self.pitch = 0

  def paintEvent(self, e):
    #logging.info("paintEvent {}".format(e.rect()))
    painter = QPainter()
    painter.begin(self)
    if self.pixmap:
      pixmap = self.pixmap.copy(self.offset, 0, self.frames, self.waveform_height)
      self.drawPositionMarker(pixmap)
      scaled_pixmap = pixmap.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
      painter.drawPixmap(0, 0, scaled_pixmap)
    painter.end()

  # draw position marker into unscaled pixmap
  def drawPositionMarker(self, pixmap):
    pixmap_painter = QPainter()
    pixmap_painter.begin(pixmap)
    pixmap_painter.fillRect(self.position_marker_offset, 0, 4, self.waveform_height, Qt.red)
    pixmap_painter.end()

  # draw position marker into scaled pixmap
  def drawPositionMarkerScaled(self, painter):
    painter.fillRect(self.position_marker*self.size().width(), 0, 4, self.size().height(), Qt.red)

  def renderWaveformPixmap(self):
    logging.info("rendering waveform")
    self.pixmap = QPixmap(self.position_marker_offset+len(self.waveform_data), self.waveform_height)
    # background
    self.pixmap.fill(Qt.black)
    painter = QPainter()
    painter.begin(self.pixmap)
    painter.setBrush(Qt.SolidPattern)
    # vertical orientation line
    painter.setPen(Qt.white)
    painter.drawLine(0, self.waveform_center, self.pixmap.width(), self.waveform_center)
    # waveform data
    if self.waveform_data:
      for data_x in range(0, len(self.waveform_data)):
        draw_x = data_x + self.position_marker_offset
        height = self.waveform_data[data_x] & 0x1f
        whiteness = self.waveform_data[data_x] >> 5
        painter.setPen(QColor(36*whiteness, 36*whiteness, 255))
        painter.drawLine(draw_x, self.waveform_center-height, draw_x, self.waveform_center+height)
      if self.beatgrid_data:
        for beat in self.beatgrid_data["beats"]:
          if beat["beat"] == 1:
            brush = Qt.red
            length = 8
          else:
            brush = Qt.white
            length = 5
          draw_x = beat["time"]*self.waveform_px_per_s//1000 + self.position_marker_offset
          painter.fillRect(draw_x-1, 0, 4, length, brush)
          painter.fillRect(draw_x-1, self.waveform_height-length, 4, length, brush)
    painter.end()
    logging.info("rendering waveform done")

  def timerEvent(self, event):
    if self.pitch > 0:
      self.offset += int(self.waveform_px_per_s*self.pitch*self.update_interval)
      self.update()
