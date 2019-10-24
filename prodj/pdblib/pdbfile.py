from construct import Array, Embedded, GreedyRange, Struct, Tell
from .fileheader import FileHeader
from .page import AlignedPage

PDBFile = Struct(
  Embedded(FileHeader),
  "pages" / GreedyRange(AlignedPage),
  "file_size" / Tell
)
