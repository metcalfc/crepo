#!/bin/bash -x

set -e

BINDIR=$(readlink -f $(dirname $0))
CREPO=$BINDIR/../crepo.py

TESTDIR=${TESTDIR:-/tmp/follow_indirect.$$}
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
COMMIT_C_HASH=$(git rev-parse HEAD)
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
    {"repo_a": { "track-indirect": ".crepo/repo_a" }}
}
EOF

mkdir .crepo
echo "commit_b" > .crepo/repo_a

$CREPO sync

## Check that the checkout is correct
pushd repo_a
test "$(git rev-parse HEAD)" == "$(git rev-parse refs/tags/commit_b)"
test $(git remote) == "origin"
test -f file_a
popd

# Now go check out the new guy
pushd repo_a
git reset --hard $COMMIT_C_HASH
popd

# And update the indirects
$CREPO update-indirect -f

test "$(cat .crepo/repo_a)" == "$COMMIT_C_HASH"