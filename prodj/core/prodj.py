import socket
import logging
from threading import Thread
from select import select
from enum import Enum

from prodj.core.clientlist import ClientList
from prodj.core.vcdj import Vcdj
from prodj.data.dataprovider import DataProvider
from prodj.network.nfsclient import NfsClient
from prodj.network.ip import guess_own_iface
from prodj.network import packets
from prodj.network import packets_dump

class OwnIpStatus(Enum):
  notNeeded = 1,
  waiting = 2,
  acquired = 3

class ProDj(Thread):
  def __init__(self):
    super().__init__()
    self.cl = ClientList(self)
    self.data = DataProvider(self)
    self.vcdj = Vcdj(self)
    self.nfs = NfsClient(self)
    self.keepalive_ip = "0.0.0.0"
    self.keepalive_port = 50000
    self.beat_ip = "0.0.0.0"
    self.beat_port = 50001
    self.status_ip = "0.0.0.0"
    self.status_port = 50002
    self.need_own_ip = OwnIpStatus.notNeeded
    self.own_ip = None

  def start(self):
    self.keepalive_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.keepalive_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    self.keepalive_sock.bind((self.keepalive_ip, self.keepalive_port))
    logging.info("Listening on {}:{} for keepalive packets".format(self.keepalive_ip, self.keepalive_port))
    self.beat_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.beat_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    self.beat_sock.bind((self.beat_ip, self.beat_port))
    logging.info("Listening on {}:{} for beat packets".format(self.beat_ip, self.beat_port))
    self.status_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.status_sock.bind((self.status_ip, self.status_port))
    logging.info("Listening on {}:{} for status packets".format(self.status_ip, self.status_port))
    self.socks = [self.keepalive_sock, self.beat_sock, self.status_sock]
    self.keep_running = True
    self.data.start()
    self.nfs.start()
    super().start()

  def stop(self):
    self.keep_running = False
    self.nfs.stop()
    self.data.stop()
    self.vcdj_disable()
    self.join()
    self.keepalive_sock.close()
    self.beat_sock.close()

  def vcdj_set_player_number(self, vcdj_player_number=5):
    logging.info("Player number set to {}".format(vcdj_player_number))
    self.vcdj.player_number = vcdj_player_number
    #self.data.dbc.own_player_number = vcdj_player_number

  def vcdj_enable(self):
    self.vcdj_set_iface()
    self.vcdj.start()

  def vcdj_disable(self):
    self.vcdj.stop()
    self.vcdj.join()

  def vcdj_set_iface(self):
    if self.own_ip is not None:
      self.vcdj.set_interface_data(*self.own_ip[1:4])

  def run(self):
    logging.debug("starting main loop")
    while self.keep_running:
      rdy = select(self.socks,[],[],1)[0]
      for sock in rdy:
        if sock == self.keepalive_sock:
          data, addr = self.keepalive_sock.recvfrom(128)
          self.handle_keepalive_packet(data, addr)
        elif sock == self.beat_sock:
          data, addr = self.beat_sock.recvfrom(128)
          self.handle_beat_packet(data, addr)
        elif sock == self.status_sock:
          data, addr = self.status_sock.recvfrom(1158) # max size of status packet (CDJ-3000), can also be smaller
          self.handle_status_packet(data, addr)
      self.cl.gc()
    logging.debug("main loop finished")

  def handle_keepalive_packet(self, data, addr):
    #logging.debug("Broadcast keepalive packet from {}".format(addr))
    try:
      packet = packets.KeepAlivePacket.parse(data)
    except Exception as e:
      logging.warning("Failed to parse keepalive packet from {}, {} bytes: {}".format(addr, len(data), e))
      packets_dump.dump_packet_raw(data)
      return
    # both packet types give us enough information to store the client
    if packet["type"] in ["type_ip", "type_status", "type_change"]:
      self.cl.eatKeepalive(packet)
    if self.own_ip is None and len(self.cl.getClientIps()) > 0:
      self.own_ip = guess_own_iface(self.cl.getClientIps())
      if self.own_ip is not None:
        logging.info("Guessed own interface {} ip {} mask {} mac {}".format(*self.own_ip))
        self.vcdj_set_iface()
    packets_dump.dump_keepalive_packet(packet)

  def handle_beat_packet(self, data, addr):
    #logging.debug("Broadcast beat packet from {}".format(addr))
    try:
      packet = packets.BeatPacket.parse(data)
    except Exception as e:
      logging.warning("Failed to parse beat packet from {}, {} bytes: {}".format(addr, len(data), e))
      packets_dump.dump_packet_raw(data)
      return
    if packet["type"] in ["type_beat", "type_absolute_position", "type_mixer"]:
      self.cl.eatBeat(packet)
    packets_dump.dump_beat_packet(packet)

  def handle_status_packet(self, data, addr):
    #logging.debug("Broadcast status packet from {}".format(addr))
    try:
      packet = packets.StatusPacket.parse(data)
    except Exception as e:
      logging.warning("Failed to parse status packet from {}, {} bytes: {}".format(addr, len(data), e))
      packets_dump.dump_packet_raw(data)
      return
    self.cl.eatStatus(packet)
    packets_dump.dump_status_packet(packet)

  # called whenever a keepalive packet is received
  # arguments of cb: this clientlist object, player number of changed client
  def set_client_keepalive_callback(self, cb=None):
    self.cl.client_keepalive_callback = cb

  # called whenever a status update of a known client is received
  # arguments of cb: this clientlist object, player number of changed client
  def set_client_change_callback(self, cb=None):
    self.cl.client_change_callback = cb

  # called when a player media changes
  # arguments of cb: this clientlist object, player_number, changed slot
  def set_media_change_callback(self, cb=None):
    self.cl.media_change_callback = cb
