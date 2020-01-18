import logging
from PyQt5.QtWidgets import QComboBox, QHeaderView, QLabel, QPushButton, QSizePolicy, QTableView, QTextEdit, QHBoxLayout, QVBoxLayout, QWidget
from PyQt5.QtGui import QPalette, QStandardItem, QStandardItemModel
from PyQt5.QtCore import Qt, pyqtSignal

from prodj.data.dbclient import sort_types

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

def ratingString(rating):
  if rating < 0 or rating > 5:
    return str(rating)
  stars = ["\u2605", "\u2606"] # black star, white star
  return "".join(rating*stars[0]+(5-rating)*stars[1])

def printableField(field):
  if field == "bpm":
    return field.upper()
  else:
    return field.replace("_", " ").title()

class Browser(QWidget):
  handleRequestSignal = pyqtSignal()
  refreshMediaSignal = pyqtSignal(str)

  def __init__(self, prodj, player_number):
    super().__init__()
    self.prodj = prodj
    self.slot = None # set after selecting slot in media menu
    self.menu = "media"
    self.sort = "default"
    self.artist_id = None
    self.track_id = None
    self.genre_id = None
    self.playlist_folder_stack = [0]
    self.playlist_id = None
    self.path_stack = []
    self.setPlayerNumber(player_number)

    self.request = None # requests are parsed on signaling handleRequestSignal
    self.handleRequestSignal.connect(self.handleRequest)
    self.refreshMediaSignal.connect(self.refreshMedia)

    self.setAutoFillBackground(True)

    # upper part
    self.path = QLabel(self)
    self.path.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    self.sort_box = QComboBox(self)
    for sort in sort_types:
      self.sort_box.addItem(printableField(sort), sort)
    self.sort_box.currentIndexChanged[int].connect(self.sortChanged)
    self.sort_box.setStyleSheet("QComboBox { padding: 2px; border-style: outset; border-radius: 2px; border-width: 1px; border-color: gray; }")
    self.back_button = QPushButton("Back", self)
    self.back_button.clicked.connect(self.backButtonClicked)
    self.back_button.setStyleSheet("QPushButton { padding: 2px; border-style: outset; border-radius: 2px; border-width: 1px; border-color: gray; }")

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
    self.view.setStyleSheet("QTableView { border-style: outset; border-radius: 2px; border-width: 1px; border-color: gray; background-color: black; } QTableView::item { color: white; } QTableView::item:focus { background-color: darkslategray; selection-background-color: black; }")
    self.view.clicked.connect(self.tableItemClicked)

    # metadata
    self.metadata_label = QLabel("Metadata:", self)
    self.metadata_edit = QTextEdit()
    self.metadata_edit.setReadOnly(True)
    self.metadata_edit.setStyleSheet("QTextEdit { padding: 2px; border-style: outset; border-radius: 2px; border-width: 1px; border-color: gray; }")

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
      btn = QPushButton("Load Player {}".format(i), self)
      btn.setFlat(True)
      btn.setEnabled(False)
      btn.setStyleSheet("QPushButton { border-style: outset; border-radius: 2px; border-width: 1px; border-color: gray; }")
      btn.clicked.connect(lambda c,i=i: self.loadIntoPlayer(i))
      buttons_layout.addWidget(btn)
      self.load_buttons += [btn]

    self.download_button = QPushButton("Download", self)
    self.download_button.setFlat(True)
    self.download_button.setStyleSheet("QPushButton { border-style: outset; border-radius: 2px; border-width: 1px; border-color: gray; }")
    self.download_button.clicked.connect(self.downloadTrack)
    buttons_layout.addWidget(self.download_button)

    layout = QVBoxLayout(self)
    layout.addLayout(top_layout)
    layout.addLayout(mid_layout)
    layout.addLayout(buttons_layout)

    self.updateButtons()
    self.mediaMenu()

  def setPlayerNumber(self, player_number):
    self.player_number = player_number
    self.setWindowTitle("Browse Player {}".format(player_number))

  def updatePath(self, text=""):
    if text:
      self.path_stack.append(text)
    self.path.setText("\u27a4".join(self.path_stack))

  def mediaMenu(self):
    c = self.prodj.cl.getClient(self.player_number)
    if c is None:
      logging.warning("failed to get client for player %d", self.player_number)
      return
    self.menu = "media"
    self.slot = None
    self.track_id = None
    self.path_stack.clear()
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
    self.prodj.data.get_root_menu(self.player_number, slot, self.storeRequest)

  def renderRootMenu(self, request, player_number, slot, reply):
    logging.debug("renderRootMenu %s %s", str(request), str(player_number))
    if player_number != self.player_number:
      return
    self.menu = "root"
    self.slot = slot
    self.model.clear()
    self.model.setHorizontalHeaderLabels(["Category"])
    for entry in reply:
      data = {"type": "root", "name": entry["name"][1:-1], "menu_id": entry["menu_id"]}
      self.model.appendRow(makeItem(data["name"], data))

  def titleMenu(self):
    self.prodj.data.get_titles(self.player_number, self.slot, self.sort, self.storeRequest)

  def titleAlbumMenu(self, album_id):
    self.album_id = album_id
    self.prodj.data.get_titles_by_album(self.player_number, self.slot, album_id, self.sort, self.storeRequest)

  def titleAlbumArtistMenu(self, album_id):
    self.album_id = album_id
    self.prodj.data.get_titles_by_artist_album(self.player_number, self.slot, self.artist_id, album_id, self.sort, self.storeRequest)

  def titleAlbumArtistGenreMenu(self, album_id):
    self.album_id = album_id
    self.prodj.data.get_titles_by_genre_artist_album(self.player_number, self.slot, self.genre_id, self.artist_id, album_id, self.sort, self.storeRequest)

  def artistMenu(self):
    self.prodj.data.get_artists(self.player_number, self.slot, self.storeRequest)

  def artistGenreMenu(self, genre_id):
    self.genre_id = genre_id
    self.prodj.data.get_artists_by_genre(self.player_number, self.slot, genre_id, self.storeRequest)

  def albumMenu(self):
    self.prodj.data.get_albums(self.player_number, self.slot, self.storeRequest)

  def albumArtistMenu(self, artist_id):
    self.artist_id = artist_id
    self.prodj.data.get_albums_by_artist(self.player_number, self.slot, artist_id, self.storeRequest)

  def albumArtistGenreMenu(self, artist_id):
    self.artist_id = artist_id
    self.prodj.data.get_albums_by_genre_artist(self.player_number, self.slot, self.genre_id, artist_id, self.storeRequest)

  def genreMenu(self):
    self.prodj.data.get_genres(self.player_number, self.slot, self.storeRequest)

  def folderPlaylistMenu(self, folder_id=0):
    if folder_id == 0:
      self.playlist_folder_stack = [0]
    else:
      self.playlist_folder_stack.append(folder_id)
    self.playlist_id = 0
    self.prodj.data.get_playlist_folder(self.player_number, self.slot, folder_id, self.storeRequest)

  def titlePlaylistMenu(self, playlist_id=0):
    self.playlist_id = playlist_id
    self.prodj.data.get_playlist(self.player_number, self.slot, playlist_id, self.sort, self.storeRequest)

  def renderList(self, request, player_number, slot, reply):
    logging.debug("rendering %s list from player %d", request, player_number)
    if player_number != self.player_number:
      return
    self.menu = request
    self.slot = slot
    self.model.clear()
    # guess columns
    columns = []
    if len(reply) > 0:
      guess = reply[0]
      if len(reply) > 1 and "all" in guess:
        guess = reply[1]
      for key in guess:
        if key[-3:] != "_id":
          columns += [key]
    self.model.setHorizontalHeaderLabels([printableField(x) for x in columns])
    for entry in reply:
      data = {"type": request, **entry}
      row = []
      if "all" in entry: # on the special "all" entry, set the id to 0
        data[columns[0]] = entry["all"][1:-1]
        data[columns[0]+"_id"] = 0
        row += [makeItem(entry["all"][1:-1], data)]
      else:
        for column in columns:
          if request == "playlist_folder" and column not in entry:
            column = "folder" if column == "playlist" else "playlist"
          if column == "rating":
            text = ratingString(entry[column])
          else:
            text = str(entry[column])
          row += [makeItem(text, data)]
      self.model.appendRow(row)

  def metadata(self, track_id):
    self.prodj.data.get_metadata(self.player_number, self.slot, track_id, self.storeRequest)

  def renderMetadata(self, request, source_player_number, slot, track_id, metadata):
    md = ""
    for key in [k for k in ["title", "artist", "album", "genre", "key", "bpm", "comment", "duration"] if k in metadata]:
      md += "{}:\t{}\n".format(printableField(key), metadata[key])
    if "rating" in metadata:
      md += "{}:\t{}\n".format("Rating", ratingString(metadata["rating"]))
    self.metadata_edit.setText(md)
    self.track_id = track_id

  def backButtonClicked(self):
    if self.menu in ["title", "artist", "album", "genre"]:
      self.rootMenu(self.slot)
    elif self.menu == "title_by_artist_album":
      self.albumArtistMenu(self.artist_id)
    elif self.menu == "title_by_album":
      self.albumMenu()
    elif self.menu == "album_by_artist":
      self.artistMenu()
    elif self.menu == "artist_by_genre":
      self.genreMenu()
    elif self.menu == "album_by_genre_artist":
      self.artistGenreMenu(self.genre_id)
    elif self.menu == "title_by_genre_artist_album":
      self.albumArtistGenreMenu(self.artist_id)
    elif self.menu == "playlist_folder":
      if len(self.playlist_folder_stack) == 1:
        self.rootMenu(self.slot)
      else:
        self.playlist_folder_stack.pop() # pop the current directory
        self.folderPlaylistMenu(self.playlist_folder_stack.pop()) # display the current directory
    elif self.menu == "playlist":
      self.folderPlaylistMenu(self.playlist_folder_stack.pop())
    elif self.menu == "root":
      self.mediaMenu()
      return
    elif  self.menu == "media":
      return # no parent menu for media
    else:
      logging.debug("back button for %s not implemented yet", self.menu)
      return
    if self.path_stack:
      self.path_stack.pop()
    self.updatePath()

  def tableItemClicked(self, index):
    data = self.model.itemFromIndex(index).data()
    logging.debug("clicked data %s", data)
    if data is None:
      return
    if data["type"] == "media":
      self.updatePath(data["name"].upper())
      self.rootMenu(data["name"])
    elif data["type"] == "root":
      if data["name"] == "TRACK":
        self.updatePath("Tracks")
        self.titleMenu()
      elif data["name"] == "ARTIST":
        self.updatePath("Artists")
        self.artistMenu()
      elif data["name"] == "ALBUM":
        self.updatePath("Albums")
        self.albumMenu()
      elif data["name"] == "GENRE":
        self.updatePath("Genres")
        self.genreMenu()
      elif data["name"] == "PLAYLIST":
        self.updatePath("Playlists")
        self.folderPlaylistMenu()
      else:
        logging.warning("root menu type %s not implemented yet", data["name"])
    elif data["type"] == "album":
      self.updatePath(data["album"])
      self.titleAlbumMenu(data["album_id"])
    elif data["type"] == "artist":
      self.updatePath(data["artist"])
      self.albumArtistMenu(data["artist_id"])
    elif data["type"] == "album_by_artist":
      self.updatePath(data["album"])
      self.titleAlbumArtistMenu(data["album_id"])
    elif data["type"] == "genre":
      self.updatePath(data["genre"])
      self.artistGenreMenu(data["genre_id"])
    elif data["type"] == "artist_by_genre":
      self.updatePath(data["artist"])
      self.albumArtistGenreMenu(data["artist_id"])
    elif data["type"] == "album_by_genre_artist":
      self.updatePath(data["album"])
      self.titleAlbumArtistGenreMenu(data["album_id"])
    elif data["type"] == "folder":
      self.updatePath(data["folder"])
      self.folderPlaylistMenu(data["folder_id"])
    elif data["type"] == "playlist_folder":
      if "playlist_id" in data: # playlist clicked
        self.updatePath(data["playlist"])
        self.titlePlaylistMenu(data["playlist_id"])
      else: # playlist folder clicked
        self.updatePath(data["folder"])
        self.folderPlaylistMenu(data["folder_id"])
    elif data["type"] in ["title", "title_by_album", "title_by_artist_album", "title_by_genre_artist_album", "playlist"]:
      self.metadata(data["track_id"])
    else:
      logging.warning("unhandled click type %s", data["type"])
    self.updateButtons() # update buttons for convenience

  def sortChanged(self):
    self.sort = self.sort_box.currentData()
    logging.debug("sort changed to %s", self.sort)
    if self.menu == "title":
      self.titleMenu()
    elif self.menu == "title_by_album":
      self.titleAlbumMenu(self.album_id)
    elif self.menu == "title_by_artist_album":
      self.titleAlbumArtistMenu(self.album_id)
    elif self.menu == "title_by_genre_artist_album":
      self.titleAlbumArtistGenreMenu(self.album_id)
    elif self.menu == "playlist":
      self.titlePlaylistMenu(self.playlist_id)
    else:
      logging.debug("unsortable menu type %s", self.menu)

  def loadIntoPlayer(self, player_number):
    if self.slot is None or self.track_id is None:
      return
    logging.debug("loading track (pn %d slot %s tid %d) into player %d",
      self.player_number, self.slot, self.track_id, player_number)
    self.prodj.vcdj.command_load_track(player_number, self.player_number, self.slot, self.track_id)

  def downloadTrack(self):
    if all([self.player_number, self.slot, self.track_id]):
      self.prodj.data.get_mount_info(self.player_number, self.slot, self.track_id,
        self.prodj.nfs.enqueue_download_from_mount_info)

  def updateButtons(self):
    for i in range(1,5):
      self.load_buttons[i-1].setEnabled(self.prodj.cl.getClient(i) is not None)

  # special request handling to get into qt gui thread
  # storeRequest is called from outside (non-qt gui)
  def storeRequest(self, request, *args):
    if self.request is not None:
      logging.debug("not storing request %s, other request pending", request)
    #logging.debug("storing request %s", request)
    self.request = (request, *args)
    self.handleRequestSignal.emit()

  # handleRequest is called by handleRequestSignal, from inside the gui thread
  def handleRequest(self):
    #logging.debug("handle request %s", str(self.request))
    if self.request is None or self.request[-1] is None:
      return
    if self.request[0] == "root_menu":
      self.renderRootMenu(*self.request)
    elif self.request[0] in ["title", "artist", "album_by_artist", "title_by_artist_album", "album", "title_by_album", "genre", "artist_by_genre", "album_by_genre_artist", "title_by_genre_artist_album", "playlist_folder", "playlist"]:
      self.renderList(*self.request[:3], self.request[-1])
    elif self.request[0] == "metadata":
      self.renderMetadata(*self.request)
    else:
      logging.warning("%s request not implemented", self.request[0])
    self.request = None

  def refreshMedia(self, slot):
    if self.slot == slot or self.menu == "media":
      logging.info("slot %s changed, going back to media overview", slot)
      self.mediaMenu()
    else:
      logging.debug("ignoring %s change", slot)
