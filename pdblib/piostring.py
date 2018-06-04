from construct import Bytes, Computed, ExprAdapter, FocusedSeq, Int8ul, Int24ul, Pointer, PaddedString, Restreamed, Switch, this

def DropOddBytes(subcon):
  return Restreamed(subcon, lambda d: d[::2], 2, lambda d: "".join(x+b"\x00" for x in d), 1, lambda n: n//2)

def Iso8859Adapter(subcon):
  return ExprAdapter(subcon, lambda o,c: o.decode("iso-8859-1"), lambda o,c: o.encode("utf-8"))

PioString = FocusedSeq("data",
  "padded_length" / Int8ul,
  "data" / Switch(this.padded_length, {
    # string longer than 127 bytes, prefixed with 3 bytes length
    0x40: FocusedSeq("text",
      "actual_length" / ExprAdapter(Int24ul, lambda o,c: o-4, lambda o,c: o+4),
      "text" / PaddedString(this.actual_length, encoding="ascii")),
    # iso-8859 text with \x00 between every character (like utf-16, but its iso-8859)
    0x90: FocusedSeq("text",
      "actual_length" / ExprAdapter(Int24ul, lambda o,c: o-4, lambda o,c: o+4),
      "text" / Iso8859Adapter(DropOddBytes(Bytes(this.actual_length//2)))),
  }, default= # just ascii text
    FocusedSeq("text",
     "actual_length" / Computed((this._.padded_length-1)//2-1),
      "text" / PaddedString(this.actual_length, encoding="ascii"))
))

# parses a PioString relative to entry start using an str_idx array
def OffsetPioString(index):
  return Pointer(this.entry_start+index, PioString)

# parses a PioString relative to entry start using an str_idx array
def IndexedPioString(index):
  return Pointer(this.entry_start+this.str_idx[index], PioString)
