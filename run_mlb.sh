#!/bin/bash

PAC_TZ="America/Los_Angeles"

# Loop until Pacific time is after 11:55 PM
while [ "$(TZ=$PAC_TZ date +%H%M)" -lt 2355 ]; do
    python3 mlb.py
    sleep 20
done
