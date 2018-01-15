from construct import Struct, Int8ul, Int16ul, Int32ul, Const, Tell, this
from .piostring import OffsetPioString

ARTIST_ENTRY_MAGIC = 0x60

Artist = Struct(
  "entry_start" / Tell,
  "magic" / Const(Int16ul, ARTIST_ENTRY_MAGIC),
  "index_shift" / Int16ul,
  "id" / Int32ul,
  "unknown" / Int8ul, # always 0x03, maybe an unindexed empty string
  "name_idx" / Int8ul,
  "name" / OffsetPioString(this.name_idx)
)
