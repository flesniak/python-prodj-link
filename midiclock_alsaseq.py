#!/usr/bin/python3

from threading import Thread
import time
import math
import alsaseq
import logging
import re

def iter_alsa_seq_clients():
  client_re = re.compile('Client[ ]+(\d+) : "(.*)"')
  port_re = re.compile('  Port[ ]+(\d+) : "(.*)"')
  with open("/proc/asound/seq/clients", "r") as f:
    client = (None, "") # client id, client name
    ports = []
    for line in f:
      match = client_re.match(line)
      if match:
        if client[0]:
          yield (*client,ports)
        client = int(match.groups()[0]), match.groups()[1]
      else:
        match = port_re.match(line)
        if match:
          ports += [int(match.groups()[0])]
    if client[0]:
      yield (*client,ports)


class MidiClock(Thread):
  def __init__(self,preferred_port=None):
    super().__init__()
    self.keep_running = True
    self.client_id = 0
    self.client_port = 0
    self.time_s = 0
    self.time_ns = 0
    self.add_s = 0
    self.add_ns = 0
    self.enqueue_at_once = 24

    # this call causes /proc/asound/seq/clients to be created
    alsaseq.client('MidiClock', 0, 1, True)

    client_name = ""
    for client in iter_alsa_seq_clients():
      self.client_id = client[0]
      client_name = client[1]
      self.client_port = client[2][0]
      logging.info("found port {} at {}:{}".format(client_name, self.client_id, self.client_port))
      if client_name == preferred_port:
        break
    logging.info("Using port {} at {}:{}".format(client_name, self.client_id, self.client_port))
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
    self.delay = 60/bpm/24
    self.add_s = math.floor(self.delay)
    self.add_ns = math.floor(1e9*(self.delay-self.add_s))
    logging.info("Midi BPM {} delay {:.9f}s".format(bpm, self.delay))

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
  mc = MidiClock("CH345")
  mc.setBpm(175)
  mc.start()
  try:
    mc.join()
  except KeyboardInterrupt:
    mc.stop()
