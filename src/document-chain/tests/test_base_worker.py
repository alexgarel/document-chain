from document_chain.base import BaseWorker
import os
import multiprocessing
import tempfile
from StringIO import StringIO
import time

output = StringIO()


class Worker(BaseWorker):
    name = 'simple'

    def run_action(self, a, b=None):
        output.write("runing with a = %r and b = %r" % dict(a, b))


def test_incoming_file():
    tmpdir = tempfile.mkdtemp()
    in_path = os.path.join(tmpdir, 'in')
    os.mkdir(in_path)
    err_path = os.path.join(tmpdir, 'err')
    os.mkdir(err_path)
    done_path = os.path.join(tmpdir, 'done')
    os.mkdir(done_path)

    import pytest;pytest.set_trace()
    w = Worker()
    p = multiprocessing.Process(target=w.start, args=tuple())

    # push a task
    task_path = os.path.join(tmpdir, 't1')
    with open(task_path) as f:
        f.write("""[simple]
a=1
b=some text
next=%s""" % done_path)
    # let's start
    os.rename(task_path, os.path.join(in_path, 't1'))
    time.sleep(2) # it's so easy
    assert 't1' in os.listdir(done_path)
    assert output.getvalue() == "runing with a = '1' and b = 'some text'"

