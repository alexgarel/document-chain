
## monkey patch older versions of pyinotify
import os
import pyinotify
try:
    pyinotify.IN_MOVED_TO
except AttributeError:
    setattr(pyinotify, 'IN_MOVED_TO', pyinotify.EventsCodes.IN_MOVED_TO)
try:
    pyinotify.Event.pathname
except AttributeError:
    pyinotify.Event.pathname = property(
                        lambda self: os.path.join(self.path + '/' + self.name))
