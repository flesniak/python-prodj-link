import fcntl
import socket
from ipaddress import IPv4Network
import struct
import logging

def get_ip_linux(sock, interface):
  return socket.inet_ntoa(
    fcntl.ioctl(
      sock.fileno(),
      0x8915, # SIOCGIFADDR
      struct.pack('256s', interface.encode('ascii'))
    )[20:24])

def get_netmask_linux(sock, interface):
  return socket.inet_ntoa(
    fcntl.ioctl(
      sock.fileno(),
      0x891b, # SIOCGIFNETMASK
      struct.pack('256s', interface.encode('ascii'))
    )[20:24])

def get_mac_linux(sock, interface):
  return ':'.join("{:02x}".format(x) for x in
    fcntl.ioctl(
      sock.fileno(),
      0x8927, # SIOCGIFHWADDR
      struct.pack('256s', interface.encode('ascii'))
    )[20:26])

#https://stackoverflow.com/questions/819355/how-can-i-check-if-an-ip-is-in-a-network-in-python
def address_is_in_network(ip, net_n_bits):
  ipaddr = struct.unpack('!L', socket.inet_aton(ip))[0]
  net, bits = net_n_bits.split('/')
  netaddr = struct.unpack('!L', socket.inet_aton(net))[0]
  netmask = (0xFFFFFFFF >> int(bits)) ^ 0xFFFFFFFF
  return ipaddr & netmask == netaddr

def guess_own_iface(sock, match_ips):
  if len(match_ips) == 0:
    return None
  for idx, iface in socket.if_nameindex():
    try:
      ip = get_ip_linux(sock, iface)
      netmask = get_netmask_linux(sock, iface)
      mac = get_mac_linux(sock, iface)
    except OSError as e:
      if e.errno == 99:
        logging.warning("{} has no IPv4 address".format(iface))
      else:
        logging.warning("Failed to get interface information for {}: {} ({})".format(iface,e.strerror,e.errno))
      continue
    net = IPv4Network(ip+"/"+netmask, strict=False)
    if any([match_ip for match_ip in match_ips if address_is_in_network(match_ip, net.with_prefixlen)]):
      return iface, ip, netmask, mac
  return None
