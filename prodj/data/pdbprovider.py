import logging
import os

from prodj.data.exceptions import FatalQueryError
from prodj.data.datastore import DataStore
from prodj.pdblib.pdbdatabase import PDBDatabase
from prodj.pdblib.usbanlzdatabase import UsbAnlzDatabase
from prodj.network.rpcreceiver import ReceiveTimeout

colors = ["none", "pink", "red", "orange", "yellow", "green", "aqua", "blue", "purple"]

class InvalidPDBDatabase:
  def __init__(self, reason):
    self.reason = reason

  def __str__(self):
    return self.reason

def wrap_get_name_from_db(call, id):
  if id == 0:
    return ""
  try:
    return call(id).name
  except KeyError as e:
    logging.warning(f'Broken database: {e}')
    return "?"

class PDBProvider:
  def __init__(self, prodj):
    self.prodj = prodj
    self.dbs = DataStore() # (player_number,slot) -> PDBDatabase
    self.usbanlz = DataStore() # (player_number, slot, track_id) -> UsbAnlzDatabase

  def cleanup_stores_from_changed_media(self, player_number, slot):
    self.dbs.removeByPlayerSlot(player_number, slot)
    self.usbanlz.removeByPlayerSlot(player_number, slot)

  def stop(self):
    self.dbs.stop()
    self.usbanlz.stop()

  def delete_pdb(self, filename):
    try:
      os.remove(filename)
    except OSError:
      pass

  def download_pdb(self, player_number, slot):
    player = self.prodj.cl.getClient(player_number)
    if player is None:
      raise FatalQueryError("player {} not found in clientlist".format(player_number))
    filename = "databases/player-{}-{}.pdb".format(player_number, slot)
    self.delete_pdb(filename)
    try:
      try:
        self.prodj.nfs.enqueue_download(player.ip_addr, slot, "/PIONEER/rekordbox/export.pdb", filename, sync=True)
      except FileNotFoundError as e:
        logging.debug("default pdb path not found on player %d, trying MacOS path", player_number)
        self.prodj.nfs.enqueue_download(player.ip_addr, slot, "/.PIONEER/rekordbox/export.pdb", filename, sync=True)
    except (RuntimeError, ReceiveTimeout) as e:
      raise FatalQueryError("database download from player {} failed: {}".format(player_number, e))
    return filename

  def download_and_parse_pdb(self, player_number, slot):
    filename = self.download_pdb(player_number, slot)
    db = PDBDatabase()
    try:
      db.load_file(filename)
    except RuntimeError as e:
      raise FatalQueryError("PDBProvider: failed to parse \"{}\": {}".format(filename, e))
    return db

  def get_db(self, player_number, slot):
    if (player_number, slot) not in self.dbs:
      try:
        db = self.download_and_parse_pdb(player_number, slot)
      except FatalQueryError as e:
        db = InvalidPDBDatabase(str(e))
      finally:
        self.dbs[player_number, slot] = db
    else:
      db = self.dbs[player_number, slot]
    if isinstance(db, InvalidPDBDatabase):
      raise FatalQueryError(f'PDB database not available: {db}')
    return db

  def download_and_parse_usbanlz(self, player_number, slot, anlz_path):
    player = self.prodj.cl.getClient(player_number)
    if player is None:
      raise FatalQueryError("player {} not found in clientlist".format(player_number))
    dat = self.prodj.nfs.enqueue_buffer_download(player.ip_addr, slot, anlz_path)
    ext = self.prodj.nfs.enqueue_buffer_download(player.ip_addr, slot, anlz_path.replace("DAT", "EXT"))
    db = UsbAnlzDatabase()
    if dat is not None and ext is not None:
      db.load_dat_buffer(dat)
      db.load_ext_buffer(ext)
    else:
      logging.warning("missing DAT or EXT data, returning empty UsbAnlzDatabase")
    return db

  def get_anlz(self, player_number, slot, track_id):
    if (player_number, slot, track_id) not in self.usbanlz:
      db = self.get_db(player_number, slot)
      track = db.get_track(track_id)
      self.usbanlz[player_number, slot, track_id] = self.download_and_parse_usbanlz(player_number, slot, track.analyze_path)
    return self.usbanlz[player_number, slot, track_id]

  def get_metadata(self, player_number, slot, track_id):
    db = self.get_db(player_number, slot)
    track = db.get_track(track_id)
    artist = wrap_get_name_from_db(db.get_artist, track.artist_id)
    album = wrap_get_name_from_db(db.get_album, track.album_id)
    key = wrap_get_name_from_db(db.get_key, track.key_id)
    genre = wrap_get_name_from_db(db.get_genre, track.genre_id)
    color_text = wrap_get_name_from_db(db.get_color, track.color_id)

    color_name = ""
    if track.color_id in range(1, len(colors)):
      color_name = colors[track.color_id]

    metadata = {
      "track_id": track.id,
      "title": track.title,
      "artist_id": track.artist_id,
      "artist": artist,
      "album_id": track.album_id,
      "album": album,
      "key_id": track.key_id,
      "key": key,
      "genre_id": track.genre_id,
      "genre": genre,
      "duration": track.duration,
      "comment": track.comment,
      "date_added": track.date_added,
      "color": color_name,
      "color_text": color_text,
      "rating": track.rating,
      "artwork_id": track.artwork_id,
      "bpm": track.bpm_100/100
    }
    return metadata

  def get_artwork(self, player_number, slot, artwork_id):
    player = self.prodj.cl.getClient(player_number)
    if player is None:
      raise FatalQueryError("player {} not found in clientlist".format(player_number))
    db = self.get_db(player_number, slot)
    try:
      artwork = db.get_artwork(artwork_id)
    except KeyError as e:
      logging.warning("No artwork for {}, returning empty data".format((player_number, slot, artwork_id)))
      return None
    return self.prodj.nfs.enqueue_buffer_download(player.ip_addr, slot, artwork.path)

  def get_waveform(self, player_number, slot, track_id):
    db = self.get_anlz(player_number, slot, track_id)
    try:
      return db.get_waveform()
    except KeyError as e:
      logging.warning("No waveform for {}, returning empty data".format((player_number, slot, track_id)))
      return None

  def get_preview_waveform(self, player_number, slot, track_id):
    db = self.get_anlz(player_number, slot, track_id)
    waveform_spread = b""
    try:
      for line in db.get_preview_waveform():
        waveform_spread += bytes([line & 0x1f, line>>5])
    except KeyError as e:
      logging.warning("No preview waveform for {}, returning empty data".format((player_number, slot, track_id)))
      return None
    return waveform_spread

  def get_color_waveform(self, player_number, slot, track_id):
    db = self.get_anlz(player_number, slot, track_id)
    try:
      return db.get_color_waveform()
    except KeyError as e:
      logging.warning("No color waveform for {}, returning empty data".format((player_number, slot, track_id)))
      return None

  def get_color_preview_waveform(self, player_number, slot, track_id):
    db = self.get_anlz(player_number, slot, track_id)
    try:
      return db.get_color_preview_waveform()
    except KeyError as e:
      logging.warning("No color preview waveform for {}, returning empty data".format((player_number, slot, track_id)))
      return None

  def get_beatgrid(self, player_number, slot, track_id):
    db = self.get_anlz(player_number, slot, track_id)
    try:
      return db.get_beatgrid()
    except KeyError as e:
      logging.warning("No beatgrid for {}, returning empty data".format((player_number, slot, track_id)))
      return None

  def get_mount_info(self, player_number, slot, track_id):
    db = self.get_db(player_number, slot)
    track = db.get_track(track_id)

    # contains additional fields to mimic dbserver reply
    mount_info = {
      "track_id": track.id,
      "duration": track.duration,
      "bpm": track.bpm_100/100,
      "mount_path": track.path
    }
    return mount_info

  # returns a dummy root menu
  def get_root_menu(self):
    return [
      {'name': '\ufffaTRACK\ufffb', 'menu_id': 4},
      {'name': '\ufffaARTIST\ufffb', 'menu_id': 2},
      {'name': '\ufffaALBUM\ufffb', 'menu_id': 3},
      {'name': '\ufffaGENRE\ufffb', 'menu_id': 1},
      {'name': '\ufffaKEY\ufffb', 'menu_id': 12},
      {'name': '\ufffaPLAYLIST\ufffb', 'menu_id': 5},
      {'name': '\ufffaHISTORY\ufffb', 'menu_id': 22},
      {'name': '\ufffaSEARCH\ufffb', 'menu_id': 18},
      {'name': '\ufffaFOLDER\ufffb', 'menu_id': 17}
    ]

  def convert_and_sort_track_list(self, db, track_list, sort_mode):
    converted = []
    # we do not know the default sort mode from pdb, thus fall back to title
    if sort_mode in ["title", "default"]:
      col2_name = "artist"
    else:
      col2_name = sort_mode
    for track in track_list:
      if col2_name in ["title", "artist"]:
        col2_item = wrap_get_name_from_db(db.get_artist, track.artist_id)
      elif col2_name == "album":
        col2_item = wrap_get_name_from_db(db.get_album, track.album_id)
      elif col2_name == "genre":
        col2_item = wrap_get_name_from_db(db.get_genre, track.genre_id)
      elif col2_name == "label":
        col2_item = wrap_get_name_from_db(db.get_label, track.label_id)
      elif col2_name == "original_artist":
        col2_item = wrap_get_name_from_db(db.get_artist, track.original_artist_id)
      elif col2_name == "remixer":
        col2_item = wrap_get_name_from_db(db.get_artist, track.remixer_id)
      elif col2_name == "key":
        col2_item = wrap_get_name_from_db(db.get_key, track.key_id)
      elif col2_name == "bpm":
        col2_item = track.bpm_100/100
      elif col2_name in ["rating", "comment", "duration", "bitrate", "play_count"]: # 1:1 mappings
        col2_item = track[col2_name]
      else:
        raise FatalQueryError("unknown sort mode {}".format(sort_mode))
      converted += [{
        "title": track.title,
        col2_name: col2_item,
        "track_id": track.id,
        "artist_id": track.artist_id,
        "album_id": track.album_id,
        "artwork_id": track.artwork_id,
        "genre_id": track.genre_id}]
    if sort_mode == "default":
      return converted
    else:
      return sorted(converted, key=lambda key: key[sort_mode], reverse=sort_mode=="rating")

  # id_list empty -> list all titles
  # one id_list entry = album_id -> all titles in album
  # two id_list entries = artist_id,album_id -> all titles in album by artist
  # three id_list entries = genre_id,artist_id,album_id -> all titles in album by artist matching genre
  def get_titles(self, player_number, slot, sort_mode="default", id_list=[]):
    logging.debug("get_titles (%d, %s, %s) sort %s", player_number, slot, str(id_list), sort_mode)
    db = self.get_db(player_number, slot)
    if len(id_list) == 3: # genre, artist, album
      if id_list[1] == 0 and id_list[2] == 0: # any artist, any album
        ff = lambda track: track.genre_id == id_list[0]
      elif id_list[2] == 0: # any album
        ff = lambda track: track.genre_id == id_list[0] and track.artist_id == id_list[1]
      elif id_list[1] == 0: # any artist
        ff = lambda track: track.genre_id == id_list[0] and track.album_id == id_list[2]
      else:
        ff = lambda track: track.genre_id == id_list[0] and track.artist_id == id_list[1] and track.album_id == id_list[2]
    elif len(id_list) == 2: # artist, album
      if id_list[1] == 0: # any album
        ff = lambda track: track.artist_id == id_list[0]
      else:
        ff = lambda track: track.artist_id == id_list[0] and track.album_id == id_list[1]
    elif len(id_list) == 1:
      ff = lambda track: track.album_id == id_list[0]
    else:
      ff = None
    track_list = filter(ff, db["tracks"])
    # on titles, fall back to "title" sort mode as we can't know the user's default choice
    if sort_mode == "default":
      sort_mode = "title"
    return self.convert_and_sort_track_list(db, track_list, sort_mode)

  # id_list empty -> list all artists
  # one id_list entry = genre_id -> all artists by genre
  def get_artists(self, player_number, slot, id_list=[]):
    logging.debug("get_artists (%d, %s, %s)", player_number, slot, str(id_list))
    db = self.get_db(player_number, slot)
    if len(id_list) == 1:
      ff = lambda artist: any(artist.id == track.artist_id for track in db["tracks"] if track.genre_id == id_list[0])
      prepend = [{"all": " ALL "}]
    else:
      ff = None
      prepend = []
    artist_list = filter(ff, db["artists"])
    artists = [{"artist": artist.name, "artist_id": artist.id} for artist in artist_list]
    return prepend+sorted(artists, key=lambda key: key["artist"])

  # id_list empty -> list all albums
  # one id_list entry = artist_id -> all albums by artist
  # two id_list entries = genre_id, artist_id -> all albums by artist matching genre
  # two id_list entries = genre_id, 0 -> all albums matching genre
  def get_albums(self, player_number, slot, id_list=[]):
    logging.debug("get_albums (%d, %s, %s)", player_number, slot, str(id_list))
    db = self.get_db(player_number, slot)
    if len(id_list) == 2:
      if id_list[1] == 0:
        ff = lambda album: any(album.id == track.album_id for track in db["tracks"] if track.genre_id == id_list[0])
      else:
        ff = lambda album: any(album.id == track.album_id for track in db["tracks"] if track.artist_id == id_list[1] and track.genre_id == id_list[0])
      prepend = [{"all": " ALL "}]
    elif len(id_list) == 1:
      ff = lambda album: any(album.id == track.album_id for track in db["tracks"] if track.artist_id == id_list[0])
      prepend = [{"all": " ALL "}]
    else:
      ff = None
      prepend = []
    album_list = filter(ff, db["albums"])
    albums = [{"album": album.name, "album_id": album.id} for album in album_list]
    return prepend+sorted(albums, key=lambda key: key["album"])

  # id_list empty -> list genres
  def get_genres(self, player_number, slot):
    logging.debug("get_genres (%d, %s)", player_number, slot)
    db = self.get_db(player_number, slot)
    genres = [{"genre": genre.name, "genre_id": genre.id} for genre in db["genres"]]
    sorted_genres = sorted(genres, key=lambda key: key["genre"])
    return sorted(genres, key=lambda key: key["genre"])

  def get_playlists(self, player_number, slot, folder_id):
    logging.debug("get_playlists (%d, %s, %d)", player_number, slot, folder_id)
    db = self.get_db(player_number, slot)
    playlists = []
    for playlist in db.get_playlists(folder_id):
      if playlist.is_folder:
        playlists += [{"folder": playlist.name, "folder_id": playlist.id, "parend_id": playlist.folder_id}]
      else:
        playlists += [{"playlist": playlist.name, "playlist_id": playlist.id, "parend_id": playlist.folder_id}]
    return playlists

  def get_playlist(self, player_number, slot, sort_mode, playlist_id):
    logging.debug("get_playlist (%d, %s, %d, %s)", player_number, slot, playlist_id, sort_mode)
    db = self.get_db(player_number, slot)
    track_list = db.get_playlist(playlist_id)
    return self.convert_and_sort_track_list(db, track_list, sort_mode)
    #{'title': 'The Raven', 'artwork_id': 123, 'track_id': 225, 'artist_id': 4, 'key': '09A', 'key_id': 4}

  def handle_request(self, request, params):
    logging.debug("handling %s request params %s", request, str(params))
    if request == "metadata":
      return self.get_metadata(*params)
    elif request == "root_menu":
      return self.get_root_menu()
    elif request == "title":
      return self.get_titles(*params)
    elif request == "title_by_album":
      return self.get_titles(*params)
    elif request == "title_by_artist_album":
      return self.get_titles(*params)
    elif request == "title_by_genre_artist_album":
      return self.get_titles(*params)
    elif request == "artist":
      return self.get_artists(*params)
    elif request == "artist_by_genre":
      return self.get_artists(*params)
    elif request == "album":
      return self.get_albums(*params)
    elif request == "album_by_artist":
      return self.get_albums(*params)
    elif request == "album_by_genre_artist":
      return self.get_albums(*params)
    elif request == "genre":
      return self.get_genres(*params)
    elif request == "playlist_folder":
      return self.get_playlists(*params)
    elif request == "playlist":
      return self.get_playlist(*params)
    elif request == "artwork":
      return self.get_artwork(*params)
    elif request == "waveform":
      return self.get_waveform(*params)
    elif request == "preview_waveform":
      return self.get_preview_waveform(*params)
    elif request == "color_waveform":
      return self.get_color_waveform(*params)
    elif request == "color_preview_waveform":
      return self.get_color_preview_waveform(*params)
    elif request == "beatgrid":
      return self.get_beatgrid(*params)
    elif request == "mount_info":
      return self.get_mount_info(*params)
    else:
      raise FatalQueryError("invalid request type {}".format(request))
