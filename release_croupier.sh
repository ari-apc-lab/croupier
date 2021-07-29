rm croupier.zip
rm *.wgn
git pull
zip -qr croupier.zip ../croupier
wagon create -f ./croupier.zip -a '--no-cache-dir -c ./constraints.txt'
