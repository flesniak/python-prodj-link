import asyncio
import logging
import time
from concurrent.futures import Future
from select import select
from threading import Thread

from .packets_nfs import getNfsCallStruct, getNfsResStruct, MountMntArgs, MountMntRes, MountVersion, NfsVersion, PortmapArgs, PortmapPort, PortmapVersion, PortmapRes, RpcMsg

class ReceiveTimeout(Exception):
  pass

class RpcReceiver:
  def __init__(self):
    super().__init__()
    self.requests = dict()
    self.keep_running = False
    self.request_timeout = 10

  def addCall(self, xid):
    if xid in self.requests:
      raise RuntimeError(f"Download xid {xid} already taken")
    future = Future()
    self.requests[xid] = (future, time.time())
    return future

  def start(self):
    asyncio.run_coroutine_threadsafe(self.checkTimeoutsTask, )
    self.keep_running = True

  def stop(self):
    self.keep_running = False
    if self.requests:
      logging.warning("Receiver: stopped but still {len(self.requests)} in queue")

  async def checkTimeoutsTask():
    while self.keep_running:
      await asyncio.sleep(1)
      self.checkTimeouts()

  def socketRead(self, sock):
    self.handleReceivedData(sock.recv(4096))

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
