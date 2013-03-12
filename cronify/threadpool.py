#!/usr/bin/env python

import threading
import Queue
import logging
import sys

log_format = ' - '.join(['%(name)s',
                         '%(threadName)s',
                         '%(levelname)s',
                         '%(message)s'])

# logging.basicConfig(format = log_format)
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
# logger.setLevel(logging.INFO)

class ThreadPool(object):
    """Producer consumer thread pool class"""

    def __init__(self, num_workers = 4, debug = False,
                 in_q = None,
                 out_q = None):
        if not in_q:
            self.in_q = Queue.Queue()
        else:
            self.in_q = in_q
        if not out_q:
            self.out_q = Queue.Queue()
        else:
            self.out_q = out_q
        self.num_workers = num_workers
        self.threads = []
        if debug:
            logger.setLevel(logging.DEBUG)
        self.start_threads(num_workers, self.in_q, self.out_q)

    def add_task_to_queue(self, func, *args, **kwargs):
        """Add func to queue to execute with *args and **kwargs"""
        logger.debug("Adding function %s with arguments %s, %s to input queue" % (func, args, kwargs,))
        self.in_q.put((func, args, kwargs))

    def add_tasks_to_queue(self, tasks):
        """Add tasks to queue where task is a tuple of (func, *args, **kwargs)
        eg (test_func, [], {})"""
        for func, args, kwargs in tasks:
            self.add_task_to_queue(func, *args, **kwargs)

    def start_threads(self, num_workers, in_q, out_q):
        """Start num_workers number of threads with in_q and out_q"""
        for _ in range(num_workers):
            p = threading.Thread(target = self._thread_worker, args = (in_q, out_q))
            self.threads.append(p)
            logger.debug("Starting thread %s" % (len(self.threads),))
            p.daemon = True
            p.start()

    def _thread_worker(self, in_q, out_q):
        """Thread target function, reads from in_q, runs function,
        puts result in out_q"""
        logger.debug("Thread started")
        while True:
            func, args, kwargs = in_q.get()
            logger.debug("Running %s with arguments %s - %s" % (func, args, kwargs,))
            try:
                result = func(*args, **kwargs)
            except Exception, e:
                logger.error("Error in thread - %s" % (e,))
                out_q.put(None)
                in_q.task_done()
                return
            logger.debug("Got result %s" % (result,))
            if result: out_q.put(result)
            in_q.task_done()

    def get_results(self, tasks):
        """Block till all tasks done, return results"""
        results = []
        for _ in tasks:
            try:
                results.append(self.out_q.get())
            except KeyboardInterrupt:
                logger.debug("Exiting due to keyboard interrupt")
                return
            self.out_q.task_done()
        return results
