#!/bin/sh

echo "Prologue Args:"
echo "Job ID: $1"
echo "User ID: $2"
echo "Group ID: $3"
echo “Job Name: $4”
echo “Requested resource limits: $5”
echo “Job execution queue: $6”
echo “Job account: $7”
echo "Timestamp: `date +%s`"
echo ""

exit 0
