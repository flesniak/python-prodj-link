import asyncio
import logging
import os
import socket
import time
from construct import Aligned, GreedyBytes
from threading import Thread

from .packets_nfs import getNfsCallStruct, getNfsResStruct, MountMntArgs, MountMntRes, MountVersion, NfsVersion, PortmapArgs, PortmapPort, PortmapVersion, PortmapRes, RpcMsg
from .rpcreceiver import RpcReceiver

class NfsClient(Thread):
  def __init__(self, prodj):
    super().__init__()
    self.prodj = prodj
    self.loop = asyncio.new_event_loop()
    self.receiver = RpcReceiver()
    self.abort = False

    # this eventually leads to ip fragmentation, but increases read speed by ~x4
    self.download_chunk_size = 1350
    self.rpc_auth_stamp = 0xdeadbeef
    self.max_receive_timeout_count = 3
    self.default_download_directory = "./downloads/"
    self.rpc_sock = None
    self.xid = 1
    self.download_file_handle = None
    self.download_buffer = None

    self.export_by_slot = {
      "sd": "/B/",
      "usb": "/C/"
    }

  def start(self):
    self.openSockets()
    self.receiver.start()
    super().start()

  def stop(self):
    logging.debug("NfsClient shutting down")
    self.abort = True
    self.loop.stop()
    self.receiver.stop()
    self.closeSockets()

  def run(self):
    self.loop.run_forever()

  def openSockets(self):
    self.rpc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.rpc_sock.bind(("0.0.0.0", 0))
    self.receiver.setSocket(self.rpc_sock)

  def closeSockets(self):
    self.receiver.setSocket(None)
    if self.rpc_sock is not None:
      self.rpc_sock.close()

  def getXid(self):
    self.xid += 1
    return self.xid

  async def RpcCall(self, host, prog, vers, proc, data):
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
    future_reply = asyncio.wrap_future(self.receiver.addCall(rpccall['xid']))
    self.rpc_sock.sendto(rpcdata + payload, host)
    return await future_reply

  async def PortmapCall(self, ip, proc, data):
    return await self.RpcCall((ip, PortmapPort), "portmap", PortmapVersion, proc, data)

  async def PortmapGetPort(self, ip, prog, vers, prot):
    call = {
      "prog": prog,
      "vers": vers,
      "prot": prot
    }
    data = PortmapArgs.build(call)
    reply = await self.PortmapCall(ip, "getport", data)
    port = PortmapRes.parse(reply)
    if port == 0:
      raise RuntimeError("PortmapGetPort failed: Program not available")
    return port

  async def MountMnt(self, host, path):
    data = MountMntArgs.build(path)
    reply = await self.RpcCall(host, "mount", MountVersion, "mnt", data)
    result = MountMntRes.parse(reply)
    if result.status != 0:
      raise RuntimeError("MountMnt failed with error {}".format(result.status))
    return result.fhandle

  async def NfsCall(self, host, proc, data):
    nfsdata = getNfsCallStruct(proc).build(data)
    reply = await self.RpcCall(host, "nfs", NfsVersion, proc, nfsdata)
    nfsreply = getNfsResStruct(proc).parse(reply)
    if nfsreply.status != "ok":
      raise RuntimeError("NFS call failed: " + nfsreply.status)
    return nfsreply.content

  async def NfsLookup(self, host, name, fhandle):
    nfscall = {
      "fhandle": fhandle,
      "name": name
    }
    return self.NfsCall(host, "lookup", nfscall)

  # async def _NfsLookupPath(self, ip, fhandle, items):
  #   for item in items:
  #     logging.debug("NfsClient: looking up \"%s\"", item)
  #     nfsreply = await self.NfsLookup(ip, item, fhandle)
  #     fhandle = nfsreply["fhandle"]
  #   return nfsreply

  async def NfsLookupPath(self, ip, mount_handle, path):
    tree = filter(None, path.split("/"))
    for item in tree:
      logging.debug("NfsClient: looking up \"%s\"", item)
      nfsreply = await self.NfsLookup(ip, item, fhandle)
      fhandle = nfsreply["fhandle"]
    return nfsreply
    # return asyncio.create_task(self._NfsLookupPath, ip, mount_handle, tree)

  async def NfsReadData(self, host, fhandle, offset, size):
    nfscall = {
      "fhandle": fhandle,
      "offset": offset,
      "count": size,
      "totalcount": 0
    }
    return self.NfsCall(host, "read", nfscall)

  # download path from player with ip after trying to mount slot
  # save to dst_path if it is not empty, otherwise to default download directory
  # if dst_path is None, the data will be stored to self.download_buffer.
  def enqueue_download(self, ip, slot, src_path, dst_path=None, sync=False):
    logging.debug(f"NfsClient: enqueueing download of {src_path} from {ip}")
    # future = self.executer.submit(self.handle_download, ip, slot, src_path, dst_path)
    future = asyncio.run_coroutine_threadsafe(
      self.handle_download(ip, slot, src_path, dst_path), self.loop)
    if sync:
      return future.result(timeout=30)

  # download path from player with ip after trying to mount slot
  # this call blocks until the download is finished and returns the downloaded bytes
  def enqueue_buffer_download(self, ip, slot, src_path):
    future = asyncio.run_coroutine_threadsafe(
      self.handle_download(ip, slot, src_path, None), self.loop)
    try:
      ret = future.result()
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

  async def handle_download(self, ip, slot, src_path, dst_path):
    logging.debug(f"Nfsclient: Starting download of {src_path} from {ip}@{slot}")
    if slot not in self.export_by_slot:
      raise RuntimeError(f"NfsClient: Unable to download from slot {slot}")
    export = self.export_by_slot[slot]

    mount_port = await self.PortmapGetPort(ip, "mount", MountVersion, "udp")
    logging.debug(f"NfsClient: mount port of player {ip}: {mount_port}")

    nfs_port = await self.PortmapGetPort(ip, "nfs", NfsVersion, "udp")
    logging.debug(f"NfsClient: nfs port of player {ip}: {nfs_port}")

    mount_handle = await self.MountMnt(self.rpc_sock, (ip, mount_port), export)
    download = NfsDownload(self, (ip, nfs_port), mount_handle, src_path)
    if dst_path is not None:
      download.setFilename(dst_path)

    # TODO: NFS UMNT
    return download.start()
