import socket
import packets
import logging
import time
from threading import Thread
from queue import Empty, Queue
from construct import FieldError, RangeError, byte2int
#from select import select

metadata_type = {
  0x0001: "folder",
  0x0002: "album",
  0x0003: "disc",
  0x0004: "title",
  0x0006: "genre",
  0x0007: "artist",
  0x0008: "playlist",
  0x000a: "rating",
  0x000b: "duration",
  0x000d: "bpm",
  0x000e: "label",
  0x000f: "key",
  0x0013: "color_none",
  0x0014: "color_pink",
  0x0015: "color_red",
  0x0016: "color_orange",
  0x0017: "color_yellow",
  0x0018: "color_green",
  0x0019: "color_aqua",
  0x001a: "color_blue",
  0x001b: "color_purple",
  0x0023: "comment",
  0x0028: "original_artist",
  0x0029: "remixer",
  0x002e: "date_added",
  0x0204: "title_and_album",
  0x0604: "title_and_genre",
  0x0704: "title_and_artist",
  0x0a04: "title_and_rating",
  0x0b04: "title_and_time",
  0x0d04: "title_and_bpm",
  0x0e04: "title_and_label",
  0x0f04: "title_and_key",
  0x1004: "title_and_bitrate",
  0x1a04: "title_and_color",
  0x2304: "title_and_comment",
  0x2804: "title_and_original_artist",
  0x2904: "title_and_remixer",
  0x2a04: "title_and_dj_play_count",
  0x2e04: "title_and_date_added"
}

class DBClient(Thread):
  def __init__(self, prodj):
    super().__init__()
    self.cl = prodj.cl
    self.remote_ports = {} # dict {player_number: (ip, port)}
    self.transaction_id = 1
    self.queue = Queue()
    self.sock = None # a single connection to one player
    self.player_number = 0 # db queries seem to work if we submit player number 0 everywhere
    self.metadata_store = {} # map of player_number,slot,track_id: metadata
    self.artwork_store = {} # map of player_number,slot,artwork_id: artwork_data
    self.waveform_store = {} # map of player_number,slot,artwork_id: waveform_data
    self.metadata_change_callback = None # 2 parameters: player_number, metadata

  def start(self):
    self.keep_running = True
    super().start()

  def stop(self):
    self.keep_running = False
    self.join()

  def get_transaction_id(self):
    tid = self.transaction_id
    self.transaction_id += 1
    return tid

  def get_server_port(self, player_number):
    if player_number not in self.remote_ports:
      client = self.cl.getClient(player_number)
      if client is None:
        logging.error("DBClient: client {} not found".format(player_number))
        return
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      sock.connect((client.ip_addr, packets.DBServerQueryPort))
      sock.send(packets.DBServerQuery.build({}))
      data = sock.recv(2)
      sock.close()
      port = packets.DBServerReply.parse(data)
      self.remote_ports[player_number] = (client.ip_addr, port)
      logging.info("DBServer port of player {}: {}".format(player_number, port))
    return self.remote_ports[player_number]

  def send_initial_packet(self):
    init_packet = packets.DBFieldFixed("int32")
    self.sock.send(init_packet.build(1))
    data = self.sock.recv(16)

  def send_setup_packet(self, connect_player_number):
    query = {
      "transaction_id": 0xfffffffe,
      "type": "setup",
      "args": [{"type": "int32", "value": self.player_number}]
    }
    self.sock.send(packets.DBMessage.build(query))
    data = self.sock.recv(48)
    if len(data) == 0:
      logging.error("Failed to connect to player {}".format(connect_player_number))
      return
    reply = packets.DBMessage.parse(data)
    logging.info("DBServer: connected to player {}".format(reply["args"][1]["value"]))

  def parse_metadata(self, data):
    md = {}
    for packet in data:
      # check packet types
      if packet["type"] == "menu_header":
        logging.debug("DBServer: parse_metadata menu_header")
        continue
      if packet["type"] == "menu_footer":
        logging.debug("DBServer: parse_metadata menu_footer")
        break
      if packet["type"] != "menu_item":
        logging.warning("DBServer: parse_metadata item not menu_item: {}".format(packet))
        continue

      # extract metadata from packet
      md_type = packet["args"][6]["value"]
      md_number = packet["args"][1]["value"]
      md_string1 = packet["args"][3]["value"]
      md_string2 = packet["args"][5]["value"]
      if md_type not in metadata_type:
        logging.warning("DBServer: metadata type {} unknown".format(md_type))
        continue
      md_name = metadata_type[md_type]

      # parse metadata depending on packet type name
      if md_name in ["duration", "rating", "disc"]:
        md_value = md_number # plain numbers
      elif md_name == "bpm":
        md_value = md_number/100
      elif md_name == "title":
        md["artwork_id"] = packet["args"][8]["value"]
        md_value = md_string1
      elif md_name[:5] == "color":
        md_value = md_name[6:]
        md_name = "color"
        md["color_text"] = md_string1
        logging.debug("DBServer: color {} color_text {}".format(md_value, md_string1))
      else:
        md_value = md_string1

      # store metadata
      md[md_name] = md_value
      logging.debug("DBServer: parse_metadata {} = {}".format(md_name, md_string1))
      if len(md_string2) > 0:
        logging.warning("DBServer: parse_metadata string2: {}".format(md_string2))
    if data[-1]["type"] != "menu_footer":
      logging.warning("DBServer: metadata packet not ending with menu_footer, buffer too small?")
    return md

  def query_track_metadata(self, slot, track_id):
    slot_id = byte2int(packets.PlayerSlot.build(slot))
    query = {
      "transaction_id": self.get_transaction_id(),
      "type": "metadata_request",
      "args": [
        {"type": "int32", "value": self.player_number<<24 | 1<<16 | slot_id<<8 | 1},
        {"type": "int32", "value": track_id}
      ]
    }
    data = packets.DBMessage.build(query)
    logging.debug("DBServer: metadata_request query {}".format(query))
    self.sock.send(data)
    data = self.sock.recv(48)
    reply = packets.DBMessage.parse(data)
    entry_count = reply["args"][1]["value"]
    if entry_count == 0:
      logging.error("DBServer: not metadata for track {} available (0 entries)".format(track_id))
    logging.info("DBServer: metadata request: {} entries available".format(entry_count))

    query = {
      "transaction_id": self.get_transaction_id(),
      "type": "render",
      "args": [
        {"type": "int32", "value": self.player_number<<24 | 1<<16 | slot_id<<8 | 1},
        {"type": "int32", "value": 0}, # entry offset
        {"type": "int32", "value": entry_count}, # entry count
        {"type": "int32", "value": 0},
        {"type": "int32", "value": entry_count}, # entry count again? (on root_menu 2 more than entry_count)
        {"type": "int32", "value": 0}
      ]
    }
    data = packets.DBMessage.build(query)
    logging.debug("DBServer: render query {}".format(query))
    self.sock.send(data)
    data = self.sock.recv(1500)
    try:
      reply = packets.ManyDBMessages.parse(data)
    except (RangeError, FieldError):
      logging.error("DBServer: failed to parse metadata reply, data: {}".format(data))
      return None
    metadata = self.parse_metadata(reply)
    return metadata

  def query_artwork(self, slot, artwork_id):
    slot_id = byte2int(packets.PlayerSlot.build(slot))
    query = {
      "transaction_id": self.get_transaction_id(),
      "type": "artwork_request",
      "args": [
        {"type": "int32", "value": self.player_number<<24 | 8<<16 | slot_id<<8 | 1},
        {"type": "int32", "value": artwork_id}
      ]
    }
    data = packets.DBMessage.build(query)
    logging.debug("DBServer: artwork_request query {}".format(query))
    self.sock.send(data)
    data = self.sock.recv(2000)
    if len(data) == 0:
      logging.error("DBServer: artwork request for id {} failed".format(artwork_id))
      return None
    reply = packets.DBMessage.parse(data)
    if reply["args"][2]["value"] == 0:
      logging.warning("DBServer: not artwork for {}".format(artwork_id))
      return None
    artwork_data = reply["args"][3]["value"]
    logging.info("DBServer: got {} bytes of artwork data".format(len(artwork_data)))
    return artwork_data

  def query_preview_waveform(self, slot, track_id):
    slot_id = byte2int(packets.PlayerSlot.build(slot))
    query = {
      "transaction_id": self.get_transaction_id(),
      "type": "preview_waveform_request",
      "args": [
        {"type": "int32", "value": self.player_number<<24 | 8<<16 | slot_id<<8 | 1},
        {"type": "int32", "value": 4},
        {"type": "int32", "value": track_id},
        {"type": "int32", "value": 0}
      ]
    }
    data = packets.DBMessage.build(query)
    logging.debug("DBServer: preview_waveform_request query {}".format(query))
    self.sock.send(data)
    data = self.sock.recv(2000)
    if len(data) == 0:
      logging.error("DBServer: preview_waveform request for id {} failed".format(track_id))
      return None
    reply = packets.DBMessage.parse(data)
    if reply["args"][2]["value"] == 0:
      logging.warning("DBServer: not preview_waveform for {}".format(track_id))
      return None
    preview_waveform_data = reply["args"][3]["value"]
    logging.info("DBServer: got {} bytes of preview_waveform data".format(len(preview_waveform_data)))
    with open("preview_waveform.bin", "wb") as f:
      f.write(preview_waveform_data)
    return preview_waveform_data

  def query_waveform(self, slot, track_id, player_number=0):
    slot_id = byte2int(packets.PlayerSlot.build(slot))
    query = {
      "transaction_id": self.get_transaction_id(),
      "type": "waveform_request",
      "args": [
        {"type": "int32", "value": self.player_number<<24 | 1<<16 | slot_id<<8 | 1},
        {"type": "int32", "value": track_id},
        {"type": "int32", "value": 0}
      ]
    }
    data = packets.DBMessage.build(query)
    logging.debug("DBServer: waveform_request query {}".format(query))
    self.sock.send(data)
    recv_tries = 0
    data = b""
    while recv_tries < 30:
      data += self.sock.recv(4096)
      try:
        reply = packets.DBMessage.parse(data)
      except RangeError as e:
        logging.debug("Received {} bytes but parsing failed, trying to receive more".format(len(data)))
        reply = None
      else:
        break
    if reply is None and recv_tries == 30:
      logging.error("Failed to receive waveform")
      return None
    if reply["args"][2]["value"] == 0:
      logging.warning("DBServer: no waveform for {}".format(track_id))
      return None
    waveform_data = reply["args"][3]["value"]
    logging.debug("DBServer: got {} bytes of waveform data".format(len(waveform_data)))
    return waveform_data

  def connectDb(self, player_number):
    if self.sock is not None:
      logging.warning("DBClient: db socket still connected, closing and resetting")
      self.closeDb()
    ip_port = self.get_server_port(player_number)
    if ip_port is None:
      logging.error("DBClient: failed to get remote port of player {}".format(player_number))
      return
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
    self.sock.connect(ip_port)
    self.transaction_id = 1 # on successful connect, reset transaction_id

    # send connection initialization packet
    self.send_initial_packet()

    # first query
    self.send_setup_packet(player_number)

  def closeDb(self):
    if self.sock:
      self.sock.close()
    self.sock = None

  # called from outside, enqueues request
  def get_track_metadata(self, player_number, slot, track_id, callback=None):
    if player_number == 0 or player_number > 4 or track_id == 0:
      logging.warning("DBServer: invalid get_track_metadata parameters")
      return
    if (player_number, slot, track_id) in self.metadata_store:
      logging.info("DBServer: metadata of player {} slot {} track_id {} already known".format(
        player_number, slot, track_id))
      if callback:
        callback(player_number, slot, track_id, self.metadata_store[player_number, slot, track_id])
    else:
      self.queue.put(("metadata", player_number, slot, track_id, callback))

  # called from inside
  def _get_track_metadata(self, player_number, slot, track_id, callback):
    self.connectDb(player_number)
    logging.info("DBServer: requesting metadata from player {} slot {} id {}".format(player_number, slot, track_id))
    md = self.query_track_metadata(slot, track_id)
    if md:
      logging.info("DBServer: got metadata of {} - {}".format(md["artist"], md["title"]))
      self.metadata_store[player_number, slot, track_id] = md
      preview_waveform = self.query_preview_waveform(slot, track_id)
      if "artwork_id" in md and md["artwork_id"] != 0:
        artwork = self.query_artwork(slot, md["artwork_id"])
        if artwork:
          self.artwork_store[player_number,slot,track_id] = artwork
      # FIXME do not call from here, client should do it if big waveform is required
      self._get_waveform(player_number, slot, track_id, None)
      if self.metadata_change_callback:
        self.metadata_change_callback(player_number, md)
      if callback:
        callback(player_number, slot, track_id, md)
    self.closeDb()

  # called from outside, enqueues request
  def get_waveform(self, player_number, slot, track_id, callback=None):
    if player_number == 0 or player_number > 4 or track_id == 0:
      logging.warning("DBServer: invalid get_waveform parameters")
      return
    if (player_number, slot, track_id) in self.waveform_store:
      logging.info("DBServer: preview waveform of player {} slot {} track_id {} already known".format(
        player_number, slot, track_id))
      if callback:
        callback(player_number, slot, track_id, self.waveform_store[player_number, slot, track_id])
    else:
      self.queue.put(("waveform", player_number, slot, track_id, callback))

  # called from inside
  def _get_waveform(self, player_number, slot, track_id, callback):
    self.connectDb(player_number)
    logging.info("DBServer: requesting waveform from player {} slot {} id {}".format(player_number, slot, track_id))
    waveform = self.query_waveform(slot, track_id)
    if waveform:
      logging.info("DBServer: got waveform from player {} slot {} id {}".format(player_number, slot, track_id))
      self.waveform_store[player_number, slot, track_id] = waveform
      with open("waveform.bin", "wb") as f:
        f.write(waveform)
      if callback:
        callback(player_number, slot, track_id, waveform)
    self.closeDb()

  def run(self):
    logging.debug("DBClient starting")
    while self.keep_running:
      try:
        item = self.queue.get(timeout=1)
      except Empty:
        continue
      client = self.cl.getClient(item[1])
      if not client or client.play_state in ["no_track", "loading_track", "cannot_play_track", "emergency"]:
        logging.debug("DBClient: delaying metadata request due to play state: {}".format(client.play_state))
        self.queue.put(item)
        time.sleep(1)
        continue
      logging.debug("DBClient request player {} slot {} track {}".format(*item[1:4]))
      if item[0] == "metadata":
        self._get_track_metadata(*item[1:])
      elif item[0] == "waveform":
        self._get_waveform(*item[1:])
      self.queue.task_done()
    logging.debug("DBClient shutting down")
