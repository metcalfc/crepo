#!/bin/bash -x

set -e

BINDIR=$(readlink -f $(dirname $0))
CREPO=$BINDIR/../crepo.py

! $CREPO help
! $CREPO asdf