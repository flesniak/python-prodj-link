#!/usr/bin/env python3

import logging
import sys
import argparse

from prodj.core.prodj import ProDj

parser = argparse.ArgumentParser(description='Python ProDJ Link Midi Clock')
notes_group = parser.add_mutually_exclusive_group()
notes_group.add_argument('-n', '--notes', action='store_true', help='Send four different note on events depending on the beat')
notes_group.add_argument('-s', '--single-note', action='store_true', help='Send the same note on event on every beat')
parser.add_argument('-l', '--list-ports', action='store_true', help='List available midi ports')
parser.add_argument('-d', '--device', help='MIDI device to use (default: first available device)')
parser.add_argument('-p', '--port', help='MIDI port to use (default: 0)', type=int, default=0)
parser.add_argument('-q', '--quiet', action='store_const', dest='loglevel', const=logging.WARNING, help='Display warning messages only', default=logging.INFO)
parser.add_argument('-D', '--debug', action='store_const', dest='loglevel', const=logging.DEBUG, help='Display verbose debugging information')
parser.add_argument('--note-base', type=int, default=60, help='Note value for first beat')
parser.add_argument('--rtmidi', action='store_true', help='Use deprecated rtmidi backend with timing issues')
args = parser.parse_args()

logging.basicConfig(level=args.loglevel, format='%(levelname)s: %(message)s')

if args.rtmidi:
  from prodj.midi.midiclock_rtmidi import MidiClock
else:
  from prodj.midi.midiclock_alsaseq import MidiClock

c = MidiClock()

if args.list_ports:
  for id, name, ports in c.iter_alsa_seq_clients():
    logging.info("MIDI device %d: %s, ports: %s",
      id, name, ', '.join([str(x) for x in ports]))
  sys.exit(0)

c.open(args.device, args.port)

p = ProDj()
p.cl.log_played_tracks = False
p.cl.auto_request_beatgrid = False

bpm = 128 # default bpm until reported from player
beat = 0
c.setBpm(bpm)

def update_master(player_number):
  global bpm, beat, p
  client = p.cl.getClient(player_number)
  if client is None or not 'master' in client.state:
    return
  if (args.notes or args.single_notes) and beat != client.beat:
    note = args.base_note
    if args.notes:
      note += client.beat
    c.send_note(note)
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
