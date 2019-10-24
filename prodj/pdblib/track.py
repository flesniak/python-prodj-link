from construct import Struct, Int8ul, Int16ul, Int32ul, Array, Const, Tell, Default
from .piostring import PioString, IndexedPioString

TRACK_ENTRY_MAGIC = 0x24

Track = Struct(
  "entry_start" / Tell,
  "magic" / Const(TRACK_ENTRY_MAGIC, Int16ul),
  "index_shift" / Int16ul, # the index inside the page <<5 (0x00, 0x20, 0x40, ...)
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
  "duration" / Int16ul,
  "u4" / Int16ul, # always 41?
  "color_id" / Int8ul,
  "rating" / Int8ul,
  "u5" / Default(Int16ul, 1), # always 1?
  "u6" / Int16ul, # alternating 2 or 3
  "str_idx" / Array(21, Int16ul),
  "str_u1" / IndexedPioString(0), # empty
  "texter" / IndexedPioString(1),
  "str_u2" / IndexedPioString(2), # thought tracknumber -> wrong!
  "str_u3" / IndexedPioString(3), # strange strings, often zero length, sometimes low binary values 0x01/0x02 as content
  "str_u4" / IndexedPioString(4), # strange strings, often zero length, sometimes low binary values 0x01/0x02 as content
  "message" / IndexedPioString(5),
  "kuvo_public" / IndexedPioString(6), # "ON" or empty
  "autoload_hotcues" / IndexedPioString(7), # "ON" or empty
  "str_u5" / IndexedPioString(8), # 8
  "str_u6" / IndexedPioString(9), # empty
  "date_added" / IndexedPioString(10),
  "release_date" / IndexedPioString(11),
  "mix_name" / IndexedPioString(12),
  "str_u7" / IndexedPioString(13), # empty
  "analyze_path" / IndexedPioString(14),
  "analyze_date" / IndexedPioString(15),
  "comment" / IndexedPioString(16),
  "title" / IndexedPioString(17),
  "str_u8" / IndexedPioString(18), # always empty; only in newer versions?
  "filename" / IndexedPioString(19),
  "path" / IndexedPioString(20)
)
