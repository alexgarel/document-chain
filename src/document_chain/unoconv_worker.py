from __future__ import with_statement
"""this module define a worker to convert document using unoconv

We abuse a bit unoconv module by monkey patching"""

import pwd
import os
import sys
from StringIO import StringIO
from document_chain.base import BaseWorker

# make a link to your unoconv script on system
import unoconv


def monkey_patch_unoconv():
    def exc_die(ret, str=None):
        raise Exception(str)

    setattr(unoconv, 'die', exc_die)


monkey_patch_unoconv()


class MonkeyedStdDescriptors(object):

    def __init__(self, outfilename):
        self.stdout = open(outfilename, 'w')

    def __enter__(self):
        stderr = StringIO()
        self.orig_err = sys.stderr
        sys.stderr = stderr
        self.orig_out = sys.stdout
        sys.stdout = self.stdout
        return self.stdout, stderr

    def __exit__(self, *args, **kwargs):
        sys.stderr = self.orig_err
        sys.stdout = self.orig_out
        self.stdout.close()


class UnoConvWorker(BaseWorker):

    name = 'unoconv'

    _converter_cache = None

    def __init__(self, *args, **kwargs):
        BaseWorker.__init__(self, *args, **kwargs)

    @property
    def converter(self):
        """it's important to do converter init in run_action as in
        init we may not be in daemon final user
        """
        if self._converter_cache is None:
            # set correct HOME as we need right .openoffice dir
            os.environ['HOME'] = pwd.getpwuid(os.getuid()).pw_dir
            op = unoconv.Options(('foo',))
            setattr(unoconv, 'op', op)
            self._converter_cache = unoconv.Convertor()
        return self._converter_cache

    def run_action(
        self, src, dest=None, dest_fmt=None, remove_src=False, **kwargs):
        """Convert src to format dest_fmt, putting file at dest using
        unoconv
        """
        opts = ['--stdout', ]
        if dest_fmt:
            opts.extend(('-f', dest_fmt))
        else:
            dest_fmt = 'pdf'
        if dest is None:
            dest = (os.path.splitext(src)[0] + '.' +
                    unoconv.fmts.byname(dest_fmt)[0].extension)
        opts.append(src)
        # global options will be read from inside converter methods
        unoconv.op = unoconv.Options(opts)
        with MonkeyedStdDescriptors(dest) as (out, err):
            self.converter.convert(src)
            if err.getvalue():
                # there where errors
                if 'URL seems to be an unsupported one' in err.getvalue():
                    err.write('\nNote that some version of OOo needs'
                           + ' permission to access the file for user group !')
                raise Exception(err.getvalue())
            # verify file is not empty
            if not os.path.getsize(dest):
                raise RuntimeError(
                    "destination file is empty, this is a failure !")

        if remove_src:
            # remove source file
            os.remove(src)
