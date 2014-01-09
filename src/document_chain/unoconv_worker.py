from __future__ import with_statement
"""this module define a worker to convert document using unoconv

We abuse a bit unoconv module by monkey patching"""

import pwd
import os
from document_chain.base import BaseWorker

# make a link to your unoconv script on system
import unoconv


def monkey_patch_unoconv():
    def exc_die(job, msg=None):
        raise Exception(msg)

    setattr(unoconv, 'die', exc_die)


monkey_patch_unoconv()


class UnoConvWorker(BaseWorker):

    name = 'unoconv'

    _job_cache = None

    def __init__(self, *args, **kwargs):
        BaseWorker.__init__(self, *args, **kwargs)

    def base_job(self):
        """We cache the job to reuse listener and converter
        """
        if self._job_cache is None:
            job = unoconv.Job()
            job.op = unoconv.Options()
            job.op.listener = True
            job.op.stop_instance = False
            job.op.complete_config()
            job.office = unoconv.office
            job.listener = unoconv.Listener(job)
            job.converter = unoconv.Convertor(job)
            self._job_cache = job
        return self._job_cache

    def run_action(
        self, src, dest=None, dest_fmt=None, remove_src=False, **kwargs):
        """Convert src to format dest_fmt, putting file at dest using
        unoconv
        """
        try:
            job = self.base_job()
            job.op.filenames = [src]
            if dest_fmt:
                job.op.format = dest_fmt
            else:
                job.op.format = 'pdf'
            if dest is None:
                dest = (os.path.splitext(src)[0] + '.' +
                        unoconv.fmts.byname(job.op.format)[0].extension)
            job.op.output = dest
            job.op.complete_config()
            job.converter.convert(src)
        except Exception as e:
            # there where errors
            if 'URL seems to be an unsupported one' in repr(e):
                e.args[0] += ('\nNote that some version of OOo needs ' +
                    'permission to access the file for user group !')
            raise
        # verify file is not empty
        if not (os.path.exists(dest) and os.path.getsize(dest)):
            raise RuntimeError(
                "destination file is empty, this is a failure !")

        if remove_src:
            # remove source file
            os.remove(src)
