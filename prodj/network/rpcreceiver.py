import logging
import time
from concurrent.futures import Future
from asyncio import Future
from select import select
from threading import Thread

from .packets_nfs import getNfsCallStruct, getNfsResStruct, MountMntArgs, MountMntRes, MountVersion, NfsVersion, PortmapArgs, PortmapPort, PortmapVersion, PortmapRes, RpcMsg

class ReceiveTimeout(Exception):
  pass

class RpcReceiver(Thread):
  def __init__(self):
    super().__init__()
    self.requests = dict()
    self.keep_running = False
    self.sock = None
    self.recv_timeout = 1
    self.request_timeout = 60

  def setSocket(self, sock):
    self.sock = sock

  def addCall(self, xid):
    if xid in self.requests:
      raise RuntimeError(f"Download xid {xid} already taken")
    future = Future()
    self.requests[xid] = (future, time.time())
    return future

  def start(self):
    self.keep_running = True
    super().start()

  def stop(self):
    self.keep_running = False
    self.join()
    if self.requests:
      logging.warning("Receiver: stopped but still {len(self.requests)} in queue")

  def run(self):
    logging.debug("Nfs Receiver starting")
    while self.keep_running:
      if self.sock is None:
        logging.info("Socket gone, waiting for recovery...")
        sleep(self.recv_timeout)
        continue

      rdy = select([self.sock], [], [], self.recv_timeout)
      if rdy[0]:
        self.handleReceivedData(self.sock.recv(4096))

      self.checkTimeouts()

  def handleReceivedData(self, data):
    if len(data) == 0:
      logging.error("BUG: Receiver: no data received!")

    try:
      rpcreply = RpcMsg.parse(data)
    except Exception as e:
      logging.warning(f"Failed to parse RPC reply: {e}")
      return

    if not rpcreply.xid in self.requests:
      logging.warning(f"Unknown RPC XID {rpcreply.xid}")
    result_future, _ = self.requests.pop(rpcreply.xid)

    if rpcreply.content.reply_stat != "accepted":
      result_future.set_exception(RuntimeError("RPC call denied: "+rpcreply.content.reject_stat))
    if rpcreply.content.content.accept_stat != "success":
      result_future.set_exception(RuntimeError("RPC call unsuccessful: "+rpcreply.content.content.accept_stat))

    result_future.set_result(rpcreply.content.content.content)

  def checkTimeouts(self):
      deadline = time.time() - self.request_timeout
      for id, (future, started_at) in list(self.requests.items()):
        if started_at < deadline:
          future.set_exception(ReceiveTimeout(f"Request timed out after {self.request_timeout} seconds"))
        del self.requests[id]
