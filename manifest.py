#!/usr/bin/env python
# (c) Copyright 2009 Cloudera, Inc.
import logging
import os
import re
import simplejson

from git_command import GitCommand
from git_repo import GitRepo


class Manifest(object):
  def __init__(self,
               base_dir=None,
               remotes=[],
               projects={},
               default_ref="master",
               default_remote="origin"):
    self.base_dir = base_dir or os.getcwd()
    self.remotes = remotes
    self.projects = projects
    self.default_ref = default_ref
    self.default_remote = default_remote

  @staticmethod
  def from_dict(data, base_dir=None):
    remotes = dict([(name, Remote.from_dict(d)) for (name, d) in data.get('remotes', {}).iteritems()])

    default_remote = data.get("default-remote", "origin")
    assert default_remote in remotes

    man = Manifest(
      base_dir=base_dir,
      default_ref=data.get("default-revision", "master"),
      default_remote=default_remote,
      remotes=remotes)
    
    for (name, d) in data.get('projects', {}).iteritems():
      man.add_project(Project.from_dict(
        manifest=man,
        name=name,
        data=d))
    return man

  @classmethod
  def from_json_file(cls, path):
    data_txt = file(path).read()
    data_txt = re.sub(r'(?s)/\*.+?\*/', "", data_txt)
    data = simplejson.loads(data_txt)
    return cls.from_dict(data, base_dir=os.path.abspath(os.path.dirname(path)))

  def add_project(self, project):
    if project.name in self.projects:
      raise Exception("Project %s already in manifest" % project.name)
    self.projects[project.name] = project


class IndirectionDb(object):
  # KILL ME?
  OPEN_DBS = {}

  def __init__(self, path):
    self.path = path

    for line in file(path).xreadlines():
      line = line.rstrip()
      key, val = line.split('=', 1)
      self.data[key] = val

  def dump_to(self, path):
    f = file(path, "w")
    try:
       for key, val in sorted(self.data.iteritems()):
         print >>f, "%s=%s\n" % (key, val)
    finally:
      f.close()

  def get_indirection(self, key):
    return self.data.get(key)

  def set_indirection(self, key, val):
    self.data[key] = val

  @classmethod
  def load(cls, path):
    path = os.path.abspath(path)
    if path in cls.OPEN_DBS:
      return cls.OPEN_DBS[path]
    else:
      db = IndirectionDb(path)
      cls.OPEN_DBS[path] = db
      return db



class Remote(object):
  def __init__(self,
               fetch):
    self.fetch = fetch

  @staticmethod
  def from_dict(data):
    return Remote(fetch=data.get('fetch'))


class TrackBranch(object):
  def __init__(self, from_remote, track_branch):
    self.from_remote = from_remote
    self.tracking_branch = track_branch

  @property
  def remote_ref(self):
    return "remotes/%s/%s" % (self.from_remote, self.tracking_branch)

  def tracking_status(self, repo):
    return repo.tracking_status(
      self.tracking_branch, "%s/%s" % (self.from_remote, self.tracking_branch))

  def create_tracking_branch(self, repo):
    repo.command(["branch", "--track",
                  self.tracking_branch, self.remote_ref])


class TrackHash(object):
  def __init__(self, hash):
    self.hash = hash

  @property
  def tracking_branch(self):
    return "crepo"

  @property
  def remote_ref(self):
    return self.hash

  def tracking_status(self, repo):
    return repo.tracking_status(
      "crepo", self.hash)

  def create_tracking_branch(self, repo):
    repo.command(["branch", "crepo", self.hash])


class TrackTag(object):
  def __init__(self, tag):
    self.tag = tag

  @property
  def tracking_branch(self):
    return self.tag

  @property
  def remote_ref(self):
    return "refs/tags/" + self.tag

  def tracking_status(self, repo):
    return repo.tracking_status(
      "refs/heads/%s" % self.tag, self.remote_ref)

  def create_tracking_branch(self, repo):
    repo.command(["branch", self.tag, self.remote_ref])


class TrackIndirect(object):
  def __init__(self, indirection_file):
    self.indirection_file = os.path.abspath(indirection_file)

  @property
  def tracking_branch(self):
    return "crepo"

  @property
  def remote_ref(self):
    return file(self.indirection_file).read().strip()

  def tracking_status(self, repo):
    return repo.tracking_status(
      self.tracking_branch, self.remote_ref)

  def create_tracking_branch(self, repo):
    repo.command(["branch", self.tracking_branch, self.remote_ref])



class Project(object):
  def __init__(self,
               name=None,
               manifest=None,
               remotes=None,
               tracker=None,
               from_remote="origin", # where to pull from
               dir=None,
               remote_project_name = None
               ):
    self.name = name
    self.manifest = manifest
    self.remotes = remotes or []
    self._dir = dir or name
    self.tracker = tracker
    self.from_remote = from_remote
    self.remote_project_name = remote_project_name or name
    # If this project tracks hash or indirect, it may already be up-to-date
    try:
        self.__is_uptodate = \
            (self.tracker.remote_ref == self.git_repo.rev_parse("HEAD"))
    except Exception:                   # Error due to uninitialized project
        self.__is_uptodate = False

  def __str__(self):
    return "Project %s" % (self.name,)

  @staticmethod
  def from_dict(manifest, name, data):
    my_remote_names = data.get('remotes', [manifest.default_remote])
    my_remotes = dict([ (r, manifest.remotes[r])
                        for r in my_remote_names])

    from_remote = data.get('from-remote')
    if not from_remote:
      if len(my_remote_names) == 1:
        from_remote = my_remote_names[0]
      elif manifest.default_remote in my_remote_names:
        from_remote = manifest.default_remote
      else:
        raise Exception("no from-remote listed for project %s, and more than one remote" %
                        name)
    
    assert from_remote in my_remote_names
    remote_project_name = data.get('remote-project-name')

    track_tag = data.get('track-tag')
    track_branch = data.get('track-branch')
    track_hash = data.get('track-hash')
    track_indirect = data.get('track-indirect')

    if len(filter(None, [track_tag, track_branch, track_hash, track_indirect])) > 1:
      raise Exception(
        "Cannot specify more than one of track-branch, track-tag, " +
        "track-hash, or track-indirect for project %s" % name)

    # This is old and deprecated
    ref = data.get('refspec')
    if not track_tag and not track_branch and not track_hash and not track_indirect:
      if ref:
        logging.warn("'ref' is deprecated - use either track-branch or track-tag " +
                     "for project %s" % name)
        track_branch = ref
      else:
        track_branch = "master"

    if track_tag:
      tracker = TrackTag(track_tag)
    elif track_branch:
      tracker = TrackBranch(from_remote, track_branch)
    elif track_hash:
      tracker = TrackHash(track_hash)
    elif track_indirect:
      tracker = TrackIndirect(track_indirect)
    else:
      assert False and "Cannot get here!"


    return Project(name=name,
                   manifest=manifest,
                   remotes=my_remotes,
                   tracker=tracker,
                   dir=data.get('dir', name),
                   from_remote=from_remote,
                   remote_project_name=remote_project_name)


  @property
  def tracking_status(self):
    return self.tracker.tracking_status(self.git_repo)

  @property
  def dir(self):
    return os.path.join(self.manifest.base_dir, self._dir)

  @property
  def git_repo(self):
    return GitRepo(self.dir)

  def is_uptodate(self):
    return self.__is_uptodate

  def is_cloned(self):
    return self.git_repo.is_cloned()

  ############################################################
  # Actual actions to be taken on a project
  ############################################################

  def clone(self):
    if self.is_cloned():
      return
    logging.warn("Initializing project: %s" % self.name)
    clone_remote = self.manifest.remotes[self.from_remote]
    clone_url = clone_remote.fetch % {"name": self.remote_project_name}
    p = GitCommand(["clone", "-o", self.from_remote, "-n", clone_url, self.dir])
    p.Wait()

    repo = self.git_repo
    if repo.command(["show-ref", "-q", "HEAD"]) != 0:
      # There is no HEAD (maybe origin/master doesnt exist) so check out the tracking
      # branch
      self.tracker.create_tracking_branch(repo)
      repo.check_command(["checkout", self.tracker.tracking_branch])
    else:
      repo.check_command(["checkout"])
    self.__is_uptodate = True
    

  def ensure_remotes(self):
    repo = self.git_repo
    for remote_name in self.remotes:
      remote = self.manifest.remotes[remote_name]
      new_url = remote.fetch % { "name": self.remote_project_name }

      p = repo.command_process(["config", "--get", "remote.%s.url" % remote_name],
                               capture_stdout=True)
      if p.Wait() == 0:
        cur_url = p.stdout.strip()
        if cur_url != new_url:
          repo.check_command(["config", "--replace-all", "remote.%s.url" % remote_name, new_url])
      else:
        repo.check_command(["remote", "add", remote_name, new_url])

  def ensure_tracking_branch(self):
    """Ensure that the tracking branch exists."""
    if not self.is_cloned():
      self.clone()

    branch_missing = self.git_repo.command(
      ["rev-parse", "--verify", "-q", "refs/heads/%s" % self.tracker.tracking_branch],
      capture_stdout=True)

    if branch_missing:
      logging.warn("Branch %s does not exist in project %s. checking out." %
                   (self.tracker.tracking_branch, self.name))
      self.tracker.create_tracking_branch(self.git_repo)
    

  def checkout_tracking_branch(self):
    """Check out the correct tracking branch."""
    self.ensure_tracking_branch()
    self.git_repo.check_command(["checkout", self.tracker.tracking_branch])
    self.__is_uptodate = True
