#!/bin/bash
# Game-relay client: run a redis-cli command against DB 5 (the mg: keyspace)
# on server.onthe1.app via the existing SSH access.
# Usage: ./via_ssh.sh <redis-cli args...>
#   e.g. ./via_ssh.sh hgetall mg:room:abc:meta
#        ./via_ssh.sh rpush mg:room:abc:moves '{"seq":1,...}'
#
# NOTE: ssh joins its command arguments with spaces and the remote side runs
# them through a shell, so every argument is re-escaped with printf %q.
# Without this, JSON payloads get mangled by the remote shell (brace
# expansion turns {"seat":0,...} into several garbage words). Bug found by
# the 2026-09-24 relay self-test.
set -euo pipefail
exec ssh vps "redis-cli -n 5 $(printf '%q ' "$@")"
