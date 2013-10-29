#!/usr/bin/env python

"""Unittests for cronify application"""

import unittest
from cronify import Watcher
from cronify.common import read_cfg
import os
import shutil
import Queue
import datetime
import pytz
import yaml
from cStringIO import StringIO

class CronifyTestCase(unittest.TestCase):

    """Unittests for cronify"""

    setup_test_dir = '/tmp/cronify_unittest'
    echo_test_action = { 'Echo filename and file datestamp' : {
        'cmd': 'echo',
        'args': ['$filename', 'YYYYMMDD'] } }

    def callback_func(self, event):
        """Callback function triggered on a successful event
        Puts filename that triggered the event on a queue so we can check it"""
        self.q.put(event.name)

    def setUp(self):
        """Create test dir, create callback queue"""
        try:
            shutil.rmtree(self.setup_test_dir)
        except OSError:
            pass
        os.mkdir(self.setup_test_dir)
        self.q = Queue.Queue()

    def tearDown(self):
        """Remove our test dir, delete callback queue"""
        shutil.rmtree(self.setup_test_dir)
        del self.q

    def _make_test_file(self, filename):
        """Write an empty file to trigger an event"""
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
        watch_data = {
            self.setup_test_dir : {
                'name': 'Test watch',
                'filemasks': {
                    test_filemask : {
                        'actions': [self.echo_test_action,],
                        }
                    }}}
        watcher = Watcher(watch_data, callback_func = self.callback_func)
        self._make_test_file(test_filemask)
        try:
            self.assertEqual(test_filemask, self.q.get(timeout = 30),
                             msg = "Expected action to be triggered for filemask %s" % (test_filemask,))
        finally:
            watcher.cleanup()

    def test_multiple_actions(self):
        """Can watch a directory and correctly trigger multiple actions for same filemask"""
        test_filemask = 'testfilemask.*'
        watch_data = {
            self.setup_test_dir : {
                'name': 'Test watch',
                'filemasks': {
                    test_filemask : {
                        'actions': [self.echo_test_action,],
                        }
                    }}}
        _ = Watcher(watch_data, callback_func = self.callback_func)
        (file1, file2) = ('testfilemask.txt', 'testfilemask.pdf')
        for file_to_test in [file1, file2]:
            self._make_test_file(file_to_test)
            self.assertEqual(file_to_test, self.q.get(timeout = 30),
                             msg = "Expected action to be triggered for filemask %s with file %s" % (test_filemask,
                                                                                                     file_to_test))

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

    def test_action_start_time_in_past(self):
        """Test that an action with start_time in the past is triggered"""
        test_filemask = 'testfilemask.txt'
        end_time = '23:59:59'
        test_action = { 'Echo filename and file datestamp' : {
            'cmd': 'echo',
            'start_time' : (datetime.datetime.now() - datetime.timedelta(minutes = 30)).strftime("%H:%M:%S"),
            'end_time' : end_time,
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
        self.assertEqual(test_filemask, self.q.get(timeout = 1),
                         msg = "Expected action with start time in the past and end_time %s to be triggered immediately" %
                         (end_time,))

    def test_modified_local_tz(self):
        """Test running action with changed local timezone"""
        # Make local_tz different from TZ we use for time 'now'
        # Action is scheduled for US/Pacific now + 30 minutes which is prior to now at US/Eastern
        # so action should be triggered.
        local_tz = "US/Eastern"
        my_tz = "US/Pacific"
        my_tz = pytz.timezone(my_tz)
        now = datetime.datetime.utcnow()
        now = datetime.datetime(now.year, now.month, now.day, now.hour, now.minute, now.second,
                                tzinfo = pytz.utc)
        now = my_tz.normalize(now.astimezone(my_tz))
        local_tz_obj = pytz.timezone(local_tz)
        local_tz_now = local_tz_obj.normalize(now.astimezone(local_tz_obj))
        now = datetime.datetime(now.year, now.month, now.day, now.hour, now.minute, now.second)
        test_filemask = 'testfilemask.txt'
        test_action = { 'Echo filename and file datestamp' : {
            'cmd': 'echo',
            'start_time' : (now + datetime.timedelta(minutes = 30)).strftime("%H:%M:%S"),
            'end_time' : '23:59:59',
            'args': ['$filename', 'YYYYMMDD'] } }
        watch_data = {
            self.setup_test_dir : {
                'name': 'Test watch',
                'local_tz' : local_tz,
                'filemasks': {
                    test_filemask : {
                        'actions': [test_action,],
                        }
                    }}}
        watcher = Watcher(watch_data, callback_func = self.callback_func)
        self._make_test_file(test_filemask)
        self.assertEqual(test_filemask, self.q.get(timeout = 1),
                         msg = "Expected action to be executed with since start_time of %s is prior to watcher's local time of %s" %
                         ((now + datetime.timedelta(minutes = 30)).strftime("%H:%M:%S"),
                          local_tz_now.strftime("%H:%M:%S"),))

    def test_yaml(self):
        """Test loading yaml file"""
        yaml_data = """
/tmp/testdir :
    name : Access log watcher
    recurse : false
    filemasks :
      somefile.* :
        actions :
          - processFile :
              args:
                - $filename
                - YYYYMMDD
              cmd: echo
              """
        expected = {'/tmp/testdir': {'recurse': False, 'filemasks': {'somefile.*': {'actions': [{'processFile': {'cmd': 'echo', 'args': ['$filename', 'YYYYMMDD']}}]}}, 'name': 'Access log watcher'}}
        parsed_yaml = yaml.load(yaml_data)
        self.assertEqual(parsed_yaml, expected, msg = "Parsed yaml does not match what we expected it to be")

    def test_common_read_yaml_file(self):
        """Test read_cfg in common"""
        yaml_data_file = StringIO("""
/tmp/testdir :
    name : Access log watcher
    recurse : false
    filemasks :
      somefile.* :
        actions :
          - processFile :
              args:
                - $filename
                - YYYYMMDD
              cmd: echo
              """)
        expected = {'/tmp/testdir': {'recurse': False, 'filemasks': {'somefile.*': {'actions': [{'processFile': {'cmd': 'echo', 'args': ['$filename', 'YYYYMMDD']}}]}}, 'name': 'Access log watcher'}}
        parsed_yaml = read_cfg(yaml_data_file)
        self.assertEqual(parsed_yaml, expected, msg = "Parsed yaml does not match what we expected it to be")

if __name__ == '__main__':
    unittest.main()
