"""utility to run a worker, based on a config file parameters"""
from ConfigParser import SafeConfigParser
from optparse import OptionParser
import os
import signal

from document_chain.http_submitter import HTTPFileSubmitter
from document_chain.unoconv_worker import UnoConvWorker


parser = OptionParser(usage="%prog [options] worker")
parser.add_option("-c", "--config",
                  help="use config file (default is config.ini)",
                  default='config.ini', dest="filename")
parser.add_option("-s", "--section",
                  help="Use section of config file (default is main)",
                  default='main', dest="section")
parser.add_option("-p", "--pid-file",
                  help="Use this file for pid (default in <worker name>.pid)",
                  default=None, dest="pid")


def worker_from_config(worker_name, filename, section='main'):
    config_parser = SafeConfigParser()
    config_parser.read(filename)
    prefix = worker_name + '_'
    config = dict((k[len(prefix):],v)
                    for k, v in config_parser.items(section)
                    if k.startswith(prefix))
    klass_name = config_parser.get(section, worker_name)
    klass = globals()[klass_name]
    return klass(**config)


def term_handler(worker, pid_path):
    def handler(signum, frame):
        worker.stop()
    return handler


def main(options, args):
    for worker_name in args:
        worker = worker_from_config(worker_name, options.filename,
                                    options.section)
        pid_path = options.pid
        if pid_path is None:
            pid_path = worker_name + '.pid'
        pid_file = open(pid_path, 'w')
        pid_file.write(str(os.getpid()))
        pid_file.close()
        signal.signal(signal.SIGTERM, term_handler(worker, pid_path))
        worker.start()
        os.unlink(pid_path)

if __name__ == '__main__':
    main(parser.parse_args())
