import time
import logging

class ClientList:
  def __init__(self, prodj):
    self.clients = []
    self.client_keepalive_callback = None
    self.client_change_callback = None
    self.master_change_callback = None
    self.prodj = prodj

  def __len__():
    return len(self.clients)

  def getClient(self, player_number):
    return next((p for p in self.clients if p.player_number == player_number), None)

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
      c.pitch = beat_packet["pitch"]
      c.bpm = beat_packet["bpm"]
      c.beat = beat_packet["beat"]
      if self.client_change_callback:
        self.client_change_callback(self, c.player_number)

  # update all known player information
  def eatStatus(self, status_packet):
    c = self.getClient(status_packet["player_number"])
    if c is None: # packet from unknown client
      return
    client_changed = False
    c.status_packet_received = True
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
      c.fw = status_packet["firmware"]
      new_actual_pitch = status_packet["actual_pitch"]
      if c.actual_pitch != new_actual_pitch:
        c.actual_pitch = new_actual_pitch
        client_changed = True
      new_beat_count = status_packet["beat_count"] if status_packet["beat_count"] != 0xffffffff else "-"
      if c.beat_count != new_beat_count:
        c.beat_count = new_beat_count
        client_changed = True
      new_cue_distance = status_packet["cue_distance"] if status_packet["cue_distance"] != 511 else "-"
      if c.cue_distance != new_cue_distance:
        c.cue_distance = new_cue_distance
        client_changed = True
      new_play_state = status_packet["play_state"]
      if c.play_state != new_play_state:
        c.play_state = new_play_state
        client_changed = True
      c.usb_state = status_packet["usb_state"]
      c.sd_state = status_packet["sd_state"]
      c.player_slot = status_packet["loaded_slot"]
      c.track_number = status_packet["track_number"]
      c.loaded_player_number = status_packet["loaded_player_number"]
      c.loaded_slot = status_packet["loaded_slot"]
      new_track_id = status_packet["track_id"]
      if c.track_id != new_track_id:
        c.track_id = new_track_id
        client_changed = True

    c.updateTtl()
    if self.client_change_callback and client_changed:
      self.client_change_callback(self, c.player_number)
    if self.master_change_callback and "master" in c.state and client_changed:
      self.master_change_callback(self, c.player_number)

  def setMetadata(self, request, player_number, slot, track_id, md):
    c = self.getClient(player_number)
    if c is None or request != "metadata": # metadata from unknown client
      return
    c.metadata = md
    if self.client_change_callback:
      self.client_change_callback(self, player_number)

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
    self.player_slot = "empty"
    self.state = []
    self.track_number = None
    self.loaded_player_number = 0
    self.loaded_slot = "empty"
    self.track_id = None
    # internal use
    self.metadata = None
    self.status_packet_received = False # ignore play state from beat packets
    self.ttl = time.time()

  def updateTtl(self):
    self.ttl = time.time()

  # drop clients after 5 seconds without keepalive packet
  def ttlExpired(self):
    return time.time()-self.ttl > 5
