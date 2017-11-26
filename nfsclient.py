import socket
import time
import os
from select import select
from packets_nfs import *
from construct import FieldError

import logging
from threading import Event, Thread
from queue import Empty, Queue

class ReceiveTimeout(Exception):
  pass

class NfsClient(Thread):
  def __init__(self, prodj):
    super().__init__()
    self.prodj = prodj
    self.queue = Queue()

    # this eventually leads to ip fragmentation, but increases read speed by ~x4
    self.download_chunk_size = 60000
    self.rpc_auth_stamp = 0xdeadbeef
    self.max_receive_timeout_count = 3
    self.default_download_directory = "./downloads/"
    self.portmap_sock = None
    self.xid = 1
    self.download_file_handle = None
    self.download_buffer = None

    self.export_by_slot = {
      "sd": "/B/",
      "usb": "/C/"
    }

  def start(self):
    if self.is_alive():
      return
    self.keep_running = True
    super().start()

  def stop(self):
    if self.is_alive():
      self.keep_running = False
      self.join()

  def getXid(self):
    self.xid += 1
    return self.xid

  def getPortmapSock(self):
    if self.portmap_sock is None:
      self.portmap_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      self.portmap_sock.bind(("0.0.0.0", 0))
    return self.portmap_sock

  def SocketRecv(self, sock, timeout=1):
    rdy = select([sock], [], [], timeout)
    if rdy[0]:
      return sock.recv(self.download_chunk_size+100)
    raise ReceiveTimeout("SocketRecv timeout after {} seconds".format(timeout))

  def RpcCall(self, sock, host, prog, vers, proc, data):
    #logging.debug("NfsClient: RpcCall ip %s prog \"%s\" proc \"%s\"", ip, prog, proc)
    rpccall = {
      "xid": self.getXid(),
      "type": "call",
      "prog": prog,
      "proc": proc,
      "vers": vers,
      "cred": {
        "flavor": "unix",
        "stamp": self.rpc_auth_stamp
      },
      "verf": {
        "flavor": "null",
      }
    }
    rpcdata = RpcMsg.build(rpccall)
    sock.sendto(rpcdata+Aligned(4, GreedyBytes).build(data), host)

    receive_timeouts = 0
    while receive_timeouts < self.max_receive_timeout_count:
      try:
        data = self.SocketRecv(sock, 1)
      except ReceiveTimeout:
        receive_timeouts += 1
      else:
        if len(data) == 0:
          logging.warning("NfsClient: RpcCall: no data received!")
          receive_timeouts += 1
        else:
          rpcreply = RpcMsg.parse(data)
          break
    if receive_timeouts >= self.max_receive_timeout_count:
      raise RuntimeError("RpcCall failed after {} timeouts".format(receive_timeouts))

    if rpcreply["reply_stat"] != "accepted":
      raise RuntimeError("RPC call denied: "+rpcreply["reject_stat"])
    if rpcreply["accept_stat"] != "success":
      raise RuntimeError("RPC call unsuccessful: "+rpcreply["accept_stat"])
    return rpcreply["content"]

  def PortmapCall(self, ip, proc, data):
    return self.RpcCall(self.getPortmapSock(), (ip, PortmapPort), "portmap", PortmapVersion, proc, data)

  def PortmapGetPort(self, ip, prog, vers, prot):
    call = {
      "prog": prog,
      "vers": vers,
      "prot": prot
    }
    data = PortmapArgs.build(call)
    reply = self.PortmapCall(ip, "getport", data)
    port = PortmapRes.parse(reply)
    if port == 0:
      raise RuntimeError("PortmapGetPort failed: Program not available")
    return port

  def MountMnt(self, sock, host, path):
    data = MountMntArgs.build(path)
    reply = self.RpcCall(sock, host, "mount", MountVersion, "mnt", data)
    result = MountMntRes.parse(reply)
    if result["status"] != 0:
      raise RuntimeError("MountMnt failed with error {}".format(result["status"]))
    return result["fhandle"]

  def NfsCall(self, sock, host, proc, data):
    nfsdata = getNfsCallStruct(proc).build(data)
    reply = self.RpcCall(sock, host, "nfs", NfsVersion, proc, nfsdata)
    nfsreply = getNfsResStruct(proc).parse(reply)
    if nfsreply["status"] != "ok":
      raise RuntimeError("NFS call failed: "+nfsreply["status"])
    return nfsreply["content"]

  def NfsLookup(self, sock, host, name, fhandle):
    nfscall = {
      "fhandle": fhandle,
      "name": name
    }
    return self.NfsCall(sock, host, "lookup", nfscall)

  def NfsLookupPath(self, sock, ip, mount_handle, path):
    tree = filter(None, path.split("/"))
    nfsreply = {"fhandle": mount_handle}
    for item in tree:
      logging.debug("NfsClient: looking up \"%s\"", item)
      nfsreply = self.NfsLookup(sock, ip, item, nfsreply["fhandle"])
    return nfsreply

  def NfsReadData(self, sock, host, fhandle, offset, size):
    nfscall = {
      "fhandle": fhandle,
      "offset": offset,
      "count": size,
      "totalcount": 0
    }
    return self.NfsCall(sock, host, "read", nfscall)

  def NfsDownloadFile(self, sock, host, mount_handle, src_path, write_handler):
    logging.info("NfsClient: starting file download ip %s port %d path %s", *host, src_path)
    args = self.NfsLookupPath(sock, host, mount_handle, src_path)

    size = args["attrs"]["size"]
    fhandle = args["fhandle"]
    offset = 0
    progress = -1
    start = time.time()
    while size > offset:
      new_progress = int(100*offset/size)
      if new_progress > progress+3:
        progress = new_progress
        logging.info("NfsClient: download progress %d%% (%d/%d Bytes)", progress, offset, size)
      remaining = size-offset
      chunk = self.download_chunk_size if remaining > self.download_chunk_size else remaining
      reply = self.NfsReadData(sock, host, fhandle, offset, chunk)
      data = reply["data"]
      if len(data) == 0:
        raise RuntimeError("NFS read data returned zero bytes")
      write_handler(data)
      offset += len(data)
    end = time.time()
    speed = offset/(end-start)/1024/1024
    logging.info("NfsClient: Download of %s complete (%s Bytes, %.2f MiB/s)", src_path, offset, speed)

  def DownloadToFileHandler(self, data):
    self.download_file_handle.write(data)

  def DownloadToBufferHandler(self, data):
    self.download_buffer += data

  def NfsDownloadToFile(self, sock, host, mount_handle, src_path, dst_path):
    self.download_file_handle = open(dst_path, "wb")
    self.NfsDownloadFile(sock, host, mount_handle, src_path, DownloadToFileHandler)
    self.download_file_handle.close()
    self.download_file_handle = None

  def NfsDownloadToBuffer(self, sock, host, mount_handle, src_path):
    self.download_buffer = b""
    self.NfsDownloadFile(sock, host, mount_handle, src_path, DownloadToBufferHandler)
    buf = self.download_buffer
    self.download_buffer = None
    return buf

  # can be used as a callback for DataProvider.get_mount_info
  def enqueue_download_from_mount_info(self, request, player_number, slot, id_list, sort_mode, mount_info):
    if request != "mount_info":
      logging.error("NfsClient: not enqueueing non-mount_info request")
      return
    c = self.prodj.cl.getClient(player_number)
    if c is None:
      logging.error("NfsClient: player {} unknown")
      return
    self.enqueue_download(c.ip_addr, slot, mount_info["mount_path"])

  # download path from player with ip after trying to mount "export"
  # save to file if file is not None, otherwise to default download directory
  # a callback can be supplied to be called when the download is complete, argument is dst_path
  def enqueue_download(self, ip, slot, src_path, dst_path=None, sync=False, callback=None):
    self.start()
    if slot not in self.export_by_slot:
      logging.error("NfsClient: Unable to download from \"%s\"", slot)
      return
    export = self.export_by_slot[slot]
    logging.debug("NfsClient: enqueueing download of \"%s\" from %s", src_path, ip)
    if dst_path is None:
      dst_path = self.default_download_directory + src_path.split("/")[-1]
    event = Event() if sync else None
    self.queue.put((ip, src_path, dst_path, export, event, callback))
    if sync and not event.wait(30):
      raise RuntimeError("NfsClient: synchronous download timed out")

  def handle_download(self, ip, src_path, dst_path, export, event, callback):
    if os.path.exists(dst_path):
      logging.error("NfsClient: file already exists: %s", dst_path)
      return
    mount_port = self.PortmapGetPort(ip, "mount", MountVersion, "udp")
    logging.debug("NfsClient mount port of player %s: %d", ip, mount_port)
    nfs_port = self.PortmapGetPort(ip, "nfs", NfsVersion, "udp")
    logging.debug("NfsClient nfs port of player %s: %d", ip, nfs_port)

    mount_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    mount_sock.bind(("0.0.0.0", 0))
    mount_handle = self.MountMnt(mount_sock, (ip, mount_port), export)
    mount_sock.close()

    # create download directory is nonexistant
    dirname = os.path.dirname(dst_path)
    if dirname:
      os.makedirs(dirname, exist_ok=True)

    nfs_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    nfs_sock.bind(("0.0.0.0", 0))
    self.NfsDownloadToFile(nfs_sock, (ip, nfs_port), mount_handle, src_path, dst_path)
    nfs_sock.close()

    if callback is not None:
      callback(filename)
    if event is not None:
      event.set()

  def run(self):
    logging.debug("NfsClient starting")
    while self.keep_running:
      try:
        request = self.queue.get(timeout=1)
      except Empty:
        continue
      try:
        self.handle_download(*request)
      except RuntimeError as e:
        logging.error("NfsClient: download failed: %s", e)
      finally:
        self.queue.task_done()
    logging.debug("NfsClient shutting down")
    if self.portmap_sock is not None:
      self.portmap_sock.close()
