import dataprovider
from datastore import DataStore

colors = ["none", "pink", "red", "orange", "yellow", "green", "aqua", "blue", "purple"]

class PDBProvider:
  def __init__(self, prodj):
    self.prodj = prodj
    self.dbs = DataStore # (player_number,slot): PDBDatabase

  def delete_pdb(self, filename):
    try:
      os.delete(filename)
    except OSError:
      pass

  def download_pdb(self, player_number, slot):
    player = self.prodj.cl.getClient(player_number)
    if player is None:
      raise dataprovider.FatalQueryError("PDBProvider: player {} not found in clientlist".format(player_number))
    filename = "databases/player-{}-{}.pdb".format(player_number, slot)
    self.delete_pdb(filename)
    try:
      self.prodj.nfs.enqueue_download(player.ip_addr, slot, "/PIONEER/rekordbox/export.pdb", filename, sync=True)
    except RuntimeError as e:
      raise dataprovider.FatalQueryError("PDBProvider: database download from player {} failed: {}".format(player_number, e))
    return filename

  def download_and_parse_pdb(self, player_number, slot):
    filename = self.download_pdb(player_number, slot)
    db = PDBDatabase()
    try:
      db.load_file(filename)
    except RuntimeError as e:
      raise FatalQueryError("PDBFile: failed to parse \"{}\": {}".format(filename, e))
    return db

  def get_db(self, player_number, slot):
    if (player_number, slot) not in self.dbs:
      db = self.download_and_parse_pdb(player_number, slot)
      self.dbs[player_number, slot] = db
    else:
      db = self.dbs[player_number, slot]
    return db

  # except KeyError:
  #   raise FatalQueryError("PDBFile: player {} slot {} track {} not found in pdb".format(player_number, slot, track_id))
  def get_metadata(self, player_number, slot, track_id):
    db = self.get_db()
    track = db.get_track(track_id)
    artist = db.get_artist(track.artist_id)
    album = db.get_album(track.album_id)
    key = db.get_key(track.key_id)
    genre = db.get_genre(track.genre_id)
    color_name = colors[track.color_id]
    if track.color_id > 0:
      color = db.get_color(track.color_id)
      color_text = color.name
    else:
      color_text = ""

    metadata = {
      "track_id": track.id,
      "title": track.title,
      "artist_id": track.artist_id,
      "artist": artist.name,
      "album_id": track.album_id,
      "album": album.name,
      "key_id": track.key_id,
      "key": key.name,
      "genre_id": track.genre_id,
      "genre": genre.name,
      "duration": track.length_seconds,
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
    db = self.get_db()
    artwork = db.get_artwork()
    self.prodj.nfs.enqueue_download(player.ip_addr, slot, artwork.path, filename, sync=True)
    pass

  def get_waveform(self, player_number, slot, track_id):
    pass

  def get_preview_waveform(self, player_number, slot, track_id):
    pass

  def get_beatgrid(self, player_number, slot, track_id):
    pass

  def get_mount_info(self, player_number, slot, track_id):
    db = self.get_db()
    track = db.get_track(track_id)

    # contains additional fields to mimic dbserver reply
    mount_info = {
      "track_id": track.id,
      "duration": track.length_seconds,
      "bpm": track.bpm_100/100
    }
    return mount_info

  def handle_request(self, request, params):
    logging.debug("DBClient: handling %s request params %s", request, str(params))
    if request == "metadata":
      return self.get_metadata(*params)
    elif request == "root_menu":
      return self.query_list(*params, None, None, "root_menu_request")
    elif request == "title":
      return self.query_list(*params, "title_request")
    elif request == "title_by_album":
      return self.query_list(*params, "title_by_album_request")
    elif request == "artist":
      return self.query_list(*params, "artist_request")
    elif request == "album_by_artist":
      return self.query_list(*params, "album_by_artist_request")
    elif request == "album":
      return self.query_list(*params, "album_request")
    elif request == "title_by_artist_album":
      return self.query_list(*params, "title_by_artist_album_request")
    elif request == "genre":
      return self.query_list(*params, "genre_request")
    elif request == "artist_by_genre":
      return self.query_list(*params, "artist_by_genre_request")
    elif request == "album_by_genre_artist":
      return self.query_list(*params, "album_by_genre_artist_request")
    elif request == "title_by_genre_artist_album":
      return self.query_list(*params, "title_by_genre_artist_album_request")
    elif request in ["playlist", "playlist_folder"]:
      return self.query_list(*params, "playlist_request")
    elif request == "artwork":
      return self.get_artwork(*params)
    elif request == "waveform":
      return self.query_blob(*params, "waveform_request", 1)
    elif request == "preview_waveform":
      return self.query_blob(*params, "preview_waveform_request")
    elif request == "mount_info":
      return self.query_list(*params, "track_data_request")
    elif request == "beatgrid":
      reply = self.query_blob(*params, "beatgrid_request")
      if reply is None:
        return None
      try: # pre-parse beatgrid data (like metadata) for easier access
        return packets.Beatgrid.parse(reply)
      except (RangeError, FieldError) as e:
        raise dataprovider.FatalQueryError("DBClient: failed to parse beatgrid data: {}".format(e))
    else:
      raise dataprovider.FatalQueryError("DBClient: invalid request type {}".format(request))
