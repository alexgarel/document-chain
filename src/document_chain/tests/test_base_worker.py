import os
from StringIO import StringIO
import shutil
import tempfile
import time

from document_chain.base import BaseWorker, controlled_worker
from document_chain.tests import make_dirs, log_all


output = StringIO()
log = StringIO()


class NoRunWorker(BaseWorker):
    """a special worker for unit testing some part"""
    name = 'testing'

    def run(self, task_path):
        """remove run to test start"""
        output.write("run %s" % task_path)


class ControlledWorker(NoRunWorker):
    """a special worker for unit testing some part"""

    def _launch_observer(self):
        """remove _launch_observer to control it our way"""
        pass


class SimpleWorker(BaseWorker):
    name = 'simple'

    def run_action(self, a, b=None, **kwargs):
        output.write("runing with a = %r and b = %r" % (a, b))


class RaiserWorker(BaseWorker):
    name = 'raiser'

    def run_action(self, **kwargs):
        raise Exception("I'm mean")


tmpdir = None  # we need to have a global var to remove it after tests


def setup_function(function):
    global tmpdir  # teardown will remove it
    tmpdir = tempfile.mkdtemp()


def teardown_function(function):
    log.truncate(0)
    output.truncate(0)
    if tmpdir and os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)


def test_main_loop():
    """test main worker loop, that is in start"""
    in_path, err_path, done_path = make_dirs(tmpdir)
    worker = ControlledWorker(in_path, err_path)

    log_all(worker, log)

    with controlled_worker(worker):
        # now we just wake it
        with worker.task_queue_guard:
            worker.task_queue.add('t1')
            worker.task_queue_signal.notify()
        while not "exit method run" in log.getvalue():
            time.sleep(0.2)
        assert output.getvalue() == "run t1"


def test_run_simple():
    """test the run method isolated"""
    in_path, err_path, done_path = make_dirs(tmpdir)
    worker = SimpleWorker(in_path, err_path)
    # push a task
    task_path = os.path.join(in_path, 't1')
    with open(task_path, 'w') as f:
        f.write("""[simple]
a=1
b=some text
next=%s""" % done_path)
    worker.run(task_path)
    assert output.getvalue() == "runing with a = '1' and b = 'some text'"
    assert 't1' in os.listdir(done_path)


def test_run_raiser():
    """test the run method isolated with a raise in run_action"""
    in_path, err_path, done_path = make_dirs(tmpdir)
    worker = RaiserWorker(in_path, err_path)
    # push a task
    task_path = os.path.join(in_path, 't1')
    with open(task_path, 'w') as f:
        f.write("""[raiser]
next=%s""" % done_path)
    worker.run(task_path)
    assert 't1' in os.listdir(err_path)
    with open(os.path.join(err_path, 't1')) as t:
        content = t.read()
    assert "Error in raiser at" in content
    assert "Exception: I'm mean" in content


def test_run_no_section():
    """test the run method isolated with a task without section"""
    in_path, err_path, done_path = make_dirs(tmpdir)
    worker = SimpleWorker(in_path, err_path)
    # push a task
    task_path = os.path.join(in_path, 't1')
    with open(task_path, 'w') as f:
        f.write("""[NOT FOR YOU DEAR]
next=%s""" % done_path)
    worker.run(task_path)
    assert 't1' in os.listdir(err_path)
    with open(os.path.join(err_path, 't1')) as t:
        content = t.read()
    assert "Error in simple at" in content
    assert "No section for me : simple" in content


def _test_init_with_files():
    """test worker when file are present in start directory"""
    in_path, err_path, done_path = make_dirs(tmpdir)
    worker = SimpleWorker(in_path, err_path)

    # push a task
    task_path = os.path.join(in_path, 't1')
    with open(task_path, 'w') as f:
        f.write("""[simple]
a=1
b=some text
next=%s""" % done_path)

    log_all(worker, log)

    worker._launch_observer = lambda: None

    # start
    with controlled_worker(worker):
        # shall execute task at startup
        while not "exit method run" in log.getvalue():
            time.sleep(0.1)
        assert output.getvalue() == "runing with a = '1' and b = 'some tyext'"


def test_observer():
    in_path, err_path, done_path = make_dirs(tmpdir)
    worker = NoRunWorker(in_path, err_path)
    log_all(worker, log)
    try:
        worker._launch_observer()
        assert worker.notifier is not None

        # add some file
        task_path = os.path.join(tmpdir, 't1')
        with open(task_path, 'w') as f:
            f.write(".")
            # take queue lock (to control the execution of notifier)
            with worker.task_queue_guard:
                # push task
                new_path = os.path.join(in_path, 't1')
                os.rename(task_path, new_path)
                # We nust be sure pyinotify have seen file before releasing
                # the lock
                worker.task_queue_signal.wait()  # notifier shall notify
                assert worker.task_queue == set([new_path])
    finally:
        worker.stop()


def test_incoming_file():
    """integration test"""
    in_path, err_path, done_path = make_dirs(tmpdir)

    worker = SimpleWorker(in_path, err_path)
    log_all(worker, log)  # we log so we now what is done by our thread

    with controlled_worker(worker):
        # prepare a task
        task_path = os.path.join(tmpdir, 't1')
        with open(task_path, 'w') as f:
            f.write("""[simple]
a=1
b=some text
next=%s""" % done_path)
        # push it
        os.rename(task_path, os.path.join(in_path, 't1'))
        # wait for completion
        while not "exit method run" in log.getvalue():
            time.sleep(0.1)
        assert 't1' in os.listdir(done_path)
        assert output.getvalue() == "runing with a = '1' and b = 'some text'"
