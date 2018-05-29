import fcntl
import socket
import netifaces as ni
from ipaddress import IPv4Network
import struct
import logging

def get_ip_address(addrs):
  if ni.AF_INET in addrs:
    return addrs[ni.AF_INET][0]['addr']

  return '127.0.0.1'

def get_netmask(addrs):
  if ni.AF_INET in addrs:
    return addrs[ni.AF_INET][0]['netmask']

  return '255.255.255.0'

def get_mac_address(addrs):
  if ni.AF_LINK in addrs:
    return addrs[ni.AF_LINK][0]['addr']

  return ''

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
      addr = ni.ifaddresses(iface)
      ip = get_ip_address(addr)
      netmask = get_netmask(addr)
      mac = get_mac_address(addr)
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
