from __future__ import with_statement

import os
import shutil
import tempfile

from document_chain.http_submitter import HTTPFileSubmitter
from document_chain import runner
from daemon import daemon


tmpdir = None
orig_dir = None


class MonkeyedWorker(object):
    def __init__(self, klass, start):
        self.start = start
        self.klass = klass

    def __enter__(self):
        self.orig = self.klass.start
        self.klass.start = self.start

    def __exit__(self, *args, **kwargs):
        self.klass.start = self.orig


def setup_function(function):
    global tmpdir  # teardown will remove it
    tmpdir = tempfile.mkdtemp()
    global orig_dir
    orig_dir = os.getcwd()
    os.chdir(tmpdir)


def teardown_function(function):
    os.chdir(orig_dir)
    if tmpdir and os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)


def make_conf():
    with open('config.ini', 'w') as f:
        f.write("""[main]
submitter=HTTPFileSubmitter
submitter_in_path=submitter/in
submitter_err_path=submitter/err
""")


def test_runner_config():
    make_conf()
    worker = runner.worker_from_config('submitter', 'config.ini')
    assert worker.__class__ == HTTPFileSubmitter
    assert worker.in_path == 'submitter/in'


def test_runner_daemon_init():
    make_conf()
    started = []


    def start_asserter(worker,  daemon=False):
        started.append(worker)

    with MonkeyedWorker(HTTPFileSubmitter, start_asserter):
       wd = runner.WorkerDaemon(argv=['-w', tmpdir, 'submitter', 'start'])
       wd.daemon_context.open = lambda: 1  # do nothing
       wd.do_action()
       dc = wd.daemon_context
       assert dc.stderr.name == tmpdir + '/submitter.log'
       assert dc.pidfile.path == tmpdir + '/submitter.pid'
       assert started
       worker = started[0]
       assert worker.__class__ == HTTPFileSubmitter
       assert worker.in_path == 'submitter/in'
