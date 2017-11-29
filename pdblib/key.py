from construct import Struct, Int32ul
from .piostring import PioString

Key = Struct(
  "id" / Int32ul,
  "id2" / Int32ul, # a duplicate of id
  "name" / PioString
)
