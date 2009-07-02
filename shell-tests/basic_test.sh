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
  "default-revision": "master",
  
  "remotes":
    {"origin": { "fetch": "$TESTDIR/%s" }},
 
  "projects":
    {"repo_a": {},
     "repo_b": {}}
}
EOF

$CREPO init

## Check that the checkouts are correct
for repo in repo_a repo_b ; do
  pushd $repo
  test $(git symbolic-ref HEAD) == "refs/heads/master"
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

## Edit a file and make sure we see it as dirty

echo > repo_a/file_a
! $CREPO check-dirty