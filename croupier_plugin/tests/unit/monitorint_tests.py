from croupier_plugin.monitoring.monitoring import (PrometheusPublisher)

monitoring_client = PrometheusPublisher()

monitoring_client.delete_metrics('my_job_id')

data = 'hpc_job_cput{job_name="job_name", user_id="user_id", workflow_id="workflow_id", queue="queue"}25'
#monitoring_client.publish_metric("my_job_id", data)