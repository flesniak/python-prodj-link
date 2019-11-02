#!/usr/bin/env python3

import logging

from prodj.core.prodj import ProDj
from prodj.midi.midiclock_alsaseq import MidiClock

default_loglevel=logging.WARNING
default_loglevel=logging.INFO
default_loglevel=logging.DEBUG

logging.basicConfig(level=default_loglevel, format='%(levelname)s: %(message)s')

c = MidiClock("CH345")
bpm = 128 # default bpm until reported from player
beat = 0
c.setBpm(bpm)

p = ProDj()
p.cl.log_played_tracks = False
p.cl.auto_request_beatgrid = False

def update_master(player_number):
  global bpm, beat, p
  client = p.cl.getClient(player_number)
  if client is None or not 'master' in client.state:
    return
  if beat != client.beat:
    beat = client.beat
    c.send_note(59+beat)
  newbpm = client.bpm*client.actual_pitch
  if bpm != newbpm:
    c.setBpm(newbpm)
    bpm = newbpm

p.set_client_change_callback(update_master)

try:
  p.start()
  p.vcdj_enable()
  c.start()
  p.join()
except KeyboardInterrupt:
  logging.info("Shutting down...")
  c.stop()
  p.stop()
