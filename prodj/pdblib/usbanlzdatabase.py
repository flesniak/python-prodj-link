import logging

from .usbanlz import AnlzFile

class UsbAnlzDatabase(dict):
  def __init__(self):
    super().__init__(self)
    self.parsed = None

  def get_beatgrid(self):
    if not "beatgrid" in self:
      raise KeyError("UsbAnlzDatabase: no beatgrid found")
    return self["beatgrid"]

  def get_cue_points(self):
    if not "cue_points" in self:
      raise KeyError("UsbAnlzDatabase: no cue points found")
    return self["cue_points"]

  def get_waveform(self):
    if not "waveform" in self:
      raise KeyError("UsbAnlzDatabase: no waveform found")
    return self["waveform"]

  def get_preview_waveform(self):
    if not "preview_waveform" in self:
      raise KeyError("UsbAnlzDatabase: no preview waveform found")
    return self["preview_waveform"]

  def get_color_preview_waveform(self):
    if not "color_preview_waveform" in self:
      raise KeyError("UsbAnlzDatabase: no color preview waveform found")
    return self["color_preview_waveform"]

  def get_color_waveform(self):
    if not "color_waveform" in self:
      raise KeyError("UsbAnlzDatabase: no color waveform found")
    return self["color_waveform"]

  def collect_entries(self, tag, target):
    obj = next((t for t in self.parsed.tags if t.type == tag), None)
    if obj is None:
      logging.warning("tag %s not found in file", tag)
      return
    self[target] = obj.content.entries

  def _load_file(self, filename):
    with open(filename, "rb") as f:
      self.parsed = AnlzFile.parse_stream(f);

  def _load_buffer(self, data):
    self.parsed = AnlzFile.parse(data);

  def _parse_dat(self):
    logging.debug("Loaded %d tags", len(self.parsed.tags))
    self.collect_entries("PWAV", "preview_waveform")
    self.collect_entries("PCOB", "cue_points")
    self.collect_entries("PQTZ", "beatgrid")
    self.parsed = None

  def _parse_ext(self):
    logging.debug("Loaded %d tags", len(self.parsed.tags))
    self.collect_entries("PWV3", "waveform")
    self.collect_entries("PWV4", "color_preview_waveform")
    self.collect_entries("PWV5", "color_waveform")
    # TODO: collect PCOB here as well?
    # self.collect_entries("PCOB", "cue_points")
    self.parsed = None

  def load_dat_buffer(self, data):
    logging.debug("Loading DAT from buffer")
    self._load_buffer(data)
    self._parse_dat()

  def load_dat_file(self, filename):
    logging.debug("Loading DAT file \"%s\"", filename)
    self._load_file(filename)
    self._parse_dat()

  def load_ext_buffer(self, data):
    logging.debug("Loading EXT from buffer")
    self._load_buffer(data)
    self._parse_ext()

  def load_ext_file(self, filename):
    logging.debug("Loading EXT file \"%s\"", filename)
    self._load_file(filename)
    self._parse_ext()
