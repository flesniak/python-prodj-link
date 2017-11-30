from construct import Enum, Int32ul

PageTypeEnum = Enum(Int32ul,
  block_tracks = 0,
  block_genres = 1,
  block_artists = 2,
  block_albums = 3,
  block_labels = 4,
  block_keys = 5,
  block_colors = 6,
  block_playlists = 7,
  block_playlist_map = 8,
  block_unknown4 = 9,
  block_unknown5 = 10,
  block_unknown6 = 11,
  block_unknown7 = 12,
  block_artwork = 13,
  block_unknown8 = 14,
  block_unknown9 = 15,
  block_columns = 16,
  block_unknown1 = 17,
  block_unknown2 = 18,
  block_synchistory = 19
)
