from threading import Event, Thread
import logging
import time

# this implements a least recently used cache
# stores key -> (timestamp, val) and updates timestamp on every access
class DataStore(Thread, dict):
  def __init__(self, size_limit=15, gc_interval=30):
    super().__init__()
    self.gc_interval = gc_interval
    self.size_limit = size_limit
    self.event = Event()
    self.start()

  # make this class hashable
  def __eq__(self, other):
    return self is other

  def __hash__(self):
    return hash(id(self))

  def __getitem__(self, key):
    val = dict.__getitem__(self, key)[1]
    #logging.debug("DataStore: get %s = %s, update timestamp", str(key), str(val))
    self.__setitem__(key, val) # update timestamp
    return val

  def __setitem__(self, key, val):
    #logging.debug("DataStore: set %s = %s", str(key), str(val))
    dict.__setitem__(self, key, (time.time(), val))

  def start(self):
    self.event.clear()
    super().start()

  def stop(self):
    self.event.set()

  def run(self):
    logging.debug("DataStore: %s initialized", hex(id(self)))
    while not self.event.wait(self.gc_interval):
      self.gc()
    logging.debug("DataStore: %s stopped", hex(id(self)))

  def gc(self):
    if len(self) <= self.size_limit:
      return
    logging.debug("DataStore: garbage collection (max %d, cur %d)", self.size_limit, len(self))
    oldest_items = sorted(self.items(), key=lambda x: x[1][0])
    for delete_item in oldest_items[0:len(self)-self.size_limit]:
      logging.debug("DataStore: delete %s due to age", str(delete_item[0]))
      del self[delete_item[0]]
