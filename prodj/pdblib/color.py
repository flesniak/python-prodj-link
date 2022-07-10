from construct import Struct, Int8ul, Padding
from .piostring import PioString

Color = Struct(
  Padding(4),
  "id_dup" / Int8ul, # set on some dbs, equals id
  "id" / Int8ul,
  Padding(2),
  "name" / PioString
)
