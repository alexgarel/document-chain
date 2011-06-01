from __future__ import with_statement

from datetime import datetime
import os
import os.path
import pyinotify
import threading
import traceback
from ConfigParser import RawConfigParser


class IncomingTaskHandler(pyinotify.ProcessEvent):
    """The inotify event handler wich signal incoming tasks to worker"""

    def __init__(self, worker):
        self.worker = worker

    def process_IN_MOVED_TO(self, event):
        """as an incoming task arrives, we just put it in queue

        event is a inotify event corresponding to task"""
        worker = self.worker
        with worker.task_queue_guard:
            worker.task_queue.add(event.pathname)
            worker.task_queue_signal.notify()


class BaseWorker(object):
    """Provide basic capability of managing incoming tasks"""

    task_queue = None
    name = 'FIXME'

    def __init__(self, in_path, err_path):
        """in_path is the path of the directory where tasks will income"""
        self.in_path = in_path
        self.err_path = err_path
        # having a set solve init pb when IncomingTaskHandler is in
        # concurrence with _init_task_queue
        self.task_queue = set()
        self.task_queue_guard = threading.Lock()
        self.task_queue_signal = threading.Condition(self.task_queue_guard)
        self._stop_signaled = False

    def stop(self):
        self._stop_signaled = True
        if hasattr(self, 'notifier'):
            self.notifier.stop()

    def start(self):
        """start to process incoming tasks"""
        self._launch_observer()
        self._init_task_queue()
        tasks = self.task_queue
        while not self._stop_signaled:
            while tasks:
                with self.task_queue_guard:
                    task_path = tasks.pop()
                self.run(task_path)
            # now we wait for a new file
            with self.task_queue_guard:
                self.task_queue_signal.wait()

    def run(self, task_path):
        """read task and launch run_action"""
        # first we read the task config
        config = RawConfigParser()
        config.read(task_path)
        if config.has_section(self.name):
            task = dict(config.items(self.name))
            try:
                self.run_action(**task)
                self._done(task_path, task['next'])
            except:
                self._error(task_path, "task raises : " +
                            traceback.format_exc())
        else:
            self._error(task_path, "No section for me : %s" % self.name)

    def run_action(self, **kwargs):
        """This is the method where your handler shall do its task
        this method will receive task parameters"""
        raise NotImplementedError

    def _init_task_queue(self):
        """seek for all present file at startup, as we won't get them
        with inotify"""
        for f in os.listdir(self.in_path):
            path = os.path.join(self.in_path, f)
            if os.path.isfile(path):
                self.task_queue.add(path)

    def _launch_observer(self):
        """Launch incoming task observer"""
        handler = IncomingTaskHandler(worker=self)
        wm = pyinotify.WatchManager()
        wm.add_watch(self.in_path, pyinotify.IN_MOVED_TO, rec=False)
        self.notifier = pyinotify.ThreadedNotifier(wm, handler)
        self.notifier.start()

    def _error(self, task_path, msg, rename=True):
        """treat task path as an error"""
        with open(task_path, 'a') as f:
            f.write('\n# Error in %s at %s:\n#   ' %
                                (self.name, datetime.now()))
            msg = msg.replace('\n', '\n#   ')
            f.write(msg)
            f.write('\n')
        if rename:
            try:
                os.rename(task_path,
                          os.path.join(self.err_path,
                          os.path.basename(task_path)))
            except:
                self._error(task_path, "can't rename task after error !\n" +
                                                        traceback.format_exc(),
                            rename=False)


    def _done(self, task_path, next_path):
        """move to next"""
        with open(task_path, 'a') as f:
            f.write('\n# Done %s at %s\n' % (self.name, datetime.now()))
        os.rename(task_path,
                  os.path.join(next_path, os.path.basename(task_path)))


class controlled_worker(object):

    def __init__(self, worker):
        self.worker = worker
        self.p = threading.Thread(target=worker.start, args=tuple())

    def __enter__(self):
        self.p.start()

    def __exit__(self, *args, **kwargs):
        with self.worker.task_queue_guard:
            self.worker.stop()
            self.worker.task_queue_signal.notify()
        self.p.join()
