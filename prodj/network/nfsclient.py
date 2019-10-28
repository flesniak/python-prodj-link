import logging
import os
import socket
import time
from construct import Aligned
from select import select
from concurrent.futures import ThreadPoolExecutor

from .packets_nfs import getNfsCallStruct, getNfsResStruct, MountMntArgs, MountMntRes, PortmapArgs, PortmapRes, RpcMsg

class ReceiveTimeout(Exception):
  pass

class NfsClient():
  def __init__(self, prodj):
    super().__init__()
    self.prodj = prodj
    self.executer = ThreadPoolExecutor(max_workers=1)
    self.abort = False

    # this eventually leads to ip fragmentation, but increases read speed by ~x4
    self.download_chunk_size = 1350
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

  def stop(self):
    logging.debug("NfsClient shutting down")
    self.abort = True
    self.executer.shutdown(wait=False)
    if self.portmap_sock is not None:
      self.portmap_sock.close()

  def getXid(self):
    self.xid += 1
    return self.xid

  def getPortmapSock(self):
    if self.portmap_sock is None:
      self.portmap_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      self.portmap_sock.bind(("0.0.0.0", 0))
    return self.portmap_sock

  def SocketSend(self, sock, data, host):
    sock.sendto(data, host)

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
      "content": {
        "prog": prog,
        "proc": proc,
        "vers": vers,
        "cred": {
          "flavor": "unix",
          "content": {
            "stamp": self.rpc_auth_stamp
          }
        },
        "verf": {
          "flavor": "null",
          "content": None
        }
      }
    }
    rpcdata = RpcMsg.build(rpccall)
    payload = Aligned(4, GreedyBytes).build(data)
    self.SocketSend(sock, rpcdata + payload, host)

    receive_timeouts = 0
    while receive_timeouts < self.max_receive_timeout_count and not self.abort:
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

    if rpcreply.content.reply_stat != "accepted":
      raise RuntimeError("RPC call denied: "+rpcreply.content.reject_stat)
    if rpcreply.content.content.accept_stat != "success":
      raise RuntimeError("RPC call unsuccessful: "+rpcreply.content.content.accept_stat)
    return rpcreply.content.content.content

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
    if result.status != 0:
      raise RuntimeError("MountMnt failed with error {}".format(result.status))
    return result.fhandle

  def NfsCall(self, sock, host, proc, data):
    nfsdata = getNfsCallStruct(proc).build(data)
    reply = self.RpcCall(sock, host, "nfs", NfsVersion, proc, nfsdata)
    nfsreply = getNfsResStruct(proc).parse(reply)
    if nfsreply.status != "ok":
      raise RuntimeError("NFS call failed: "+nfsreply.status)
    return nfsreply.content

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
      try:
        nfsreply = self.NfsLookup(sock, ip, item, nfsreply["fhandle"])
      except RuntimeError as e:
        raise FileNotFoundError(path) from None
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

    size = args.attrs.size
    fhandle = args["fhandle"]
    offset = 0
    progress = -1
    start = time.time()
    while size > offset:
      new_progress = int(100*offset/size)
      if new_progress > progress+3:
        progress = new_progress
        speed = offset/(time.time()-start)/1024/1024
        logging.info("NfsClient: download progress %d%% (%d/%d Bytes, %.2f MiB/s)", progress, offset, size, speed)
      remaining = size - offset
      chunk = self.download_chunk_size if remaining > self.download_chunk_size else remaining
      reply = self.NfsReadData(sock, host, fhandle, offset, chunk)
      data = reply.data
      if len(data) == 0:
        raise RuntimeError("NFS read data returned zero bytes")
      write_handler(data)
      offset += len(data)
      if self.abort:
        return
    end = time.time()
    speed = offset/(end-start)/1024/1024
    logging.info("NfsClient: Download of %s complete (%s Bytes, %.2f MiB/s)", src_path, offset, speed)

  def DownloadToFileHandler(self, data):
    self.download_file_handle.write(data)

  def DownloadToBufferHandler(self, data):
    self.download_buffer += data

  def NfsDownloadToFile(self, sock, host, mount_handle, src_path, dst_path):
    # if dst_path is empty, use a default download path
    if not dst_path:
      dst_path = self.default_download_directory + src_path.split("/")[-1]

    if os.path.exists(dst_path):
      raise FileExistsError(f"NfsClient: file already exists: {dst_path}")

    # create download directory if nonexistent
    dirname = os.path.dirname(dst_path)
    if dirname:
      os.makedirs(dirname, exist_ok=True)

    self.download_file_handle = open(dst_path, "wb")
    self.NfsDownloadFile(sock, host, mount_handle, src_path, self.DownloadToFileHandler)
    self.download_file_handle.close()
    self.download_file_handle = None

    return dst_path

  def NfsDownloadToBuffer(self, sock, host, mount_handle, src_path):
    self.download_buffer = b""
    self.NfsDownloadFile(sock, host, mount_handle, src_path, self.DownloadToBufferHandler)
    return self.download_buffer

  # download path from player with ip after trying to mount slot
  # save to dst_path if it is not empty, otherwise to default download directory
  # if dst_path is None, the data will be stored to self.download_buffer
  # a callback can be supplied to be called when the download is complete,
  # the callback argument is dst_path or the downloaded data if dst_path is None
  def enqueue_download(self, ip, slot, src_path, dst_path=None, sync=False, callback=None):
    logging.debug(f"NfsClient: enqueueing download of {src_path} from {ip}")
    future = self.executer.submit(self.handle_download, ip, slot, src_path, dst_path)
    if callback is not None:
      future.add_done_callback(lambda future: callback(future.result()))
    if sync:
      return future.result(timeout=30)

  # download path from player with ip after trying to mount slot
  # this call blocks until the download is finished and returns the downloaded bytes
  def enqueue_buffer_download(self, ip, slot, src_path):
    future = self.executer.submit(self.handle_download, ip, slot, src_path, None)
    try:
      # return future.result()
      ret = future.result()
      logging.warning(f'ret: {ret}')
      return ret
    except RuntimeError as e:
      logging.warning(f"NfsClient: returning empty buffer because: {e}")
      return None

  # can be used as a callback for DataProvider.get_mount_info
  def enqueue_download_from_mount_info(self, request, player_number, slot, id_list, mount_info):
    if request != "mount_info" or "mount_path" not in mount_info:
      logging.error("NfsClient: not enqueueing non-mount_info request")
      return
    c = self.prodj.cl.getClient(player_number)
    if c is None:
      logging.error(f"NfsClient: player {player_number} unknown")
      return
    self.enqueue_download(c.ip_addr, slot, mount_info["mount_path"])

  def handle_download(self, ip, slot, src_path, dst_path):
    if slot not in self.export_by_slot:
      raise RuntimeError(f"NfsClient: Unable to download from slot {slot}")
    export = self.export_by_slot[slot]

    mount_port = self.PortmapGetPort(ip, "mount", MountVersion, "udp")
    logging.debug(f"NfsClient mount port of player {ip}: {mount_port}")
    nfs_port = self.PortmapGetPort(ip, "nfs", NfsVersion, "udp")
    logging.debug(f"NfsClient nfs port of player {ip}: {nfs_port}")

    mount_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    mount_sock.bind(("0.0.0.0", 0))
    mount_handle = self.MountMnt(mount_sock, (ip, mount_port), export)
    mount_sock.close()

    nfs_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    nfs_sock.bind(("0.0.0.0", 0))
    if dst_path is None:
      ret = self.NfsDownloadToBuffer(nfs_sock, (ip, nfs_port), mount_handle, src_path)
    else:
      ret = self.NfsDownloadToFile(nfs_sock, (ip, nfs_port), mount_handle, src_path, dst_path)
    nfs_sock.close()

    # TODO: NFS UMNT
    return ret
