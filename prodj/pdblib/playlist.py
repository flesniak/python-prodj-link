from construct import Struct, Int32ul, Padding
from .piostring import PioString

Playlist = Struct(
  "folder_id" / Int32ul, # id of parent folder, 0 for root
  Padding(4),
  "sort_order" / Int32ul,
  "id" / Int32ul,
  "is_folder" / Int32ul, # 1 for folder, 0 for playlist
  "name" / PioString
)
