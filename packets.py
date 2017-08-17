# based in part of:
# https://github.com/brunchboy/dysentery
# https://bitbucket.org/awwright/libpdjl

from construct import Adapter, Array, Byte, Const, CString, Default, Embedded, Enum, FlagsEnum, If, Int8ub, Int16ub, Int24ub, Int32ub, Padded, Padding, String, Struct, Switch, this

MacAddr = Array(6, Byte)
IpAddr = Array(4, Byte)

class IpAddrAdapter(Adapter):
  def _encode(self, obj, context):
    return list(map(int, obj.split(".")))
  def _decode(self, obj, context):
    return ".".join("{}".format(x) for x in obj)
IpAddr = IpAddrAdapter(Byte[4])

class MacAddrAdapter(Adapter):
  def _encode(self, obj, context):
    return list(int(x,16) for x in obj.split(":"))
  def _decode(self, obj, context):
    return ":".join("{:02x}".format(x) for x in obj)
MacAddr = MacAddrAdapter(Byte[6])

KeepAlivePacketType = Enum(Int8ub,
  type_hello = 0x0a,
  type_number = 0x04,
  type_mac = 0x00,
  type_ip = 0x02,
  type_status = 0x06,
  type_change = 0x08
)

KeepAlivePacketSubtype = Enum(Int8ub,
  stype_hello = 0x25,
  stype_number = 0x26,
  stype_mac = 0x2c,
  stype_ip = 0x32,
  stype_status = 0x36,
  stype_change = 0x29
)

DeviceType = Enum(Int8ub,
  djm = 1,
  cdj = 2,
  rekordbox = 3
)

PlayerNumberAssignment = Enum(Int8ub,
  auto = 1,
  manual = 2
)

# received on udp port 50000
KeepAlivePacket = Struct(
  "magic" / Const(String(10), b'Qspt1WmJOL'),
  "type" / KeepAlivePacketType, # pairs with subtype
  Padding(1),
  "model" / Padded(20, CString(encoding="ascii")),
  "u1" / Const(Int8ub, 1),
  "device_type" / Default(DeviceType, "cdj"),
  Padding(1),
  "subtype" / KeepAlivePacketSubtype,
  Embedded(Switch(this.type, {
    # type=0x0a, request for other players to propose a player number?
    "type_hello": Struct(
      "u2" / Const(Int8ub, 1)),
    # type=0x04, publishing a proposed player number, check if anyone else has it? iteration goes 1..2..3
    "type_number": Struct(
      "proposed_player_number" / Int8ub,
      "iteration" / Int8ub),
    # type=0x00, publishing mac address, iteration goes 1..2..3 again
    "type_mac": Struct(
      "iteration" / Int8ub,
      "u2" / Default(Int8ub, 1), # rekordbox has 4 here
      "mac_addr" / MacAddr),
    # type=0x02, publishing ip + mac, iteration goes 1..2..3 again
    "type_ip": Struct(
      "ip_addr" / IpAddr,
      "mac_addr" / MacAddr,
      "player_number" / Int8ub,
      "iteration" / Int8ub,
      "u2" / Default(Int8ub, 1), # rekordbox has 4 here
      "player_number_assignment" / Default(PlayerNumberAssignment, "manual")),
    # type=0x06, the standard keepalive packet
    "type_status": Struct(
      "player_number" / Int8ub,
      "u2" / Default(Int8ub, 1), # actual player number? sometimes other player's id, sometimes own id
      "mac_addr" / MacAddr,
      "ip_addr" / IpAddr,
      "device_count" / Default(Int8ub, 1), # number of known prodjlink devices
      Padding(2),
      "u3" / Default(Int16ub, 1)), # rekordbox has 4 here
    "type_change": Struct( # when changing player number
      "old_player_number" / Int8ub,
      "ip_addr" / IpAddr)
  }))
)

class PitchAdapter(Adapter):
  def _encode(self, obj, context):
    return obj*0x100000
  def _decode(self, obj, context):
    return obj/0x100000
Pitch = PitchAdapter(Int32ub)

class BpmAdapter(Adapter):
  def _encode(self, obj, context):
    return obj*100
  def _decode(self, obj, context):
    return obj/100
Bpm = BpmAdapter(Int16ub)

BeatPacketType = Enum(Int8ub,
  type_beat = 0x28
)

BeatPacketSubtype = Enum(Int8ub,
  stype_beat = 0x3c
)

# received on udp port 50001
BeatPacket = Struct(
  "magic" / Const(String(10), b'Qspt1WmJOL'),
  "type" / BeatPacketType, # pairs with subtype
  "model" / Padded(20, CString(encoding="ascii")),
  "u1" / Default(Int16ub, 256), # 256 for cdjs, 257 for rekordbox
  "player_number" / Int8ub,
  "u2" / Const(Int8ub, 0),
  "subtype" / BeatPacketSubtype,
  Embedded(Switch(this.type, {
    # type=0x28, the standard beat info packet
    "type_beat": Struct(
      # distances in ms to the next beat, 2nd next beat, next bar...
      "distances" / Struct(
        "next_beat" / Int32ub,
        "2nd_beat" / Int32ub,
        "next_bar" / Int32ub,
        "4th_beat" / Int32ub,
        "2nd_bar" / Int32ub,
        "8th_beat" / Int32ub
      ),
      Padding(24),
      "pitch" / Pitch,
      Padding(2), # always 0 except when scratching 0xff
      "bpm" / Bpm,
      "beat" / Int8ub,
      Padding(2), # always 0 except when scratching 0xff
      "player_number2" / Int8ub)
  }))
)

StatusPacketType = Enum(Int8ub,
  cdj = 0x0a,
  djm = 0x29
)

PlayerSlot = Enum(Int8ub,
  empty = 0,
  cd = 1,
  sd = 2,
  usb = 3,
  rekordbox = 4
)

TrackAnalyzeType = Enum(Int8ub,
  unknown = 0, # no track or unanalyzed
  rekordbox = 1, # rekordbox-analyzed track
  file = 2, # unanalyzed file on usb
  cd = 5
)

ActivityIndicator = Enum(Int8ub,
  inactive = 4,
  active = 6
)

StorageIndicator = Enum(Int32ub,
  loaded = 0,
  stopping = 2,
  unmounting = 3,
  not_loaded = 4
)

PlayState = Enum(Int32ub,
  no_track = 0x00,
  loading_track = 0x02,
  playing = 0x03,
  looping = 0x04,
  paused = 0x05, # paused anywhere other than cue point
  cued = 0x06, # paused at cue point
  cueing = 0x07, # playing from cue point = cue play
  cuescratch = 0x08, # cue play + touching platter
  seeking = 0x09,
  end_of_track = 0x11,
  emergency = 0x12 # emergency mode when losing connection
)

BpmState = Enum(Int16ub,
  unknown = 0x7fff, # no track or not analyzed
  rekordbox = 0x8000,
  cd = 0
)

class StateMaskAdapter(Adapter):
  def _encode(self, obj, context):
    return obj | 0x84 # add bits which are always 1
  def _decode(self, obj, context):
    return obj
StateMask = FlagsEnum(StateMaskAdapter(Int16ub),
  on_air = 8,
  sync = 16,
  master = 32,
  play = 64)

# received on udp port 50002
StatusPacket = Struct(
  "magic" / Const(String(10), b'Qspt1WmJOL'),
  "type" / StatusPacketType,
  "model" / Padded(20, CString(encoding="ascii")),
  "u1" / Const(Int8ub, 1),
  "u2" / Default(Int8ub, 4), # some kind of revision? 3 for cdj2000nx, 4 for xdj1000. 1 for djm/rekordbox
  "player_number" / Int8ub, # 0x11 for rekordbox
  "u3" / Default(Int16ub, 0xf8), # 0xb0 cdj2000nxs, 0xf8 xdj1000, 0x14 djm, 0x38 rekordbox
  "player_number2" / Int8ub, # equal to player_number
  "u4" / Default(Int8ub, 0), # 1 cdj2000nxs or 0 xdj1000, 0 for rekordbox
  Embedded(Switch(this.type, {
    "cdj": Struct(
      "activity" / Int16ub, # 0 when idle, 1 when playing, 0xc0 for rekordbox
      "loaded_player_number" / Int8ub, # player number of loaded track, own number if local track
      "loaded_slot" / PlayerSlot,
      "track_analyze_type" / TrackAnalyzeType,
      Padding(1),
      "track_id" / Int32ub, # rekordbox database id or cd track number
      "track_number" / Int32ub, # number in playlist or browse list
      "u5" / Default(Int32ub, 0), # 0 on start, 4 after loading track, 17 on unanalyzed track
      "u6" / Default(Int32ub, 0), # become != 0 when loading track, unknown
      "u7" / Default(Int32ub, 0), # become != 0 when loading track, unknown
      Padding(4), # always zero
      "u8" / Default(Int32ub, 0), # 0 on start, 4 after loading track, 1 on unanalyzed track
      Padding(32), # a lot of zero fields
      Const(Int16ub, 0x100),
      "usb_active" / Default(ActivityIndicator, "inactive"),
      "sd_active" / Default(ActivityIndicator, "inactive"),
      "usb_state" / Default(StorageIndicator, "not_loaded"), # having "loaded" makes them try to mount nfs
      "sd_state" / Default(StorageIndicator, "not_loaded"), # having "loaded" makes them try to mount nfs
      "link_available" / Default(Int32ub, 1), # may be cd state
      "play_state" / Default(PlayState, "no_track"),
      "firmware" / String(4, encoding="ascii"),
      # 0x80
      Padding(4), # always zero
      "tempo_master_count" / Default(Int32ub, 0), # how often a player changed its tempo master
      "state" / StateMask,
      "u9" / Default(Int8ub, 0xff), # counts from 0 up to 0xff after startup, then stays at 0xff
      "play_state2" / Int8ub, # xdj1000: 0xfe=stop, 0xfa=playing (also reverse), 2000nxs: 0x6e=stop, 0x6a=playing
      "actual_pitch" / Pitch,
      "bpm_state" / Default(BpmState, "rekordbox"),
      "bpm" / Bpm,
      Const(Int32ub, 0x7fffffff),
      "pitch" / Pitch, # physical pitch
      "play_state3" / Int16ub, # 0=empty, 1=paused/reverse/vinyl grab, 9=playing, 0xd=jog
      "u10" / Int8ub, # 1 for rekordbox analyzed tracks, 2 for unanalyzed mp3
      Const(Int8ub, 0xff),
      "beat_count" / Default(Int32ub, 0),
      "cue_distance" / Default(Int16ub, 0x1ff), # 0x1ff when no next cue, 0x100 for 64 bars (=256 beats)
      "beat" / Default(Int8ub, 1), # 1..4
      Padding(15),
      "u11" / Default(Int16ub, 0x1000), # 0x0100 for xdj1000, 0x1000 for cdj2000nxs
      Padding(8),
      "actual_pitch2" / Pitch,
      "physical_pitch2" / Pitch,
      "packet_count" / Default(Int32ub, 0), # permanently increasing
      "u12" / Default(Int8ub, 0x0f), # 0x0f=nexus, 0x05=non-nexus player
      Padding(7)),
    "djm": Struct(
      "state" / StateMask,
      "pitch" / Pitch,
      "u5" / Default(Int16ub, 0x8000),
      "bpm" / Bpm,
      Padding(7),
      "beat" / Default(Int8ub, 1), # 1..4
    )
  }))
)
