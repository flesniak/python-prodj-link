import logging
import time
from threading import Thread
from queue import Empty, Queue

from .datastore import DataStore
from .dbclient import DBClient
from .pdbprovider import PDBProvider
from .exceptions import TemporaryQueryError, FatalQueryError

class DataProvider(Thread):
  def __init__(self, prodj):
    super().__init__()
    self.prodj = prodj
    self.queue = Queue()
    self.keep_running = True

    self.pdb_enabled = True
    self.pdb = PDBProvider(prodj)

    self.dbc_enabled = True
    self.dbc = DBClient(prodj)

    # db queries seem to work if we submit player number 0 everywhere (NOTE: this seems to work only if less than 4 players are on the network)
    # however, this messes up rendering on the players sometimes (i.e. when querying metadata and player has browser opened)
    # alternatively, we can use a player number from 1 to 4 without rendering issues, but then only max. 3 real players can be used
    self.own_player_number = 0
    self.request_retry_count = 3

    self.metadata_store = DataStore() # map of player_number,slot,track_id: metadata
    self.artwork_store = DataStore() # map of player_number,slot,artwork_id: artwork_data
    self.waveform_store = DataStore() # map of player_number,slot,track_id: waveform_data
    self.preview_waveform_store = DataStore() # map of player_number,slot,track_id: preview_waveform_data
    self.color_waveform_store = DataStore() # map of player_number,slot,track_id: color_waveform_data
    self.color_preview_waveform_store = DataStore() # map of player_number,slot,track_id: color_preview_waveform_data
    self.beatgrid_store = DataStore() # map of player_number,slot,track_id: beatgrid_data

  def start(self):
    self.keep_running = True
    super().start()

  def stop(self):
    self.keep_running = False
    self.pdb.stop()
    self.metadata_store.stop()
    self.artwork_store.stop()
    self.waveform_store.stop()
    self.preview_waveform_store.stop()
    self.color_waveform_store.stop()
    self.color_preview_waveform_store.stop()
    self.beatgrid_store.stop()
    self.join()

  def cleanup_stores_from_changed_media(self, player_number, slot):
    self.metadata_store.removeByPlayerSlot(player_number, slot)
    self.artwork_store.removeByPlayerSlot(player_number, slot)
    self.waveform_store.removeByPlayerSlot(player_number, slot)
    self.preview_waveform_store.removeByPlayerSlot(player_number, slot)
    self.color_waveform_store.removeByPlayerSlot(player_number, slot)
    self.color_preview_waveform_store.removeByPlayerSlot(player_number, slot)
    self.beatgrid_store.removeByPlayerSlot(player_number, slot)
    self.pdb.cleanup_stores_from_changed_media(player_number, slot)

  # called from outside, enqueues request
  def get_metadata(self, player_number, slot, track_id, callback=None):
    self._enqueue_request("metadata", self.metadata_store, (player_number, slot, track_id), callback)

  def get_root_menu(self, player_number, slot, callback=None):
    self._enqueue_request("root_menu", None, (player_number, slot), callback)

  def get_titles(self, player_number, slot, sort_mode="default", callback=None):
    self._enqueue_request("title", None, (player_number, slot, sort_mode), callback)

  def get_titles_by_album(self, player_number, slot, album_id, sort_mode="default", callback=None):
    self._enqueue_request("title_by_album", None, (player_number, slot, sort_mode, [album_id]), callback)

  def get_titles_by_artist_album(self, player_number, slot, artist_id, album_id, sort_mode="default", callback=None):
    self._enqueue_request("title_by_artist_album", None, (player_number, slot, sort_mode, [artist_id, album_id]), callback)

  def get_titles_by_genre_artist_album(self, player_number, slot, genre_id, artist_id, album_id, sort_mode="default", callback=None):
    self._enqueue_request("title_by_genre_artist_album", None, (player_number, slot, sort_mode, [genre_id, artist_id, album_id]), callback)

  def get_artists(self, player_number, slot, callback=None):
    self._enqueue_request("artist", None, (player_number, slot), callback)

  def get_artists_by_genre(self, player_number, slot, genre_id, callback=None):
    self._enqueue_request("artist_by_genre", None, (player_number, slot, [genre_id]), callback)

  def get_albums(self, player_number, slot, callback=None):
    self._enqueue_request("album", None, (player_number, slot), callback)

  def get_albums_by_artist(self, player_number, slot, artist_id, callback=None):
    self._enqueue_request("album_by_artist", None, (player_number, slot, [artist_id]), callback)

  def get_albums_by_genre_artist(self, player_number, slot, genre_id, artist_id, callback=None):
    self._enqueue_request("album_by_genre_artist", None, (player_number, slot, [genre_id, artist_id]), callback)

  def get_genres(self, player_number, slot, callback=None):
    self._enqueue_request("genre", None, (player_number, slot), callback)

  def get_playlist_folder(self, player_number, slot, folder_id=0, callback=None):
    self._enqueue_request("playlist_folder", None, (player_number, slot, folder_id), callback)

  def get_playlist(self, player_number, slot, playlist_id, sort_mode="default", callback=None):
    self._enqueue_request("playlist", None, (player_number, slot, sort_mode, playlist_id), callback)

  def get_artwork(self, player_number, slot, artwork_id, callback=None):
    self._enqueue_request("artwork", self.artwork_store, (player_number, slot, artwork_id), callback)

  def get_waveform(self, player_number, slot, track_id, callback=None):
    self._enqueue_request("waveform", self.waveform_store, (player_number, slot, track_id), callback)

  def get_preview_waveform(self, player_number, slot, track_id, callback=None):
    self._enqueue_request("preview_waveform", self.preview_waveform_store, (player_number, slot, track_id), callback)

  def get_color_waveform(self, player_number, slot, track_id, callback=None):
    self._enqueue_request("color_waveform", self.color_waveform_store, (player_number, slot, track_id), callback)

  def get_color_preview_waveform(self, player_number, slot, track_id, callback=None):
    self._enqueue_request("color_preview_waveform", self.color_preview_waveform_store, (player_number, slot, track_id), callback)

  def get_beatgrid(self, player_number, slot, track_id, callback=None):
    self._enqueue_request("beatgrid", self.beatgrid_store, (player_number, slot, track_id), callback)

  def get_mount_info(self, player_number, slot, track_id, callback=None):
    self._enqueue_request("mount_info", None, (player_number, slot, track_id), callback)

  def get_track_info(self, player_number, slot, track_id, callback=None):
    self._enqueue_request("track_info", None, (player_number, slot, track_id), callback)

  def _enqueue_request(self, request, store, params, callback):
    player_number = params[0]
    if player_number == 0 or player_number > 4:
      logging.warning("invalid %s request parameters", request)
      return
    logging.debug("enqueueing %s request with params %s", request, str(params))
    self.queue.put((request, store, params, callback, self.request_retry_count))

  def _handle_request_from_store(self, store, params):
    if len(params) != 3:
      logging.error("unable to handle request from store with != 3 arguments")
      return None
    if params in store:
      return store[params]
    return None

  def _handle_request_from_pdb(self, request, params):
    return self.pdb.handle_request(request, params)

  def _handle_request_from_dbclient(self, request, params):
    return self.dbc.handle_request(request, params)

  def _handle_request(self, request, store, params, callback):
    #logging.debug("handling %s request params %s", request, str(params))
    reply = None
    answered_by_store = False
    if store is not None:
      logging.debug("trying request %s %s from store", request, str(params))
      reply = self._handle_request_from_store(store, params)
      if reply is not None:
        answered_by_store = True
    if self.pdb_enabled and reply is None:
      try:
        logging.debug("trying request %s %s from pdb", request, str(params))
        reply = self._handle_request_from_pdb(request, params)
      except FatalQueryError as e: # on a fatal error, continue with dbc
        logging.warning("pdb failed [%s]", str(e))
        if not self.dbc_enabled:
          raise
    if self.dbc_enabled and reply is None:
      logging.debug("trying request %s %s from dbc", request, str(params))
      reply = self._handle_request_from_dbclient(request, params)

    if reply is None:
      raise FatalQueryError("DataStore: request returned none, see log for details")

    # special call for metadata since it is expected to be part of the client status
    if request == "metadata":
      self.prodj.cl.storeMetadataByLoadedTrack(*params, reply)

    if store is not None and answered_by_store == False:
      store[params] = reply

    # TODO: synchronous mode
    if callback is not None:
      callback(request, *params, reply)

  def _retry_request(self, request):
    self.queue.task_done()
    if request[-1] > 0:
      if request[0] == "color_waveform":
        logging.info("Color waveform request failed, trying normal waveform instead")
        request = ("waveform", *request[1:])
      elif request[0] == "color_preview_waveform":
        logging.info("Color preview waveform request failed, trying normal waveform instead")
        request = ("preview_waveform", *request[1:])
      else:
        logging.info("retrying %s request", request[0])
      self.queue.put((*request[:-1], request[-1]-1))
      time.sleep(1) # yes, this is dirty, but effective to work around timing problems on failed request
    else:
      logging.info("%s request failed %d times, giving up", request[0], self.request_retry_count)

  def gc(self):
    self.dbc.gc()

  def run(self):
    logging.debug("DataProvider starting")
    while self.keep_running:
      try:
        request = self.queue.get(timeout=1)
      except Empty:
        self.gc()
        continue
      try:
        self._handle_request(*request[:-1])
        self.queue.task_done()
      except TemporaryQueryError as e:
        logging.warning("%s request failed: %s", request[0], e)
        self._retry_request(request)
      except FatalQueryError as e:
        logging.error("%s request failed: %s", request[0], e)
        self.queue.task_done()
    logging.debug("DataProvider shutting down")
