#!/usr/bin/env python3

from threading import Thread
import time
import math
import alsaseq
import logging
import re

class MidiClock(Thread):
  def __init__(self):
    super().__init__()
    self.keep_running = True
    self.client_id = None
    self.client_port = None
    self.time_s = 0
    self.time_ns = 0
    self.add_s = 0
    self.add_ns = 0
    self.enqueue_at_once = 24

    # this call causes /proc/asound/seq/clients to be created
    alsaseq.client('MidiClock', 0, 1, True)

  # this may only be called after creating this object
  def iter_alsa_seq_clients(self):
    client_re = re.compile('Client[ ]+(\d+) : "(.*)"')
    port_re = re.compile('  Port[ ]+(\d+) : "(.*)"')
    try:
      with open("/proc/asound/seq/clients", "r") as f:
        id = None
        name = ""
        ports = []
        for line in f:
          match = client_re.match(line)
          if match:
            if id:
              yield (id, name, ports)
            id = int(match.groups()[0])
            name = match.groups()[1]
            ports = []
          else:
            match = port_re.match(line)
            if match:
              ports += [int(match.groups()[0])]
        if id:
          yield (id, name, ports)
    except FileNotFoundError:
      pass

  def open(self, preferred_name=None, preferred_port=0):
    clients_found = False
    for id, name, ports in self.iter_alsa_seq_clients():
      clients_found = True
      logging.debug("midi device %d: %s [%s]", id, name, ','.join([str(x) for x in ports]))
      if (preferred_name is None and name != "Midi Through") or name == preferred_name:
        self.client_id = id
        if preferred_port not in ports:
          preferred_port = ports[0]
          logging.warning("Preferred port not found, using %d", preferred_port)
        self.client_port = preferred_port
        break
    if self.client_id is None:
      if clients_found:
        raise RuntimeError(f"Requested device {preferred_name} not found")
      else:
        raise RuntimeError("No sequencers found")
    logging.info("Using device %s at %d:%d", name, self.client_id, self.client_port)
    alsaseq.connectto(0, self.client_id, self.client_port)

  def advance_time(self):
    self.time_ns += self.add_ns
    if self.time_ns > 1000000000:
      self.time_s += 1
      self.time_ns -= 1000000000
    self.time_s = self.time_s + self.add_s

  def enqueue_events(self):
    for i in range(self.enqueue_at_once):
      send = (36, 1, 0, 0, (self.time_s, self.time_ns), (128,0), (self.client_id, self.client_port), None)
      alsaseq.output(send)
      self.advance_time()

  def send_note(self, note):
    alsaseq.output((6, 0, 0, 0, (0,0), (128,0), (self.client_id, self.client_port), (0,note,127,0,0)))

  def run(self):
    logging.info("Starting MIDI clock queue")
    self.enqueue_events()
    alsaseq.start()
    while self.keep_running:
      # not using alsaseq.syncoutput() here, as we would not be fast enough to enqueue more events after
      # the queue has flushed, thus sleep for half the approximate time the queue will need to drain
      time.sleep(self.enqueue_at_once/2*self.delay)
      status, time_t, events = alsaseq.status()
      if events >= self.enqueue_at_once:
        #logging.info("more than 24*4 events queued, skipping enqueue")
        continue
      self.enqueue_events()
    alsaseq.stop()
    logging.info("MIDI clock queue stopped")

  def stop(self):
    self.keep_running = False
    self.join()

  def setBpm(self, bpm):
    if bpm <= 0:
      logging.warning("Ignoring zero bpm")
      return
    self.delay = 60/bpm/24
    self.add_s = math.floor(self.delay)
    self.add_ns = math.floor(1e9*(self.delay-self.add_s))
    logging.info("Midi BPM %d delay %.9fs", bpm, self.delay)

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
  mc = MidiClock()
  mc.open("CH345", 0)
  mc.setBpm(175)
  mc.start()
  try:
    mc.join()
  except KeyboardInterrupt:
    mc.stop()
