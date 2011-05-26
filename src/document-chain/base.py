import pyinotify
import os
import os.path
import sys
import threading
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
        self.task_queue_signal = threading.Semaphore(threading.Lock())

    def start(self):
        """start to process incoming tasks"""
        self._launch_observer()
        self._init_task_queue()
        tasks = self.task_queue
        while True:
            while tasks:
                with self.task_queue_guard:
                    task_path = tasks.pop()
                self.run(task_path)
            # now we wait for a new file
            self.task_queue_signal.wait()

    def run(self, task_path):
        """read task and launch run_action"""
        # first we read the task config
        config = RawConfigParser()
        config.read(task_path)
        if config.has_section(self.name):
            task = dict(config.items(self.name))
            try:
                self.run_action(self, **task)
                self.done(self, task_path, task['next'])
            except:
                self._error(task_path, "task raises : " + sys.format_exc())
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
        handler = IncomingTaskHandler(worker = self)
        wm = pyinotify.WatchManager()
        self.notifier = pyinotify.Notifier(wm, handler)
        wm.add_watch(self.in_dir, pyinotify.IN_MOVED_TO, rec=False)
        self.notifier.loop(daemonize=True)

    def _error(self, task_path, msg):
        """treat task path as an error"""
        os.rename(os.path.join(self.in_path, task_path),
                  os.path.join(self.err_path, task_path))
        # TODO : log message

    def _done(self, task_path, next_path):
        """move to next"""
        os.rename(os.path.join(self.in_path, task_path),
                  os.path.join(self.next_path, task_path))
        
