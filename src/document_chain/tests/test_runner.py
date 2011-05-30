from __future__ import with_statement

import os
import shutil
import tempfile

from document_chain.http_submitter import HTTPFileSubmitter
from document_chain import runner


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


def test_runner_run():
    make_conf()
    options, args = runner.parser.parse_args(['submitter', ])
    started = []

    def start_asserter(worker):
        assert os.path.exists('%s/submitter.pid' % tmpdir)
        started.append(worker)

    with MonkeyedWorker(HTTPFileSubmitter, start_asserter):
        runner.main(options, args)
    assert started
    worker = started[0]
    assert worker.__class__ == HTTPFileSubmitter
    assert worker.in_path == 'submitter/in'
