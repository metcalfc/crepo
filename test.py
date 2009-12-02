#!/usr/bin/env python2.5
# (c) Copyright 2009 Cloudera, Inc.

import unittest
from unittest import TestCase
import os
import subprocess
import sys
import re

TESTS_DIR=os.path.join(os.getcwd(), "shell-tests")

class ShellTests(TestCase):
  def _run_shell_test(self, path):
    print "running: " + path
    p = subprocess.Popen([os.path.join(TESTS_DIR, path)],
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    ret = p.wait()
    if ret != 0:
      print >>sys.stderr, "Stderr:\n%s\n\nStdout:\n%s\n" % (stderr, stdout)
      self.fail("Test at %s failed" % path)

def __add_tests():
  for x in os.listdir(TESTS_DIR):
    if x.startswith("."): continue
    t = lambda self,x=x: self._run_shell_test(x)
    t.__name__ = 'test' + re.sub('[^a-zA-Z0-9]', '_', 'test' + x)
    setattr(ShellTests, t.__name__,  t)
__add_tests()

if __name__ == "__main__":
  unittest.main()
