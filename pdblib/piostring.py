from construct import Computed, ExprAdapter, FocusedSeq, Int8ul, Int24ul, Pointer, RepeatUntil, String, Switch, this

#PioString = Struct(
PioString = FocusedSeq(1,
  "padded_length" / RepeatUntil(lambda x,lst,ctx: x!=0, Int8ul),
  "data" / Switch(this.padded_length[-1], {
    # string longer than 127 bytes, prefixed with 3 bytes length
    0x40: FocusedSeq(1,
      "actual_length" / ExprAdapter(Int24ul, lambda o,c: o+4, lambda o,c: o-4),
      "text" / String(this.actual_length, encoding="ascii")),
    # iso-8859 text with \x00 between every character (like utf-16, but its iso-8859)
    0x90: FocusedSeq(1,
      "actual_length" / ExprAdapter(Int24ul, lambda o,c: o+4, lambda o,c: o-4),
      "text" / ExprAdapter(String(this.actual_length, encoding="iso-8859-1"), lambda o,c: "".join(x+"\x00" for x in o), lambda o,c: o[::2])),
  }, default= # just ascii text
    FocusedSeq(1,
      "actual_length" / Computed((this.padded_length[-1]-1)//2-1),
      "text" / String(this.actual_length, encoding="ascii")))
)

# parses a PioString relative to entry start using an str_idx array
def OffsetPioString(index):
  return Pointer(this.entry_start+index, PioString)

# parses a PioString relative to entry start using an str_idx array
def IndexedPioString(index):
  return Pointer(this.entry_start+this.str_idx[index], PioString)
