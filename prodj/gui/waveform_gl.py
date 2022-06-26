#!/usr/bin/env python3

import sys
import logging
from threading import Lock
from PyQt5.QtCore import pyqtSignal, QSize, Qt
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QOpenGLWidget, QSlider, QWidget
from PyQt5.QtGui import QSurfaceFormat
import OpenGL.GL as gl

from prodj.network.packets import PlayStatePlaying, PlayStateStopped
from prodj.pdblib.usbanlzdatabase import UsbAnlzDatabase
from .waveform_blue_map import blue_map

class GLWaveformWidget(QOpenGLWidget):
  waveform_zoom_changed_signal = pyqtSignal(int)

  def __init__(self, parent=None):
    super().__init__(parent)

    # multisampling
    fmt = QSurfaceFormat(self.format())
    fmt.setSamples(4)
    fmt.setSwapBehavior(QSurfaceFormat.DoubleBuffer)
    self.setFormat(fmt)

    self.lists = None
    self.clearLists = False
    self.waveform_data = None # if not none, it will be rendered and deleted (to None)
    self.beatgrid_data = None # if not none, it will be rendered and deleted (to None)
    self.waveform_colored = False
    self.data_lock = Lock()
    self.time_offset = 0
    self.zoom_seconds = 4
    self.pitch = 1 # affects animation speed

    self.viewport = (50, 40) # viewport +- x, y
    self.waveform_lines_per_x = 150
    self.baseline_height = 0.2
    self.position_marker_width = 0.3

    self.waveform_zoom_changed_signal.connect(self.setZoom)

    self.update_interval_ms = 40
    self.startTimer(self.update_interval_ms)

  def minimumSizeHint(self):
    return QSize(400, 75)

  def sizeHint(self):
    return QSize(500, 100)

  def clear(self):
    with self.data_lock:
      self.waveform_data = None
      self.beatgrid_data = None
      if self.lists is not None:
        self.clearLists = True
        self.update()

  def setData(self, waveform_data, colored=False):
    with self.data_lock:
      self.waveform_data = waveform_data
      self.waveform_colored = colored
      self.update()

  def setBeatgridData(self, beatgrid_data):
    with self.data_lock:
      self.beatgrid_data = beatgrid_data
      self.update()

  # current time in seconds at position marker
  def setPosition(self, position, pitch=1, state="playing"):
    #logging.debug("setPosition {} pitch {} state {}".format(position, pitch, state))
    if position is not None and pitch is not None:
      if state in PlayStateStopped:
        pitch = 0
      self.pitch = pitch
      if self.time_offset != position:
        #logging.debug("time offset diff %.6f", position-self.time_offset)
        offset = abs(position - self.time_offset)
        if state in PlayStatePlaying and offset < 0.05: # ignore negligible offset
          return
        if state in PlayStatePlaying and offset < 0.1: # small enough to compensate by temporary pitch modification
          if position > self.time_offset:
            #logging.debug("increasing pitch to catch up")
            self.pitch += 0.01
          else:
            #logging.debug("decreasing pitch to fall behind")
            self.pitch -= 0.01
        else: # too large to compensate or non-monotonous -> direct assignment
          #logging.debug("offset %.6f, direct assignment", offset)
          self.time_offset = position
          self.update()
    else:
      self.offset = 0
      self.pitch = 0

  def wheelEvent(self, event):
    if event.angleDelta().y() > 0 and self.zoom_seconds > 2:
      self.waveform_zoom_changed_signal.emit(self.zoom_seconds-1)
    elif event.angleDelta().y() < 0 and self.zoom_seconds < 15:
      self.waveform_zoom_changed_signal.emit(self.zoom_seconds+1)

  # how many seconds to show left and right of the position marker
  def setZoom(self, seconds):
    if seconds != self.zoom_seconds:
      self.zoom_seconds = seconds
      self.update()

  def timerEvent(self, event):
    if self.pitch != 0:
      self.time_offset += self.pitch*self.update_interval_ms / 1000
      self.update()

  def initializeGL(self):
    logging.info("Renderer \"{}\" OpenGL \"{}\"".format(
      gl.glGetString(gl.GL_RENDERER).decode("ascii"),
      gl.glGetString(gl.GL_VERSION).decode("ascii")))
    gl.glClearColor(0,0,0,255)
    gl.glShadeModel(gl.GL_FLAT)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_CULL_FACE)
    self.lists = gl.glGenLists(3)
    gl.glLineWidth(1.0)
    self.renderCrosshair()

  def updateViewport(self):
    gl.glMatrixMode(gl.GL_PROJECTION)
    gl.glLoadIdentity()
    gl.glOrtho(-1*self.viewport[0], self.viewport[0], -1*self.viewport[1], self.viewport[1], -2, 2)
    gl.glMatrixMode(gl.GL_MODELVIEW)

  def paintGL(self):
    self.updateViewport()
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    gl.glLoadIdentity()
    gl.glCallList(self.lists)

    gl.glScalef(self.viewport[0]/self.zoom_seconds, 1, 1)
    gl.glTranslatef(-1*self.time_offset, 0, 0)
    if self.clearLists:
      gl.glNewList(self.lists+1, gl.GL_COMPILE)
      gl.glEndList()
      gl.glNewList(self.lists+2, gl.GL_COMPILE)
      gl.glEndList()
      self.clearLists = False
    self.renderWaveform()
    self.renderBeatgrid()
    gl.glCallList(self.lists+1)
    gl.glCallList(self.lists+2)

  def resizeGL(self, width, height):
    gl.glViewport(0, 0, width, height)

  def renderCrosshair(self):
    gl.glNewList(self.lists, gl.GL_COMPILE)
    gl.glBegin(gl.GL_QUADS)
    # white baseline
    gl.glColor3f(1, 1, 1)
    gl.glVertex3f(-1*self.viewport[0], -1, -1)
    gl.glVertex3f(self.viewport[0], -1, -1)
    gl.glVertex3f(self.viewport[0], 1, -1)
    gl.glVertex3f(-1*self.viewport[0], 1, -1)
    gl.glEnd()

    gl.glBegin(gl.GL_QUADS)
    # red position marker
    gl.glColor3f(1, 0, 0)
    gl.glVertex3f(0, -1*self.viewport[1], 1)
    gl.glVertex3f(.5, -1*self.viewport[1], 1)
    gl.glVertex3f(.5, self.viewport[1], 1)
    gl.glVertex3f(0, self.viewport[1], 1)
    gl.glEnd()
    gl.glEndList()

  def renderWaveform(self):
    with self.data_lock:
      if self.waveform_data is None:
        return

      gl.glNewList(self.lists+1, gl.GL_COMPILE)
      gl.glEnable(gl.GL_MULTISAMPLE)

      if self.waveform_colored:
        self.renderColoredQuads()
      else:
        self.renderMonochromeQuads()

      gl.glEndList()
      self.waveform_data = None # delete data after rendering

  def renderMonochromeQuads(self):
    for x,v in enumerate(self.waveform_data):
      height = v & 0x1f
      whiteness = v >> 5

      gl.glBegin(gl.GL_QUADS)
      gl.glColor3ub(*blue_map[7-whiteness])
      gl.glVertex3f(x/self.waveform_lines_per_x, -height-1, 0)
      gl.glVertex3f((x+1)/self.waveform_lines_per_x, -height-1, 0)
      gl.glVertex3f((x+1)/self.waveform_lines_per_x, height+1, 0)
      gl.glVertex3f(x/self.waveform_lines_per_x, height+1, 0)
      gl.glEnd()

  def renderColoredQuads(self):
    for x,v in enumerate(self.waveform_data):
      height = ((v >> 2) & 0x1F)
      blue = ((v >> 7) & 0x07) / 7
      green = ((v >> 10) & 0x07) / 7
      red = ((v >> 13) & 0x07) / 7

      gl.glBegin(gl.GL_QUADS)
      gl.glColor3f(red, green, blue)
      gl.glVertex3f(x/self.waveform_lines_per_x, -height-1, 0)
      gl.glVertex3f((x+1)/self.waveform_lines_per_x, -height-1, 0)
      gl.glVertex3f((x+1)/self.waveform_lines_per_x, height+1, 0)
      gl.glVertex3f(x/self.waveform_lines_per_x, height+1, 0)
      gl.glEnd()

  def renderBeatgrid(self):
    with self.data_lock:
      if self.beatgrid_data is None:
        return

      gl.glNewList(self.lists+2, gl.GL_COMPILE)
      gl.glDisable(gl.GL_MULTISAMPLE)
      gl.glBegin(gl.GL_LINES)

      for beat in self.beatgrid_data:
        if beat.beat == 1:
          gl.glColor3f(1, 0, 0)
          height = 8
        else:
          gl.glColor3f(1, 1, 1)
          height = 5
        x = beat.time/1000

        gl.glVertex3f(x, self.viewport[1]-height, 0)
        gl.glVertex3f(x, self.viewport[1], 0)
        gl.glVertex3f(x, -1*self.viewport[1], 0)
        gl.glVertex3f(x, -1*self.viewport[1]+height, 0)

      gl.glEnd()
      gl.glEndList()
      self.beatgrid_data = None # delete data after rendering

class Window(QWidget):
  def __init__(self):
    super(Window, self).__init__()

    self.setWindowTitle("GL Waveform Test")
    self.glWidget = GLWaveformWidget()

    self.timeSlider = QSlider(Qt.Vertical)
    self.timeSlider.setRange(0, 300)
    self.timeSlider.setSingleStep(1)
    self.timeSlider.setTickInterval(10)
    self.timeSlider.setTickPosition(QSlider.TicksRight)
    self.zoomSlider = QSlider(Qt.Vertical)
    self.zoomSlider.setRange(2, 10)
    self.zoomSlider.setSingleStep(1)
    self.zoomSlider.setTickInterval(1)
    self.zoomSlider.setTickPosition(QSlider.TicksRight)

    self.timeSlider.valueChanged.connect(self.glWidget.setPosition)
    self.zoomSlider.valueChanged.connect(self.glWidget.setZoom)

    mainLayout = QHBoxLayout()
    mainLayout.addWidget(self.glWidget)
    mainLayout.addWidget(self.timeSlider)
    mainLayout.addWidget(self.zoomSlider)
    self.setLayout(mainLayout)

    self.timeSlider.setValue(0)
    self.zoomSlider.setValue(4)

if __name__ == '__main__':
    app = QApplication([])
    window = Window()

    base_path = sys.argv[1]
    colored = len(sys.argv) > 2 and sys.argv[2] == "color"
    with open(base_path+"/ANLZ0000.DAT", "rb") as f:
      dat = f.read()
    with open(base_path+"/ANLZ0000.EXT", "rb") as f:
      ext = f.read()
    db = UsbAnlzDatabase()
    if dat is not None and ext is not None:
      db.load_dat_buffer(dat)
      db.load_ext_buffer(ext)
      if colored:
        window.glWidget.setData(db.get_color_waveform(), True)
      else:
        window.glWidget.setData(db.get_waveform(), False)
      window.glWidget.setBeatgridData(db.get_beatgrid())

    window.show()
    app.exec_()
