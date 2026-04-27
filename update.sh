#!/bin/bash
set -e

git pull

export GIT_COMMIT=$(git rev-parse HEAD)
export GIT_DATE=$(git log -1 --format=%ci)
export GIT_MESSAGE=$(git log -1 --format=%s)

docker compose up -d --build
