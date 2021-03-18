#!/bin/bash -x

set -e

BINDIR=$(readlink -f $(dirname $0))
CREPO=$BINDIR/../crepo.py

TESTDIR=${TESTDIR:-/tmp/basic_test.$$}
mkdir -p $TESTDIR
cd $TESTDIR


################
# REPO A
################
mkdir repo_a
pushd repo_a
git init
echo "First commit" > file_a
git add . && git commit -a -m '1'

echo "Second commit" > file_b
git add . && git commit -a -m '2'
git tag commit_b

echo "Third commit" >> file_a
git add . && git commit -a -m '3'

REPO_A=`pwd`

popd

################
# REPO B
################
mkdir repo_b
pushd repo_b
git init
echo "First commit" > file_a
git add . && git commit -a -m '1'

echo "Second commit" > file_b
git add . && git commit -a -m '2'
git tag commit_b

echo "Third commit" >> file_a
git add . && git commit -a -m '3'

REPO_B=`pwd`

popd


##############
# Run crepo in a new dir
##############
mkdir tests
pushd tests

cat > manifest.json <<EOF
{
  "default-remote": "origin",
  "default-revision": "main",

  "remotes":
    {"origin": { "fetch": "$TESTDIR/%(name)s" }},

  "projects":
    {"repo_a": {},
     "repo_b": {}}
}
EOF

$CREPO sync

## Check that the checkouts are correct
for repo in repo_a repo_b ; do
  pushd $repo
  test $(git symbolic-ref HEAD) == "refs/heads/main"
  test $(git remote) == "origin"
  test -f file_a
  popd
done

## Go back to a repo and commit something
pushd $REPO_A

echo 'Fourth commit' >> file_a
git commit -a -m '4'

## Update crepo by hard reset
popd
$CREPO fetch
$CREPO status | grep -A1 'repo_a' | grep '1 revisions ahead'
$CREPO hard-reset
test $($CREPO status | grep 'up to date' | wc -l) -eq 2


## Again, go back to a repo and commit something
pushd $REPO_A

echo 'Fifth commit' >> file_a
git commit -a -m '5'

## Update crepo by crepo sync
popd
$CREPO sync
# Make sure we got the update
  pushd repo_a
  git show | grep -q 'Fifth commit'
  popd
test $($CREPO status | grep 'up to date' | wc -l) -eq 2

# Edit a file and make sure we see it as dirty
echo > repo_a/file_a
$CREPO check-dirty && exit 1

## Make sure sync -f blows away changes
$CREPO sync -f
# No longer should be dirty
$CREPO check-dirty

# Commit something locally and do a crepo sync

$CREPO status | grep -A1 'repo_a' | grep -v '1 revisions ahead'
pushd repo_a
  echo 'Local commit' >> file_a
  git commit -a -m 'local'
popd
$CREPO status | grep -A1 'repo_a' | grep '1 revisions ahead of remote'

# Sync shouldn't do anything
$CREPO sync && exit 1
$CREPO status | grep -A1 'repo_a' | grep '1 revisions ahead of remote'

## sync -f shouldn't blow away local changes
$CREPO sync -f && exit 1
$CREPO status | grep -A1 'repo_a' | grep '1 revisions ahead of remote'

echo ALL GOOD
