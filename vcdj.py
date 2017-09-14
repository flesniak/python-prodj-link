from threading import Event, Thread
from ipaddress import IPv4Network
from construct import byte2int
import packets
import logging
import traceback

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
      "player_number": self.player_number,
      "ip_addr": self.ip_addr,
      "mac_addr": self.mac_addr
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
      "source_ip": self.ip_addr,
      "remote_player_number": player_number,
      "slot": slot_id
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
      "player_number2": self.player_number, # our player number -> we receive confirmation packet
      "load_player_number": load_player_number,
      "load_slot": load_slot_id,
      "load_track_id": load_track_id
    }
    data = packets.StatusPacket.build(cmd)
    logging.debug("send load packet to %s struct %s", cl.ip_addr, str(cmd))
    self.prodj.status_sock.sendto(data, (cl.ip_addr, self.prodj.status_port))
