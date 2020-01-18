import logging

try:
    unicode
    _unicode = True
except NameError:
    _unicode = False

class CursesHandler(logging.Handler):
  def __init__(self, screen):
    logging.Handler.__init__(self)
    self.screen = screen
  def emit(self, record):
    msg = self.format(record)
    self.screen.addstr('\n{}'.format(msg))
    self.screen.refresh()
    return
    try:
      msg = self.format(record)
      screen = self.screen
      fs = "\n%s"
      if not _unicode: #if no unicode support...
        screen.addstr(fs % msg)
        screen.refresh()
      else:
        try:
          if (isinstance(msg, unicode)):
            ufs = u'\n%s'
            try:
              screen.addstr(ufs % msg)
              screen.refresh()
            except UnicodeEncodeError:
              screen.addstr((ufs % msg).encode(code))
              screen.refresh()
          else:
            screen.addstr(fs % msg)
            screen.refresh()
        except UnicodeError:
            screen.addstr(fs % msg.encode("UTF-8"))
            screen.refresh()
    except (KeyboardInterrupt, SystemExit):
      raise
    except:
      self.handleError(record)
