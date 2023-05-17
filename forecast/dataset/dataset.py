import tarfile
import os
import glob


def extract_tarball(tarfile_path, tarfile_target):
    file = tarfile.open(tarfile_path)
    for filename in file.getnames():
        print(filename)
    file.extractall(tarfile_target)
    file.close()

def getPartitionHeader(metric_names):
    header = "date," + ",".join(metric_names) + '\n'
    return header

def getJobsHeader(metric_names):
    header = "job_id," + ",".join(metric_names) + '\n'
    return header

def get_job_metrics_names(metrics):
    metric_names = []
    for partition in metrics.keys(): # Partition iterator
        for job_id in metrics[partition].keys(): # Jobs iterator
            for metric_name in metrics[partition][job_id].keys(): # Metrics iterator:
                if metric_name not in metric_names:
                    metric_names.append(metric_name)
    return metric_names

def read_partition_metrics(metrics_file, metrics):
    metric_names = []
    with open(metrics_file, 'r') as f:
        lines = f.readlines()
        for line in lines[1:]:
            line_split = line.split(',')
            metric_name = line_split[0]
            metric_name = metric_name.replace('slurm_partition_', '')
            if metric_name not in metric_names:
                metric_names.append(metric_name)
            partition = line_split[-1].rstrip()
            if partition not in metrics:
                metrics[partition] = {}
            if metric_name not in metrics[partition]:
                metrics[partition][metric_name] = {}
            index = 2
            for split in line_split[1::2]:
                if '[' in split or ']' in split:
                    # Collect metrics
                    timestamp = split[2:]
                    metric = line_split[index][0:-2].lstrip()
                    index += 2
                    metrics[partition][metric_name][timestamp] = metric

def read_job_metrics(metrics_file, metrics):
    metric_names = []
    with open(metrics_file, 'r') as f:
        lines = f.readlines()
        for line in lines[1:]:
            line_split = line.split(',')
            metric_name = line_split[0]
            metric_name = metric_name.replace('slurm_partition_', '')
            if metric_name not in metric_names:
                metric_names.append(metric_name)
            # detecting last metric entry
            for i, token in enumerate(line_split[1:]):
                if not token.__contains__(']"') and not token.__contains__('"[') :
                    break
            n_metadata = len(line_split) - (i + 1) # get number of remaining metadata
            # checking recording metric style
            priority = None
            if (n_metadata == 8): # old recording of metrics
                time_limit = line_split[-1].rstrip()
                submit_time = line_split[-2]
                priority = line_split[-3] # record priority as metric, not metadata
                partition = line_split[-4]
                job_id = line_split[-5]
                entry = line_split[-10:-8]
            else: # new recording
                time_limit = line_split[-1].rstrip()
                submit_time = line_split[-2]
                partition = line_split[-3]
                job_id = line_split[-4]
                entry = line_split[-9:-7]
            if partition not in metrics:
                metrics[partition] = {}
            if job_id not in metrics[partition]:
                metrics[partition][job_id] = {}
            if "time_limit" not in metrics[partition][job_id]:
                metrics[partition][job_id]["time_limit"] = time_limit
            if "submit_time" not in metrics[partition][job_id]:
                metrics[partition][job_id]["submit_time"] = submit_time
            # TODO process dynamic priority (for new collected metrics after hpc-exporter fix)
            if priority is not None:
                if "priority" not in metrics[partition][job_id]:
                    metrics[partition][job_id]["priority"] = []
                if priority not in metrics[partition][job_id]["priority"]:
                    metrics[partition][job_id]["priority"].append(priority)

            # TODO:
            # Process dynamic metrics: queue_time, execution_time, left_time
            # Adapt indexing when processing new metrics after hpc-exporter fix
            # process changing metrics: start_time (expected, actual), end_time (expected, actual)
            # Adapt indexing when processing new metrics after hpc-exporter fix
            
            metric_timestamp = entry[0][2:].rstrip()
            metric_value = entry[1][:-2].lstrip()
            if metric_name not in metrics[partition][job_id]:
                metrics[partition][job_id][metric_name] = {}
                metrics[partition][job_id][metric_name]["timestamp"] = metric_timestamp
                metrics[partition][job_id][metric_name]["value"] = metric_value
            else:
                if metric_timestamp > metrics[partition][job_id][metric_name]["timestamp"]:
                    metrics[partition][job_id][metric_name]["timestamp"] = metric_timestamp
                    metrics[partition][job_id][metric_name]["value"] = metric_value    

def write_partition_metrics(metrics):
    if not os.path.exists("partitions"):
        os.makedirs("partitions")

    for partition in metrics.keys(): # Partition iterator
        filename = partition + '_partition.csv'
        print("Creating " + filename)
        with open('partitions/' + filename, 'w') as w:
            # Write header
            metric_names = metrics[partition].keys()
            header = getPartitionHeader(metric_names)
            w.write(header)
            # Collect metrics
            partition_metrics = {}
            for metric_name in metrics[partition].keys(): # Metrics iterator
                for timestamp in metrics[partition][metric_name].keys(): # Timestamp iterator
                    if timestamp not in partition_metrics:
                        partition_metrics[timestamp] = {}
                    metric = metrics[partition][metric_name][timestamp]
                    partition_metrics[timestamp][metric_name] = metric  
            # Write metrics
            *_, last = metric_names
            for timestamp in partition_metrics.keys():
                w.write(timestamp + ',')

                for metric_name in metric_names:
                    if metric_name not in partition_metrics[timestamp]:
                        w.write(',')
                    else:
                        w.write(partition_metrics[timestamp][metric_name])
                        if last != metric_name:
                            w.write(',')
                w.write('\n')

def write_job_metrics(metrics):
    if not os.path.exists("jobs"):
        os.makedirs("jobs")

    metric_names = get_job_metrics_names(metrics)
    for partition in metrics.keys(): # Partition iterator
        filename = partition + '_jobs.csv'
        print("Creating " + filename)
        with open('jobs/' + filename, 'w') as w:
            # Write header
            header = getJobsHeader(metric_names)
            w.write(header)
            # Collect metrics
            partition_metrics = {}
            for job_id in metrics[partition].keys(): # Jobs iterator
            # Write job metrics
                *_, last = metric_names
                w.write(job_id + ',')
                for metric_name in metric_names:
                    if metric_name not in metrics[partition][job_id]:
                        w.write(',')
                    else:
                        metric = metrics[partition][job_id][metric_name]
                        if type(metric) is str:
                            w.write(metric)
                        elif type(metric) is dict:
                            w.write(metric["value"])
                        # TODO Evaluate what to do with dynamic metrics
                        elif type(metric) is list:
                            w.write(metric[0])
                        if last != metric_name:
                            w.write(',')
                w.write('\n')

def remove_suffix(input_string, suffix):
    if suffix and input_string.endswith(suffix):
        return input_string[:-len(suffix)]
    return input_string

# Read Metrics (Partition|Jobs)
# Process the tarball with Prometheus metrics, and generates corresponding csv per partition for average partition and jobs metrics
# Process all tarballs in target folder

tarballs_path = "../../prometheus/metrics"
tarballs_target = "./tarballs"
partition_metrics = {}
job_metrics = {}
tarballs = glob.glob(tarballs_path + "/*.tgz")
for tarball in tarballs:
    # unzip file tarball
    tarball_target = tarballs_target + '/' + remove_suffix(tarball[tarball.rfind("/") + 1:], '.tgz')
    extract_tarball(tarball, tarball_target)
    _root, _files = os.walk(tarball_target)
    tarball_target = tarball_target + '/' + _root[1][0]
    for root, dirs, files in os.walk(tarball_target):
        tarfile_target = root   
        for file in files:
            tarfile_path = tarfile_target + '/' + file
            print("Extracting: " + tarfile_path)
            # unzip file tarball
            extract_tarball(tarfile_path, tarfile_target)
            # read metrics
            metrics_file = tarfile_target + '/' + file.replace(".tgz", "")
            if not file.startswith("slurm_partition_job"): 
                pass
                #read_partition_metrics(metrics_file, partition_metrics)
            else:
               read_job_metrics(metrics_file, job_metrics)
            # remove unzip tarball
            os.remove(metrics_file)
            os.remove(tarfile_path)

# Write Partition metrics in csv
# write_partition_metrics(partition_metrics)

# Write Partition metrics in csv
write_job_metrics(job_metrics)