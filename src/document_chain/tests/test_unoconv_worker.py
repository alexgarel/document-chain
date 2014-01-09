from __future__ import with_statement

import os
import shutil
import stat
from StringIO import StringIO
import tempfile
import time

from document_chain.base import controlled_worker
from document_chain.unoconv_worker import UnoConvWorker
from document_chain.tests import make_dirs, log_all
import document_chain.tests

import pytest

sample_path = os.path.join(os.path.dirname(document_chain.tests.__file__),
                           'sample-text.odt')


tmpdir = None  # we need to have a global tempdir to remove it after tests


def teardown_function(function):
    if tmpdir and os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)


def setup_function(function):
    global tmpdir  # teardown will remove it
    tmpdir = tempfile.mkdtemp()


def group_permissions(path):
    """we have a strange pb on older OOo, we need group read permissions
    to use unoconv
    """
    # read perm on file
    os.chmod(path, (os.stat(path)[0] & 0xFFF) | stat.S_IRGRP)
    # list perm on directory
    dirpath = os.path.dirname(path)
    if not os.stat(dirpath)[0] & stat.S_IXGRP:
        os.chmod(dirpath, (os.stat(dirpath)[0] & 0xFFF) | stat.S_IXGRP)


def test_run_action():
    """just test the action is working"""
    temp_path = os.path.join(tmpdir, 'sample-text.odt')
    shutil.copyfile(sample_path, temp_path)
    group_permissions(temp_path)
    worker = UnoConvWorker(tmpdir, tmpdir)
    worker.run_action(src=temp_path, remove_src=True)
    pdf_path = os.path.join(tmpdir, 'sample-text.pdf')
    assert os.path.exists(pdf_path)
    with open(pdf_path) as f:
        assert f.read(5) == "%PDF-"
    assert not os.path.exists(temp_path)

    shutil.copyfile(sample_path, temp_path)
    group_permissions(temp_path)
    worker.run_action(src=temp_path, dest_fmt='doc')
    odt_path = os.path.join(tmpdir, 'sample-text.doc')
    assert os.path.exists(odt_path)
    assert os.path.exists(temp_path)


def test_run_action_with_error():
    """test with an error at unoconv time"""
    temp_path = os.path.join(tmpdir, 'this-file-does-not-exists.odt')
    worker = UnoConvWorker(tmpdir, tmpdir)
    with pytest.raises(Exception):
        worker.run_action(src=temp_path)

    temp_path = os.path.join(tmpdir, 'sample-text.odt')
    worker = UnoConvWorker(tmpdir, tmpdir)
    with pytest.raises(Exception):
        worker.run_action(src=temp_path, dest_fmt='not-existing')


def test_integration():
    """integration test"""
    in_path, err_path, done_path = make_dirs(tmpdir)
    temp_path = os.path.join(tmpdir, 'sample-text.odt')
    log = StringIO()

    worker = UnoConvWorker(in_path, err_path)
    log_all(worker, log)  # we log so we now what is done by our thread

    with controlled_worker(worker):
        # prepare a task
        shutil.copyfile(sample_path, temp_path)
        group_permissions(temp_path)
        task_path = os.path.join(tmpdir, 't1')
        with open(task_path, 'w') as f:
            f.write("[unoconv]\n")
            f.write("src=%s\n" % temp_path)
            f.write("next=%s\n" % done_path)
        # push it
        os.rename(task_path, os.path.join(in_path, 't1'))
        # wait for completion
        while not "exit method run" in log.getvalue():
            time.sleep(0.1)
        assert 't1' in os.listdir(done_path)
        pdf_path = os.path.join(tmpdir, 'sample-text.pdf')
        assert os.path.exists(pdf_path)
