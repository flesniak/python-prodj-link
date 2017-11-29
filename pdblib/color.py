from construct import Struct, Int16ul, Padding
from .piostring import PioString

Color = Struct(
  Padding(4),
  "id" / Int16ul,
  Padding(2),
  "name" / PioString
)
