from croupier_plugin.monitoring.monitoring import (PrometheusPublisher)

monitoring_client = PrometheusPublisher()

monitoring_client.delete_metrics('258771.cl5intern')