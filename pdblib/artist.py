from construct import Struct, Int16ul, Int32ul, Const
from .piostring import PioString

ARTIST_ENTRY_MAGIC = 0x60

Artist = Struct(
  "magic" / Const(Int16ul, ARTIST_ENTRY_MAGIC),
  "index_shift" / Int16ul,
  "id" / Int32ul,
  # maybe 0x03 is an empty string here
  "unknown" / Int16ul, # usually 0x0a03, 0x0c03 for iso-8859 artist names
  "name" / PioString
)
