from construct import Struct, Int32ul

PlaylistMap = Struct(
  "entry_index" / Int32ul,
  "track_id" / Int32ul,
  "playlist_id" / Int32ul
)
