#!/usr/bin/python3

import logging

from prodj import ProDj
from midiclock_alsaseq import MidiClock

#default_loglevel=logging.DEBUG
default_loglevel=logging.INFO
#default_loglevel=logging.WARNING

logging.basicConfig(level=default_loglevel, format='%(levelname)s: %(message)s')

c = MidiClock("CH345")
bpm = 128 # default bpm until reported from player
c.setBpm(bpm)

def update_master_bpm(cl, player_number):
  global bpm
  client = cl.getClient(player_number)
  newbpm = client.bpm*client.actual_pitch
  if bpm != newbpm:
    c.setBpm(newbpm)
    bpm = newbpm

p = ProDj()
p.set_master_change_callback(update_master_bpm)

try:
  p.start()
  p.vcdj_enable()
  c.start()
  p.join()
except KeyboardInterrupt:
  logging.info("Shutting down...")
  c.stop()
  p.stop()
