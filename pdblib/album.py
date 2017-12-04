from construct import Struct, Int16ul, Int32ul, Const, Padding
from .piostring import PioString

ALBUM_ENTRY_MAGIC = 0x80

Album = Struct(
  "magic" / Const(Int16ul, ALBUM_ENTRY_MAGIC),
  "index_shift" / Int16ul,
  Padding(4),
  "album_artist_id" / Int32ul,
  "id" / Int32ul,
  Padding(4),
  # maybe 0x03 is an empty string here
  "unknown" / Int16ul, # usually 0x1603, 0x0c03 for iso-8859 artist names
  "name" / PioString
)
