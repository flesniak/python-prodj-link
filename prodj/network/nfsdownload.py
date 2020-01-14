import asyncio
import functools
import logging
import os
import time
from concurrent.futures import Future
from enum import Enum

class NfsDownloadType(Enum):
  buffer = 1,
  file = 2

class NfsDownload:
  def __init__(self, nfsclient, host, mount_handle, src_path):
    self.nfsclient = nfsclient
    self.host = host # tuple of (ip, port)
    self.mount_handle = mount_handle
    self.src_path = src_path
    self.dst_path = None
    self.fhandle = None # set by lookupCallback
    self.progress = -3
    self.started_at = 0 # set by start
    self.future = Future()
    self.default_download_directory = "./downloads/"

    self.max_in_flight = 5
    self.in_flight = 0
    self.download_chunk_size = 1024

    self.size = 0
    self.read_offset = 0
    self.write_offset = 0
    self.type = NfsDownloadType.buffer
    self.download_buffer = b""
    self.download_file_handle = None

    # maps offset -> data of blocks, written
    # when continuously available
    self.blocks = dict()

  async def start(self):
    lookup_result = await self.nfsclient.NfsLookupPath(self.host, self.mount_handle, self.src_path)
    self.size = lookup_result.attrs.size
    self.fhandle = lookup_result.fhandle
    self.started_at = time.time()
    self.sendReadRequests()
    return await asyncio.wrap_future(self.future)

  def setFilename(self, dst_path=""):
    self.dst_path = dst_path
    # if dst_path is empty, use a default download path
    if not self.dst_path:
      self.dst_path = self.default_download_directory + os.path.split(self.src_path)[1]

    if os.path.exists(self.dst_path):
      raise FileExistsError(f"NfsClient: file already exists: {self.dst_path}")

    # create download directory if nonexistent
    dirname = os.path.dirname(self.dst_path)
    if dirname:
      os.makedirs(dirname, exist_ok=True)

    self.download_file_handle = open(self.dst_path, "wb")
    self.type = NfsDownloadType.file

  def sendReadRequests(self):
    while self.in_flight < self.max_in_flight and self.read_offset < self.size:
      remaining = self.size - self.read_offset
      chunk = min(self.download_chunk_size, remaining)
      self.in_flight += 1
      task = asyncio.create_task(self.nfsclient.NfsReadData(self.host, self.fhandle, self.read_offset, chunk))
      task.add_done_callback(functools.partial(self.readCallback, self.read_offset))
      self.read_offset += chunk

  def readCallback(self, offset, task):
    self.in_flight = max(0, self.in_flight-1)
    # logging.debug(f"NfsDownload: readCallback @ {offset}/{self.size}")
    if self.write_offset <= offset:
      reply = task.result()
      self.blocks[offset] = reply.data
    else:
      logging.warning(f"Offset {offset} received twice, ignoring")

    self.writeBlocks()

    self.updateProgress(offset)

    if self.write_offset == self.size:
      self.finish()
    else:
      self.sendReadRequests()

  def updateProgress(self, offset):
    new_progress = int(100*offset/self.size)
    if new_progress > self.progress+3:
      self.progress = new_progress
      speed = offset/(time.time()-self.started_at)/1024/1024
      logging.info("NfsClient: download progress %d%% (%d/%d Bytes, %.2f MiB/s)",
        self.progress, offset, self.size, speed)

  def writeBlocks(self):
    while self.write_offset in self.blocks:
      data = self.blocks.pop(self.write_offset)
      if self.type == NfsDownloadType.buffer:
        self.downloadToBufferHandler(data)
      else:
        self.downloadToFileHandler(data)
      self.write_offset += len(data)
    if len(self.blocks) > 0:
      logging.debug(f"NfsDownload: {len(self.blocks)} blocks still in queue, first is {self.blocks.keys()[0]}")

  def downloadToFileHandler(self, data):
    self.download_file_handle.write(data)

  def downloadToBufferHandler(self, data):
    self.download_buffer += data

  def finish(self):
    if self.in_flight > 0:
      logging.error(f"BUG: finishing download of {self.src_path} but packets are still in flight")
    if self.type == NfsDownloadType.buffer:
      self.future.set_result(self.download_buffer)
    else:
      self.download_file_handle.close()
      self.future.set_result(self.dst_path)
