import logging
import os
import socket
import time
from construct import Aligned, GreedyBytes
from concurrent.futures import Future, ThreadPoolExecutor

from .packets_nfs import getNfsCallStruct, getNfsResStruct, MountMntArgs, MountMntRes, MountVersion, NfsVersion, PortmapArgs, PortmapPort, PortmapVersion, PortmapRes, RpcMsg
from .rpcreceiver import RpcReceiver

# add done_callback to future and catch+attach it's exception if it fails during execution
def chain_future_helper(done_callback, original_future, result_future):
  try:
    result_future.set_result(done_callback(original_future))
  except Exception as ex:
    result_future.set_exception(ex)

def chain_future(future, done_callback):
  result_future = Future()
  future.add_done_callback(chain_future_helper(done_callback, future, result_future))
  return result_future

class NfsClient():
  def __init__(self, prodj):
    super().__init__()
    self.prodj = prodj
    self.executer = ThreadPoolExecutor(max_workers=1)
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

    self.openSockets()
    self.receiver.start()

  def openSockets(self):
    self.rpc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.rpc_sock.bind(("0.0.0.0", 0))
    self.receiver.setSocket(self.rpc_sock)

  def closeSockets(self):
    self.receiver.setSocket(None)
    if self.rpc_sock is not None:
      self.rpc_sock.close()

  def stop(self):
    logging.debug("NfsClient shutting down")
    self.abort = True
    self.executer.shutdown(wait=False)
    self.receiver.stop()
    self.closeSockets()

  def getXid(self):
    self.xid += 1
    return self.xid

  def RpcCall(self, host, prog, vers, proc, data):
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
    future_reply = self.receiver.addCall(rpccall['xid'])
    self.rpc_sock.sendto(rpcdata + payload, host)
    return future_reply

  def PortmapCall(self, ip, proc, data):
    return self.RpcCall((ip, PortmapPort), "portmap", PortmapVersion, proc, data)

  def PortmapGetPort(self, ip, prog, vers, prot):
    call = {
      "prog": prog,
      "vers": vers,
      "prot": prot
    }
    data = PortmapArgs.build(call)
    future_reply = self.PortmapCall(ip, "getport", data)
    future_reply.add_done_callback
    return chain_future(future_reply, self.PortmapGetPortCallback)

  def PortmapGetPortCallback(self, future):
      # try:
      #   port = PortmapRes.parse(future.result())
      # except Exception as e:
      #   future.set_exception(e)
      # else:
      #   if port == 0:
      #     future.set_exception(RuntimeError("PortmapGetPort failed: Program not available"))
      #   else:
      #     future.set_result(port)
      port = PortmapRes.parse(future.result())
      if port == 0:
        raise RuntimeError("PortmapGetPort failed: Program not available")
      future.set_result(port)

  def MountMnt(self, host, path):
    data = MountMntArgs.build(path)
    future_reply = self.RpcCall(host, "mount", MountVersion, "mnt", data)
    return chain_future(future_reply, self.MountMntCallback)

  def MountMntCallback(self, future):
    result = MountMntRes.parse(future.result())
    if result.status != 0:
      raise RuntimeError("MountMnt failed with error {}".format(result.status))
    return result.fhandle

  def NfsCall(self, host, proc, data):
    nfsdata = getNfsCallStruct(proc).build(data)
    reply = self.RpcCall(host, "nfs", NfsVersion, proc, nfsdata)
    return chain_future(reply, self.NfsCallCallback)

  def NfsCallCallback(self, future):
    nfsreply = getNfsResStruct(proc).parse(future.result())
    if nfsreply.status != "ok":
      raise RuntimeError("NFS call failed: " + nfsreply.status)
    return nfsreply.content

  def NfsLookup(self, host, name, fhandle):
    nfscall = {
      "fhandle": fhandle,
      "name": name
    }
    return self.NfsCall(host, "lookup", nfscall)

  # lookup first item in items in the directory referenced by fhandle
  def NfsLookupPathHelper(self, ip, fhandle, items):
    logging.debug("NfsClient: looking up \"%s\"", items[0])
    future_nfsreply = self.NfsLookup(self.rpc_sock, ip, items[0], nfsreply["fhandle"])
    return chain_future(future_nfsreply, self.NfsLookupPathHelperCallback)

  def NfsLookupPathHelperCallback(self, future):
    try:
      return self.NfsLookupPathHelper(future.result(), items[1:0])
    except RuntimeError as e:
      raise FileNotFoundError(path) from None

  def NfsLookupPath(self, ip, mount_handle, path):
    tree = filter(None, path.split("/"))
    return self.NfsLookupPathHelper(ip, mount_handle, tree)

  def NfsReadData(self, host, fhandle, offset, size):
    nfscall = {
      "fhandle": fhandle,
      "offset": offset,
      "count": size,
      "totalcount": 0
    }
    return self.NfsCall(host, "read", nfscall)

  def NfsDownloadFile(self, host, mount_handle, src_path, write_handler):
    logging.info("NfsClient: starting file download ip %s port %d path %s", *host, src_path)
    lookup_result_future = self.NfsLookupPath(host, mount_handle, src_path)
    # chain_future(lookup_result_future, lambda future:
    #   lookup_result = future.result(),
    #   size = lookup_result.attrs.size
    #   fhandle = lookup_result.fhandle
    #   offset = 0
    #   progress = -1
    #   start = time.time())

    lookup_result = future.result()
    size = lookup_result.attrs.size
    fhandle = lookup_result.fhandle

    max_in_flight = 5
    offset = 0
    progress = -1
    start = time.time()
    while offset < size:
      new_progress = int(100*offset/size)
      if new_progress > progress+3:
        progress = new_progress
        speed = offset/(time.time()-start)/1024/1024
        logging.info("NfsClient: download progress %d%% (%d/%d Bytes, %.2f MiB/s)", progress, offset, size, speed)

      remaining = size - offset
      chunk = min(self.download_chunk_size, remaining)
      future_reply = self.NfsReadData(host, fhandle, offset, chunk)
      future_reply.add_done_callback(lambda future: write_handler(future, offset))

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

  def NfsDownloadToFile(self, host, mount_handle, src_path, dst_path):
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
    self.NfsDownloadFile(host, mount_handle, src_path, self.DownloadToFileHandler)
    self.download_file_handle.close()
    self.download_file_handle = None

    return dst_path

  def NfsDownloadToBuffer(self, host, mount_handle, src_path):
    self.download_buffer = b""
    self.NfsDownloadFile(host, mount_handle, src_path, self.DownloadToBufferHandler)
    return self.download_buffer

  # download path from player with ip after trying to mount slot
  # save to dst_path if it is not empty, otherwise to default download directory
  # if dst_path is None, the data will be stored to self.download_buffer.
  def enqueue_download(self, ip, slot, src_path, dst_path=None, sync=False):
    logging.debug(f"NfsClient: enqueueing download of {src_path} from {ip}")
    future = self.executer.submit(self.handle_download, ip, slot, src_path, dst_path)
    if sync:
      return future.result(timeout=30)

  # download path from player with ip after trying to mount slot
  # this call blocks until the download is finished and returns the downloaded bytes
  def enqueue_buffer_download(self, ip, slot, src_path):
    future = self.executer.submit(self.handle_download, ip, slot, src_path, None)
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

  def handle_download(self, ip, slot, src_path, dst_path):
    if slot not in self.export_by_slot:
      raise RuntimeError(f"NfsClient: Unable to download from slot {slot}")
    export = self.export_by_slot[slot]

    future_mount_port = self.PortmapGetPort(ip, "mount", MountVersion, "udp")
    future_nfs_port = self.PortmapGetPort(ip, "nfs", NfsVersion, "udp")

    mount_port = future_mount_port.result()
    logging.debug(f"NfsClient mount port of player {ip}: {mount_port}")
    future_mount_handle = self.MountMnt(self.rpc_sock, (ip, mount_port), export)

    nfs_port = future_nfs_port.result()
    logging.debug(f"NfsClient nfs port of player {ip}: {nfs_port}")
    mount_handle = future_mount_handle.result()

    download = NfsDownload(self, (ip, nfs_port), mount_handle, src_path)
    if dst_path is not None:
      download.setFilename(dst_path)

    # TODO: NFS UMNT
    return download.start()
