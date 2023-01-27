d=`date +%m-%d-%Y_%H-%M-%S`
declare -a metrics=('slurm_partition_availability' 'slurm_partition_avg_alloc_mem' 'slurm_partition_avg_allocated_cpus_per_job' 'slurm_partition_avg_allocated_nodes_per_job' 'slurm_partition_avg_cpus_load_lower' 'slurm_partition_avg_cpus_load_upper' 'slurm_partition_avg_execution_time_per_job' 'slurm_partition_avg_free_mem_lower' 'slurm_partition_avg_free_mem_upper' 'slurm_partition_avg_job_size_lower' 'slurm_partition_avg_job_size_upper' 'slurm_partition_avg_maximum_allocated_cpus_per_job' 'slurm_partition_avg_maximum_allocated_nodes_per_job' 'slurm_partition_avg_memory' 'slurm_partition_avg_minimum_requested_cpus_per_job' 'slurm_partition_avg_minimum_requested_memory_per_job' 'slurm_partition_avg_minimum_requested_nodes_per_job' 'slurm_partition_avg_pending_jobs' 'slurm_partition_avg_queue_time_per_job' 'slurm_partition_avg_requested_cpus_per_job' 'slurm_partition_avg_running_jobs' 'slurm_partition_avg_time_left_per_job' 'slurm_partition_avg_time_limit' 'slurm_partition_cores', 'slurm_partition_cpus' 'slurm_partition_job_allocated_minimum_requested_nodes' 'slurm_partition_job_end_time', 'slurm_partition_job_execution_time' 'slurm_partition_job_maximum_allocated_cpus' 'slurm_partition_job_maximum_allocated_nodes' 'slurm_partition_job_minimum_requested_cpus' 'slurm_partition_job_minimum_requested_memory' 'slurm_partition_job_queue_time' 'slurm_partition_job_requested_allocated_cpus' 'slurm_partition_job_start_time' 'slurm_partition_job_state' 'slurm_partition_job_time_left' 'slurm_partition_node_alloc' 'slurm_partition_node_idle' 'slurm_partition_node_other' 'slurm_partition_node_total' 'slurm_partition_nodes')

download_metric()
{
  echo 'Downloading metric' $1
  target=$1_1w.csv
  metric=$1
  ./prom_csv.py -s https://prometheus.croupier.ari-aidata.eu -l hpc=mahti.csc.fi -m $metric -p 1w -r 5m > $d/$target
  cd $d
  tar cvzf $target.tgz $target
  rm $target
  cd ..
}

mkdir -p $d
#Download metrics
for m in "${metrics[@]}"
do
  download_metric $m
done
exit








