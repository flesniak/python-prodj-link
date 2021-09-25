from construct import Array, Const, GreedyRange, Int32ul, Padding, Struct, Tell
from .page import AlignedPage
from .pagetype import PageTypeEnum

FileHeaderEntry = Struct(
  "page_type" / PageTypeEnum,
  "empty_candidate" / Int32ul,
  "first_page" / Int32ul, # always points to a strange page, which then links to a real data page
  "last_page" / Int32ul
)

PDBFile = Struct(
  Padding(4), # always 0
  "page_size" / Const(4096, Int32ul),
  "page_entries" / Int32ul, # FileHeaderEntry follow, usually 20
  "next_unused_page" / Int32ul, # even unreferenced -> not used as any "empty_candidate", points "out of file"
  "unknown1" / Int32ul, # (5,4,4,1,1,1...)
  "sequence" / Int32ul, # sequence number, always incremented by 1 (sometimes 2/3)
  Padding(4), # always 0
  "entries" / Array(lambda ctx: ctx.page_entries, FileHeaderEntry),
  "length" / Tell, # usually 348 when page_entries=20
  Padding(lambda ctx: ctx.page_size-ctx.length),
  "pages" / GreedyRange(AlignedPage),
  "file_size" / Tell
)
