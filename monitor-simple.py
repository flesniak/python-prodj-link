#!/usr/bin/python3

import logging

from prodj import ProDj

default_loglevel=logging.DEBUG
#default_loglevel=logging.INFO
#default_loglevel=logging.WARNING

logging.basicConfig(level=default_loglevel, format='%(levelname)s: %(message)s')

def print_clients(cl, player_number):
  for c in cl.clients:
    if c.player_number == player_number:
      logging.info("Player {}: {} {} BPM Pitch {:.2f}% Beat {}".format(
        c.player_number, c.model, c.bpm, (c.pitch-1)*100, c.beat))

p = ProDj(print_clients)

try:
  p.start()
  p.vcdj_enable()
  p.join()
except KeyboardInterrupt:
  logging.info("Shutting down...")
  p.stop()
