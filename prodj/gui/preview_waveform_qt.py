#!/usr/bin/env python3

import sys
from threading import Lock
from PyQt5.QtWidgets import QApplication, QHBoxLayout
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtCore import pyqtSignal, Qt, QSize

from prodj.pdblib.usbanlzdatabase import UsbAnlzDatabase
from .waveform_blue_map import blue_map

class PreviewWaveformWidget(QWidget):
  redraw_signal = pyqtSignal()

  def __init__(self, parent):
    super().__init__(parent)
    self.pixmap_width = 400
    self.pixmap_height = 34
    self.top_offset = 4
    self.total_height = self.pixmap_height + self.top_offset
    self.setMinimumSize(self.pixmap_width, self.total_height)
    self.data = None
    self.pixmap = None
    self.pixmap_lock = Lock()
    self.position = 0 # relative, between 0 and 1
    self.redraw_signal.connect(self.update)
    self.colored_render_blue_only = False

  def clear(self):
    self.setData(None)

  def setData(self, data, colored=False):
    with self.pixmap_lock:
      self.data = data
      if colored:
        self.pixmap = self.drawColoredPreviewWaveformPixmap()
      else:
        self.pixmap = self.drawPreviewWaveformPixmap()
    self.redraw_signal.emit()

  def sizeHint(self):
    return QSize(self.pixmap_width, self.total_height)

  def heightForWidth(self, width):
    return width*self.total_height//self.pixmap_width

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
        painter.drawPixmap(0, self.top_offset, scaled_pixmap)
        height = scaled_pixmap.height() + self.top_offset
        marker_position = int(self.position * scaled_pixmap.width())
        painter.fillRect(marker_position-1, 0, 3, height, Qt.black)
        painter.fillRect(marker_position-3, 0, 7, 7, Qt.black)
        painter.fillRect(marker_position-2, 1, 5, 5, Qt.white)
        painter.fillRect(marker_position, 1, 1, height, Qt.white)
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
        height = self.data[2*x]-2 # only seen from 2..23
        height = height if height > 0 else 0
        # self.data[2*x+1] only seen from 1..6
        color = blue_map[2] if self.data[2*x+1] > 3 else blue_map[6]
        painter.setPen(QColor(*color))
        painter.drawLine(x, 31, x, 31-height)
    # base line
    painter.setPen(Qt.white)
    painter.drawLine(0,33,399,33)
    painter.end()
    return pixmap

  def drawColoredPreviewWaveformPixmap(self):
    if self.data is None:
      return None
    pixmap = QPixmap(self.pixmap_width, self.pixmap_height)
    pixmap.fill(Qt.black)
    painter = QPainter()
    painter.begin(pixmap)
    painter.setBrush(Qt.SolidPattern)

    w = 1200
    xr = self.pixmap_width / w
    if self.data and len(self.data) >= w:
      data = self.data

      # Get max_height to adjust waveform height
      max_height = 0
      for x in range(w):
        d3 = data[x * 6 + 3]
        d4 = data[x * 6 + 4]
        d5 = data[x * 6 + 5]
        max_height = max(max_height, d3, d4, d5)

      max_back_height = 0
      max_front_height = 0

      hr = 127 / max_height
      for x in range(w):
        # d0 & d1: max of d1 and d2 sets the steepness of the ramp of the blueness
        d0 = data[x * 6 + 0]
        d1 = data[x * 6 + 1]
        # d2: ""\__ blueness
        d2 = data[x * 6 + 2]
        # d3: "\___ red
        d3 = data[x * 6 + 3]
        # d4: _/"\_ green
        d4 = data[x * 6 + 4]
        # d5: ___/" blue and height of front waveform
        d5 = data[x * 6 + 5]

        # background waveform height is max height of d3, d4 (and d5 as it is foreground)
        back_height = max(d3, d4, d5)
        # front waveform height is d5
        front_height = d5

        if not self.colored_render_blue_only: # color
          if back_height > 0:
            red = d3 / back_height * 255
            green = d4 / back_height * 255
            blue = d5 / back_height * 255
          else:
            red = green = blue = 0
        else: # NXS2 blue
          # NOTE: the whole steepness and zero cutoff just don't seems to make any sense, however it looks as on CDJ
          # Maybe this is related to the bytes wrongly(?) interpreted as signed bytes instead of unsigned.
          steepness = max(d0, d1)
          blueness = d2
          color = 0
          if steepness > 0 and blueness > 0:
            color = min(int((blueness * (127 / steepness)) / 16), 7)
          red, green, blue = blue_map[color]

        back_height = int(back_height * hr)
        front_height = int(front_height * hr)

        max_back_height = max(back_height, max_back_height)
        max_front_height = max(front_height, max_front_height)

        xd = int(x * xr)
        if int((x + 1) * xr) > xd:
          painter.setPen(QColor(int(red * .75), int(green * .75), int(blue * .75)))
          painter.drawLine(xd, 31, xd, 31 - int(max_back_height / 4))
          painter.setPen(QColor(int(red), int(green), int(blue)))
          painter.drawLine(xd, 31, xd, 31 - int(max_front_height / 4))
          max_back_height = max_front_height = 0

    # base line
    painter.setPen(Qt.white)
    painter.drawLine(0,33,399,33)
    painter.end()

    return pixmap

class Window(QWidget):
  def __init__(self):
    super(Window, self).__init__()

    self.setWindowTitle("Preview Waveform Test")
    self.previewWidget = PreviewWaveformWidget(self)

    mainLayout = QHBoxLayout()
    mainLayout.addWidget(self.previewWidget)
    self.setLayout(mainLayout)

if __name__ == '__main__':
    app = QApplication([])
    window = Window()
    base_path = "."
    dat = None
    ext = None

    if len(sys.argv) > 1:
      base_path = sys.argv[1]
    colored = len(sys.argv) > 2 and sys.argv[2] == "color"
    try:
      with open(base_path+"/ANLZ0000.DAT", "rb") as f:
        dat = f.read()
    except FileNotFoundError as e:
      print("No DAT file loaded")
    try:
      with open(base_path+"/ANLZ0000.EXT", "rb") as f:
        ext = f.read()
    except FileNotFoundError as e:
      print("No EXT file loaded")
    if dat is None and ext is None:
      print("Error: No ANLZ files loaded")
      sys.exit(1)
    db = UsbAnlzDatabase()
    if dat is not None:
      db.load_dat_buffer(dat)
    if ext is not None:
      db.load_ext_buffer(ext)
    if colored:
      window.previewWidget.setData(db.get_color_preview_waveform(), True)
    else:
      waveform_spread = b""
      for line in db.get_preview_waveform():
        waveform_spread += bytes([line & 0x1f, line>>5])
      window.previewWidget.setData(waveform_spread)
    window.previewWidget.setPosition(0.2)

    window.show()
    app.exec_()
