from threading import Event, Thread
from ipaddress import IPv4Network
from construct import byte2int
import logging
import traceback

from prodj.network import packets

class Vcdj(Thread):
  def __init__(self, prodj):
    super().__init__()
    self.prodj = prodj
    self.player_number = 5
    self.model = "Virtual CDJ"
    self.packet_interval = 1.5
    self.event = Event()
    self.ip_addr = ""
    self.mac_addr = ""
    self.broadcast_addr = ""

  def start(self):
    self.event.clear()
    super().start()

  def stop(self):
    self.event.set()

  def run(self):
    logging.info("Starting virtual cdj with player number {}".format(self.player_number))
    try:
      while not self.event.wait(self.packet_interval):
        self.send_keepalive_packet()
    except Exception as e:
      logging.critical("Exception in vcdj.run: "+str(e)+"\n"+traceback.format_exc())

  def set_interface_data(self, ip, netmask, mac):
    self.ip_addr = ip
    self.mac_addr = mac
    n = IPv4Network(ip+"/"+netmask, strict=False)
    self.broadcast_addr = str(n.broadcast_address)

  def send_keepalive_packet(self):
    if len(self.ip_addr) == 0 or len(self.mac_addr) == 0:
      return
    data = {
      "type": "type_status",
      "subtype": "stype_status",
      "model": self.model,
      "content": {
        "player_number": self.player_number,
        "ip_addr": self.ip_addr,
        "mac_addr": self.mac_addr
      }
    }
    #logging.debug("send keepalive data: %s", str(data))
    raw = packets.KeepAlivePacket.build(data)
    self.prodj.keepalive_sock.sendto(raw, (self.broadcast_addr, self.prodj.keepalive_port))

  def query_link_info(self, player_number, slot):
    cl = self.prodj.cl.getClient(player_number)
    if cl is None:
      logging.warning("Failed to get player %d", player_number)
      return
    slot_id = byte2int(packets.PlayerSlot.build(slot))
    cmd = {
      "type": "link_query",
      "model": self.model,
      "player_number": self.player_number,
      "extra": {
        "source_ip": self.ip_addr
      },
      "content": {
        "remote_player_number": player_number,
        "slot": slot_id
      }
    }
    data = packets.StatusPacket.build(cmd)
    logging.debug("query link info to %s struct %s", cl.ip_addr, str(cmd))
    self.prodj.status_sock.sendto(data, (cl.ip_addr, self.prodj.status_port))

  def command_load_track(self, player_number, load_player_number, load_slot, load_track_id):
    cl = self.prodj.cl.getClient(player_number)
    if cl is None:
      logging.warning("Failed to get player %d", player_number)
      return
    load_slot_id = byte2int(packets.PlayerSlot.build(load_slot))
    cmd = {
      "type": "load_cmd",
      "model": self.model,
      "player_number": self.player_number, # our player number -> we receive confirmation packet
      "extra": None,
      "content": {
        "load_player_number": load_player_number,
        "load_slot": load_slot_id,
        "load_track_id": load_track_id
      }
    }
    data = packets.StatusPacket.build(cmd)
    logging.debug("send load packet to %s struct %s", cl.ip_addr, str(cmd))
    self.prodj.status_sock.sendto(data, (cl.ip_addr, self.prodj.status_port))

  # if start is True, start the player, otherwise stop the player
  def command_fader_start_single(self, player_number, start=True):
    player_commands = ["ignore"]*4
    player_commands[player_number-1] = "start" if start is True else "stop"
    self.command_fader_start(player_commands)

  # player_commands is an array of size 4 containing "start", "stop" or "ignore"
  def command_fader_start(self, player_commands):
    cmd = {
      "type": "type_fader_start",
      "subtype": "stype_fader_start",
      "model": self.model,
      "player_number": self.player_number,
      "player": player_commands
    }
    data = packets.BeatPacket.build(cmd)
    self.prodj.beat_sock.sendto(data, (self.broadcast_addr, self.prodj.beat_port))
