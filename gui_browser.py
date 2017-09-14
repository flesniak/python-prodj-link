import logging
from PyQt5.QtWidgets import QComboBox, QHeaderView, QLabel, QPushButton, QTableView, QTextEdit, QHBoxLayout, QVBoxLayout, QWidget
from PyQt5.QtGui import QPalette, QStandardItem, QStandardItemModel
from PyQt5.QtCore import Qt, pyqtSignal

from dbclient import sort_types

# small helper functions
def makeMediaInfo(info):
  if all(key in info for key in ["name", "track_count", "playlist_count", "bytes_total", "bytes_free"]):
    return "{}, {} tracks, {} playlists, {}/{}MB free".format(info["name"], info["track_count"],
      info["playlist_count"], info["bytes_free"]//1024//1024, info["bytes_total"]//1024//1024)
  else:
    return "No information available"

def makeItem(text, data=None):
  item = QStandardItem(text)
  item.setFlags(Qt.ItemIsEnabled)
  item.setData(data)
  return item

class Browser(QWidget):
  handleRequestSignal = pyqtSignal()
  refreshMediaSignal = pyqtSignal(str)

  def __init__(self, prodj, player_number):
    super().__init__()
    self.prodj = prodj
    self.player_number = player_number
    self.slot = None # set after selecting slot in media menu
    self.menu = None
    self.sort = "default"
    self.track_id = None
    self.setWindowTitle("Browse Player {}".format(self.player_number))

    self.request = None # requests are parsed on signaling handleRequestSignal
    self.handleRequestSignal.connect(self.handleRequest)
    self.refreshMediaSignal.connect(self.refreshMedia)

    pal = self.palette()
    pal.setColor(self.foregroundRole(), Qt.white)
    pal.setColor(self.backgroundRole(), Qt.black)
    pal.setColor(QPalette.Base, Qt.black)
    self.setPalette(pal)
    self.setAutoFillBackground(True)

    # upper part
    self.path = QLabel(self)
    self.sort_box = QComboBox(self)
    for sort in sort_types:
      self.sort_box.addItem(sort.title(), sort)
    self.sort_box.currentIndexChanged[int].connect(self.sortChanged)
    self.back_button = QPushButton("Back", self)
    self.back_button.clicked.connect(self.backButtonClicked)

    top_layout = QHBoxLayout()
    top_layout.addWidget(self.path)
    top_layout.addWidget(self.sort_box)
    top_layout.addWidget(self.back_button)
    top_layout.setStretch(0, 1)

    # mid part
    self.model = QStandardItemModel(self)
    self.view = QTableView(self)
    self.view.setModel(self.model)
    self.view.verticalHeader().hide()
    #self.view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents);
    self.view.verticalHeader().setSectionResizeMode(QHeaderView.Fixed);
    self.view.verticalHeader().setDefaultSectionSize(18); # TODO replace by text bounding height
    self.view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);
    self.view.setStyleSheet("QTableView { background-color: black; } QTableView::item:focus { background-color: darkslategray; selection-background-color: black; }")
    self.view.clicked.connect(self.tableItemClicked)

    # metadata
    self.metadata_label = QLabel("Metadata:", self)
    self.metadata_edit = QTextEdit()
    self.metadata_edit.setReadOnly(True)

    metadata_layout = QVBoxLayout()
    metadata_layout.addWidget(self.metadata_label)
    metadata_layout.addWidget(self.metadata_edit)

    mid_layout = QHBoxLayout()
    mid_layout.addWidget(self.view)
    mid_layout.addLayout(metadata_layout)

    # lower part (load buttons)
    buttons_layout = QHBoxLayout()
    self.load_buttons = []
    for i in range(1,5):
      btn = QPushButton("Load Player {}".format(i))
      btn.setFlat(True)
      btn.setEnabled(False)
      btn.clicked.connect(lambda: self.loadIntoPlayer(i))
      buttons_layout.addWidget(btn)
      self.load_buttons += [btn]

    layout = QVBoxLayout(self)
    layout.addLayout(top_layout)
    layout.addLayout(mid_layout)
    layout.addLayout(buttons_layout)

    self.updateButtons()
    self.mediaMenu()

  def mediaMenu(self):
    c = self.prodj.cl.getClient(self.player_number)
    if c is None:
      logging.warning("Browser: failed to get client for player %d", self.player_number)
      return
    self.menu = "media"
    self.slot = None
    self.path.setText("Media overview")
    self.model.clear()
    if c.usb_state != "loaded" and c.sd_state != "loaded":
      self.model.setHorizontalHeaderLabels(["Media"])
      self.model.appendRow(makeItem("No media in player"))
      return
    self.model.setHorizontalHeaderLabels(["Media", "Info"])
    if c.usb_state == "loaded":
      data = {"type": "media", "name": "usb"}
      self.model.appendRow([makeItem("USB", data), makeItem(makeMediaInfo(c.usb_info), data)])
    if c.sd_state == "loaded":
      data = {"type": "media", "name": "sd"}
      self.model.appendRow([makeItem("SD Card", data), makeItem(makeMediaInfo(c.sd_info), data)])

  def rootMenu(self, slot):
    self.prodj.dbs.get_root_menu(self.player_number, slot, self.storeRequest)

  def renderRootMenu(self, request, player_number, slot, reply):
    logging.debug("renderRootMenu %s %s", str(request), str(player_number))
    if player_number != self.player_number:
      return
    self.menu = "root"
    self.slot = slot
    self.path.setText("Root menu "+slot)
    self.model.clear()
    self.model.setHorizontalHeaderLabels(["Category"])
    for entry in reply:
      data = {"type": "root", "name": entry["name"][1:-1], "menu_id": entry["menu_id"]}
      self.model.appendRow(makeItem(data["name"], data))
    #self.view.update()

  def titleMenu(self, slot, sort_mode):
    self.prodj.dbs.get_titles(self.player_number, slot, sort_mode, self.storeRequest)

  def artistMenu(self, slot, sort_mode):
    self.prodj.dbs.get_artists(self.player_number, slot, sort_mode, self.storeRequest)

  def albumMenu(self, slot, sort_mode):
    self.prodj.dbs.get_albums(self.player_number, slot, sort_mode, self.storeRequest)

  def renderList(self, request, player_number, slot, query_ids, sort_mode, reply):
    logging.debug("renderList %s %s", request, str(player_number))
    if player_number != self.player_number:
      return
    self.menu = request
    self.slot = slot
    self.path.setText("{} on {}".format(request.title(), slot.upper()))
    self.model.clear()
    # guess columns
    columns = []
    if len(reply) > 0:
      for key in reply[0]:
        if key[-3:] != "_id":
          columns += [key]
    self.model.setHorizontalHeaderLabels([x.title() for x in columns])
    for entry in reply:
      data = {"type": request, **entry}
      row = []
      for column in columns:
        row += [makeItem(str(entry[column]), data)]
      self.model.appendRow(row)

  def metadata(self, slot, track_id):
    self.prodj.dbs.get_metadata(self, self.player_number, slot, track_id, self.storeRequest)

  def renderMetadata(self, request, source_player_number, slot, track_id, metadata):
    md = ""
    for key in [k for k in ["title", "artist", "album", "genre", "key", "bpm", "comment", "rating", "duration"] if k in metadata]:
      md += "{}:\t{}\n".format(key.title(), metadata[key])
    self.metadata_edit.setText(md)
    self.track_id = track_id

  def backButtonClicked(self):
    if self.menu in ["title", "artist", "album"]:
      self.rootMenu(self.slot)
    elif self.menu == "root":
      self.mediaMenu()
    elif  self.menu == "media":
      pass # no parent menu for media
    else:
      logging.debug("Browser: back button for %s not implemented yet", self.menu)

  def tableItemClicked(self, index):
    data = self.model.itemFromIndex(index).data()
    logging.debug("Browser: clicked data %s", data)
    if data is None:
      return
    if data["type"] == "media":
      self.rootMenu(data["name"])
    elif data["type"] == "root":
      if data["name"] == "TRACK":
        self.titleMenu(self.slot, "default")
      elif data["name"] == "ARTIST":
        self.artistMenu(self.slot, "default")
      elif data["name"] == "ALBUM":
        self.albumMenu(self.slot, "default")
      else:
        logging.warning("Browser: root menu type %s not implemented yet", data["name"])
    elif data["type"] == "title":
      self.metadata(self.slot, data["track_id"])
    else:
      logging.warning("Browser: unhandled click type %s", data["type"])
    self.updateButtons() # update buttons for convenience

  def sortChanged(self):
    self.sort = self.sort_box.currentData()
    if self.menu in ["title"]:
      logging.debug("sort changed to %s", self.sort)
      self.titleMenu(self.slot, self.sort)

  def loadIntoPlayer(self, player_number):
    logging.debug("Browser: loading track (pn %d slot %s tid %d) into player %d",
      self.player_number, self.slot, self.track_id, player_number)
    self.prodj.vcdj.command_load_track(player_number, self.player_number, self.slot, self.track_id)

  def updateButtons(self):
    for i in range(1,5):
      self.load_buttons[i-1].setEnabled(i in self.prodj.gui.players)

  # special request handling to get into qt gui thread
  # storeRequest is called from outside (non-qt gui)
  def storeRequest(self, request, *args):
    if self.request is not None:
      logging.debug("Browser: not storing request %s, other request pending", request)
    logging.debug("Browser: storing request %s", request)
    self.request = (request, *args)
    self.handleRequestSignal.emit()

  # handleRequest is called by handleRequestSignal, from inside the gui thread
  def handleRequest(self):
    logging.debug("handleRequest %s", self.request[0])
    if self.request is None:
      return
    if self.request[0] == "root_menu":
      self.renderRootMenu(*self.request)
    elif self.request[0] in ["title", "artist", "album"]:
      self.renderList(*self.request)
    else:
      logging.warning("Browser: %s request not implemented", self.request[0])
    self.request = None

  def refreshMedia(self, slot):
    if self.slot == slot:
      logging.info("Browser: slot %s changed, going back to media overview")
      self.mediaMenu()
    else:
      logging.debug("Browser: ignoring %s change", slot)
