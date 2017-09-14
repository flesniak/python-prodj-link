import logging

# dump functions for debugging
def dump_keepalive_packet(packet):
  if logging.getLogger().getEffectiveLevel() > 5:
    return
  if packet["subtype"] == "stype_status":
    logging.log(5, "keepalive {} model {} ({}) player {} ip {} mac {} devcnt {} u2 {} u3 {}".format(
      packet["subtype"], packet["model"], packet["device_type"], packet["player_number"], packet["ip_addr"],
      packet["mac_addr"], packet["device_count"], packet["u2"], packet["u3"]
    ))
  elif packet["subtype"] == "stype_ip":
    logging.log(5, "keepalive {} model {} ({}) player {} ip {} mac {} iteration {} assignment {} u2 {}".format(
      packet["subtype"], packet["model"], packet["device_type"], packet["player_number"], packet["ip_addr"],
      packet["mac_addr"], packet["iteration"], packet["player_number_assignment"], packet["u2"]
    ))
  elif packet["subtype"] == "stype_mac":
    logging.log(5, "keepalive {} model {} ({}) mac {} iteration {} u2 {}".format(
      packet["subtype"], packet["model"], packet["device_type"], packet["mac_addr"],
      packet["iteration"], packet["u2"]
    ))
  elif packet["subtype"] == "stype_number":
    logging.log(5, "keepalive {} model {} ({}) proposed_player_number {} iteration {}".format(
      packet["subtype"], packet["model"], packet["device_type"], packet["proposed_player_number"],
      packet["iteration"]
    ))
  elif packet["subtype"] == "stype_hello":
    logging.log(5, "keepalive {} model {} ({}) u2 {}".format(
      packet["subtype"], packet["model"], packet["device_type"], packet["u2"]
    ))
  else:
    logging.warning("BUG: unhandled packet type {}".format(packet["subtype"]))

def dump_beat_packet(packet):
  if logging.getLogger().getEffectiveLevel() > 5:
    return
  if packet["type"] == "type_beat":
      logging.log(5, "beat {} player {} pitch {:.3f} bpm {:.2f} beat {} player2 {} distances {}".format(
      packet["model"], packet["player_number"], packet["pitch"], packet["bpm"], packet["beat"],
      packet["player_number2"], "/".join([str(y) for x,y in packet["distances"].items()])
    ))

def dump_status_packet(packet):
  if logging.getLogger().getEffectiveLevel() > 5 or packet["type"] not in ["djm", "cdj"]:
    return
  logging.log(5, "type {} model \"{}\" pn {} u1 {} u2 {} u3 {} u4 {}".format(packet["type"], packet["model"],
    packet["player_number"], packet["u1"], packet["u2"], packet["u3"], packet["u4"]))
  logging.log(5, "state {} pitch {:.2f} bpm {} beat {} u5 {}".format(
    ",".join(x for x,y in packet["state"].items() if y==True),
    packet["physical_pitch"], packet["bpm"], packet["beat"], packet["u5"]))
  if packet["type"] == "cdj":
    logging.log(5, "active {} ldpn {} lds {} tat {} tid {} tn {} link {} tmc {} fw {} usb {}/{}".format(
      packet["activity"], packet["loaded_player_number"], packet["loaded_slot"],
      packet["track_analyze_type"], packet["track_id"], packet["track_number"], packet["link_available"],
      packet["tempo_master_count"], packet["firmware"], packet["usb_state"], packet["usb_active"]))
    logging.log(5, "pstate {} pstate2 {} pstate3 {} pitch {:.2f} {:.2f} {:.2f} {:.2f} bpm {} ({}) beat {}/{} cue {}".format(
      packet["play_state"], packet["play_state2"], packet["play_state3"],
      packet["actual_pitch"], packet["actual_pitch2"], packet["physical_pitch"], packet["physical_pitch2"],
      packet["bpm"], packet["bpm_state"], packet["beat_count"], packet["beat"], packet["cue_distance"]))
    logging.log(5, "u5 {} u6 {} u7 {} u8 {} u9 {} u10 {} u11 {} u12 {}".format(packet["u5"], packet["u6"],
      packet["u7"], packet["u8"], packet["u9"], packet["u10"], packet["u11"], packet["u12"]))

def dump_packet_raw(data):
  # warning level to get message in case of decoding errors
  logging.warning(" ".join("{:02x}".format(b) for b in data))
