import logging
import os
import time
from concurrent.futures import Future

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
    self.start = 0 # set by start

    self.future = Future()
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

  def start(self):
    self.start = time.time()
    lookup_future = self.NfsLookupPath(self.host, self.mount_handle, self.src_path)
    lookup_future.add_done_callback(self.lookupCallback)
    return self.future

  def setFilename(self, dst_path=""):
    # if dst_path is empty, use a default download path
    if not dst_path:
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
      future_reply = self.NfsReadData(self.host, self.fhandle, self.read_offset, chunk)
      future_reply.add_done_callback(lambda future:
        self.readCallback(self.read_offset, future)
      )

  def readCallback(self, offset, future):
    self.in_flight = max(0, self.in_flight-1)
    data = future.result()
    if self.write_offset <= offset:
      self.blocks[offset] = data
    else:
      logging.warning("Offset {offset} received twice, ignoring")

    self.writeBlocks()

    self.updateProgress()

    if self.write_offset == self.size:
      self.finished()

  def updateProgress(self):
    new_progress = int(100*offset/size)
    if new_progress > self.progress+3:
      self.progress = new_progress
      speed = self.offset/(time.time()-self.start)/1024/1024
      logging.info("NfsClient: download progress %d%% (%d/%d Bytes, %.2f MiB/s)",
        self.progress, self.offset, self.size, speed)

  def writeBlocks(self):
    while self.write_offset in self.blocks:
      data = self.blocks[self.write_offset]
      if self.type == NfsDownloadType.buffer:
        self.downloadToBufferHandler(data)
      else:
        self.downloadToFileHandler(data)
      self.write_offset += len(data)

  def downloadToFileHandler(self, data):
    self.download_file_handle.write(data)

  def downloadToBufferHandler(self, data):
    self.download_buffer += data

  def lookupCallback(self, future):
    lookup_result = future.get_value()
    self.size = lookup_result.attrs.size
    self.fhandle = lookup_result.fhandle
    self.sendReadRequests()

  def finished(self):
    if self.type == NfsDownloadType.buffer:
      self.future.set_result(self.download_buffer)
    else:
      self.download_file_handle.close()
      self.future.set_result(self.dst_path)
