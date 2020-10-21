import os
import ConfigParser

import requests


def str_to_bool(s):
    if s.lower() == 'true':
        return True
    elif s.lower() == 'false':
        return False
    else:
        raise ValueError  # evil ValueError that doesn't tell you what the wrong value was


class PrometheusPublisher:
    prometheus_server = None
    report_to_monitoring = False

    def __init__(self):
        # Configure Accounting endpoint from configuration file
        config = ConfigParser.RawConfigParser()
        config_file = str(os.path.dirname(os.path.realpath(__file__))) + '/../Croupier.cfg'
        print('Reading Accounting configuration from file {file}'.format(
            file=config_file))
        config.read(config_file)
        try:
            prometheus_server = config.get('Monitoring', 'prometheus_server')
            if prometheus_server is not None:
                self.prometheus_server = prometheus_server

            report_to_monitoring = config.get('Monitoring', 'report_to_monitoring')
            if report_to_monitoring is not None:
                self.report_to_monitoring = str_to_bool(report_to_monitoring)
        except ConfigParser.NoSectionError:
            pass

    def publish_metric(self, job_id, data):
        response = requests.post(
            self.prometheus_server + '/metrics/job/{j}'.format(j=job_id),
            data='{k}\n'.format(k=data))

    def delete_metrics(self, job_id):
        response = requests.delete(
            self.prometheus_server + '/metrics/job/{j}'.format(j=job_id))

    def publish_job_metric(self, job_id, job_name, user_id, workflow_id, queue, metric_label, metric):
        data = '{metric_label}{{job_name="{job_name}", user_id="{user_id}", workflow_id="{workflow_id}, queue="{queue}"}}{metric}' \
            .format(
                metric_label=metric_label, job_name=job_name, user_id=user_id,
                workflow_id=workflow_id, queue=queue, metric=str(metric))
        self.publish_metric(job_id, data)

    def publish_job_queued_time(self, job_id, job_name, user_id, workflow_id, queue, queued_time):
        self.publish_job_metric(job_id, job_name, user_id, workflow_id, queue, "hpc_job_queued_time", queued_time)

    def publish_job_execution_start_time(self, job_id, job_name, user_id, workflow_id, queue, start_time):
        self.publish_job_metric(job_id, job_name, user_id, workflow_id, queue, "hpc_job_execution_start_time",
                                start_time)

    def publish_job_execution_completion_time(self, job_id, job_name, user_id, workflow_id, queue, completion_time):
        self.publish_job_metric(
            job_id, job_name, user_id, workflow_id, queue, "hpc_job_execution_completion_time", completion_time)

    def publish_job_execution_exit_status(self, job_id, job_name, user_id, workflow_id, queue, execution_exit_status):
        self.publish_job_metric(
            job_id, job_name, user_id, workflow_id, queue, "hpc_job_execution_exit_status", execution_exit_status)

    def publish_job_resources_used_cput(self, job_id, job_name, user_id, workflow_id, queue, resources_used_cput):
        self.publish_job_metric(
            job_id, job_name, user_id, workflow_id, queue, "hpc_job_resources_used_cput", resources_used_cput)

    def publish_job_resources_used_cpupercent(self, job_id, job_name, user_id, workflow_id, queue,
                                              resources_used_cpupercent):
        self.publish_job_metric(
            job_id, job_name, user_id, workflow_id, queue, "hpc_job_resources_used_cpupercent",
            resources_used_cpupercent)

    def publish_job_resources_used_ncpus(self, job_id, job_name, user_id, workflow_id, queue, resources_used_ncpus):
        self.publish_job_metric(
            job_id, job_name, user_id, workflow_id, queue, "hpc_job_resources_used_ncpus", resources_used_ncpus)

    def publish_job_resources_used_vmem(self, job_id, job_name, user_id, workflow_id, queue, resources_used_vmem):
        self.publish_job_metric(
            job_id, job_name, user_id, workflow_id, queue, "hpc_job_resources_used_vmem", resources_used_vmem)

    def publish_job_resources_used_mem(self, job_id, job_name, user_id, workflow_id, queue, resources_used_mem):
        self.publish_job_metric(
            job_id, job_name, user_id, workflow_id, queue, "hpc_job_resources_used_mem", resources_used_mem)

    def publish_job_resources_used_walltime(self, job_id, job_name, user_id, workflow_id, queue,
                                            resources_used_walltime):
        self.publish_job_metric(
            job_id, job_name, user_id, workflow_id, queue, "hpc_job_resources_used_walltime", resources_used_walltime)

    def publish_data_transfer_metrics(self, job_name, instance_name, app, transferred_bytes, transfer_time_seconds,
                                      user, wspace, source, destination):
        bandwidth = float(transferred_bytes) / float(transfer_time_seconds)

        # register transferred_bytes
        data = "data_transfer_bytes{hlrs_user_id=\"" + user + "\"," "wspace=\"" + wspace + "\", " "app=\"" + app \
               + "\"," "source=\"" + source + "\", " "destination=\"" + destination + "\"}" + str(transferred_bytes)

        response = requests.post(
            self.prometheus_server + '/metrics/job/{j}/instance/{i}'.format(j=job_name, i=instance_name),
            data='{k}\n'.format(k=data))

        # register duration of the transference
        data = "transfer_time_seconds{hlrs_user_id=\"" + user + "\"," "wspace=\"" + wspace + "\", " "app=\"" + app \
               + "\"," "source=\"" + source + "\", " "destination=\"" + destination + "\"}" + str(transfer_time_seconds)

        response = requests.post(
            self.prometheus_server + '/metrics/job/{j}/instance/{i}'.format(j=job_name, i=instance_name),
            data='{k}\n'.format(k=data))

        # register bandwidth
        data = "bandwidth{hlrs_user_id=\"" + user + "\"," "wspace=\"" + wspace + "\", " "app=\"" + app \
               + "\"," "source=\"" + source + "\", " "destination=\"" + destination + "\"}" + str(bandwidth)

        response = requests.post(
            self.prometheus_server + '/metrics/job/{j}/instance/{i}'.format(j=job_name, i=instance_name),
            data='{k}\n'.format(k=data))

        return response
