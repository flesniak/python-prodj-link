#!/usr/bin/env python3

# NOTE: This module suffers bad timing!
# Use the alsaseq implementation if possible.

from threading import Thread
import time
import rtmidi
import logging

class MidiClock(Thread):
  def __init__(self,preferred_port=None):
    super().__init__()
    self.keep_running = True
    self.delay = 1
    self.calibration_cycles = 60
    self.midiout = rtmidi.MidiOut()

    available_ports = self.midiout.get_ports()
    if available_ports is None:
      raise Exception("No available midi ports")

    port_index = 0
    logging.info("Available ports:")
    for index, port in enumerate(available_ports):
      logging.info("- {}".format(port))
      if port == preferred_port:
        port_index = index
    logging.info("Using port {}".format(preferred_port))
    self.midiout.open_port(port_index)

  def run(self):
    cal = 0
    last = time.time()
    while self.keep_running:
      for n in range(self.calibration_cycles):
        self.midiout.send_message([0xF8])
        time.sleep(self.delay-cal)
      now = time.time()
      cal = 0.3*cal+0.7*((now-last)/self.calibration_cycles-self.delay)
      last = now
      print(str(cal))

  def stop(self):
    self.keep_running = False
    self.join()

  def setBpm(self, bpm):
    self.delay = 60/bpm/24
    logging.info("BPM {} delay {}s".format(bpm, self.delay))

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
  mc = MidiClock("CH345:CH345 MIDI 1 28:0")
  mc.setBpm(175)
  mc.start()
  try:
    mc.join()
  except KeyboardInterrupt:
    mc.stop()
