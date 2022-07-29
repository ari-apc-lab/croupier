#!/usr/bin/env python

import csv
import requests
import sys


def GetMetrixNames(url):
    response = requests.get('{0}/api/v1/label/__name__/values'.format(url))
    names = response.json()['data']
    # Return metrix names
    return names


def parseArguments(args):
    import argparse

    ap = argparse.ArgumentParser()

    ap.add_argument("-s", "--prometheus_server", required=True,
                    help="endpoint to Prometheus server")

    ap.add_argument("-m", "--metrics", required=False,
                    help="comma separate list of metrics to get. If not set, all metrics are returned")

    ap.add_argument("-l", "--labels", required=False,
                    help="comma separate list of labels in form label=value. "
                         "If set, returned metrics are filtered out by these labels, otherwise not")

    ap.add_argument("-p", "--period", required=False,
                    help="time period of collected metrics in Prometheus notation. Default: [1h]")

    args = vars(ap.parse_args())
    return args


"""
Prometheus hourly data as csv.
"""
writer = csv.writer(sys.stdout)

# if len(sys.argv) != 2:
#     print('Usage: {0} http://localhost:9090'.format(sys.argv[0]))
#     sys.exit(1)

# Parse arguments
args = parseArguments(sys.argv[1:])

prometheus = args['prometheus_server']
metrics = args['metrics']
labels = args['labels']
period = args['period']

# metrics
if metrics:
    metrixNames = metrics.split(",")
    metrixNames = [m.strip() for m in metrixNames]
else:
    metrixNames = GetMetrixNames(prometheus)

# period
if not period:
    period = '[1h]'

# labels
if labels:
    labels = labels.split(",")
    labels = [l.split("=")[0] + "=" + "\"" + l.split("=")[1] + "\"" for l in labels]
    labels = ','.join(labels)

writeHeader = True
for metrixName in metrixNames:
    # now its hardcoded for hourly
    if not labels:
        query = metrixName + period
    else:
        query = metrixName + "{" + labels + "}" + period
    response = requests.get('{0}/api/v1/query'.format(prometheus), params={'query': query})
    results = response.json()['data']['result']
    # Build a list of all labelnames used.
    # gets all keys and discard __name__
    labelnames = set()
    for result in results:
        labelnames.update(result['metric'].keys())
    # Canonicalize
    labelnames.discard('__name__')
    labelnames = sorted(labelnames)
    # Write the samples.
    if writeHeader:
        writer.writerow(['name', 'timestamp', 'value'] + labelnames)
        writeHeader = False
    for result in results:
        # convert result values to float
        result["values"] = [[entry[0], float(entry[1])] for entry in result["values"]]
        l = [result['metric'].get('__name__', '')] + result['values']
        for label in labelnames:
            l.append(result['metric'].get(label, ''))
        writer.writerow(l)
