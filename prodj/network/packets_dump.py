import logging

# dump functions for debugging
def dump_keepalive_packet(packet):
  if logging.getLogger().getEffectiveLevel() > 5:
    return
  if packet.subtype == "stype_status":
    logging.log(5, "keepalive {} model {} ({}) player {} ip {} mac {} devcnt {} u2 {} u3 {}".format(
      packet.subtype, packet.model, packet.device_type, packet.content.player_number, packet.content.ip_addr,
      packet.content.mac_addr, packet.content.device_count, packet.content.u2, packet.content.u3
    ))
  elif packet.subtype == "stype_ip":
    logging.log(5, "keepalive {} model {} ({}) player {} ip {} mac {} iteration {} assignment {} u2 {}".format(
      packet.subtype, packet.model, packet.device_type, packet.content.player_number, packet.content.ip_addr,
      packet.content.mac_addr, packet.content.iteration, packet.content.player_number_assignment, packet.content.u2
    ))
  elif packet.subtype == "stype_mac":
    logging.log(5, "keepalive {} model {} ({}) mac {} iteration {} u2 {}".format(
      packet.subtype, packet.model, packet.device_type, packet.content.mac_addr,
      packet.content.iteration, packet.content.u2
    ))
  elif packet.subtype == "stype_number":
    logging.log(5, "keepalive {} model {} ({}) proposed_player_number {} iteration {}".format(
      packet.subtype, packet.model, packet.device_type, packet.content.proposed_player_number,
      packet.content.iteration
    ))
  elif packet.subtype == "stype_hello":
    logging.log(5, "keepalive {} model {} ({}) u2 {}".format(
      packet.subtype, packet.model, packet.device_type, packet.content.u2
    ))
  else:
    logging.warning("BUG: unhandled packet type {}".format(packet.subtype))

def dump_beat_packet(packet):
  if logging.getLogger().getEffectiveLevel() > 5:
    return
  if packet.type == "type_beat":
      logging.log(5, "beat {} player {} actual_pitch {:.3f} bpm {:.2f} beat {} player2 {} distances {}".format(
      packet.model, packet.player_number, packet.content.pitch, packet.content.bpm, packet.content.beat,
      packet.content.player_number2, "/".join([str(y) for x,y in packet.content.distances.items()])
    ))

def dump_status_packet(packet):
  if logging.getLogger().getEffectiveLevel() > 5 or packet.type not in ["djm", "cdj"]:
    return
  logging.log(5, "type {} model \"{}\" pn {} u1 {} u2 {} u3 {}".format(packet.type, packet.model,
    packet.player_number, packet.u1, packet.u2, packet.extra.u3 if "u3" in packet.extra else "N/A"))
  logging.log(5, "state {} pitch {:.2f} bpm {} beat {} u5 {}".format(
    ",".join(x for x,y in packet.content.state.items() if y==True),
    packet.content.physical_pitch, packet.content.bpm, packet.content.beat, packet.content.u5))
  if packet.type == "cdj":
    logging.log(5, "active {} ldpn {} lds {} tat {} tid {} tn {} link {} tmc {} fw {} usb {}/{}".format(
      packet.content.activity, packet.content.loaded_player_number, packet.content.loaded_slot,
      packet.content.track_analyze_type, packet.content.track_id, packet.content.track_number, packet.content.link_available,
      packet.content.tempo_master_count, packet.content.firmware, packet.content.usb_state, packet.content.usb_active))
    logging.log(5, "pstate {} pstate2 {} pstate3 {} pitch {:.2f} {:.2f} {:.2f} {:.2f} bpm {} ({}) beat {}/{} cue {}".format(
      packet.content.play_state, packet.content.play_state2, packet.content.play_state3,
      packet.content.actual_pitch, packet.content.actual_pitch2, packet.content.physical_pitch, packet.content.physical_pitch2,
      packet.content.bpm, packet.content.bpm_state, packet.content.beat_count, packet.content.beat, packet.content.cue_distance))
    logging.log(5, "u5 {} u6 {} u7 {} u8 {} u9 {} u10 {} u11 {} is_nexus {:x}".format(packet.content.u5, packet.content.u6,
      packet.content.u7, packet.content.u8, packet.content.u9, packet.content.u10, packet.content.u11, packet.content.is_nexus))

def dump_packet_raw(data):
  # warning level to get message in case of decoding errors
  logging.warning(" ".join("{:02x}".format(b) for b in data))
