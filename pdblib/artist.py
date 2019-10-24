from construct import Struct, Int8ul, Int16ul, Int32ul, OneOf, IfThenElse, Tell, this
from .piostring import OffsetPioString

ARTIST_ENTRY_MAGIC = 0x60
LONG_ARTIST_ENTRY_MAGIC = 0x64

Artist = Struct(
  "entry_start" / Tell,
  "magic" / OneOf(Int16ul, [ARTIST_ENTRY_MAGIC, LONG_ARTIST_ENTRY_MAGIC]),
  "index_shift" / Int16ul,
  "id" / Int32ul,
  "unknown" / IfThenElse(this.magic == LONG_ARTIST_ENTRY_MAGIC, Int16ul, Int8ul), # always 0x03, maybe an unindexed empty string
  "name_idx" / IfThenElse(this.magic == LONG_ARTIST_ENTRY_MAGIC, Int16ul, Int8ul),
  "name" / OffsetPioString(this.name_idx)
)
