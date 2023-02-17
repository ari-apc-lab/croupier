d=`date +%m-%d-%Y_%H-%M-%S`
declare -a metrics=(
'slurm_partition_job_allocated_minimum_requested_nodes' 
'slurm_partition_job_end_time'
'slurm_partition_job_execution_time'
'slurm_partition_job_maximum_allocated_cpus'
'slurm_partition_job_maximum_allocated_nodes'
'slurm_partition_job_minimum_requested_cpus'
'slurm_partition_job_minimum_requested_memory'
'slurm_partition_job_queue_time'
'slurm_partition_job_requested_allocated_cpus'
'slurm_partition_job_start_time'
'slurm_partition_job_state'
'slurm_partition_job_time_left'
)

download_metric_part(){
  metric=$1
  period=1d
  resolution=5m
  if [ $# -eq 1 ]
  then
    echo 'Downloading metric part with no offset'
    target=$1_1d.csv
    #echo "./prom_csv.py -s https://prometheus.croupier.ari-aidata.eu -l hpc=mahti.csc.fi -m $metric -p $period -r $resolution"
    ./prom_csv.py -s https://prometheus.croupier.ari-aidata.eu -l hpc=mahti.csc.fi -m $metric -p $period -r $resolution > $d/$target
    cd $d
    tar cvzf $target.tgz $target
    rm $target
    cd ..
  else
    offset=$2
    echo 'Downloading metric part with offset ' "$offset"
    target=$1_1d_offset_$offset.csv
    #echo "./prom_csv.py -s https://prometheus.croupier.ari-aidata.eu -l hpc=mahti.csc.fi -m $metric -p $period -r $resolution -o $offset"
    ./prom_csv.py -s https://prometheus.croupier.ari-aidata.eu -l hpc=mahti.csc.fi -m $metric -p $period -r $resolution -o $offset > $d/$target
    cd $d
    tar cvzf $target.tgz $target
    rm $target
    cd ..
  fi
}

download_metric()
{
  echo 'Downloading metric' "$1"
  download_metric_part "$1"
  offsets=(1d 2d 3d 4d 5d 6d)
  for offset in "${offsets[@]}"; do
    download_metric_part "$1" "$offset"
  done
}

mkdir -p $d
#Download metrics
for m in "${metrics[@]}"
do
  download_metric "$m"
done
exit








