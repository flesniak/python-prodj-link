import os
import logging

from .pdbfile import PDBFile

class PDBDatabase(dict):
  def __init__(self):
    super().__init__(self, tracks=[], artists=[], albums=[], playlists=[], playlist_map=[], artwork=[], colors=[], genres=[], labels=[], key_names=[])
    self.parsed = None

  def get_track(self, track_id):
    for track in self["tracks"]:
      if track.id == track_id:
        return track
    raise KeyError("PDBDatabase: track {} not found".format(track_id))

  def get_artist(self, artist_id):
    for artist in self["artists"]:
      if artist.id == artist_id:
        return artist
    raise KeyError("PDBDatabase: artist {} not found".format(artist_id))

  def get_album(self, album_id):
    for album in self["albums"]:
      if album.id == album_id:
        return album
    raise KeyError("PDBDatabase: album {} not found".format(album_id))

  def get_key(self, key_id):
    for key in self["key_names"]:
      if key.id == key_id:
        return key
    raise KeyError("PDBDatabase: key {} not found".format(key_id))

  def get_genre(self, genre_id):
    for genre in self["genres"]:
      if genre.id == genre_id:
        return genre
    raise KeyError("PDBDatabase: genre {} not found".format(genre_id))

  def get_label(self, label_id):
    for label in self["labels"]:
      if label.id == label_id:
        return label
    raise KeyError("PDBDatabase: label {} not found".format(genre_id))

  def get_color(self, color_id):
    for color in self["colors"]:
      if color.id == color_id:
        return color
    raise KeyError("PDBDatabase: color {} not found".format(color_id))

  def get_artwork(self, artwork_id):
    for artwork in self["artwork"]:
      if artwork.id == artwork_id:
        return artwork
    raise KeyError("PDBDatabase: artwork {} not found".format(artwork_id))

  def collect_entries(self, page_type, target):
    for page in filter(lambda x: x.page_type == page_type, self.parsed.pages):
      #logging.debug("PDBDatabase: parsing page %s %d", page.page_type, page.index)
      for entry_block in page.entry_list:
        for entry,enabled in zip(reversed(entry_block["entries"]), reversed(entry_block["entry_enabled"])):
          if not enabled:
            continue
          self[target] += [entry]
    logging.debug("PDBDatabase: done collecting {}".format(target))

  def load_file(self, filename):
    logging.debug("PDBDatabase: Loading file \"%s\"", filename)
    stat = os.stat(filename)
    fh = PDBFile
    with open(filename, "rb") as f:
      self.parsed = fh.parse_stream(f);

    if stat.st_size != self.parsed["file_size"]:
      raise RuntimeError("PDBDatabase: failed to parse the complete file ({}/{} bytes parsed)".format(self.parsed["file_size"], stat.st_size))

    self.collect_entries("block_tracks", "tracks")
    self.collect_entries("block_artists", "artists")
    self.collect_entries("block_albums", "albums")
    self.collect_entries("block_playlists", "playlists")
    self.collect_entries("block_playlist_map", "playlist_map")
    self.collect_entries("block_artwork", "artwork")
    self.collect_entries("block_colors", "colors")
    self.collect_entries("block_genres", "genres")
    self.collect_entries("block_keys", "key_names")
    self.collect_entries("block_labels", "labels")

    logging.debug("PDBDatabase: Loaded %d pages, %d tracks, %d playlists", len(self.parsed.pages), len(self["tracks"]), len(self["playlists"]))
