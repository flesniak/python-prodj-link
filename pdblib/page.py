from construct import Sequence, Struct, Int8ul, Int16ul, Int32ul, Embedded, Switch, Const, Array, Padded, Padding, Pass, Computed, Tell, Pointer, this, Seek, Bitwise, Flag, ByteSwapped, BitsSwapped, FocusedSeq
from .pagetype import PageTypeEnum
from .track import Track
from .artist import Artist
from .album import Album
from .playlist import Playlist
from .playlist_map import PlaylistMap
from .artwork import Artwork
from .color import Color
from .genre import Genre
from .key import Key
from .label import Label

# a strange page exists for every (?) page type, header.u9 is 1004 and page is filled with 0xf8ffff1f
StrangePage = Struct(
  "strange_header" / Struct(
    "index" / Int32ul, # page index (same as header?)
    "next_index" / Int32ul, # index of next page containing real data or 0x3ffffff if next page empty
    Const(0x3fffffff, Int32ul),
    Padding(4),
    "entry_count" / Int16ul, # number of 4-byte values
    "u2" / Int16ul, # always 8191?
    ),
  Array(1004, Int32ul),
  Padding(20)
)

ReverseIndexedEntry = FocusedSeq(1,
  "entry_offset" / Int16ul,
  "entry" / Pointer(this._._.entries_start+this.entry_offset,
    Switch(lambda ctx: "strange" if ctx._._.is_strange_page else ctx._._.page_type, {
      "block_tracks": Track,
      "block_artists": Artist,
      "block_albums": Album,
      "block_playlists": Playlist,
      "block_playlist_map": PlaylistMap,
      "block_artwork": Artwork,
      "block_colors": Color,
      "block_genres": Genre,
      "block_keys": Key,
      "block_labels": Label,
      #"strange": StrangePage,
    }, default = Computed("page type not implemented")),
  )
)

# unfortunately, the entry_enabled field contains even unexistant entries:
# entry_enabled[:-1] matches revidx[:-1],
# but len(entry_enabled)==16 while len(revidx)<=16

FirstReverseIndexArray = Struct(
  "entries" / Array(this._._.entry_count%16, ReverseIndexedEntry),
  "entry_enabled" / ByteSwapped(Bitwise(Array(16, Flag))), # may start with unexistant entries, see above!
  "entry_enabled_override" / ByteSwapped(Bitwise(Array(16, Flag))) # may start with unexistant entries, see above!
)

FullReverseIndexArray = Struct(
  "entries" / Array(16, ReverseIndexedEntry),
  "entry_enabled" / ByteSwapped(Bitwise(Array(16, Flag))),
  "entry_enabled_override" / ByteSwapped(Bitwise(Array(16, Flag)))
)

PageEndHeader = Sequence(
  FirstReverseIndexArray,
  Embedded(Array(this._.entry_count//16, FullReverseIndexArray))
)

PageHeader = Struct( # 40 bytes
  Padding(4), # always 0
  "index" / Int32ul, # in units of 4096 bytes
  "page_type" / PageTypeEnum,
  "next_index" / Int32ul, # in units of 4096 bytes, finally points to empty page, even outside of file
  "u1" / Int32ul, # sequence number (0->1: 8->13, 1->2: 22, 2->3: 27)
  Padding(4),
  "real_entry_count" / Int8ul,
  "u3" / Int8ul, # a bitmask (1st track: 32)
  "u4" / Int8ul, # often 0, sometimes larger, esp. for pages with high real_entry_count (e.g. 12 for 101 entries)
  "u5" / Int8ul, # strange pages: 0x44, 0x64; otherwise seen: 0x24, 0x34
  "free_size" / Int16ul, # excluding data at page end
  "payload_size" / Int16ul,
  "u7" / Int16ul, # (0->1: 2)
  "alternative_entry_count" / Int16ul, # usually <= entry_count except for playlist_map?
  "u9" / Int16ul, # 1004 for strange blocks, 0 otherwise
  "u10" / Int16ul, # always 0 except 1 for synchistory, entry count for strange pages?
  "is_strange_page" / Computed(lambda ctx: ctx.index != 0 and ctx.u5 & 0x40),
  "is_empty_page" / Computed(lambda ctx: ctx.index == 0 and ctx.u9 == 0),
  # this is fishy: artwork and playlist_map pages have much more entries than set in real_entry_count
  # so use the alternative_entry_count if applicable, but ignore if it is 8191
  # there are even some normal track pages where alternative_entry_count is 8191, so catch this as well
  "entry_count" / Computed(lambda ctx: ctx.alternative_entry_count if ctx.real_entry_count < ctx.alternative_entry_count and not ctx.is_strange_page and not ctx.is_empty_page and not ctx.alternative_entry_count == 8191 else ctx.real_entry_count)
  #"entry_count" / Computed(this.real_entry_count)
)

AlignedPage = Struct(
  "page_start" / Tell,
  Embedded(PageHeader),
  "entries_start" / Tell, # reverse index is relative to this position
  # this expression jumps to the end of the section and parses the reverse index
  # TODO: calculation does not work on block_playlist_map
  "entry_list" / Pointer(this.page_start+4096-4*(this.entry_count//16+1)-this.entry_count*2, PageEndHeader),
  "page_end" / Tell,
  Seek(this.page_start+0x1000) # DEBUG: always jump to next page
)
