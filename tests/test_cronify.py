#!/usr/bin/env python

import unittest
from cronify import Watcher
import os
import shutil
import time
import Queue
import datetime

"""Unittests for cronify application"""

class CronifyTestCase(unittest.TestCase):
    setup_test_dir = '/tmp/cronify_unittest'

    def callback_func(self, event):
        self.q.put(event.name)

    def setUp(self):
        try:
            shutil.rmtree(self.setup_test_dir)
        except OSError:
            pass
        os.mkdir(self.setup_test_dir)
        self.q = Queue.Queue()

    def tearDown(self):
        shutil.rmtree(self.setup_test_dir)
        del self.q

    def _make_test_file(self, filename):
        open(os.path.sep.join([self.setup_test_dir, filename]), 'w').close()

    def test_bad_watch_data(self):
        """Test starting a watcher object with various missing required watch data"""
        for data in [{}, { self.setup_test_dir : { } },
                     { self.setup_test_dir : { 'name' : 'Fake' } },
                     { self.setup_test_dir : { 'name' : 'Fake', 'filemasks' : { } } },
                     { self.setup_test_dir : { 'name' : 'Fake', 'filemasks' : { 'somefilemask' : {} } } },
                     { self.setup_test_dir : { 'name' : 'Fake', 'filemasks' : { 'somefilemask' : { 'actions' : [] } } } },
                     ]:
            try:
                Watcher(data)
            except SystemExit:
                pass

    def test_can_watch_dir(self):
        """Can watch a directory and trigger an action
        by creating a file matching the configured filemask"""
        test_filemask = 'testfilemask.txt'
        test_action = { 'Echo filename and file datestamp' : {
            'cmd': 'echo',
            'args': ['$filename', 'YYYYMMDD'] } }
        watch_data = {
            self.setup_test_dir : {
                'name': 'Test watch',
                'filemasks': {
                    test_filemask : {
                        'actions': [test_action,],
                        }
                    }}}
        watcher = Watcher(watch_data, callback_func = self.callback_func)
        self._make_test_file(test_filemask)
        try:
            self.assertEqual(test_filemask, self.q.get(timeout = 30),
                             msg = "Expected action to be triggered for filemask %s" % (test_filemask,))
        finally:
            watcher.cleanup()

    def test_delayed_action(self):
        """Test that an action with start_time in the future is not triggered"""
        test_filemask = 'testfilemask.txt'
        test_action = { 'Echo filename and file datestamp' : {
            'cmd': 'echo',
            'start_time' : (datetime.datetime.now() + datetime.timedelta(minutes = 30)).strftime("%H:%M:%S"),
            'end_time' : '23:59:59',
            'args': ['$filename', 'YYYYMMDD'] } }
        watch_data = {
            self.setup_test_dir : {
                'name': 'Test watch',
                'filemasks': {
                    test_filemask : {
                        'actions': [test_action,],
                        }
                    }}}
        watcher = Watcher(watch_data, callback_func = self.callback_func)
        self._make_test_file(test_filemask)
        try:
            result = self.q.get(timeout = 1)
        except Queue.Empty:
            result = None
        try:
            self.assertEqual(None, result,
                             msg = "Got result from action where action has start time in future")
        finally:
            watcher.cleanup()

if __name__ == '__main__':
    unittest.main()
