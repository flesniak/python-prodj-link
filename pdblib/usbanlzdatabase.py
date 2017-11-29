import logging

from .usbanlz import AnlzFile

class UsbAnlzDatabase(dict):
  def __init__(self):
    super().__init__(self)
    self.parsed = None

  def get_beatgrid(self, track_id):
    if not "beatgrid" in self:
      raise KeyError("UsbAnlzDatabase: no beatgrid found".format(key_id))
    return self["beatgrid"]

  def get_cue_points(self, artist_id):
    if not "cue_points" in self:
      raise KeyError("UsbAnlzDatabase: no cue points found".format(key_id))
    return self["cue_points"]

  def get_waveform(self, album_id):
    if not "waveform" in self:
      raise KeyError("UsbAnlzDatabase: no waveform found".format(key_id))
    return self["waveform"]

  def get_preview_waveform(self):
    if not "preview_waveform" in self:
      raise KeyError("UsbAnlzDatabase: no preview waveform found".format(key_id))
    return self["preview_waveform"]

  def collect_entries(self, tag, target):
    if not tag in self.parsed.content:
      logging.warning("UsbAnlzDatabase: tag %s not found in file")
      return
    self[target] = self.parsed.content[tag]["entries"]

  def _load_file(self, filename):
    fh = AnlzFile()
    with open(filename, "rb") as f:
      self.parsed = fh.parse_stream(f);

  def _load_buffer(self, data):
    fh = AnlzFile()
    self.parsed = fh.parse(data);

  def _parse_dat(self):
    logging.debug("UsbAnlzDatabase: Loaded %d tags", len(self.parsed.content))
    self.collect_entries("PWAV", "preview_waveform")
    self.collect_entries("PCOB", "cue_points")
    self.collect_entries("PQTZ", "beatgrid")
    self.parsed = None

  def _parse_ext(self):
    logging.debug("UsbAnlzDatabase: Loaded %d tags", len(self.parsed.content))
    self.collect_entries("PWV3", "waveform")
    self.parsed = None

  def load_dat_buffer(self, data):
    logging.debug("UsbAnlzDatabase: Loading DAT buffer")
    self._load_buffer(data)
    self._parse_dat()

  def load_dat_file(self, filename):
    logging.debug("UsbAnlzDatabase: Loading DAT file \"%s\"", filename)
    self._load_file(filename)
    self._parse_dat()

  def load_ext_buffer(self, data):
    logging.debug("UsbAnlzDatabase: Loading DAT buffer")
    self._load_buffer(data)
    self._parse_ext()

  def load_ext_file(self, filename):
    logging.debug("UsbAnlzDatabase: Loading EXT file \"%s\"", filename)
    self._load_file(filename)
    self._parse_ext()
