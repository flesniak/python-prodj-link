from construct import Struct, Int8ul, Int16ul, Int32ul, Array, Const, Padding, Tell
from .piostring import PioString

TRACK_ENTRY_MAGIC = 0x24

Track = Struct(
  "magic" / Const(Int16ul, TRACK_ENTRY_MAGIC),
  "index_shift" / Int16ul,
  "bitmask" / Int32ul,
  "sample_rate" / Int32ul,
  "composer_index" / Int32ul,
  "file_size" / Int32ul,
  "u1" / Int32ul, # some id?
  "u2" / Int16ul, # always 19048?
  "u3" / Int16ul, # always 30967?
  "artwork_id" / Int32ul,
  "key_id" / Int32ul, # not sure
  "original_artist_id" / Int32ul,
  "label_id" / Int32ul,
  "remixer_id" / Int32ul,
  "bitrate" / Int32ul,
  "track_number" / Int32ul,
  "bpm_100" / Int32ul,
  "genre_id" / Int32ul,
  "album_id" / Int32ul, # album artist is set in album entry
  "artist_id" / Int32ul,
  "id" / Int32ul, # the rekordbox track id
  "disc_number" / Int16ul,
  "play_count" / Int16ul,
  "year" / Int16ul,
  "sample_depth" / Int16ul, # not sure
  "length_seconds" / Int16ul,
  "u9" / Int16ul, # always 41?
  "color_id" / Int8ul,
  "rating" / Int8ul,
  "unknown_arr" / Array(23, Int16ul),
  "str_u1" / PioString, # empty
  "texter" / PioString,
  "u9.5" / PioString, # thought tracknumber -> wrong!
  "u10" / PioString, # strange strings, often zero length, sometimes low binary values 0x01/0x02 as content
  "u11" / PioString, # strange strings, often zero length, sometimes low binary values 0x01/0x02 as content
  "message" / PioString,
  "unknown_switch" / PioString, # "ON" or empty
  "autoload_hotcues" / PioString, # "ON" or empty
  "str_u2" / PioString, # empty
  "str_u3" / PioString, # empty
  "date_added" / PioString,
  "release_date" / PioString,
  "mix_name" / PioString,
  "str_u4" / PioString, # empty
  "analyze_path" / PioString,
  "analyze_date" / PioString,
  "comment" / PioString,
  "title" / PioString,
  "u12" / PioString, # always empty; only in newer versions?
  "filename" / PioString,
  "path" / PioString,
  "end" / Tell,
)
