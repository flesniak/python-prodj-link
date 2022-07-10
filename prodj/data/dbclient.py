import socket
import logging
from select import select
from construct import MappingError, StreamError, RangeError, byte2int

from prodj.network import packets
from prodj.data import dataprovider
from prodj.data.exceptions import FatalQueryError, TemporaryQueryError
from prodj.pdblib.usbanlz import AnlzTag

metadata_type = {
  0x0000: "mount_path",
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
  0x0010: "bitrate",
  0x0011: "year",
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
  0x002a: "play_count",
  0x002e: "date_added",
  0x002f: "unknown1",
  0x0080: "root_genre",
  0x0081: "root_artist",
  0x0082: "root_album",
  0x0083: "root_track",
  0x0084: "root_playlist",
  0x0085: "root_bpm",
  0x0086: "root_rating",
  0x0087: "root_time",
  0x0088: "root_remixer",
  0x0089: "root_label",
  0x008a: "root_original_artist",
  0x008b: "root_key",
  0x008e: "root_color",
  0x0090: "root_folder",
  0x0091: "root_search",
  0x0092: "root_time",
  0x0093: "root_bitrate",
  0x0094: "root_filename",
  0x0095: "root_history",
  0x0098: "root_hot_cue_bank",
  0x00a0: "all",
  0x0204: "title_and_album",
  0x0604: "title_and_genre",
  0x0704: "title_and_artist",
  0x0a04: "title_and_rating",
  0x0b04: "title_and_duration",
  0x0d04: "title_and_bpm",
  0x0e04: "title_and_label",
  0x0f04: "title_and_key",
  0x1004: "title_and_bitrate",
  0x1a04: "title_and_color",
  0x2304: "title_and_comment",
  0x2804: "title_and_original_artist",
  0x2904: "title_and_remixer",
  0x2a04: "title_and_play_count",
  0x2e04: "title_and_date_added"
}

# columns depend on sort mode
sort_types = {
  "default": 0x00, # title | <depending on rekordbox configuration>
  "title": 0x01, # title | artist
  "artist": 0x02, # title | artist
  "album": 0x03, # title | album (+id)
  "bpm": 0x04, # title | bpm
  "rating": 0x05, # title | rating
  "genre": 0x06, # title | genre (+id)
  "comment": 0x07, # title | comment
  "duration": 0x08, # title | duration
  "remixer": 0x09, # title | remixer (+id)
  "label": 0x0a, # title | label (+id) # TODO: label is duplicate
  "original_artist": 0x0b, # title | original artist (+id)
  "key": 0x0c, # title | key (+id)
  "bitrate": 0x0d, # title | bitrate
  "play_count": 0x10, # title | play_count
  "label": 0x11, # title | label (+id) # TODO: label is duplicate
}

def sockrcv(sock, length, timeout=1):
  rdy = select([sock], [], [], timeout)
  if rdy[0]:
    return sock.recv(length)
  else:
    logging.warning("socket receive timeout")
    return b""

class DBClient:
  def __init__(self, prodj):
    self.prodj = prodj
    self.remote_ports = {} # dict {player_number: (ip, port)}
    self.socks = {} # dict of player_number: (sock, ttl, transaction_id)

    # db queries seem to work if we submit player number 0 everywhere (NOTE: this seems to work only if less than 4 players are on the network)
    # however, this messes up rendering on the players sometimes (i.e. when querying metadata and player has browser opened)
    # alternatively, we can use a player number from 1 to 4 without rendering issues, but then only max. 3 real players can be used
    self.own_player_number = 0
    self.parse_error_count = 40
    self.receive_timeout_count = 3

  def parse_metadata_payload(self, payload):
    entry = {}

    # we may test payload[n]["type"] here to verify the argument types, but it
    # seems constant on every db query, so let's just assume this fixed mapping
    entry_id1 = payload[0]["value"]
    entry_id2 = payload[1]["value"]
    entry_string1 = payload[3]["value"]
    entry_string2 = payload[5]["value"]
    entry_type = payload[6]["value"]
    entry_id3 = payload[8]["value"]
    if entry_type not in metadata_type:
      logging.warning("metadata type %d unknown", entry_type)
      logging.debug("packet contents: %s", str(payload))
      return None
    entry_label = metadata_type[entry_type]

    if entry_label in ["duration", "rating", "disc", "play_count", "bitrate", "year"]:
      entry[entry_label] = entry_id2 # plain numbers
    elif entry_label == "bpm":
      entry[entry_label] = entry_id2/100
    elif entry_label == "title":
      entry[entry_label] = entry_string1
      entry["artwork_id"] = entry_id3
      entry["track_id"] = entry_id2
      entry["artist_id"] = entry_id1
    elif entry_label[:5] == "color":
      entry["color"] = entry_label[6:]
      entry["color_text"] = entry_string1
    elif entry_label in ["artist", "album", "genre", "original_artist", "remixer", "key", "label", "folder"]:
      entry[entry_label] = entry_string1
      entry[entry_label+"_id"] = entry_id2
    elif entry_label == "playlist": # merge with above? entry_id1 always seems to be some kind of parent id
      entry["playlist"] = entry_string1
      entry["playlist_id"] = entry_id2
      entry["parent_id"] = entry_id1
    elif entry_label in ["date_added", "comment", "mount_path", "all"]:
      entry[entry_label] = entry_string1
    elif entry_label == "unknown1":
      logging.debug("parse_metadata unknown1 id1 %d id2 %d", entry_id1, entry_id2)
      entry["unknown1"] = entry_id2 # entry_id1 seems to be 0 everytime here
    elif entry_label[:5] == "root_":
      entry["name"] = entry_string1
      entry["menu_id"] = entry_id2
    elif entry_label[:10] == "title_and_":
      entry_label1 = entry_label[:5] # "title"
      entry_label2 = entry_label[10:]
      entry[entry_label1] = entry_string1
      entry["artwork_id"] = entry_id3
      entry["track_id"] = entry_id2
      entry["artist_id"] = entry_id1
      entry_type2 = next((k for k,v in metadata_type.items() if v==entry_label2), None)
      if entry_type2 is None:
        logging.warning("second column %s of %s not parseable", entry_label2, entry_type)
      else:
        entry2 = self.parse_metadata_payload([
          {"value": entry_id1}, {"value": entry_id1}, None, # duplicate entry1, as entry2 unused and swapped
          {"value": entry_string2}, None,
          {"value": ""}, {"value": entry_type2}, None,
          {"value": entry_id3}])
        if entry2 is not None:
          entry = {**entry, **entry2}
    else:
      logging.warning("unhandled metadata type %s", entry_label)
      return None

    #logging.debug("parse_metadata %s", str(entry))
    return entry

  def parse_list(self, data):
    entries = [] # for list data
    for packet in data:
      # check packet types
      if packet["type"] == "menu_header":
        logging.debug("parse_list menu_header")
        continue
      if packet["type"] == "menu_footer":
        logging.debug("parse_list menu_footer")
        break
      if packet["type"] != "menu_item":
        logging.warning("parse_list item not menu_item: {}".format(packet))
        continue

      # extract metadata from packet
      entry = self.parse_metadata_payload(packet["args"])
      if entry is None:
        continue
      entries += [entry]

    if data[-1]["type"] != "menu_footer":
      logging.warning("list entries not ending with menu_footer")
    return entries

  def parse_metadata(self, data):
    md = {}
    for packet in data:
      # check packet types
      if packet["type"] == "menu_header":
        logging.debug("parse_metadata menu_header")
        continue
      if packet["type"] == "menu_footer":
        logging.debug("parse_metadata menu_footer")
        break
      if packet["type"] != "menu_item":
        logging.warning("parse_metadata item not menu_item: {}".format(packet))
        continue

      # extract metadata from packet
      entry = self.parse_metadata_payload(packet["args"])
      if entry is None:
        continue
      md = {**md, **entry}

    if data[-1]["type"] != "menu_footer":
      logging.warning("metadata packet not ending with menu_footer, buffer too small?")
    return md

  def receive_dbmessage(self, sock):
    parse_errors = 0
    receive_timeouts = 0
    data = b""
    while parse_errors < self.parse_error_count and receive_timeouts < self.receive_timeout_count:
      new_data = sockrcv(sock, 4096, 1)
      if len(new_data) == 0:
        receive_timeouts += 1
        continue
      data += new_data
      try:
        return packets.DBMessage.parse(data)
      except (StreamError, RangeError, TypeError) as e:
        logging.debug("Received %d bytes but parsing failed, trying to receive more", len(data))
        parse_errors += 1
    raise TemporaryQueryError("Failed to receive dbmessage after {} tries and {} timeouts".format(parse_errors, receive_timeouts))

  def query_list(self, player_number, slot, sort_mode, id_list, request_type):
    sock = self.getSocket(player_number)
    slot_id = byte2int(packets.PlayerSlot.build(slot)) if slot is not None else 0
    if sort_mode is None:
      sort_id = 0 # 0 for root_menu, playlist folders
    else:
      if sort_mode not in sort_types:
        logging.warning("unknown sort mode %s", sort_mode)
        return None
      sort_id = sort_types[sort_mode]
    query = {
      "transaction_id": self.getTransactionId(player_number),
      "type": request_type,
      "args": [
        {"type": "int32", "value": self.own_player_number<<24 | 1<<16 | slot_id<<8 | 1}
      ]
    }
    # request-specific argument agumentations
    if request_type == "root_menu_request":
      query["args"].append({"type": "int32", "value": 0})
      query["args"].append({"type": "int32", "value": 0xffffff})
    elif request_type in ["metadata_request", "track_data_request", "track_info_request"]:
      query["args"].append({"type": "int32", "value": id_list[0]})
    elif request_type == "playlist_request":
      query["args"].append({"type": "int32", "value": sort_id})
      query["args"].append({"type": "int32", "value": id_list[1] if id_list[1]>0 else id_list[0]})
      query["args"].append({"type": "int32", "value": 0 if id_list[1]>0 else 1}) # 1 -> get folder, 0 -> get playlist
    else: # for any (non-playlist) "*_by_*_request"
      query["args"].append({"type": "int32", "value": sort_id})
      for item_id in id_list:
        if item_id == 0: # we use id 0 for "ALL", dbserver expects all bits set
          item_id = 0xffffffff
        query["args"].append({"type": "int32", "value": item_id})
    data = packets.DBMessage.build(query)
    logging.debug("query_list request: {}".format(query))
    self.socksnd(sock, data)

    try:
      reply = self.receive_dbmessage(sock)
    except (RangeError, MappingError, KeyError) as e:
      logging.error("parsing %s query failed on player %d failed: %s", query["type"], player_number, str(e))
      return None
    if reply is None or reply["type"] != "success":
      logging.error("%s failed on player %d (got %s)", query["type"], player_number, "NONE" if reply is None else reply["type"])
      return None
    entry_count = reply["args"][1]["value"]
    if entry_count == 0 or entry_count == 0xffffffff:
      logging.warning("%s empty (request returned %d entries)", request_type, entry_count)
      return None
    logging.debug("query_list %s: %d entries available", request_type, entry_count)

    # i could successfully receive hundreds of entries at once on xdj 1000
    # thus i do not fragment render requests here
    query = {
      "transaction_id": self.getTransactionId(player_number),
      "type": "render",
      "args": [
        {"type": "int32", "value": self.own_player_number<<24 | 1<<16 | slot_id<<8 | 1},
        {"type": "int32", "value": 0}, # entry offset
        {"type": "int32", "value": entry_count}, # entry count
        {"type": "int32", "value": 0},
        {"type": "int32", "value": entry_count}, # entry count
        {"type": "int32", "value": 0}
      ]
    }
    data = packets.DBMessage.build(query)
    logging.debug("render query {}".format(query))
    self.socksnd(sock, data)
    parse_errors = 0
    receive_timeouts = 0
    data = b""
    while parse_errors < self.parse_error_count and receive_timeouts < self.receive_timeout_count:
      new_data = sockrcv(sock, 4096, 1)
      if len(new_data) == 0:
        receive_timeouts += 1
        continue
      data += new_data
      try:
        reply = packets.ManyDBMessages.parse(data)
      except (RangeError, MappingError, KeyError, TypeError) as e:
        logging.debug("failed to parse %s render reply (%d bytes), trying to receive more", request_type, len(data))
        parse_errors += 1
      else:
        if reply[-1]["type"] != "menu_footer":
          logging.debug("%s rendering without menu_footer @ %d bytes, trying to receive more", request_type, len(data))
          parse_errors += 1
        else:
          break
    if parse_errors >= self.parse_error_count or receive_timeouts >= self.receive_timeout_count:
      raise FatalQueryError("Failed to receive {} render reply after {} timeouts, {} parse errors".format(request_type, receive_timeouts, parse_errors))

    # basically, parse_metadata returns a single dict whereas parse_list returns a list of dicts
    if request_type in ["metadata_request", "mount_info_request", "track_info_request"]:
      parsed = self.parse_metadata(reply)
    else:
      parsed = self.parse_list(reply)
    return parsed

  def query_blob(self, player_number, slot, item_id, request_type, location=8):
    sock = self.getSocket(player_number)
    slot_id = byte2int(packets.PlayerSlot.build(slot))
    query = {
      "transaction_id": self.getTransactionId(player_number),
      "type": request_type,
      "args": [
        {"type": "int32", "value": self.own_player_number<<24 | location<<16 | slot_id<<8 | 1},
        {"type": "int32", "value": item_id}
      ]
    }
    # request-specific argument agumentations
    if request_type == "waveform_request":
      query["args"].append({"type": "int32", "value": 0})
    elif request_type == "preview_waveform_request":
      query["args"].insert(1, {"type": "int32", "value": 4})
      query["args"].append({"type": "int32", "value": 0})
    if request_type == "color_waveform_request":
      query["type"] = "nxs2_ext_request"
      query["args"].append({"type": "int32", "value": packets.Nxs2RequestIds["5VWP"]})
      query["args"].append({"type": "int32", "value": packets.Nxs2RequestIds["TXE"]})
    elif request_type == "color_preview_waveform_request":
      query["type"] = "nxs2_ext_request"
      query["args"].append({"type": "int32", "value": packets.Nxs2RequestIds["4VWP"]})
      query["args"].append({"type": "int32", "value": packets.Nxs2RequestIds["TXE"]})
    logging.debug("{} query {}".format(request_type, query))
    data = packets.DBMessage.build(query)
    self.socksnd(sock, data)
    try:
      reply = self.receive_dbmessage(sock)
    except (RangeError, MappingError, KeyError, TypeError) as e:
      logging.error("%s query parse error: %s", request_type, str(e))
      return None
    if reply is None:
      return None
    if reply["type"] == "invalid_request" or len(reply["args"])<3 or reply["args"][2]["value"] == 0:
      logging.error("%s blob query failed on player %d (got %s)", query["type"], player_number, reply["type"])
      return None
    blob = reply["args"][3]["value"]
    logging.debug("got %d bytes of blob data", len(blob))
    return blob

  def get_server_port(self, player_number):
    if player_number not in self.remote_ports:
      client = self.prodj.cl.getClient(player_number)
      if client is None:
        raise TemporaryQueryError("failed to get remote port, player {} unknown".format(player_number))
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      sock.connect((client.ip_addr, packets.DBServerQueryPort))
      sock.send(packets.DBServerQuery.build({}))
      data = sockrcv(sock, 2)
      sock.close()
      port = packets.DBServerReply.parse(data)
      self.remote_ports[player_number] = (client.ip_addr, port)
      logging.info("DBClient port of player {}: {}".format(player_number, port))
    return self.remote_ports[player_number]

  def send_initial_packet(self, sock):
    init_packet = packets.DBFieldFixed("int32")
    sock.send(init_packet.build(1))
    data = sockrcv(sock, 16)
    try:
      reply = init_packet.parse(data)
      logging.debug("initial packet reply %d", reply)
    except:
      logging.warning("failed to parse initial packet reply, ignoring")

  def send_setup_packet(self, sock, player_number):
    query = {
      "transaction_id": 0xfffffffe,
      "type": "setup",
      "args": [{"type": "int32", "value": self.own_player_number}]
    }
    sock.send(packets.DBMessage.build(query))
    data = sockrcv(sock, 48)
    if len(data) == 0:
      raise TemporaryQueryError("Failed to connect to player {}".format(player_number))
    reply = packets.DBMessage.parse(data)
    logging.info("connected to player {}".format(reply["args"][1]["value"]))

  def getTransactionId(self, player_number):
    sock_info = self.socks[player_number]
    self.socks[player_number] = (sock_info[0], sock_info[1], sock_info[2]+1)
    return sock_info[2]

  def resetSocketTtl(self, player_number):
    sock = self.socks[player_number]
    self.socks[player_number] = (sock[0], 30, sock[2])

  def gc(self):
    for player_number in list(self.socks):
      sock = self.socks[player_number]
      if sock[1] <= 0:
        logging.info("Closing DB socket of player %d", player_number)
        self.closeSocket(player_number)
      else:
        self.socks[player_number] = (sock[0], sock[1]-1, sock[2])

  def getSocket(self, player_number):
    if player_number in self.socks:
      self.resetSocketTtl(player_number)
      return self.socks[player_number][0]

    ip_port = self.get_server_port(player_number)

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
      self.socks[player_number][0].close()
      del self.socks[player_number]
    else:
      logging.warning("Requested to delete unexistant socket for player %d", player_number)

  def socksnd(self, sock, data):
    try:
      sock.send(data)
    except BrokenPipeError as e:
      player_number = next((n for n, d in self.socks.items() if d[0] == sock), None)
      if player_number is None:
        raise FatalQueryError("socksnd failed with unknown sock")
      else:
        self.closeSocket(player_number)
        raise TemporaryQueryError("Connection to player {} lost".format(player_number))

  def ensure_request_possible(self, request, player_number):
    client = self.prodj.cl.getClient(player_number)
    if client is None:
      raise TemporaryQueryError("player {} not found in clientlist".format(player_number))
    critical_requests = ["metadata_request", "artwork_request", "preview_waveform_request", "beatgrid_request", "waveform_request"]
    critical_play_states = ["no_track", "loading_track", "cannot_play_track", "emergency"]
    if request in critical_requests and client.play_state in critical_play_states:
      raise TemporaryQueryError("DataProvider: delaying %s request due to play state: %s".format(request, client.play_state))

  def handle_request(self, request, params):
    self.ensure_request_possible(request, params[0])
    logging.debug("handling %s request params %s", request, str(params))
    if request == "metadata":
      return self.query_list(*params[:2], None, [params[2]], "metadata_request")
    elif request == "root_menu":
      return self.query_list(*params, None, [], "root_menu_request")
    elif request == "title":
      return self.query_list(*params, [], "title_request")
    elif request == "title_by_album":
      return self.query_list(*params, "title_by_album_request")
    elif request == "title_by_artist_album":
      return self.query_list(*params, "title_by_artist_album_request")
    elif request == "title_by_genre_artist_album":
      return self.query_list(*params, "title_by_genre_artist_album_request")
    elif request == "artist":
      return self.query_list(*params, None, [], "artist_request")
    elif request == "artist_by_genre":
      return self.query_list(*params[:2], None, params[2], "artist_by_genre_request")
    elif request == "album":
      return self.query_list(*params, None, [], "album_request")
    elif request == "album_by_artist":
      return self.query_list(*params[:2], None, params[2], "album_by_artist_request")
    elif request == "album_by_genre_artist":
      return self.query_list(*params[:2], None, params[2], "album_by_genre_artist_request")
    elif request == "genre":
      return self.query_list(*params, None, [], "genre_request")
    elif request == "playlist_folder":
      return self.query_list(*params[:2], None, [params[2], 0], "playlist_request")
    elif request == "playlist":
      return self.query_list(*params[:3], [0, params[3]], "playlist_request")
    elif request == "artwork":
      return self.query_blob(*params, "artwork_request")
    elif request == "waveform":
      waveform = self.query_blob(*params, "waveform_request", 1)
      return None if waveform is None else waveform[20:]
    elif request == "preview_waveform":
      return self.query_blob(*params, "preview_waveform_request")
    elif request == "color_waveform":
      blob = self.query_blob(*params, "color_waveform_request", 1)
      return None if blob is None else AnlzTag.parse(blob[4:]).content.entries
    elif request == "color_preview_waveform":
      blob = self.query_blob(*params, "color_preview_waveform_request")
      return None if blob is None else AnlzTag.parse(blob[4:]).content.entries
    elif request == "beatgrid":
      reply = self.query_blob(*params, "beatgrid_request")
      if reply is None:
        return None
      try: # pre-parse beatgrid data (like metadata) for easier access
        return packets.Beatgrid.parse(reply)["beats"]
      except (RangeError, FieldError) as e:
        raise FatalQueryError("failed to parse beatgrid data: {}".format(e))
    elif request == "mount_info":
      return self.query_list(*params[:2], None, [params[2]], "mount_info_request")
    elif request == "track_info":
      return self.query_list(*params[:2], None, [params[2]], "track_info_request")
    else:
      raise FatalQueryError("invalid request type {}".format(request))
