from construct import Struct, Int32ul
from .piostring import PioString

Genre = Struct(
  "id" / Int32ul,
  "name" / PioString
)
