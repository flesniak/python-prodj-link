import asyncio
import functools
import logging
import os
import time
from concurrent.futures import Future
from enum import Enum

class NfsDownloadType(Enum):
  buffer = 1,
  file = 2,
  failed = 3

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
    self.last_write_at = None
    self.speed = 0
    self.future = Future()

    self.max_in_flight = 4 # values > 4 did not increase read speed in my tests
    self.in_flight = 0
    self.single_request_timeout = 2 # retry read after n seconds
    self.max_read_retries = 5
    self.read_retries = 0

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

    if os.path.exists(self.dst_path):
      raise FileExistsError(f"file already exists: {self.dst_path}")

    # create download directory if nonexistent
    dirname = os.path.dirname(self.dst_path)
    if dirname:
      os.makedirs(dirname, exist_ok=True)

    self.download_file_handle = open(self.dst_path, "wb")
    self.type = NfsDownloadType.file

  def sendReadRequest(self, offset):
    remaining = self.size - offset
    chunk = min(self.nfsclient.download_chunk_size, remaining)
    # logging.debug("sending read request @ %d for %d bytes [%d in flight]", offset, chunk, self.in_flight)
    self.in_flight += 1
    task = asyncio.create_task(self.nfsclient.NfsReadData(self.host, self.fhandle, offset, chunk))
    task.add_done_callback(functools.partial(self.readCallback, offset))
    return chunk

  def sendReadRequests(self):
    if self.last_write_at is not None and self.last_write_at + self.single_request_timeout < time.time():
      if self.read_retries > self.max_read_retries:
        self.fail_download("read requests timed out %d times, aborting download", self.max_read_retries)
        return
      else:
        logging.warning("read at offset %d timed out, retrying request", self.write_offset)
        self.sendReadRequest(self.write_offset)
        self.read_retries += 1

    while self.in_flight < self.max_in_flight and self.read_offset < self.size:
      self.read_offset += self.sendReadRequest(self.read_offset)

  def readCallback(self, offset, task):
    # logging.debug("readCallback @ %d/%d [%d in flight]", offset, self.size, self.in_flight)
    self.in_flight = max(0, self.in_flight-1)
    if self.write_offset <= offset:
      try:
        reply = task.result()
      except Exception as e:
        self.fail_download(str(e))
        return
      self.blocks[offset] = reply.data
    else:
      logging.warning("Offset %d received twice, ignoring", offset)

    self.writeBlocks()

    self.updateProgress(offset)

    if self.write_offset == self.size:
      self.finish()
    else:
      self.sendReadRequests()

  def updateProgress(self, offset):
    new_progress = int(100*offset/self.size)
    if new_progress > self.progress+3 or new_progress == 100:
      self.progress = new_progress
      self.speed = offset/(time.time()-self.started_at)/1024/1024
      logging.info("download progress %d%% (%d/%d Bytes, %.2f MiB/s)",
        self.progress, offset, self.size, self.speed)

  def writeBlocks(self):
    # logging.debug("writing %d blocks @ %d [%d in flight]",
    #   len(self.blocks), self.write_offset, self.in_flight)
    while self.write_offset in self.blocks:
      data = self.blocks.pop(self.write_offset)
      expected_length = min(self.nfsclient.download_chunk_size, self.size-self.write_offset)
      if len(data) != expected_length:
        logging.warning("Received %d bytes instead %d as requested. Try to decrease "\
          "the download chunk size!", len(data), expected_length)
      if self.type == NfsDownloadType.buffer:
        self.downloadToBufferHandler(data)
      elif self.type == NfsDownloadType.file:
        self.downloadToFileHandler(data)
      else:
        logging.debug("dropping write @ %d", self.write_offset)
      self.write_offset += len(data)
      self.last_write_at = time.time()
    if len(self.blocks) > 0:
      logging.debug("%d blocks still in queue, first is %d",
        len(self.blocks), self.blocks.keys()[0])

  def downloadToFileHandler(self, data):
    self.download_file_handle.write(data)

  def downloadToBufferHandler(self, data):
    self.download_buffer += data

  def finish(self):
    logging.info("finished downloading %s to %s, %d bytes, %.2f MiB/s",
      self.src_path, self.dst_path, self.write_offset, self.speed)
    if self.in_flight > 0:
      logging.error("BUG: finishing download of %s but packets are still in flight", self.src_path)
    if self.type == NfsDownloadType.buffer:
      self.future.set_result(self.download_buffer)
    elif self.type == NfsDownloadType.file:
      self.download_file_handle.close()
      self.future.set_result(self.dst_path)

  def fail_download(self, message="Unknown error"):
    self.type = NfsDownloadType.failed
    self.future.set_exception(RuntimeError(message))

def generic_file_download_done_callback(future):
  if future.exception() is not None:
    logging.error("download failed: %s", future.exception())
