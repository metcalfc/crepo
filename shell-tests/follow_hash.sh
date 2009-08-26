#!/bin/bash -x

set -e

DIRNAME=$(dirname $0)
BINDIR=$(python -c "import os; print os.path.abspath('$DIRNAME')")
CREPO=$BINDIR/../crepo.py

TESTDIR=${TESTDIR:-/tmp/follow_hash.$$}
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
COMMIT_B=$(git rev-parse commit_b)

echo "Third commit" >> file_a
git add . && git commit -a -m '3'

REPO_A=`pwd`

popd

##############
# Run crepo in a new dir
##############
mkdir tests
pushd tests

cat > manifest.json <<EOF
{  
  "remotes":
    {"origin": { "fetch": "$TESTDIR/%(name)s" }},
 
  "projects":
    {"repo_a": { "track-hash": "$COMMIT_B" }}
}
EOF

$CREPO sync

## Check that the checkout is correct
pushd repo_a
test $(git symbolic-ref HEAD) == "refs/heads/crepo"
test $(git remote) == "origin"
test -f file_a
test -f file_b
popd
