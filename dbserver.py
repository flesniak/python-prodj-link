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
    self.own_player_number = 0 # db queries seem to work if we submit player number 0 everywhere
    self.remote_ports = {} # dict {player_number: (ip, port)}
    self.socks = {} # dict of player_number: (sock, ttl, transaction_id)
    self.queue = Queue()

    self.metadata_store = {} # map of player_number,slot,track_id: metadata
    self.artwork_store = {} # map of player_number,slot,artwork_id: artwork_data
    self.waveform_store = {} # map of player_number,slot,artwork_id: waveform_data
    self.preview_waveform_store = {} # map of player_number,slot,artwork_id: preview_waveform_data
    self.beatgrid_store = {} # map of player_number,slot,artwork_id: beatgrid_data

  def start(self):
    self.keep_running = True
    super().start()

  def stop(self):
    self.keep_running = False
    self.join()

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

  def query_metadata(self, player_number, slot, track_id):
    sock = self.getSocket(player_number)
    slot_id = byte2int(packets.PlayerSlot.build(slot))
    query = {
      "transaction_id": self.getTransactionId(player_number),
      "type": "metadata_request",
      "args": [
        {"type": "int32", "value": self.own_player_number<<24 | 1<<16 | slot_id<<8 | 1},
        {"type": "int32", "value": track_id}
      ]
    }
    data = packets.DBMessage.build(query)
    logging.debug("DBServer: metadata_request query {}".format(query))
    sock.send(data)
    data = sock.recv(48)
    reply = packets.DBMessage.parse(data)
    entry_count = reply["args"][1]["value"]
    if entry_count == 0:
      logging.error("DBServer: not metadata for track {} available (0 entries)".format(track_id))
    logging.debug("DBServer: metadata request: {} entries available".format(entry_count))

    query = {
      "transaction_id": self.getTransactionId(player_number),
      "type": "render",
      "args": [
        {"type": "int32", "value": self.own_player_number<<24 | 1<<16 | slot_id<<8 | 1},
        {"type": "int32", "value": 0}, # entry offset
        {"type": "int32", "value": entry_count}, # entry count
        {"type": "int32", "value": 0},
        {"type": "int32", "value": entry_count}, # entry count again? (on root_menu 2 more than entry_count)
        {"type": "int32", "value": 0}
      ]
    }
    data = packets.DBMessage.build(query)
    logging.debug("DBServer: render query {}".format(query))
    sock.send(data)
    data = sock.recv(1500)
    try:
      reply = packets.ManyDBMessages.parse(data)
    except (RangeError, FieldError):
      logging.error("DBServer: failed to parse metadata reply, data: {}".format(data))
      return None
    metadata = self.parse_metadata(reply)
    return metadata

  def query_blob(self, player_number, slot, id, request_type, location=8):
    sock = self.getSocket(player_number)
    slot_id = byte2int(packets.PlayerSlot.build(slot))
    query = {
      "transaction_id": self.getTransactionId(player_number),
      "type": request_type,
      "args": [
        {"type": "int32", "value": self.own_player_number<<24 | location<<16 | slot_id<<8 | 1},
        {"type": "int32", "value": track_id}
      ]
    }
    # request-specifig argument agumentations
    if request_type == "waveform_request":
      query["args"] += [{"type": "int32", "value": 0}]
    elif request_type == "preview_waveform":
      query["args"].insert(1, {"type": "int32", "value": 4})
      query["args"] += [{"type": "int32", "value": 0}]
    logging.debug("DBServer: {} query {}".format(request_type, query))
    data = packets.DBMessage.build(query)
    sock.send(data)
    recv_tries = 0
    data = b""
    while recv_tries < 30:
      data += sock.recv(4096)
      try:
        reply = packets.DBMessage.parse(data)
      except RangeError as e:
        logging.debug("DBServer: Received %d bytes but parsing failed, trying to receive more", len(data))
        reply = None
      else:
        break
    if reply is None:
      logging.error("Failed to receive %s blob (%d tries)", request_type, recv_tries)
      return None
    if reply["args"][2]["value"] == 0:
      logging.warning("DBServer: no {} blob for track {}".format(request_type, track_id))
      return None
    blob = reply["args"][3]["value"]
    logging.debug("DBServer: got {} bytes of blob data".format(len(blob)))
    return blob

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

  def send_initial_packet(self, sock):
    init_packet = packets.DBFieldFixed("int32")
    sock.send(init_packet.build(1))
    data = sock.recv(16)
    try:
      reply = init_packet.parse(data)
      logging.debug("DBServer: initial packet reply %d", reply)
    except:
      logging.warning("DBServer: failed to parse initial packet reply, ignoring")

  def send_setup_packet(self, sock, player_number):
    query = {
      "transaction_id": 0xfffffffe,
      "type": "setup",
      "args": [{"type": "int32", "value": self.own_player_number}]
    }
    sock.send(packets.DBMessage.build(query))
    data = sock.recv(48)
    if len(data) == 0:
      logging.error("Failed to connect to player {}".format(player_number))
      return
    reply = packets.DBMessage.parse(data)
    logging.info("DBServer: connected to player {}".format(reply["args"][1]["value"]))

  def getTransactionId(self, player_number):
    sock_info = self.socks[player_number]
    self.socks[player_number] = (sock_info[0], sock_info[1], sock_info[2]+1)
    return sock_info[2]

  def resetSocketTtl(self, player_number):
    sock = self.socks[player_number]
    self.socks[player_number] = (sock[0], 30, sock[2])

  def gc(self):
    for player_number, sock in self.socks.items():
      if sock[1] <= 0:
        logging.info("Closing DB socket of player %d", player_number)
        self.closeSocket()
      else:
        self.socks[player_number] = (sock[0], sock[1]-1, sock[2])

  def getSocket(self, player_number):
    if player_number in self.socks:
      self.resetSocketTtl(player_number)
      return self.socks[player_number][0]

    ip_port = self.get_server_port(player_number)
    if ip_port is None:
      logging.error("DBClient: failed to get remote port of player {}".format(player_number))
      return

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
    sock.connect(ip_port)
    self.socks[player_number] = (sock, 30, 1) # socket, ttl, transaction_id

    # send connection initialization packet
    self.send_initial_packet(sock)
    # first query
    self.send_setup_packet(sock, player_number)

    return sock

  def closeSocket(self, player_number):
    if player_number in self.socks:
      self.socks[player_number].close()
      del self.socks[player_number]
    else:
      logging.warning("Requested to delete unexistant socket for player %d", player_number)

  # called from outside, enqueues request
  def get_metadata(self, player_number, slot, track_id, callback=None):
    self._enqueue_request("metadata", self.metadata_store, player_number, slot, track_id, callback)

  def get_artwork(self, player_number, slot, artwork_id, callback=None):
    self._enqueue_request("artwork", self.waveform_store, player_number, slot, artwork_id, callback)

  def get_waveform(self, player_number, slot, track_id, callback=None):
    self._enqueue_request("waveform", self.waveform_store, player_number, slot, track_id, callback)

  def get_preview_waveform(self, player_number, slot, track_id, callback=None):
    self._enqueue_request("preview_waveform", self.waveform_store, player_number, slot, track_id, callback)

  def get_beatgrid(self, player_number, slot, track_id, callback=None):
    self._enqueue_request("beatgrid", self.waveform_store, player_number, slot, track_id, callback)

  def _enqueue_request(self, request, store, player_number, slot, item_id, callback):
    if player_number == 0 or player_number > 4 or item_id == 0:
      logging.warning("DBServer: invalid %s request parameters", request)
      return
    logging.debug("DBServer: enqueueing %s request for player %d slot %s item_id %d",
      request, player_number, slot, item_id)
    self.queue.put((request, store, player_number, slot, item_id, callback))

  def _handle_request(self, request, store, player_number, slot, item_id, callback):
    if (player_number, slot, item_id) in store:
      logging.debug("DBServer: %s request for player %d slot %s item_id %d already known",
        request, player_number, slot, item_id)
      if callback:
        callback(request, player_number, slot, item_id, store[player_number, slot, item_id])
      return
    logging.debug("DBServer: handling %s request for player %d slot %s id %d",
      request, player_number, slot, item_id)
    if request == "metadata":
      reply = self.query_metadata(player_number, slot, item_id)
    elif request == "artwork":
      reply = self.query_blob(player_number, slot, item_id, "artwork_request")
    elif request == "waveform":
      reply = self.query_blob(player_number, slot, item_id, "waveform_request", 1)
    elif request == "preview_waveform":
      reply = self.query_blob(player_number, slot, item_id, "preview_waveform_request")
    elif request == "beatgrid":
      reply = self.query_blob(player_number, slot, item_id, "beatgrid_request")
    else:
      logging.error("DBServer: invalid request type %s", request)
      return
    store[player_number, slot, item_id] = reply
    if callback:
      callback(request, player_number, slot, item_id, reply)

  def run(self):
    logging.debug("DBClient starting")
    while self.keep_running:
      try:
        request = self.queue.get(timeout=1)
      except Empty:
        self.gc()
        continue
      client = self.cl.getClient(request[2])
      if not client or client.play_state in ["no_track", "loading_track", "cannot_play_track", "emergency"]:
        if client:
          logging.debug("DBClient: delaying %s request due to play state: %s", request[0], client.play_state)
        else:
          logging.warning("DBClient: player %s not found in clientlist", request[2])
        self.queue.put(request)
        time.sleep(1)
        continue
      self._handle_request(*request)
      self.queue.task_done()
    logging.debug("DBClient shutting down")
