#
# Copyright (C) 2008 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import subprocess
from trace import REPO_TRACE, IsTrace, Trace

GIT = 'git'
MIN_GIT_VERSION = (1, 5, 4)
GIT_DIR = 'GIT_DIR'


LAST_GITDIR = None
LAST_CWD = None

class GitCommand(object):
  def __init__(self,
               cmdv,
               capture_stdout = False,
               ignore_stdout=False,
               capture_stderr = False,
               cwd = None):
    env = dict(os.environ)

    for e in [REPO_TRACE,
              GIT_DIR,
              'GIT_ALTERNATE_OBJECT_DIRECTORIES',
              'GIT_OBJECT_DIRECTORY',
              'GIT_WORK_TREE',
              'GIT_GRAFT_FILE',
              'GIT_INDEX_FILE']:
      if e in env:
        del env[e]

    command = [GIT]
    command.extend(cmdv)

    stdout = subprocess.PIPE if capture_stdout else None
    if ignore_stdout:
      stdout=file("/dev/null", "w")
    stderr = subprocess.PIPE if capture_stderr else None

    if IsTrace():
      global LAST_CWD
      global LAST_GITDIR

      dbg = ''

      if cwd and LAST_CWD != cwd:
        if LAST_GITDIR or LAST_CWD:
          dbg += '\n'
        dbg += ': cd %s\n' % cwd
        LAST_CWD = cwd

      if GIT_DIR in env and LAST_GITDIR != env[GIT_DIR]:
        if LAST_GITDIR or LAST_CWD:
          dbg += '\n'
        dbg += ': export GIT_DIR=%s\n' % env[GIT_DIR]
        LAST_GITDIR = env[GIT_DIR]

      dbg += ': '
      dbg += ' '.join(command)
      if stdout == subprocess.PIPE:
        dbg += ' 1>|'
      if stderr == subprocess.PIPE:
        dbg += ' 2>|'
      Trace('%s', dbg)

    try:
      p = subprocess.Popen(command,
                           cwd = cwd,
                           env = env,
                           stdout = stdout,
                           stderr = stderr)
    except Exception, e:
      raise Exception('%s: %s' % (command[1], e))

    self.process = p
    self.stdin = p.stdin

  def Wait(self):
    p = self.process

    if p.stdin:
      p.stdin.close()
      self.stdin = None

    if p.stdout:
      self.stdout = p.stdout.read()
      p.stdout.close()
    else:
      p.stdout = None

    if p.stderr:
      self.stderr = p.stderr.read()
      p.stderr.close()
    else:
      p.stderr = None

    return self.process.wait()
