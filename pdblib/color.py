from construct import Struct, Int16ub, Padding
from .piostring import PioString

Color = Struct(
  Padding(4),
  "id" / Int16ub,
  Padding(2),
  "name" / PioString
)
