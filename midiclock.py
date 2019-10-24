#!/usr/bin/env python3

import logging

from prodj.core.prodj import ProDj
from prodj.midi.midiclock_alsaseq import MidiClock

#default_loglevel=logging.DEBUG
default_loglevel=logging.INFO
#default_loglevel=logging.WARNING

logging.basicConfig(level=default_loglevel, format='%(levelname)s: %(message)s')

c = MidiClock("CH345")
bpm = 128 # default bpm until reported from player
beat = 0
c.setBpm(bpm)

def update_master(cl, player_number):
  global bpm, beat
  client = cl.getClient(player_number)
  if beat != client.beat:
    beat = client.beat
    c.send_note(59+beat)
  newbpm = client.bpm*client.actual_pitch
  if bpm != newbpm:
    c.setBpm(newbpm)
    bpm = newbpm

p = ProDj()
p.set_master_change_callback(update_master)

try:
  p.start()
  p.vcdj_enable()
  c.start()
  p.join()
except KeyboardInterrupt:
  logging.info("Shutting down...")
  c.stop()
  p.stop()
