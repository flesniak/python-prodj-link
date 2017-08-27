from threading import Event, Thread
from ipaddress import IPv4Network
import packets
import logging
import traceback

class Vcdj(Thread):
  def __init__(self, prodj):
    super().__init__()
    self.prodj = prodj
    self.player_number = 5
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
      "model": "Virtual CDJ",
      "player_number": self.player_number,
      "ip_addr": self.ip_addr,
      "mac_addr": self.mac_addr
    }
    #logging.debug("send keepalive data: %s", str(data))
    raw = packets.KeepAlivePacket.build(data)
    self.prodj.keepalive_sock.sendto(raw, (self.broadcast_addr, self.prodj.keepalive_port))
