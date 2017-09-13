import time
import logging

class ClientList:
  def __init__(self, prodj):
    self.clients = []
    self.client_keepalive_callback = None
    self.client_change_callback = None
    self.master_change_callback = None
    self.auto_request_beatgrid = True # to enable position detection
    self.prodj = prodj

  def __len__():
    return len(self.clients)

  def getClient(self, player_number):
    return next((p for p in self.clients if p.player_number == player_number), None)

  def clientsByLoadedTrack(self, loaded_player_number, loaded_slot, track_id):
    for p in self.clients:
      if (p.loaded_player_number == loaded_player_number and
          p.loaded_slot == loaded_slot and
          p.track_id == track_id):
        yield p

  def clientsByLoadedTrackArtwork(self, loaded_player_number, loaded_slot, artwork_id):
    for p in self.clients:
      if (p.loaded_player_number == loaded_player_number and
          p.loaded_slot == loaded_slot and
          p.metadata is not None and
          p.metadata["artwork_id"] == artwork_id):
        yield p

  def storeMetadataByLoadedTrack(self, loaded_player_number, loaded_slot, track_id, metadata):
    for p in self.clients:
      if (p.loaded_player_number == loaded_player_number and
          p.loaded_slot == loaded_slot and
          p.track_id == track_id):
        p.metadata = metadata

  def updatePositionByBeat(self, player_number, new_beat_count, new_play_state):
    c = self.getClient(player_number)
    #logging.debug("Track position p %d abs %f actual_pitch %.6f play_state %s beat %d", player_number, c.position if c.position is not None else -1, c.actual_pitch, new_play_state, new_beat_count)
    identifier = (c.loaded_player_number, c.loaded_slot, c.track_id)
    if identifier in self.prodj.dbs.beatgrid_store:
      if new_beat_count > 0:
        if (c.play_state == "cued" and new_play_state == "cueing") or (c.play_state == "playing" and new_play_state == "paused") or (c.play_state == "paused" and new_play_state == "playing"):
          return # ignore absolute position when switching from cued to cueing
        if new_play_state != "cued": # when releasing cue scratch, the beat count is still +1
          new_beat_count -= 1
        beatgrid = self.prodj.dbs.beatgrid_store[identifier]
        if beatgrid is not None and len(beatgrid["beats"]) > new_beat_count:
          c.position = beatgrid["beats"][new_beat_count]["time"] / 1000
      else:
        c.position = 0
    else:
      c.position = None
    c.position_timestamp = time.time()

  # adds client if it is not known yet, in any case it resets the ttl
  def eatKeepalive(self, keepalive_packet):
    c = next((x for x in self.clients if x.ip_addr == keepalive_packet["ip_addr"]), None)
    if c is None:
      c = Client()
      c.model = keepalive_packet["model"]
      c.ip_addr = keepalive_packet["ip_addr"]
      c.mac_addr = keepalive_packet["mac_addr"]
      c.player_number = keepalive_packet["player_number"]
      self.clients += [c]
      logging.info("New Player %d: %s, %s, %s", c.player_number, c.model, c.ip_addr, c.mac_addr)
      if self.client_keepalive_callback:
        self.client_keepalive_callback(self, c.player_number)
    else:
      n = keepalive_packet["player_number"]
      if c.player_number != n:
        logging.info("Player {} changed player number from {} to {}".format(c.ip_addr, c.player_number, n))
        c.player_number = n
        if self.client_keepalive_callback:
          self.client_keepalive_callback(self, c.player_number)
        if self.client_change_callback:
          self.client_change_callback(self, c.player_number)
    c.updateTtl()

  # updates pitch/bpm/beat information for player if we do not receive status packets (e.g. no vcdj enabled)
  def eatBeat(self, beat_packet):
    c = self.getClient(beat_packet["player_number"])
    if c is None: # packet from unknown client
      return
    c.updateTtl()
    if not c.status_packet_received:
      client_changed = False;
      new_actual_pitch = beat_packet["pitch"]
      if c.actual_pitch != new_actual_pitch:
        c.actual_pitch = new_actual_pitch
        client_changed = True
      new_bpm = beat_packet["bpm"]
      if c.bpm != new_bpm:
        c.bpm = new_bpm
        client_changed = True
      new_beat = beat_packet["beat"]
      if c.beat != new_beat:
        c.beat = new_beat
        client_changed = True
      if self.client_change_callback and client_changed:
        self.client_change_callback(self, c.player_number)

  # update all known player information
  def eatStatus(self, status_packet):
    c = self.getClient(status_packet["player_number"])
    if c is None: # packet from unknown client
      return
    client_changed = False
    c.status_packet_received = True
    if status_packet["type"] not in ["cdj", "djm"]:
      logging.info("Received %s status packet, ignoring", status_packet["type"])
      return
    c.type = status_packet["type"] # cdj or djm

    new_bpm = status_packet["bpm"] if status_packet["bpm"] != 655.35 else "-"
    if c.bpm != new_bpm:
      c.bpm = new_bpm
      client_changed = True

    new_pitch = status_packet["physical_pitch"]
    if c.pitch != new_pitch:
      c.pitch = new_pitch
      client_changed = True

    new_beat = status_packet["beat"] if status_packet["beat"] != 0xffffffff else 0
    if c.beat != new_beat:
      c.beat = new_beat
      client_changed = True

    new_state = [x for x in ["on_air","sync","master","play"] if status_packet["state"][x]==True]
    if c.state != new_state:
      c.state = new_state
      client_changed = True

    if c.type == "cdj":
      new_beat_count = status_packet["beat_count"] if status_packet["beat_count"] != 0xffffffff else 0
      new_play_state = status_packet["play_state"]
      if new_beat_count != c.beat_count or new_play_state != c.play_state:
        self.updatePositionByBeat(c.player_number, new_beat_count, new_play_state) # position tracking, set new absolute grid value
      else: # otherwise, increment by pitch
        c.updatePositionByPitch()

      if c.beat_count != new_beat_count:
        c.beat_count = new_beat_count
        client_changed = True

      if c.play_state != new_play_state:
        c.play_state = new_play_state
        client_changed = True

      c.fw = status_packet["firmware"]

      new_actual_pitch = status_packet["actual_pitch"]
      if c.actual_pitch != new_actual_pitch:
        c.actual_pitch = new_actual_pitch
        client_changed = True

      new_cue_distance = status_packet["cue_distance"] if status_packet["cue_distance"] != 511 else "-"
      if c.cue_distance != new_cue_distance:
        c.cue_distance = new_cue_distance
        client_changed = True

      c.usb_state = status_packet["usb_state"]
      c.sd_state = status_packet["sd_state"]
      c.track_number = status_packet["track_number"]
      c.loaded_player_number = status_packet["loaded_player_number"]
      c.loaded_slot = status_packet["loaded_slot"]

      new_track_id = status_packet["track_id"]
      if c.track_id != new_track_id:
        c.track_id = new_track_id
        client_changed = True
        c.metadata = None
        c.position = None
        if self.auto_request_beatgrid and c.track_id != 0:
          self.prodj.dbs.get_beatgrid(c.loaded_player_number, c.loaded_slot, c.track_id)

    c.updateTtl()
    if self.client_change_callback and client_changed:
      self.client_change_callback(self, c.player_number)
    if self.master_change_callback and "master" in c.state and client_changed:
      self.master_change_callback(self, c.player_number)

  # checks ttl and clears expired clients
  def gc(self):
    cur_clients = self.clients
    self.clients = []
    for client in cur_clients:
      if not client.ttlExpired():
        self.clients += [client]
      else:
        logging.info("Player {} dropped due to timeout".format(client.player_number))
        if self.client_change_callback:
          self.client_change_callback(self, client.player_number)

  # returns a list of ips of all clients (used to guess own ip)
  def getClientIps(self):
    return [client.ip_addr for client in self.clients]

class Client:
  def __init__(self):
    # device specific
    self.type = "" # cdj, djm, rekordbox (currently rekordbox is detected as djm)
    self.model = ""
    self.fw = ""
    self.ip_addr = ""
    self.mac_addr = ""
    self.player_number = 0
    # play state
    self.bpm = None
    self.pitch = 1
    self.actual_pitch = 1
    self.beat = None
    self.beat_count = None
    self.cue_distance = None
    self.play_state = "no_track"
    self.usb_state = "not_loaded"
    self.sd_state = "not_loaded"
    self.loaded_player_number = 0
    self.loaded_slot = "empty"
    self.state = []
    self.track_number = None
    self.track_id = None
    self.position = None # position in track in seconds, 0 if not determinable
    self.position_timestamp = None
    # internal use
    self.metadata = None
    self.status_packet_received = False # ignore play state from beat packets
    self.ttl = time.time()

  # calculate the current position by linear interpolation
  def updatePositionByPitch(self):
    if not self.position or self.actual_pitch == 0:
      return
    pitch = self.actual_pitch
    if self.play_state in ["cued"]:
      pitch = 0
    now = time.time()
    self.position += pitch*(now-self.position_timestamp)
    self.position_timestamp = now
    #logging.debug("Track position inc %f actual_pitch %.6f play_state %s beat %d", self.position, self.actual_pitch, self.play_state, self.beat_count)
    return self.position

  def updateTtl(self):
    self.ttl = time.time()

  # drop clients after 5 seconds without keepalive packet
  def ttlExpired(self):
    return time.time()-self.ttl > 5
