"""tests !


__init__ provide some utility methods for tests
"""

import os


def log_in_out(method, name, log):
    """wrapper to log each time we enter or exit method"""
    def fn(*args, **kwargs):
        log.write('entered method %s with %r, %r\n' % (name, args, kwargs))
        result = method(*args, **kwargs)
        log.write('exit method %s with %r, %r\n' % (name, args, kwargs))
        return result
    return fn


def log_all(obj, log):
    """apply log_in_out to each method of obj"""
    for m in dir(obj):
        if not m.startswith('__'):
            meth = getattr(obj, m)
            if callable(meth):
                setattr(obj, m, log_in_out(meth, m, log))


def make_dirs(tmpdir):
    """make tmpdir and 'in', 'err', and 'done' subdirs"""
    in_path = os.path.join(tmpdir, 'in')
    os.mkdir(in_path)
    err_path = os.path.join(tmpdir, 'err')
    os.mkdir(err_path)
    done_path = os.path.join(tmpdir, 'done')
    os.mkdir(done_path)
    return in_path, err_path, done_path

