#!/usr/bin/env python2.5
# (c) Copyright 2009 Cloudera, Inc.

import unittest
from unittest import TestCase
import os
import subprocess
import re

TESTS_DIR=os.path.join(os.getcwd(), "shell-tests")

class ShellTests(TestCase):
  def _run_shell_test(self, path):
    print "running: " + path
    ret = subprocess.call([os.path.join(TESTS_DIR, path)])
    self.assertEquals(ret, 0)

def __add_tests():
  for x in os.listdir(TESTS_DIR):
    if x.startswith("."): continue
    t = lambda self,x=x: self._run_shell_test(x)
    t.__name__ = 'test' + re.sub('[^a-zA-Z0-9]', '_', 'test' + x)
    setattr(ShellTests, t.__name__,  t)
__add_tests()

if __name__ == "__main__":
  unittest.main()
