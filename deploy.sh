#!/bin/bash
set -e

REMOTE_USER="macmillan"
REMOTE_HOST="grant.cs.uchicago.edu"
REMOTE_DIR="html"

echo "Building site..."
hugo --minify --cleanDestinationDir

echo "Computing page sizes..."
python3 scripts/page_size.py public/
python3 scripts/page_size.py public/ --verify

echo "Deploying to ${REMOTE_HOST}..."
rsync -azc --delete --itemize-changes \
  --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
  public/ "${REMOTE_USER}@${REMOTE_HOST}:~/${REMOTE_DIR}/"

echo "Done."
