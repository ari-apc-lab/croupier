import os, re, os.path

if not os.path.exists("extracted_metrics"):
    os.makedirs("extracted_metrics")

print("Extracting metrics in folder extracted_metrics. Deleting preexisting files")
for root, dirs, files in os.walk("extracted_metrics"):
    for file in files:
        os.remove(os.path.join(root, file))

metric_names = []
partition_names = []
metrics = {}


def getHeader(partition, metrics):
    header = "date,"
    metric_names = []
    for date in metrics[partition]:
        for metric in metrics[partition][date]:
            if metrics[partition][date][metric] is not None:
                if metric not in metric_names:
                    metric_names.append(metric)
    header = "date," + ",".join(metric_names) + '\n'
    return header


with open('metrics_mahti_last_month.csv', 'r') as f:
    lines = f.readlines()
    for line in lines[1:]:
        line_split = line.split(',')
        metric_name = line_split[0]
        metric_name = metric_name.replace('slurm_partition_', '')
        if metric_name not in metric_names:
            metric_names.append(metric_name)
        line_split = line_split[1:]
        index = 0
        for split in line_split:
            if '[' in split or ']' in split:
                index += 1
            else:
                if "mahti" in line_split[index]:
                    if '/' in line_split[index+3]:
                        break;
                    partition = line_split[index+3]
                    if partition not in partition_names:
                        partition_names.append(partition)
                    if partition not in metrics:
                        metrics[partition] = {}
                    filename = metric_name + '_' + partition + '.txt'
                    # print("Extracting " + filename)
                    # with open('extracted_metrics/' + filename, 'w') as w:
                    #     w.write(line)
                    # Create csv for each metric
                    filename = metric_name + '_' + partition + '.csv'
                    print("Extracting " + filename)
                    with open('extracted_metrics/' + filename, 'w') as w:
                        # Write header
                        w.write("Date," + metric_name + '\n')
                        # Write metrics, one at each line
                        pattern = r'"\[([^\]]+)\]'
                        metric_matches = re.findall(pattern, line)
                        for metric_match in metric_matches:
                            w.write(metric_match.replace(' ', '') + '\n')
                            metric_split = metric_match.split(',')
                            date = metric_split[0]
                            metric = float(metric_split[1])
                            if date not in metrics[partition]:
                                metrics[partition][date] = {}
                            metrics[partition][date][metric_name] = metric
                break

    # Create csv for each partition, collecting metrics for same timestamps
    # print('Metrics: ', metric_names)
    # print('Partitions: ', partition_names)

    for partition in partition_names:
        # Create partition cvs file
        filename = partition + '.csv'
        print("Extracting " + filename)
        with open('extracted_metrics/' + filename, 'w') as w:
            # Write header
            # Filter out metric names for those not collected.
            header = getHeader(partition, metrics)
            w.write(header)
            # for each metrics for given partition
            # Add a metric column in csv file (including header), for identical timestamps
            for date in metrics[partition]:
                line = ""
                line += date;
                for metric in metrics[partition][date]:
                    line += ',' + str(metrics[partition][date][metric])
                line += '\n'
                w.write(line)

