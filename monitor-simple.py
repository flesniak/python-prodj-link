#!/usr/bin/python3

import logging
import time

from prodj import ProDj

default_loglevel=0
#default_loglevel=logging.DEBUG
default_loglevel=logging.INFO
#default_loglevel=logging.WARNING

logging.basicConfig(level=default_loglevel, format='%(levelname)s: %(message)s')

def print_clients(cl, player_number):
  for c in cl.clients:
    if c.player_number == player_number:
      logging.info("Player {}: {} {} BPM Pitch {:.2f}% Beat {}".format(
        c.player_number, c.model, c.bpm, (c.pitch-1)*100, c.beat))

def print_metadata(player_number, md):
  logging.info("Player {} playing {} - {} ({}) {}:{} {} BPM".format(player_number,
    md["artist"], md["title"], md["album"], md["duration"]//60, md["duration"]%60, md["bpm"]))

p = ProDj()
p.set_client_keepalive_callback(print_clients)
p.set_client_change_callback(print_clients)
p.set_metadata_change_callback(print_metadata)

try:
  p.start()
  p.vcdj_set_player_number(5)
  p.vcdj_enable()
  p.join()
except KeyboardInterrupt:
  logging.info("Shutting down...")
  p.stop()
