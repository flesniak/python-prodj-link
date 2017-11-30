from construct import Struct, Int32ul
from .piostring import PioString

Label = Struct(
  "id" / Int32ul,
  "name" / PioString
)
