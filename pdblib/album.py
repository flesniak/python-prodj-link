from construct import Struct, Int8ul, Int16ul, Int32ul, Const, Padding, Tell, this
from .piostring import OffsetPioString

ALBUM_ENTRY_MAGIC = 0x80

Album = Struct(
  "entry_start" / Tell,
  "magic" / Const(ALBUM_ENTRY_MAGIC, Int16ul),
  "index_shift" / Int16ul,
  Padding(4),
  "album_artist_id" / Int32ul,
  "id" / Int32ul,
  Padding(4),
  "unknown" / Int8ul, # always 0x03, maybe an unindexed empty string
  "name_idx" / Int8ul,
  "name" / OffsetPioString(this.name_idx)
)
