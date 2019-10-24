#!/usr/bin/env python3

import logging
import time

from prodj.core.prodj import ProDj

default_loglevel=0
default_loglevel=logging.DEBUG
#default_loglevel=logging.INFO
#default_loglevel=logging.WARNING

logging.basicConfig(level=default_loglevel, format='%(levelname)s: %(message)s')

p = ProDj()

def print_clients(player_number):
  return
  for c in p.cl.clients:
    if c.player_number == player_number:
      logging.info("Player {}: {} {} BPM Pitch {:.2f}% ({:.2f}%) Beat {} Beatcnt {} pos {:.6f}".format(
        c.player_number, c.model, c.bpm, (c.pitch-1)*100, (c.actual_pitch-1)*100, c.beat, c.beat_count,
        c.position if c.position is not None else 0))

def print_metadata(player_number, md):
  logging.info("Player {} playing {} - {} ({}) {}:{} {} BPM".format(player_number,
    md["artist"], md["title"], md["album"], md["duration"]//60, md["duration"]%60, md["bpm"]))

def print_menu(request, player_number, slot, reply):
  logging.info("Root Menu:")
  for entry in reply:
    logging.info("  {}".format(entry))

def print_list(request, player_number, slot, query_ids, reply):
  logging.info("List entries:")
  for track in reply:
    s = ""
    for label, content in track.items():
      s += "{}: \"{}\" ".format(label, content)
    logging.info("  {}".format(s))

p.set_client_keepalive_callback(print_clients)
p.set_client_change_callback(print_clients)

try:
  p.start()
  p.cl.auto_request_beatgrid = False # we do not need beatgrids, but usually this doesnt hurt
  p.vcdj_set_player_number(5)
  p.vcdj_enable()
  time.sleep(5)
  p.data.get_root_menu(2, "usb", print_menu)
  p.data.get_titles(2, "usb", "album", print_list)
  #p.data.get_titles_by_album(2, "usb", 16, "bpm", print_list)
  #p.data.get_playlists(2, "usb", 0, print_list)
  #p.data.get_playlist(2, "usb", 0, 12, "default", print_list)
  #p.data.get_artists(2, "usb", "default", print_list)
  #p.vcdj.command_load_track(1, 2, "usb", 650)
  #p.vcdj.query_link_info(2, "usb")
  p.data.get_track_info(2, "usb", 0x7bc6, print_list)
  p.join()
except KeyboardInterrupt:
  logging.info("Shutting down...")
  p.stop()
