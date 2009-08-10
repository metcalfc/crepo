#!/usr/bin/env python2.5
# (c) Copyright 2009 Cloudera, Inc.
import logging
import os
import simplejson

from git_command import GitCommand
from git_repo import GitRepo


class Manifest(object):
  def __init__(self,
               base_dir=None,
               remotes=[],
               projects={},
               default_refspec="master",
               default_remote="origin"):
    self.base_dir = base_dir or os.getcwd()
    self.remotes = remotes
    self.projects = projects
    self.default_refspec = default_refspec
    self.default_remote = default_remote

  @staticmethod
  def from_dict(data, base_dir=None):
    remotes = dict([(name, Remote.from_dict(d)) for (name, d) in data.get('remotes', {}).iteritems()])

    default_remote = data.get("default-remote", "origin")
    assert default_remote in remotes

    man = Manifest(
      base_dir=base_dir,
      default_refspec=data.get("default-revision", "master"),
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
    data = simplejson.load(file(path))
    return cls.from_dict(data, base_dir=os.path.abspath(os.path.dirname(path)))

  def add_project(self, project):
    if project.name in self.projects:
      raise Exception("Project %s already in manifest" % project.name)
    self.projects[project.name] = project

  def to_json(self):
    return simplejson.dumps(self.data_for_json(), indent=2)

  def data_for_json(self):
    return {
      "default-revision": self.default_refspec,
      "default-remote": self.default_remote,
      "remotes": dict( [(name, remote.data_for_json()) for (name, remote) in self.remotes.iteritems()] ),
      "projects": dict( [(name, project.data_for_json()) for (name, project) in self.projects.iteritems()] ),
      }

  def __repr__(self):
    return self.to_json()


class Remote(object):
  def __init__(self,
               fetch):
    self.fetch = fetch

  @staticmethod
  def from_dict(data):
    return Remote(fetch=data.get('fetch'))

  def to_json(self):
    return simplejson.dumps(self.data_for_json(), indent=2)

  def data_for_json(self):
    return {'fetch': self.fetch}

class Project(object):
  def __init__(self,
               name=None,
               manifest=None,
               remotes=None,
               refspec="master", # the remote ref to pull
               from_remote="origin", # where to pull from
               dir=None,
               remote_project_name = None
               ):
    self.name = name
    self.manifest = manifest
    self.remotes = remotes if remotes else []
    self._dir = dir if dir else name
    self.from_remote = from_remote
    self.refspec = refspec
    self.remote_project_name = remote_project_name if remote_project_name else name

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
    return Project(name=name,
                   manifest=manifest,
                   remotes=my_remotes,
                   refspec=data.get('refspec', 'master'),
                   dir=data.get('dir', name),
                   from_remote=from_remote,
                   remote_project_name=remote_project_name)

  @property
  def tracking_branch(self):
    return self.refspec

  @property
  def remote_refspec(self):
    return "%s/%s" % (self.from_remote, self.refspec)

  @property
  def tracking_status(self):
    return self.git_repo.tracking_status(
      self.tracking_branch, self.remote_refspec)

  def to_json(self):
    return simplejson.dumps(self.data_for_json())

  def data_for_json(self):
    return {'name': self.name,
            'remotes': self.remotes.keys(),
            'refspec': self.refspec,
            'from-remote': self.from_remote,
            'dir': self.dir}

  @property
  def dir(self):
    return os.path.join(self.manifest.base_dir, self._dir)

  @property
  def git_repo(self):
    return GitRepo(self.dir)

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
      repo.check_command(["checkout", "--track", "-b", self.tracking_branch,
                        self.remote_refspec])
    else:
      repo.check_command(["checkout"])
    

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
      self.init()

    branch_missing = self.git_repo.command(
      ["rev-parse", "--verify", "-q", self.refspec],
      capture_stdout=True)

    if branch_missing:
      logging.warn("Branch %s does not exist in project %s. checking out." %
                   (self.refspec, name))
      self.git_repo.command(["branch", "--track",
                    self.tracking_branch, self.remote_refspec])
    

  def checkout_tracking_branch(self):
    """Check out the correct tracking branch."""
    self.ensure_tracking_branch()
    self.git_repo.check_command(["checkout", self.tracking_branch])

def load_manifest(path):
  return Manifest.from_json_file(path)


def test_json_load_store():
  man = load_manifest(os.path.join(os.path.dirname(__file__), 'test', 'test_manifest.json'))
  assert len(man.to_json()) > 10
