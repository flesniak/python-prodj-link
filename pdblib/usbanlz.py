from construct import Array, Const, Default, Enum, GreedyRange, Int8sb, Int8ub, Int16ub, Int32ub, Padding, PrefixedArray, PaddedString, Struct, Switch, this

# file format from https://reverseengineering.stackexchange.com/questions/4311/help-reversing-a-edb-database-file-for-pioneers-rekordbox-software

AnlzTagPath = Struct(
  "payload_size" / Int32ub, # is 0 for some tag types
  "path" / PaddedString(this.payload_size-2, encoding="utf-16-be"),
  Padding(2)
)

AnlzTagVbr = Struct(
  Padding(4),
  "idx" / Array(400, Int32ub),
  "unknown" / Int32ub
)

AnlzQuantizeTick = Struct(
  "beat" / Int16ub,
  "bpm_100" / Int16ub,
  "time" / Int32ub # in ms from start
)

AnlzTagQuantize = Struct(
  Padding(4),
  "unknown" / Const(0x80000, Int32ub),
  "entries" / PrefixedArray(Int32ub, AnlzQuantizeTick)
)

AnlzTagQuantize2 = Struct(
  Padding(4),
  "u1" / Const(0x01000002, Int32ub), # maybe this encodes the count of "bpm" objects below
  Padding(4),
  "bpm" / Array(2, AnlzQuantizeTick),
  "entry_count" / Int32ub, # 680
  "u3" / Int32ub,
  "u4" / Int32ub,
  "u5" / Int32ub,
  "u6" / Int32ub,
  Padding(8)
)

AnlzTagWaveform = Struct(
  "payload_size" / Int32ub, # is 0 for some tag types
  "unknown" / Const(0x10000, Int32ub),
  "entries" / Array(this.payload_size, Int8ub)
)
AnlzTagBigWaveform = Struct(
  "u1" / Const(1, Int32ub),
  "payload_size" / Int32ub,
  "u2" / Const(0x960000, Int32ub),
  "entries" / Array(this.payload_size, Int8ub)
)
AnlzTagColorWaveform = Struct(
  "payload_word_size" / Const(0x06, Int32ub),
  "payload_size" / Int32ub,
  "unknown" / Const(0x00, Int32ub),
  "entries" / Array(this.payload_word_size * this.payload_size, Int8sb), # See doubts about signed in ColorPreviewWaveformWidget
)
AnlzTagColorBigWaveform = Struct(
  "payload_word_size" / Const(0x02, Int32ub),
  "payload_size" / Int32ub,
  "unknown" / Int32ub,
  "entries" / Array(this.payload_size, Int16ub),
)

AnlzCuePointType = Enum(Int8ub,
  single = 1,
  loop = 2
)

AnlzCuePointStatus = Enum(Int32ub,
  disabled = 0,
  enabled = 4
)

# unfortunately, this can't be embedded into AnlzTag due to the recursive
# dependency between AnlzTag and AnlzTagCueObject
AnlzCuePoint = Struct(
  "type" / Const("PCPT", PaddedString(4, encoding="ascii")),
  "head_size" / Int32ub,
  "tag_size" / Int32ub,
  "hotcue_number" / Int32ub, # 0 for memory
  "status" / AnlzCuePointStatus,
  "u1" / Const(0x10000, Int32ub),
  "order_first" / Int16ub, # 0xffff for first cue, 0,1,3 for next
  "order_last" / Int16ub, # 1,2,3 for first, second, third cue, 0xffff for last
  "type" / AnlzCuePointType,
  Padding(1),
  "u3" / Const(1000, Int16ub),
  "time" / Int32ub,
  "time_end" / Default(Int32ub, -1),
  Padding(16)
)

AnlzTagCueObjectType = Enum(Int32ub,
  memory = 0,
  hotcue = 1
)

AnlzTagCueObject = Struct(
  "type" / AnlzTagCueObjectType,
  "count" / Int32ub,
  "memory_count" / Int32ub,
  "entries" / Array(this.count, AnlzCuePoint)
)

AnlzCuePoint2 = Struct(
  "type" / Const("PCP2", PaddedString(4, encoding="ascii")),
  "head_size" / Int32ub,
  "tag_size" / Int32ub,
  "hotcue_number" / Int32ub, # 0 for memory
  "u2" / Int32ub, # spotted: 0x010003e8 0x020003e8
  "time" / Int32ub,
  "time_end" / Default(Int32ub, -1),
  "u1" / Int32ub, # spotted: 0x00010000 0x00010247
  Padding(56)
)

AnlzTagCueObject2 = Struct(
  "type" / AnlzTagCueObjectType,
  "count" / Int16ub,
  "unknown" / Int16ub,
  "entries" / Array(this.count, AnlzCuePoint2)
)

AnlzTag = Struct(
  "type" / PaddedString(4, encoding="ascii"),
  "head_size" / Int32ub,
  "tag_size" / Int32ub,
  "content" / Switch(this.type, {
    "PPTH": AnlzTagPath,
    "PVBR": AnlzTagVbr,
    "PQTZ": AnlzTagQuantize,
    "PWAV": AnlzTagWaveform,
    "PWV2": AnlzTagWaveform,
    "PCOB": AnlzTagCueObject, # seen in both DAT and EXT files
    "PWV3": AnlzTagBigWaveform, # seen in EXT files
    "PWV4": AnlzTagColorWaveform, # seen in EXT files
    "PWV5": AnlzTagColorBigWaveform, # seen in EXT files
    "PCO2": AnlzTagCueObject2, # seen in EXT files
  }, default=Padding(this.tag_size-12))
)

AnlzFile = Struct(
  "type" / Const("PMAI", PaddedString(4, encoding="ascii")),
  "head_size" / Int32ub,
  "file_size" / Int32ub,
  "u1" / Int32ub,
  "u2" / Int32ub,
  "u3" / Int32ub,
  "u4" / Int32ub,
  "tags" / GreedyRange(AnlzTag)
  #"tags" / Array(8, AnlzTag)
)
