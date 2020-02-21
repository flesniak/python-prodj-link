# based in part of:
# https://github.com/brunchboy/dysentery
# https://bitbucket.org/awwright/libpdjl

from construct import Adapter, Array, Byte, Const, CString, Default, Enum, ExprAdapter, FlagsEnum, FocusedSeq, GreedyBytes, GreedyRange, Int8ub, Int16ub, Int32ub, Int64ub, Int16ul, Int32ul, Padded, Padding, Pass, PascalString, PaddedString, Prefixed, Rebuild, Struct, Subconstruct, Switch, this, len_

class IpAddrAdapter(Adapter):
  def _encode(self, obj, context, path):
    return list(map(int, obj.split(".")))
  def _decode(self, obj, context, path):
    return ".".join("{}".format(x) for x in obj)
IpAddr = IpAddrAdapter(Byte[4])

class MacAddrAdapter(Adapter):
  def _encode(self, obj, context, path):
    return list(int(x,16) for x in obj.split(":"))
  def _decode(self, obj, context, path):
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
  stype_change = 0x29,
  stype_status_mixer = 0x00 # djm 900 nxs sends this stype on type_status
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

UdpMagic = Const("Qspt1WmJOL", PaddedString(10, encoding="ascii"))

# received on udp port 50000
KeepAlivePacket = Struct(
  "magic" / UdpMagic,
  "type" / KeepAlivePacketType, # pairs with subtype
  Padding(1),
  "model" / Padded(20, CString(encoding="ascii")),
  "u1" / Const(1, Int8ub),
  "device_type" / Default(DeviceType, "cdj"),
  Padding(1),
  "subtype" / KeepAlivePacketSubtype,
  "content" / Switch(this.type, {
    # type=0x0a, request for other players to propose a player number?
    "type_hello": Struct(
      "u2" / Default(Int8ub, 1)), # cdjs send 1, djm900nxs sends 3
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
  })
)

class PitchAdapter(Adapter):
  def _encode(self, obj, context, path):
    return obj*0x100000
  def _decode(self, obj, context, path):
    return obj/0x100000
Pitch = PitchAdapter(Int32ub)

class BpmAdapter(Adapter):
  def _encode(self, obj, context, path):
    return obj*100
  def _decode(self, obj, context, path):
    return obj/100
Bpm = BpmAdapter(Int16ub)

BeatPacketType = Enum(Int8ub,
  type_beat = 0x28,
  type_mixer = 0x03,
  type_mixer_unknown = 0x04, # some kind of "hello" packet sent by djm900nxs2
  type_fader_start = 0x02
)

BeatPacketSubtype = Enum(Int8ub,
  stype_beat = 0x3c,
  stype_mixer = 0x09,
  stype_mixer_unknown = 0x40,
  stype_fader_start = 0x04
)

FaderStartCommand = Enum(Int8ub,
  start = 0,
  stop = 1,
  ignore = 2
)

# received on udp port 50001
BeatPacket = Struct(
  "magic" / UdpMagic,
  "type" / BeatPacketType, # pairs with subtype
  "model" / Padded(20, CString(encoding="ascii")),
  "u1" / Default(Int16ub, 256), # 256 for cdjs, 257 for rekordbox
  "player_number" / Int8ub,
  "u2" / Const(0, Int8ub),
  "subtype" / BeatPacketSubtype,
  "content" / Switch(this.type, {
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
      "player_number2" / Int8ub),
    # type=0x03, a nxs mixer status packet containing on_air data
    "type_mixer": Struct(
      "ch_on_air" / Array(4, Int8ub)),
    # type=0x40, unknown mixer beat info packet
    "type_mixer_unknown": Struct(
      "u3" / Int8ub, # counts 0x14, 0x24, 0x34, 0x44
      "player_number2" / Int8ub),
    # type=0x04,
    "type_fader_start": Struct(
      "player" / Array(4, FaderStartCommand))
  })
)

StatusPacketType = Enum(Int8ub,
  cdj = 0x0a,
  djm = 0x29,
  load_cmd = 0x19,
  load_cmd_reply = 0x1a,
  link_query = 0x05,
  link_reply = 0x06,
  rekordbox_hello = 0x10, # sent by players to rekordbox
  rekordbox_reply = 0x11 # sent by rekordbox in reply to rekordbox_hello
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
  cannot_play_track = 0x0e,
  end_of_track = 0x11,
  emergency = 0x12 # emergency mode when losing connection
)
PlayStateStopped = [
  "cued", "paused",
  "cannot_play_track", "end_of_track", "emergency"
]
PlayStatePlaying = [
  "playing", "cueing", "looping"
]

BpmState = Enum(Int16ub,
  unknown = 0x7fff, # no track or not analyzed
  rekordbox = 0x8000,
  cd = 0
)

class StateMaskAdapter(Adapter):
  def _encode(self, obj, context, path):
    return obj | 0x84 # add bits which are always 1
  def _decode(self, obj, context, path):
    return obj
StateMask = FlagsEnum(StateMaskAdapter(Int16ub),
  on_air = 8,
  sync = 16,
  master = 32,
  play = 64)

# received on udp port 50002
StatusPacket = Struct(
  "magic" / UdpMagic,
  "type" / StatusPacketType,
  "model" / Padded(20, CString(encoding="ascii")),
  "u1" / Const(1, Int8ub),
  "u2" / Default(Int8ub, 4), # some kind of revision? 3 for cdj2000nx, 4 for xdj1000. 1 for djm/rekordbox, 0 for link query
  "player_number" / Int8ub, # 0x11 for rekordbox
  # 34 bytes until now
  "extra" / Switch(this.type, {
    "link_query": Struct(
      "u3" / Default(Int16ub, 0x0c),
      "source_ip" / IpAddr),
    "rekordbox_hello": Struct("payload_size" / Int16ub), # always 0 till now
    "link_reply": Struct("payload_size" / Int16ub), # always 0x9c
  }, default=Struct(
    "u3" / Default(Int16ub, 0xf8), # b0 cdj2000nxs, f8 xdj1000, 14 djm, 34/38 rekordbox, 104 rdbx_reply
    "player_number2" / Rebuild(Int8ub, this._.player_number), # equal to player_number
    "u4" / Default(Int8ub, 0) # 1 cdj2000nxs or 0 xdj1000, 0 for rekordbox))
  )),
  # default: 38 bytes until now
  "content" / Switch(this.type, {
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
      Default(Int16ub, 0x100), # 0x100 for xdj1000, 0x300 for cdj2000nxs
      "usb_active" / Default(ActivityIndicator, "inactive"),
      "sd_active" / Default(ActivityIndicator, "inactive"),
      "usb_state" / Default(StorageIndicator, "not_loaded"), # having "loaded" makes them try to mount nfs
      "sd_state" / Default(StorageIndicator, "not_loaded"), # having "loaded" makes them try to mount nfs
      "link_available" / Default(Int32ub, 1), # may be cd state
      "play_state" / Default(PlayState, "no_track"),
      "firmware" / PaddedString(4, encoding="ascii"),
      # 0x80
      Padding(4), # always zero
      "tempo_master_count" / Default(Int32ub, 0), # how often a player changed its tempo master
      "state" / StateMask,
      "u9" / Default(Int8ub, 0xff), # counts from 0 up to 0xff after startup, then stays at 0xff
      "play_state2" / Int8ub, # xdj1000: 0xfe=stop, 0xfa=playing (also reverse), 2000nxs: 0x6e=stop, 0x6a=playing
      "physical_pitch" / Pitch, # the pitch slider position,
      "bpm_state" / Default(BpmState, "rekordbox"),
      "bpm" / Bpm,
      "u13" / Default(Int32ub, 0x7fffffff), # is default most of the time, but also seen 0x800043f8
      "actual_pitch" / Pitch, # the actual pitch the player is currently playing
      "play_state3" / Int16ub, # 0=empty, 1=paused/reverse/vinyl grab, 9=playing, 0xd=jog
      "u10" / Default(Int8ub, 1), # 1 for rekordbox analyzed tracks, 2 for unanalyzed mp3
      Default(Int8ub, 0xff), # often 0xff, sometimes player_number of another player
      "beat_count" / Default(Int32ub, 0),
      "cue_distance" / Default(Int16ub, 0x1ff), # 0x1ff when no next cue, 0x100 for 64 bars (=256 beats)
      "beat" / Default(Int8ub, 1), # 1..4
      Padding(15),
      "u11" / Default(Int16ub, 0x1000), # 0x0100 for xdj1000, 0x1000 for cdj2000nxs
      Padding(8),
      "physical_pitch2" / Pitch,
      "actual_pitch2" / Pitch,
      "packet_count" / Default(Int32ub, 0), # permanently increasing
      "is_nexus" / Default(Int8ub, 0x0f), # 0x0f=nexus, 0x05=non-nexus player
      Padding(3)),
      # 4 bytes padding for 2000nxs or newer, cdj2000 does not have this
    "djm": Struct(
      "state" / StateMask,
      "physical_pitch" / Pitch,
      "u5" / Default(Int16ub, 0x8000),
      "bpm" / Bpm,
      Padding(7),
      "beat" / Default(Int8ub, 1), # 1..4
    ),
    "load_cmd": Struct(
      Padding(2),
      "load_player_number" / Int8ub, # 0x11 for rekordbox
      "load_slot" / PlayerSlot,
      "u5" / Const(0x100, Int16ub),
      "load_track_id" / Int32ub,
      "u6" / Default(Int32ub, 0x32),
      Padding(16),
      "u7" / Default(Int32ub, 0),
      "u8" / Default(Int32ub, 0),
      "u9" / Default(Int32ub, 0),
      Padding(8)
    ),
    "load_cmd_reply": Struct(
      Padding(2)
    ),
    "link_query": Struct(
      Padding(3),
      "remote_player_number" / Int8ub,
      Padding(3),
      "slot" / PlayerSlot
    ),
    "link_reply": Struct(
      Padding(3),
      "source_player_number" / Int8ub,
      Padding(3),
      "slot" / PlayerSlot,
      "name" / PaddedString(64, encoding="utf-16-be"),
      "date" / PaddedString(24, encoding="utf-16-be"),
      "u5" / PaddedString(32, encoding="utf-16-be"), # "1000" as string? model?
      "track_count" / Int32ub,
      "u6" / Default(Int16ub, 0), # also seen 0x200
      "u7" / Default(Int16ub, 0x101),
      "playlist_count" / Int32ub,
      "bytes_total" / Int64ub,
      "bytes_free" / Int64ub
    ),
    "rekordbox_hello": Pass,
    "rekordbox_reply": Struct(
      Padding(2),
      "name" / PaddedString(256, encoding="utf-16-be")
    ),
  })
)

DBServerQueryPort = 12523
DBServerQuery = Struct(
  "magic" / Const(0x0f, Int32ub),
  "query" / Const("RemoteDBServer", CString(encoding="ascii"))
)
DBServerReply = Int16ub

DBFieldType = Enum(Int8ub,
  int8 = 0x0f,
  int16 = 0x10,
  int32 = 0x11,
  binary = 0x14,
  string = 0x26
)

DBField = Struct(
  "type" / DBFieldType,
  "value" / Switch(this.type, {
    "int8": Int8ub,
    "int16": Int16ub,
    "int32": Int32ub,
    "string" : FocusedSeq("str",
      "str" / PascalString(ExprAdapter(Int32ub, encoder=lambda obj,ctx: obj//2+1, decoder=lambda obj,ctx: (obj-1)*2), encoding="utf-16-be"),
      "pad" / Padding(2)),
    "binary": Prefixed(Int32ub, GreedyBytes) # parses to byte string
  })
)

class DBFieldFixedAdapter(Adapter):
  def __init__(self, subcon, ftype):
    self.ftype = ftype
    super().__init__(subcon)
  def _encode(self, obj, context, path):
    return {"type": self.ftype, "value": obj}
  def _decode(self, obj, context, path):
    if obj["type"] != self.ftype:
      raise TypeError("Parsed type {} but expected {}".format(obj["type"], self.ftype))
    return obj["value"]
DBFieldFixed = lambda x: DBFieldFixedAdapter(DBField, x)

DBMessageFieldType = Enum(Int8ub,
  int8 = 0x04,
  int16 = 0x05,
  int32 = 0x06,
  binary = 0x03,
  string = 0x02
)

class ArgumentTypes(Subconstruct):
  def __init__(self, subcon):
    super().__init__(subcon)
    self.flagbuildnone = True
  def _parse(self, stream, context, path):
    subobj = self.subcon._parse(stream, context, path)
    return [DBMessageFieldType.parse(bytes([x])) for x in subobj if x != 0]
  def _build(self, obj, stream, context, path):
    arg_types = b"".join([DBMessageFieldType.build(x["type"]) for x in context.args])
    return self.subcon._build(arg_types[:12] + b"\x00"*(12-len(arg_types)), stream, context, path)
  def _sizeof(self, context, path):
    raise 17
ArgumentTypesField = ArgumentTypes(DBFieldFixed("binary"))

DBRequestType = Enum(DBFieldFixed("int16"),
  setup = 0,
  invalid = 1,
  invalid2 = 0x100, # sent by nxs2 players as reply to player_number=0 requests
  # list requests, cascading by appending id parameters
  root_menu_request = 0x1000,
  genre_request = 0x1001,
  artist_request = 0x1002,
  album_request = 0x1003,
  title_request = 0x1004,
  bpm_request = 0x1006,
  rating_request = 0x1007,
  century_request = 0x1008, # entries 2000, 1990, ...
  label_request = 0x100a,
  color_request = 0x100d,
  duration_request = 0x1010, # entries in minutes
  bitrate_request = 0x1011,
  history_request = 0x1012,
  filename_request = 0x1013,
  artist_by_genre_request = 0x1101,
  album_by_artist_request = 0x1102,
  title_by_album_request = 0x1103,
  playlist_request = 0x1105,
  year_by_century_request = 0x1108,
  artist_by_label_request = 0x110a,
  title_by_color_request = 0x110d,
  title_by_duration_request = 0x1110, # parameter in minutes
  title_by_bitrate_request = 0x1111,
  title_by_history_request = 0x1112,
  album_by_genre_artist_request = 0x1201,
  title_by_artist_album_request = 0x1202,
  title_by_bpm_request = 0x1206,
  title_by_century_year_request = 0x1208,
  album_by_label_artist_request = 0x120a,
  title_by_genre_artist_album_request = 0x1301,
  original_artist_request = 0x1302,
  title_by_label_artist_album_request = 0x130a,
  album_by_original_artist_request = 0x1402,
  title_by_original_artist_album_request = 0x1502,
  remixer_request = 0x1602,
  album_by_remixer_request = 0x1702,
  title_by_remixer_album_request = 0x1802,
  # track specific requests
  hot_cue_bank_request = 0x2001,
  metadata_request = 0x2002,
  artwork_request = 0x2003,
  preview_waveform_request = 0x2004,
  folder_request = 0x2006, # wtf, one list request here? params: 0, 0xffffffff, 0
  mount_info_request = 0x2102, # contains absolute storage path (nfs) among other data
  cues_request = 0x2104,
  track_info_request = 0x2202, # metadata of unanalyzed data (i.e. cd or folder view)
  beatgrid_request = 0x2204,
  unknown1_request = 0x2504, # issued when loading track, reply 0x4502, contains lots of 0 and some data at end
  waveform_request = 0x2904,
  unknown2_request = 0x2b04, # issued when loading track, reply 0x4e02, no render request
  nxs2_ext_request = 0x2c04, # nxs2 ext request, seen with PWV4, PWV5, PVB2, PQT2
  render = 0x3000,
  unknown3_request = 0x3100, # issued when loading track, reply 0x4000 with 0 items, never seen >0 items
  success = 0x4000,
  menu_header = 0x4001,
  artwork = 0x4002,
  invalid_request = 0x4003, # guessed?
  menu_item = 0x4101,
  menu_footer = 0x4201,
  preview_waveform = 0x4402,
  unknown1 = 0x4502,
  beatgrid = 0x4602,
  cues = 0x4702,
  waveform = 0x4a02,
  unknown2 = 0x4e02,
  nxs2_ext = 0x4f02 # nxs2 ext response
)

DBMessage = Struct(
  "magic" / Const(0x872349ae, DBFieldFixed("int32")),
  "transaction_id" / Default(DBFieldFixed("int32"), 1),
  "type" / DBRequestType,
  "argument_count" / Rebuild(DBFieldFixed("int8"), len_(this.args)),
  "arg_types" / ArgumentTypesField,
  "args" / Array(this.argument_count, DBField)
)

ManyDBMessages = GreedyRange(DBMessage)

Beatgrid = Struct(
  Padding(4),
  "beat_count" / Int32ul,
  "payload_size" / Int32ul, # bytes
  "u1" / Default(Int32ul, 1),
  "u2" / Int16ul,
  "u3" / Int16ul,
  "beats" / Array(this.beat_count, Struct(
    "beat" / Int16ul, # beat in measure 1..4
    "bpm_100" / Int16ul, # bpm may change dynamically on each beat
    "time" / Int32ul, # time in ms from start
    Padding(8) # 8 times 0xff
  ))
)

# ids for sending nxs2_ext_request packets
Nxs2RequestIds = {
  "4VWP": 0x34565750, # colored preview waveform
  "5VWP": 0x35565750, # colored waveform
  "TXE": 0x00545845
}
