#!/bin/bash
# Game-relay client: run a redis-cli command against DB 5 (the mg: keyspace)
# on server.onthe1.app via the existing SSH access.
# Usage: ./via_ssh.sh <redis-cli args...>
#   e.g. ./via_ssh.sh hgetall mg:room:abc:meta
#        ./via_ssh.sh rpush mg:room:abc:moves '{"seq":1,...}'
set -euo pipefail
exec ssh vps redis-cli -n 5 "$@"
