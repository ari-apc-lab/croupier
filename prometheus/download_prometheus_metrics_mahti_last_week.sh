d=`date +%m-%d-%Y_%H-%M-%S`
declare -a metrics=(
'slurm_partition_availability' 
'slurm_partition_avg_alloc_mem' 
'slurm_partition_avg_allocated_cpus_per_job' 
'slurm_partition_avg_allocated_nodes_per_job' 
'slurm_partition_avg_cpus_load_lower' 
'slurm_partition_avg_cpus_load_upper' 
'slurm_partition_avg_execution_time_per_job' 
'slurm_partition_avg_free_mem_lower' 
'slurm_partition_avg_free_mem_upper' 
'slurm_partition_avg_job_size_lower' 
'slurm_partition_avg_job_size_upper' 
'slurm_partition_avg_maximum_allocated_cpus_per_job' 
'slurm_partition_avg_maximum_allocated_nodes_per_job' 
'slurm_partition_avg_memory' 
'slurm_partition_avg_minimum_requested_cpus_per_job' 
'slurm_partition_avg_minimum_requested_memory_per_job' 
'slurm_partition_avg_minimum_requested_nodes_per_job' 
'slurm_partition_avg_pending_jobs' 
'slurm_partition_avg_queue_time_per_job' 
'slurm_partition_avg_requested_cpus_per_job' 
'slurm_partition_avg_running_jobs' 
'slurm_partition_avg_time_left_per_job' 
'slurm_partition_avg_time_limit' 
'slurm_partition_cores' 
'slurm_partition_cpus'
'slurm_partition_node_alloc' 
'slurm_partition_node_idle' 
'slurm_partition_node_other' 
'slurm_partition_node_total' 
'slurm_partition_nodes'
)

download_metric()
{
  echo 'Downloading metric' $1
  target=$1_1w.csv
  metric=$1
  period=1w
  resolution=5m
  #echo "./prom_csv.py -s https://prometheus.croupier.ari-aidata.eu -l hpc=mahti.csc.fi -m $metric -p $period -r $resolution"
  ./prom_csv.py -s https://prometheus.croupier.ari-aidata.eu -l hpc=mahti.csc.fi -m $metric -p $period -r $resolution > $d/$target
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








