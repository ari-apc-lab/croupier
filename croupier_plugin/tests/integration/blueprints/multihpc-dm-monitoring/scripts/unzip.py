#!/usr/bin/python

import sys, getopt
import zipfile


def main(argv):
    zip_file = ''
    output_directory = ''
    try:
        opts, args = getopt.getopt(argv, "hi:o:", ["ifile=", "ofile="])
    except getopt.GetoptError:
        print('unzip.py -i <zip_file> -o <output_directory>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('unzip.py -i <zipfile> -o <output_directory>')
            sys.exit()
        elif opt in ("-i", "--ifile"):
            zip_file = arg
        elif opt in ("-o", "--ofile"):
            output_directory = arg
    if len(opts) == 2:
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(output_directory)
    else:
        print('unzip.py -i <zip_file> -o <output_directory>')


if __name__ == "__main__":
    main(sys.argv[1:])
