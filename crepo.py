#!/usr/bin/env python2.5
# (c) Copyright 2009 Cloudera, Inc.

import os
import sys
import optparse
import manifest
import logging
import textwrap
from git_command import GitCommand
from git_repo import GitRepo

LOADED_MANIFEST = None
def load_manifest():
  global LOADED_MANIFEST
  if not LOADED_MANIFEST:
    LOADED_MANIFEST = manifest.load_manifest("manifest.json")
  return LOADED_MANIFEST

def help(args):
  """Shows help"""
  if len(args) == 1:
    command = args[0]
    doc = COMMANDS[command].__doc__
    if doc:
      print >>sys.stderr, "Help for command %s:\n" % command
      print >>sys.stderr, doc
      sys.exit(1)
  usage()


def init(args):
  """Initializes repository - DEPRECATED - use sync"""
  print >>sys.stderr, "crepo init is deprecated - use crepo sync"
  sync(args)

def sync(args):
  """Synchronize your local repository with the manifest and the real world.
  This includes:
    - ensures that all projects are cloned
    - ensures that they have the correct remotes set up
    - fetches from the remotes
    - checks out the correct tracking branches
    - if the local branch is not dirty and it is a fast-forward update, merges
      the remote branch's changes in

  Process exit code will be 0 if all projects updated correctly.
  """
  
  man = load_manifest()

  for (name, project) in man.projects.iteritems():
    if not project.is_cloned():
      project.clone()
  ensure_remotes([])
  fetch([])
  checkout_branches([])

  retcode = 0
  
  for project in man.projects.itervalues():
    repo = project.git_repo
    if repo.is_workdir_dirty() or repo.is_index_dirty():
      print >>sys.stderr, "Not syncing project %s - it is dirty." % project.name
      retcode = 1
      continue
    (left, right) = project.tracking_status
    if left > 0:
      print >>sys.stderr, \
            ("Not syncing project %s - you have %d unpushed changes." % 
             (project.name, left))
      retcode = 1
      continue
    elif right > 0:
      repo.check_command(["merge", project.tracker.remote_ref])
    else:
      print >>sys.stderr, "Project %s needs no update" % project.name

  return retcode

def ensure_remotes(args):
  """Ensure that remotes are set up"""
  man = load_manifest()
  for (proj_name, project) in man.projects.iteritems():
    project.ensure_remotes()


def ensure_tracking_branches(args):
  """Ensures that the tracking branches are set up"""
  man = load_manifest()
  for (name, project) in man.projects.iteritems():
    project.ensure_tracking_branch()

def check_dirty(args):
  """Prints output if any projects have dirty working dirs or indexes."""
  man = load_manifest()
  any_dirty = False
  for (name, project) in man.projects.iteritems():
    repo = project.git_repo
    any_dirty = check_dirty_repo(repo) or any_dirty
  return any_dirty

def check_dirty_repo(repo, indent=0):
  workdir_dirty = repo.is_workdir_dirty()
  index_dirty = repo.is_index_dirty()

  name = repo.name
  if workdir_dirty:
    print " " * indent + "Project %s has a dirty working directory (unstaged changes)." % name
  if index_dirty:
    print " " * indent + "Project %s has a dirty index (staged changes)." % name

  return workdir_dirty or index_dirty


def checkout_branches(args):
  """Checks out the tracking branches listed in the manifest."""

  if check_dirty([]) and '-f' not in args:
    raise Exception("Cannot checkout new branches with dirty projects.")
  
  man = load_manifest()
  for (name, project) in man.projects.iteritems():
    print >>sys.stderr, "Checking out tracking branch in project: %s" % name
    project.checkout_tracking_branch()

def hard_reset_branches(args):
  """Hard-resets your tracking branches to match the remotes."""
  checkout_branches(args)
  man = load_manifest()
  for (name, project) in man.projects.iteritems():
    print >>sys.stderr, "Hard resetting tracking branch in project: %s" % name
    project.git_repo.check_command(["reset", "--hard", project.tracker.remote_ref])
  

def do_all_projects(args):
  """Run the given git-command in every project

  Pass -p to do it in parallel"""
  man = load_manifest()

  if args[0] == '-p':
    parallel = True
    del args[0]
  else:
    parallel = False

  towait = []

  for (name, project) in man.projects.iteritems():
    print >>sys.stderr, "In project: ", name, " running ", " ".join(args)
    p = project.git_repo.command_process(args)
    if not parallel:
      p.Wait()
      print >>sys.stderr
    else:
      towait.append(p)

  for p in towait:
    p.Wait()
      
def do_all_projects_remotes(args):
  """Run the given git-command in every project, once for each remote.

  Pass -p to do it in parallel"""
  man = load_manifest()

  if args[0] == '-p':
    parallel = True
    del args[0]
  else:
    parallel = False
  towait = []

  for (name, project) in man.projects.iteritems():
    for remote_name in project.remotes.keys():
      cmd = [arg % {"remote": remote_name} for arg in args]
      print >>sys.stderr, "In project: ", name, " running ", " ".join(cmd)
      p = project.git_repo.command_process(cmd)
      if not parallel:
        p.Wait()
        print >>sys.stderr
      else:
        towait.append(p)
  for p in towait:
    p.Wait()


def fetch(args):
  """Run git-fetch in every project"""
  do_all_projects_remotes(
    args + ["fetch", "-t", "%(remote)s",
            "refs/heads/*:refs/remotes/%(remote)s/*"])

def pull(args):
  """Run git-pull in every project"""
  do_all_projects(args + ["pull", "-t"])

def _format_tracking(local_branch, remote_branch,
                     left, right):
  """
  Takes a tuple returned by repo.tracking_status and outputs a nice string
  describing the state of the repository.
  """
  if (left,right) == (0,0):
    return "Your tracking branch and remote branches are up to date."
  elif left == 0:
    return ("The remote branch %s is %d revisions ahead of tracking branch %s." %
            (remote_branch, right, local_branch))
  elif right == 0:
    return ("Your tracking branch %s is %s revisions ahead of remote branch %s." %
            (local_branch, left, remote_branch))
  else:
    return (("Your local branch %s and remote branch %s have diverged by " +
            "%d and %d revisions.") %
            (local_branch, remote_branch, left, right))

def project_status(project, indent=0):
  repo = project.git_repo
  repo_status(repo,
              project.tracker.tracking_branch,
              project.tracker.remote_ref, indent=indent)

def repo_status(repo, tracking_branch, remote_ref, indent=0):
  # Make sure the right branch is checked out
  if repo.current_branch() != tracking_branch:
    print " " * indent + ("Checked out branch is %s instead of %s" %
                         (repo.current_branch(), tracking_branch))

  # Make sure the branches exist
  has_tracking = repo.has_ref("refs/heads/" + tracking_branch)
  has_remote = repo.has_ref(remote_ref)

  if not has_tracking:
    print " " * indent + "You appear to be missing the tracking branch " + \
          tracking_branch
  if not has_remote:
    print " " * indent + "You appear to be missing the remote branch " + \
          remote_ref

  if not has_tracking or not has_remote:
    return

  # Print tracking branch status
  (left, right) = repo.tracking_status("refs/heads/" + tracking_branch, remote_ref)
  text = _format_tracking(tracking_branch, remote_ref, left, right)
  indent_str = " " * indent
  print textwrap.fill(text, initial_indent=indent_str, subsequent_indent=indent_str)

def status(args):
  """Shows where your branches have diverged from the specified remotes."""
  ensure_tracking_branches([])
  man = load_manifest()
  first = True
  for (name, project) in man.projects.iteritems():
    if not first: print
    first = False

    print "Project %s:" % name
    project_status(project, indent=2)
    check_dirty_repo(project.git_repo,
                     indent=2)

  man_repo = get_manifest_repo()
  if man_repo:
    print
    print "Manifest repo:"
    repo_status(man_repo,
                man_repo.current_branch(),
                "origin/" + man_repo.current_branch(),
                indent=2)
    check_dirty_repo(man_repo, indent=2)


def get_manifest_repo():
  """
  Return a GitRepo object pointing to the repository that contains
  the crepo manifest.
  """
  # root dir is cwd for now
  cdup = GitRepo(".").command_process(["rev-parse", "--show-cdup"],
                                      capture_stdout=True,
                                      capture_stderr=True)
  if cdup.Wait() != 0:
    return None
  cdup_path = cdup.stdout.strip()
  if cdup_path:
    return GitRepo(cdup_path)
  else:
    return GitRepo(".")

def dump_refs(args):
  """
  Output a list of all repositories along with their
  checked out branches and their hashes.
  """
  man = load_manifest()
  first = True
  for (name, project) in man.projects.iteritems():
    if not first: print
    first = False
    print "Project %s:" % name

    repo = project.git_repo
    print "  HEAD: %s" % repo.rev_parse("HEAD")
    print "  Symbolic: %s" % repo.current_branch()
    project_status(project, indent=2)

  repo = get_manifest_repo()
  if repo:
    print
    print "Manifest repo:"
    print "  HEAD: %s" % repo.rev_parse("HEAD")
    print "  Symbolic: %s" % repo.current_branch()
    repo_status(repo,
                repo.current_branch(),
                "origin/" + repo.current_branch(),
                indent=2)
    check_dirty_repo(repo, indent=2)
  


COMMANDS = {
  'help': help,
  'init': init,
  'sync': sync,
  'checkout': checkout_branches,
  'hard-reset': hard_reset_branches,
  'do-all': do_all_projects,
  'fetch': fetch,
  'pull': pull,
  'status': status,
  'check-dirty': check_dirty,
  'setup-remotes': ensure_remotes,
  'dump-refs': dump_refs
  }

def usage():
  print >>sys.stderr, "you screwed up. here are the commands:"
  print >>sys.stderr

  max_comlen = 0
  out = []
  for (command, function) in COMMANDS.iteritems():
    docs = function.__doc__ or "no docs"
    docs = docs.split("\n")[0]
    if len(command) > max_comlen:
      max_comlen = len(command)

    out.append( (command, docs) )

  for (command, docs) in sorted(out):
    command += " " * (max_comlen - len(command))
    available_len = 80 - max_comlen - 5
    output_docs = []
    cur_line = ""
    for word in docs.split(" "):
      if cur_line and len(cur_line + " " + word) > available_len:
        output_docs.append(cur_line)
        cur_line = " " * (max_comlen + 5)
      cur_line += " " + word
    if cur_line: output_docs.append(cur_line)
    print >>sys.stderr, "  %s   %s" % (command, "\n".join(output_docs))
  sys.exit(1)

def main():
  args = sys.argv[1:]
  if len(args) == 0 or args[0] not in COMMANDS:
    usage()
  command = COMMANDS[args[0]]
  sys.exit(command.__call__(args[1:]))

if __name__ == "__main__":
  main()
