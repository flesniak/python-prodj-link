#!/usr/bin/python3

import curses
import logging

from prodj import ProDj
from logcurse import CursesHandler

default_loglevel=logging.DEBUG
default_loglevel=logging.INFO

# init curses
win = curses.initscr()
win.clear()
client_win = win.subwin(16, curses.COLS-1, 0, 0)
log_win = win.subwin(18, 0)
log_win.scrollok(True)
win.hline(17,0,"-",curses.COLS)
win.refresh()

# init logging
ch = CursesHandler(log_win)
ch.setFormatter(logging.Formatter(fmt='%(levelname)s: %(message)s'))
logging.basicConfig(level=default_loglevel, handlers=[ch])

def update_clients(client_win, cl):
  try:
    client_win.clear()
    client_win.addstr(0, 0, "Detected Pioneer devices:\n")
    if len(cl.clients) == 0:
      client_win.addstr("  No devices detected\n")
    else:
      for c in cl.clients:
        client_win.addstr("Player {}: {} {} BPM Pitch {:.2f}% Beat {}/{} NextCue {}\n".format(
          c.player_number, c.model if c.fw=="" else "{}({})".format(c.model,c.fw),
          c.bpm, (c.pitch-1)*100, c.beat, c.beat_count, c.cue_distance))
        if c.status_packet_received:
          client_win.addstr("  {} ({}) Track {} from Player {},{} Actual Pitch {:.2f}%\n".format(
            c.play_state, ",".join(c.state), c.track_number, c.loaded_player_number,
            c.loaded_slot, (c.actual_pitch-1)*100))
    client_win.refresh()
  except Exception as e:
    logging.critical(str(e))

p = ProDj(lambda cl, n: update_clients(client_win, cl))
update_clients(client_win, p.cl)

try:
  p.start()
  p.vcdj_enable()
  p.join()
except KeyboardInterrupt:
  logging.info("Shutting down...")
  p.stop()
#except:
#  curses.endwin()
#  raise
finally:
  curses.endwin()
