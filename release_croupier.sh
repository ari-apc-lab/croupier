#!/bin/bash
echo $# arguments
if [ "$#" -ne 1 ]; then
    echo "Error: croupier branch not provided. Use: release_croupier <branch>" >&2
    exit 2
fi

rm croupier.zip
rm *.wgn
git pull origin $1
zip -qr croupier.zip ../croupier
wagon create -f ./croupier.zip -a '--no-cache-dir -c ./constraints.txt'
