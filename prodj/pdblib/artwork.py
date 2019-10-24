from construct import Struct, Int32ul
from .piostring import PioString

Artwork = Struct(
  "id" / Int32ul,
  "path" / PioString
)
