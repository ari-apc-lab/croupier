#!/usr/bin/env python

import csv
import requests
import sys


def get_metrics_names(url, metrics_prefix):
    response = requests.get('{0}/api/v1/label/__name__/values'.format(url))
    names = response.json()['data']
    # Filter by prefix
    if metrics_prefix:
        names = [n for n in names if n.startswith(metrics_prefix)]
    # Return metrix names
    return names


def parse_arguments(args):
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

    ap.add_argument("-r", "--resolution", required=False,
                    help="time interval between reported metrics within the given period in Prometheus notation. "
                         "Default: not set, Prometheus default")

    ap.add_argument("-sm", "--show_metrics", required=False,
                    help="print available metrics")

    ap.add_argument("-mp", "--metrics_prefix", required=False,
                    help="filter metrics by prefix")

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
args = parse_arguments(sys.argv[1:])

prometheus = args['prometheus_server']
metrics = args['metrics']
labels = args['labels']
period = args['period']
resolution = args['resolution']
show_metrics = args["show_metrics"]
metrics_prefix = args["metrics_prefix"]


# metrics
if metrics:
    metricNames = metrics.split(",")
    metricNames = [m.strip() for m in metricNames]
else:
    metricNames = get_metrics_names(prometheus, metrics_prefix)

# show-metrics
if bool(show_metrics):
    print('Available Metrics:')
    print(metricNames)
    exit(0)

# period
if not period and not resolution:
    period = '[1h]'
elif not period and resolution:
    period = '[1h:' + resolution + ']'
elif period and not resolution:
    period = '[' + period + ']'
else:
    period = '[' + period + ":" + resolution + ']'

# labels
if labels:
    labels = labels.split(",")
    labels = [l.split("=")[0] + "=" + "\"" + l.split("=")[1] + "\"" for l in labels]
    labels = ','.join(labels)

writeHeader = True
timeout = 60*10  # 10 minutes
for metricName in metricNames:
    # now its hardcoded for hourly
    if not labels:
        query = metricName + period
    else:
        query = metricName + "{" + labels + "}" + period
    response = requests.get('{0}/api/v1/query'.format(prometheus), params={'query': query}, timeout=timeout)
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
