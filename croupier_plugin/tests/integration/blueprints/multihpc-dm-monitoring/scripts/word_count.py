#!/usr/bin/python

import sys, getopt
import os
from collections import Counter
from os.path import expanduser


def main(argv):
    in_file = ''
    out_file = ''
    try:
        opts, args = getopt.getopt(argv, "hi:o:", ["ifile=", "ofile="])
    except getopt.GetoptError:
        print('word_count.py -i <text_file> -o <output>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('word_count.py -i <text_file> -o <output>')
            sys.exit()
        elif opt in ("-i", "--ifile"):
            in_file = arg
        elif opt in ("-o", "--ofile"):
            out_file = arg
    if len(opts) == 2:
        home = expanduser("~")
        in_path = in_file
        if in_file.startswith('~'):
            in_path = os.path.join(home, in_file[2:])
        out_path = out_file
        if out_file.startswith('~'):
            out_path = os.path.join(home, out_file[2:])
        with open(in_path) as f:
            # create a list of all words fetched from the file using a list comprehension
            words = [word for line in f for word in line.split()]
            print("The total word count is:", len(words))
            # now use collections.Counter
            c = Counter(words)
            if os.path.exists(out_path):
                os.remove(out_path)
            with open(out_path, 'w') as out:
                for word, count in c.most_common():
                    out.write(word + ': ' + str(count))
    else:
        print('word_count.py -i <text_file> -o <output>')


if __name__ == "__main__":
    main(sys.argv[1:])
