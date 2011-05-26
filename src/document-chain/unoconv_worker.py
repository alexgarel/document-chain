import os

from document_chain.base import BaseWorker

# make a link to your unoconv script on system
import unoconv

# monkey patch unoconv
def exc_die(ret, str=None):
    raise Exception(str)

setattr(unoconv, 'die', exc_die)

def error(level, str):
    pass # TODO Log !

setattr(unoconv, 'error', error)

def info(level, str):
    pass

setattr(unoconv, 'info', info)


class UnoConvWorker(BaseWorker):

    name = 'unoconv'

    def __init__(self, *args, **kwargs):
        BaseWorker.__init__(self, *args, **kwargs)
        op = unoconv.Options(('foo',))
        setattr(unoconv, 'op', op)
        # we immediatly init our convertor
        self.converter = unoconv.Convertor()
        

    def run_action(self, src, dest_fmt=None):
        """Convert src to format dest_fmt, putting file at dest using
        unoconv
        """
        opts = []
        if dest_fmt:
            opts.append('-f', dest_fmt)
        opts.append(src)
        unoconv.op = unoconv.Options(opts)
        self.converter.convert(src)
        # remove destination file
        os.remove(src)
