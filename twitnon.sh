#!/bin/sh
mkdir -p out
./twitnon.py > out/$(date -I).html
date -I
