#!/usr/bin/env python

#This script has to be executed with the vendor account
#it is assumed that the vendor has GridFtp credentials, and it is installed the grid-proxy in the machine where this script is executed.

#NOTICE: If -p provide a filename, and the Destination is a folder end with '/', then the file is copied in that folder at destination.
#WARNING: If -p provide a filename, and the Destination does not ended with '/' then the file will be uploaded renamed as the Destination provided.
#NOTICE: If -p provide a directory, then the Destination will be considered as a directory at destination even not ended with '/'.

#sudo add-apt-repository ppa:maarten-baert/simplescreenrecorder
#Author: Jose Miguel Montanana, montanana@hlrs.de
#version 1.1, 24-Mar-2020.

#Tested with python3.6.9 in Ubuntu 18.04 64bits, and Hezelhen system.
#TODO: Before use it need to test the input parameters are correct received from the Cloudify blueprint/yaml file.
#TODO: modify to support 2 different GridFTP servers, current version only uses the hezelhen GridFtp.

# THIS ARE THE EXAMPLES YOU SHOW IN THE DEMO:
#python data_mover.py -s ATOSFR -u hpcuserid -w olu -t download -p 'hello_jose.txt' -d 'hello_jose.txt' -x ~/globus_fr/userkey.pem -z ~/globus_fr/usercert.pem
#python data_mover.py -s HLRS -u hpcjmont -w new -t upload -p 'hello_jose.txt' -d 'hello_jose.txt' -x ~/globus_hlrs/userkey.pem -z ~/globus_hlrs/usercert.pem

import os
import sys
import wget
import os.path
import tarfile
import time
import subprocess
from os import path
from cloudify import ctx
from shutil import copyfile
from pathlib import Path
import subprocess
from os.path import expanduser
home = expanduser("~")


#HLRS GRIDFTP params:
HLRS_WS_BASE_PATH="lustre/cray/ws9/6/ws"
#the port at hezelhen is not the standard for gridftp (2811)
HLRS_GRIDFTP_PORT=2812
HLRS_GRIDFTP_HOST="gridftp-fr1.hww.de"
HLRS_SSH_HOST="hazelhen.hww.de"


#ATOSFR GRIDFTP params:
ATOSFR_WS_BASE_PATH="home/euxdat_user/user-data"
ATOSFR_GRIDFTP_PORT=2811
ATOSFR_GRIDFTP_HOST="gridftp-s1.euxdat.eu"

#the maximum possible value for the lifetime is 30 !
lifetime=1
user_ssh_credentials=home+"/.ssh/id_rsa"
dest_output=""
source_input=""
userkey_file=""
usercert_file=""
DEBUG="FALSE"

#EXAMPLE input parameters
ws_name="olu88"
user_id="hpcxxx"
source_input="localfolder.txt"
dest_output="demo"  # WARNING, if "source_input" points to a file, then the file will be renamed at destination as "dest_output" if "dest_output" doesnt ends with '/'
type_transfer="upload"
lifetime=1
userkey_file=home+"/.globus/userkey.pem"
usercert_file=home+"/.globus/usercert.pem"

def show_help():
	print ("Wrapper for uploading files in to Hazelhen GridFtp and ATOS-Fr GridFTP")
	print ("v1.1 MAR-2020$")
	print ("\n To see this help run: python data_mover.py -h\n")

	print ("Sintaxis:")
	print (" GrifFTP server [-s HLRS/ATOSFR]  <- Mandatory")
	print (" user_id at hezelhen [-u user_id]  <- Mandatory")
	print (" transfer type [-t upload/download/grid2grid]  <- Mandatory")
	print (" Workspace name [-w ws_name] <- Mandatory")
	print (" Path to data to upload [-p path to file or folder] <- Mandatory")
	print (" Destination [-d dest] <- Optional, default value is empty script")
	print (" Lifetime [-l time_in_days] <- Optional, maximum valid value is 30")
	print (" userkey.pem file path [-x path] <- Mandatory")
	print (" usercert.pem file path [-z path] <- Mandatory")

	print ("\n\n NOTICE: If -p provide a filename, and the Destination is a folder end with '/', then the file is copied in that folder at destination.")
	print (" WARNING: If -p provide a filename, and the Destination does not ended with '/' then the file will be uploaded renamed as the Destination provided.")
	print (" NOTICE: If -p provide a directory, then the Destination will be considered as a directory at destination even not ended with '/'.")

	print ("\n\nEXAMPLES:")
	print (" python data_mover.py -s HLRS -u hpcuserid -w olu -t upload -p localfolder_or_localfile -d dest_output_or_renamedfile -x path_userkey.pem -z path_usercert.pem\n")
	print (" python data_mover.py -s ATOSFR -u hpcuserid -w olu -t download -p localfolder_or_localfile -d dest_output_or_renamedfile -x path_userkey.pem -z path_usercert.pem\n")
	print (" python data_mover.py -u hpcuserid -w olu -t grid2grid -p localfolder_or_localfile -d dest_output_or_renamedfile -x path_userkey.pem -z path_usercert.pem\n")
	sys.exit(1)

############## Allocate workspace via SSH
# The workspace will be reused if it already exists, and the lifetime will not be extended
def create_ws(user_id, SSH_HOST, user_ssh_credentials, ws_name, LIFETIME):
	#example of exec: ssh $user_id@$SSH_HOST -i $user_ssh_credentials "module load system/ws_tools; ws_allocate $ws_name $LIFETIME;";
	command="ssh "+ user_id+"@"+SSH_HOST+" -i "+user_ssh_credentials+" \"module load system/ws_tools; ws_allocate "+ws_name+" "+format(lifetime, "d")+"\""
	print (" create_ws "+ command)
	try:
		server_response=subprocess.check_output(command, shell=True)
	except subprocess.CalledProcessError as grepexc:
		print ("Error creating workspace.")
		print ("error code", grepexc.returncode, grepexc.output)
		sys.exit(1)
	response=server_response.decode("utf-8")
	return response


#need a timeout for not whilisted ips
############## delete the workspace via SSH after end the application and we collected the outputs
# Warning this must be done ONLY after the output result-files are copied in a external storage!
#example: ssh user_id@SSH_HOST -i user_ssh_credentials "module load system/ws_tools ws_release ws_name"
def delete_ws(user_id, SSH_HOST, user_ssh_credentials, ws_name):
	command="ssh "+ user_id+"@"+SSH_HOST+" -i "+user_ssh_credentials+" \"module load system/ws_tools; ws_release "+ws_name+"\""
	try:
		server_response=subprocess.check_output(command, shell=True)
	except subprocess.CalledProcessError as grepexc:
		print ("Error removing workspace.")
		print ("error code", grepexc.returncode, grepexc.output)
		sys.exit(1)
	response=server_response.decode("utf-8")
	return response

def get_size(start_path):
	total_size = 0
	if os.path.isfile(start_path):
		total_size += os.path.getsize(start_path)
	else:
		for dirpath, dirnames, filenames in os.walk(start_path):
			for f in filenames:
				fp = os.path.join(dirpath, f)
				# skip if it is symbolic link
				if not os.path.islink(fp):
					total_size += os.path.getsize(fp)
	return total_size


# TODO: Next variables has to be defined in the cloudify blue print !!!!

ws_name=inputs["ws_name"]
user_id=inputs["user_id"]
source_input=inputs["source_input"]
dest_output=inputs["dest_output"]
type_transfer=inputs["type_transfer"]
lifetime=inputs["lifetime"]
userkey_file=inputs["userkey_file"]
usercert_file=inputs["usercert_file"]

############## Verification of Mandatory input parameters
if DEBUG == "TRUE":
	print ("Verification of Mandatory input parameters.")
if not source_input:
	print ("Error: missing or empty input parameter '-p Path_to_data_to_upload.")
	sys.exit(1)
if not userkey_file:
	print ("Error: missing or empty parameter: -x user_key_file.")
	sys.exit(1)
if not usercert_file:
	print ("Error: missing or empty parameter: -z user_cert_file.")
	sys.exit(1)
if not dest_output:
	print ("Error: missing or empty parameter: -d dest_output.")
	sys.exit(1)

# fixing the directory paths that dont ends with '/'
if DEBUG == "TRUE":
	print ("Fixing the directory paths that dont ends with '/'.")
if type_transfer == "upload":
	# if source is a path, then it must end with "/"
	if path.isdir(source_input):
		if source_input[-1] != '/':
			source_input=source_input+'/'
	# if src is a path, then dst must end with "/"
	if source_input[-1] == '/':
		if dest_output[-1] != '/':
			dest_output=dest_output+'/'

if type_transfer == "download":
	# if dest is a path, then it must end with "/"

	if path.isdir(dest_output):
		if dest_output[-1] != '/':
			dest_output=dest_output+'/'
	# if dest is a path, then src must end with "/"
	if dest_output[-1] == '/':
		if source_input[-1] != '/':
			source_input=source_input+'/'

if DEBUG == "TRUE":
	print ("Allocate workspace via SSH.")
if SERVER == "HLRS":
	new_wspath=create_ws(user_id, SSH_HOST, user_ssh_credentials, ws_name, lifetime)
else:
	new_wspath=""

# IMPORTANT: we need to return the workspace path
#ctx.node.properties['workspace'] =new_wspath

############## Request to create the destination folder, it may not exists yet.
#first, need to know if the destination is a folder, then we remove the end before the last character "/"
new_path=""
if DEBUG == "TRUE":
	print ("Request to create the destination folder, it may not exists yet.")
new_folder=dest_output
if "/" not in new_folder:
	while new_folder and new_folder[-1] != "/":
		new_folder=new_folder[:-1]
	if new_folder != '/' and SERVER == "HLRS":
		#now, request to create that folder at destination if not empty path
		command="ssh "+ user_id+"@"+SSH_HOST+" -i "+user_ssh_credentials+" \"mkdir -p /"+WS_BASE_PATH+"/"+user_id+"-"+ws_name+"/"+new_folder+"\""
		try:
			server_response=subprocess.check_output(command, shell=True)
		except subprocess.CalledProcessError as grepexc:
			print("Error creating folder in the workspace")
			print ("error code", grepexc.returncode, grepexc.output)
			sys.exit(1)

############## Preparation of the GRIDFTP certificates
# notice that starting the grid-proxy-init may ask for a password if the keys are encrypted.
if DEBUG == "TRUE":
	print ("Preparation of the GRIDFTP certificates.")

if not os.path.exists(home+"/.globus"):
	os.mkdir( home+"/.globus")
elif not os.path.isdir(home+"/.globus"):
	print ("Error: "+home+"/.globus must be a folder.")
	sys.exit(1)

my_file = Path(userkey_file)
if not my_file.is_file():
	print ("Error: user key file not found.")
	sys.exit(1)

if userkey_file != home+"/.globus/userkey.pem":
	copyfile(userkey_file, home+"/.globus/userkey.pem")

my_file = Path(usercert_file)
if not my_file.is_file():
	print ("Error: user cert file not found.")
	sys.exit(1)

if usercert_file != home+"/.globus/usercert.pem":
	copyfile( usercert_file , home+"/.globus/usercert.pem")
thecertpath=home+"/.globus/usercert.pem"
thecertkey=home+"/.globus/userkey.pem"

my_file = Path(thecertpath)
if not my_file.is_file():
	print ("Error: missing credentials (cert)")
	sys.exit(1)
my_file = Path(thecertkey)
if not my_file.is_file():
	print ("Error: missing credentials (key)")
	sys.exit(1)

os.chmod(home+"/.globus/usercert.pem", 0o0644)
os.chmod(home+"/.globus/userkey.pem", 0o0600)

if not os.path.exists(home+"/.globus/certificates"):
	os.mkdir( home+"/.globus/certificates", 0o0755 )
	download_folder=home+"/.globus/certificates/"
	os.chdir(download_folder)
	url = " https://winnetou.surfsara.nl/prace/certs/globuscerts.tar.gz"
	wget.download(url, download_folder)
	my_file = Path(download_folder+"globuscerts.tar.gz")
	if not my_file.is_file():
		print ("Error: file globuscerts.tar.gz not found.")
		sys.exit(1)
	tar = tarfile.open("globuscerts.tar.gz")
	tar.extractall(path=os.path.dirname(download_folder)) # untar file into same directory
	tar.close()
	os.remove("globuscerts.tar.gz")
elif not os.path.isdir(home+"/.globus/certificates"):
	print ("Error: "+home+"/.globus/certificates must be a folder.")
	sys.exit(1)

############## start the gridftp proxy, WARNNING: THE IDEA IS THIS BE ALREADY RUNNING AND NOT STARTED HERE !
if DEBUG == "TRUE":
	print ("start the gridftp proxy.");
command="grid-proxy-init > /dev/null"# -debug
try:
	subprocess.check_output(command, shell=True)
except subprocess.CalledProcessError as grepexc:
	print("Error creating folder in the workspace")
	print ("error code", grepexc.returncode, grepexc.output)
	sys.exit(1)


############# Some metrics for uploading in the monitoring server
size_bytes=0
# 2GB = 2147483648 bytes
# 10GB = 10737418240 bytes

start_time=time.time()
############## Transfer the files
if DEBUG == "TRUE":
	print ("start transfer.")
if type_transfer == "upload" and SERVER == "HLRS":
	command="globus-url-copy file://"+home+"/"+source_input+" gsiftp://"+user_id+"@"+GRIDFTP_HOST+":"+str(GRIDFTP_PORT)+"/"+WS_BASE_PATH+"/"+user_id+"-"+ws_name+"/"+dest_output
elif type_transfer == "download" and SERVER == "HLRS":
	command="globus-url-copy gsiftp://"+user_id+"@"+GRIDFTP_HOST+":"+str(GRIDFTP_PORT)+"/"+WS_BASE_PATH+"/"+user_id+"-"+ws_name+"/"+source_input+" file://"+home+"/"+dest_output
elif type_transfer == "upload" and SERVER == "ATOSFR":
	command="globus-url-copy file://"+home+"/"+source_input+" gsiftp://"+GRIDFTP_HOST+":"+str(GRIDFTP_PORT)+"/"+WS_BASE_PATH+"/"+dest_output
elif type_transfer == "download" and SERVER == "ATOSFR":
	command="globus-url-copy gsiftp://"+GRIDFTP_HOST+":"+str(GRIDFTP_PORT)+"/"+WS_BASE_PATH+"/"+source_input+" file://"+home+"/"+dest_output
elif type_transfer == "grid2grid":
	command="globus-url-copy gsiftp://"+user_id+"@"+GRIDFTP_HOST+":"+GRIDFTP_PORT+"/"+WS_BASE_PATH+"/"+user_id+"-"+ws_name+"/"+source_input+" gsiftp://"+user_id+"@"+GRIDFTP_HOST+":"+GRIDFTP_PORT+"/"+WS_BASE_PATH+"/"+user_id+"-"+ws_name+"/"+dest_output
else:
	print ("Error: type of transfer not supported.")
	sys.exit(1)

print ("command is " + command)

try:
	subprocess.check_output(command, shell=True)
except subprocess.CalledProcessError as grepexc:
	print("Error transfering data")
	print ("error code", grepexc.returncode, grepexc.output)
	sys.exit(1)


if type_transfer == "upload":
	source_folder=home+"/"+source_input
	size_bytes=str(int(get_size(source_folder)))
elif type_transfer == "download":
	dest_folder=home+"/"+dest_output
	size_bytes=str(int(get_size(dest_folder)))
end_time=time.time()

dt=end_time - start_time
dd=dt/86400
dt2=dt-86400*dd
dh=dt2/3600
dt3=dt2-3600*dh
dm=dt3/60
ds=dt3-60*dm




import requests

job_name='my_custom_metrics'
instance_name='some_job_id'
payload_key='bytes'
payload_value=size_bytes
team_name='euxdat'

response = requests.post('http://prometheus-pushgateway.test.euxdat.eu/metrics/job/{j}/instance/{i}/team/{t}'.format(j=job_name, i=instance_name, t=team_name), data='{k} {v}\n'.format(k=payload_key, v=payload_value))
#print(response.status_code)


############# Register metrics in json format
#human_time=format(dd, ".0f")+":"+format(dh, ".0f")+":"+format(dm, "02.0f")+":"+format(ds, "02.4f")
#time_secs=format(dt, "1.4f")

#myjson="{\n"
#myjson+="  \"starttime\":\""+format(start_time, ".0f")+"\",\n"
#myjson+="  \"end_time\":\""+format(end_time, ".0f")+"\",\n"
#myjson+="  \"userid\":\""+user_id+"\",\n"
#myjson+="  \"transfertype\":\""+type_transfer+"\",\n"
#myjson+="  \"bytes\":\""+size_bytes+"\",\n"
#myjson+="  \"totaltimesecs\":\""+time_secs+"\",\n"
#myjson+="  \"totaltimehumanformat\":\""+human_time+"\",\n"
#myjson+="  \"wsname\":\""+ws_name+"\",\n"
#myjson+="  \"source_input\":\""+source_input+"\",\n"
#myjson+="  \"dest_output\":\""+dest_output+"\"\n"
#myjson+="}"

# Example of output:
# {
#   "starttime":"1582205332.547720412",
#   "userid":"user_id",
#   "transfertype":"upload",
#   "bytes":"4096",
#   "totaltimesecs":"0.4212",
#   "totaltimehumanformat":"0:00:00:0.4212",
#   "wsname":"olu",
#   "source_input":"jojo.txt",
#   "dest_output":"dest_output"
# }

#print(" myjson is "+myjson)

#TODO: add pusgateway call.
if DEBUG == "TRUE":
	print ("pusgateway call to place here.")

############## successful?
#if ! ?
	#print ("Error: Data-staging Failed.")
	#cat /tmp/rucio_user_id-ws_name
	#sys.exit(1)

#print (ws_path) already returned in ctx.node.properties['workspace']

############## delete the workspace via SSH after end the application and we collected the outputs
# Warning this must be done ONLY after the output result-files are copied in a external storage!
#ssh user_id@SSH_HOST -i user_ssh_credentials "module load system/ws_tools ws_release ws_name"
#if DEBUG == "TRUE":
#	print ("Allocate workspace via SSH.")
#new_wspath=delete_ws(user_id, SSH_HOST, user_ssh_credentials, ws_name)
