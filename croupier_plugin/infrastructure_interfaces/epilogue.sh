#!/bin/sh

echo "Epilogue Args:"
echo "Job ID: $1"
echo "User ID: $2"
echo "Group ID: $3"
echo "Job Name: $4"
echo "Session ID: $5"
echo "Resource List: $6"
echo "Resources Used: $7"
echo "Queue Name: $8"
echo "Job Account: $9"
echo "Job exit code: $10"
echo "Timestamp: `date +%s`"
echo ""

exit 0