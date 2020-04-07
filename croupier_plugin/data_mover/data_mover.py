#!/usr/bin/env python

#Author: Jose Miguel Montanana, montanana@hlrs.de
#version 1.21, 7-Apr-2020.

#This script has to be executed with the vendor account
#it is assumed that the vendor has GridFtp credentials, and it is installed the grid-proxy in the machine where this script is executed.

#NOTICE: If -p provide a filename, and the Destination is a folder end with '/', then the file is copied in that folder at destination.
#WARNING: If -p provide a filename, and the Destination does not ended with '/' then the file will be uploaded renamed as the Destination provided.
#NOTICE: If -p provide a directory, then the Destination will be considered as a directory at destination even not ended with '/'.

#Tested with python3.6.9 in Ubuntu 18.04 64bits, and Hezelhen system.
#TODO: Before use it need to test the input parameters are correct received from the Cloudify blueprint/yaml file.
#TODO: modify to support 2 different GridFTP servers, current version only uses the hezelhen GridFtp.

import os
import sys
import wget
import os.path
import tarfile
import time
import subprocess
import requests
from os import path
from cloudify import ctx
from shutil import copyfile
from pathlib import Path
import subprocess
from os.path import expanduser

home = expanduser("~")
DEBUG="TRUE"

class Workspaces:
	############## Allocate workspace via SSH
	# The workspace will be reused if it already exists, and the lifetime will not be extended
	def create_ws(self,user_id, SSH_HOST, user_ssh_credentials, ws_name, LIFETIME):
		#example of exec: ssh $user_id@$SSH_HOST -i $user_ssh_credentials "module load system/ws_tools; ws_allocate $ws_name $LIFETIME;";
		command="ssh " + user_id+"@"+SSH_HOST+" -i "+user_ssh_credentials+" \"module load system/ws_tools; ws_allocate "+ws_name+" "+format(lifetime, "d")+"\""
		print (" create_ws "+ command)
		try:
			server_response=subprocess.check_output(command, shell=True)
		except subprocess.CalledProcessError as grepexc:
			print ("Error creating workspace.")
			print ("error code", grepexc.returncode, grepexc.output)
			sys.exit(1)
		response=server_response.decode("utf-8")
		return response

	#TODO: need a timeout for not whilisted ip_addresses
	############## delete the workspace via SSH after end the application and we collected the outputs
	# Warning this must be done ONLY after the output result-files are copied in a external storage!
	#example: ssh user_id@SSH_HOST -i user_ssh_credentials "module load system/ws_tools ws_release ws_name"
	def delete_ws(self,user_id, SSH_HOST, user_ssh_credentials, ws_name):
		command="ssh "+ user_id+"@"+SSH_HOST+" -i "+user_ssh_credentials+" \"module load system/ws_tools; ws_release "+ws_name+"\""
		try:
			server_response=subprocess.check_output(command, shell=True)
		except subprocess.CalledProcessError as grepexc:
			print ("Error removing workspace.")
			print ("error code", grepexc.returncode, grepexc.output)
			sys.exit(1)
		response=server_response.decode("utf-8")
		return response

class Local_gridftp_conf:
	# constructor of class, need place the mandatory generric files if missing
	def __init__(self):
		if not os.path.exists(home+"/.globus/certificates"):
			os.mkdir( home+"/.globus/certificates", 0o0755)
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

	def start_proxy(self,grid_cert_passwd):
		if DEBUG == "TRUE":
			print ("start the gridftp proxy.");
		command="echo \""+grid_cert_passwd+"\" | grid-proxy-init -pwstdin" # -debug for verbose output
		try:
			subprocess.check_output(command, shell=True)
		except subprocess.CalledProcessError as grepexc:
			print("Error creating folder in the workspace")
			print ("error code", grepexc.returncode, grepexc.output)
			sys.exit(1)

	def place_certificates(self, userkey, usercert,grid_cert_passwd):
		if not os.path.exists(home+"/.globus"):
			os.mkdir( home+"/.globus")
		elif not os.path.isdir(home+"/.globus"):
			print ("Error: "+home+"/.globus must be a folder.")
			sys.exit(1)
		#my_file = Path(userkey_file_source_path)
		#if not my_file.is_file():
			#print ("Error: user key file not found.")
			#sys.exit(1)
		#if userkey_file_source_path != home+"/.globus/userkey.pem":
			#copyfile(userkey_file_source_path, home+"/.globus/userkey.pem")
		text_file = open(home+"/.globus/userkey.pem", "w")
		text_file.write("{0}".format(userkey))
		text_file.close()

		#my_file = Path(usercert_file)
		#if not my_file.is_file():
			#print ("Error: user cert file not found.")
			#sys.exit(1)

		#if usercert_file != home+"/.globus/usercert.pem":
			#copyfile( usercert_file , home+"/.globus/usercert.pem")
		text_file = open(home+"/.globus/usercert.pem", "w")
		text_file.write("{0}".format(usercert))
		text_file.close()

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
		self.start_proxy(grid_cert_passwd)


class DataMover:
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
	#ATOSFR_GRIDFTP_HOST="ecs-80-158-5-38.reverse.open-telekom-cloud.com"
#GSS Minor Status Error Chain:
#globus_gsi_gssapi: Authorization denied: The expected name for the remote host (host@ecs-80-158-5-38.reverse.open-telekom-cloud.com) does not match the authenticated name of the remote host (host@gridftp-s1.euxdat.eu). This happens when the name in the host certificate does not match the information obtained from DNS and is often a DNS configuration problem.



	def __init__(self, SERVER, user_id, user_ssh_credentials, ws_name, ws_lifetime, userkey, usercert,grid_cert_passwd ):
		self.size_bytes=0
		self.start_time=0
		self.end_time=0
		self.gridftpserver=SERVER
		self.WS_BASE_PATH=""
		self.GRIDFTP_PORT=""
		self.GRIDFTP_HOST=""
		self.SSH_HOST=""
		self.new_wspath=""
		if self.gridftpserver == "HLRS":
			self.WS_BASE_PATH=self.HLRS_WS_BASE_PATH
			self.GRIDFTP_PORT=self.HLRS_GRIDFTP_PORT
			self.GRIDFTP_HOST=self.HLRS_GRIDFTP_HOST
			self.SSH_HOST=self.HLRS_SSH_HOST
		else:
			self.WS_BASE_PATH=self.ATOSFR_WS_BASE_PATH
			self.GRIDFTP_PORT=self.ATOSFR_GRIDFTP_PORT
			self.GRIDFTP_HOST=self.ATOSFR_GRIDFTP_HOST
		hlrs_workspace = Workspaces()
		if DEBUG == "TRUE":
			print ("Allocate workspace via SSH.")
		if SERVER == "HLRS":
			new_wspath=hlrs_workspace.create_ws(user_id, SSH_HOST, user_ssh_credentials, ws_name, ws_lifetime)
		if (userkey) and (usercert) : #if both certificates are not empty
			############## PREPARATION OF THE GRIDFTP CERTIFICATES
			# notice that starting the grid-proxy-init may ask for a password if the keys are encrypted.
			# it should not be needed it if the gridftp proxy be already running, and not need change credentials
			if DEBUG == "TRUE":
				print ("Preparation of the GRIDFTP certificates.")
			local_grdiftpconf=Local_gridftp_conf()
			local_grdiftpconf.place_certificates(userkey, usercert, grid_cert_passwd)


	def wspath(self):
		return self.new_wspath

	def get_size(self,start_path):
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

	def make_destination_folder(self, dest_output):# needed because gridFTP transfer will fail it it not exists.
		#first, need to know if the destination is a folder, then we remove the end before the last character "/"
		if DEBUG == "TRUE":
			print ("Request to create the destination folder, it may not exists yet.")
		new_folder=dest_output
		if "/" not in new_folder:
			while new_folder and new_folder[-1] != "/":
				new_folder=new_folder[:-1]
			if new_folder != '/' and self.gridftpserver == "HLRS":
				#now, request to create that folder at destination
				command="ssh "+ user_id+"@"+SSH_HOST+" -i "+user_ssh_credentials+" \"mkdir -p /"+WS_BASE_PATH+"/"+user_id+"-"+ws_name+"/"+new_folder+"\""
				try:
					server_response=subprocess.check_output(self.command, shell=True)
				except subprocess.CalledProcessError as grepexc:
					print("Error creating folder in the workspace")
					print ("error code", grepexc.returncode, grepexc.output)
					sys.exit(1)
			elif new_folder != '/' and self.gridftpserver == "ATOSFR":
				#now, request to create that folder at destination
				#Using the GSI security files created by grid-init-proxy
				command="uberftp -mkdir gsiftp://"+self.GRIDFTP_HOST+":"+str(self.GRIDFTP_PORT)+"/"+self.WS_BASE_PATH+"/"+dest_output
				try:
					server_response=subprocess.check_output(command, shell=True)
				except subprocess.CalledProcessError as grepexc:
					print("Error creating folder in the workspace")
					print ("error code", grepexc.returncode, grepexc.output)
					sys.exit(1)

	def run_transference(self, type_transfer, source_input, dest_output):
		self.size_bytes=0
		self.start_time=time.time()

		if DEBUG == "TRUE":
			print ("start transfer.")
		if type_transfer == "upload":
			self.make_destination_folder(dest_output )
		if type_transfer == "upload" and self.gridftpserver == "HLRS":
			command="globus-url-copy file://"+home+"/"+source_input+" gsiftp://"+user_id+"@"+self.GRIDFTP_HOST+":"+str(self.GRIDFTP_PORT)+"/"+self.WS_BASE_PATH+"/"+user_id+"-"+ws_name+"/"+dest_output
		elif type_transfer == "download" and self.gridftpserver == "HLRS":
			command="globus-url-copy gsiftp://"+user_id+"@"+self.GRIDFTP_HOST+":"+str(self.GRIDFTP_PORT)+"/"+self.WS_BASE_PATH+"/"+user_id+"-"+ws_name+"/"+source_input+" file://"+home+"/"+dest_output
		elif type_transfer == "upload" and self.gridftpserver == "ATOSFR":
			command="globus-url-copy file://"+home+"/"+source_input+" gsiftp://"+self.GRIDFTP_HOST+":"+str(self.GRIDFTP_PORT)+"/"+self.WS_BASE_PATH+"/"+dest_output
		elif type_transfer == "download" and self.gridftpserver == "ATOSFR":
			command="globus-url-copy gsiftp://"+self.GRIDFTP_HOST+":"+str(self.GRIDFTP_PORT)+"/"+self.WS_BASE_PATH+"/"+source_input+" file://"+home+"/"+dest_output
		elif type_transfer == "grid2grid":
			command="globus-url-copy gsiftp://"+user_id+"@"+self.GRIDFTP_HOST+":"+self.GRIDFTP_PORT+"/"+self.WS_BASE_PATH+"/"+user_id+"-"+ws_name+"/"+source_input+" gsiftp://"+user_id+"@"+self.GRIDFTP_HOST+":"+self.GRIDFTP_PORT+"/"+self.WS_BASE_PATH+"/"+user_id+"-"+ws_name+"/"+dest_output
		else:
			print ("Error: type of transfer not supported.")
			sys.exit(1)
		if DEBUG == "TRUE":
			print ("command is " + command)
		try:
			subprocess.check_output(command, shell=True)
		except subprocess.CalledProcessError as grepexc:
			print("Error transfering data")
			print ("error code", grepexc.returncode, grepexc.output)
			sys.exit(1)
		if type_transfer == "upload":
			source_folder=home+"/"+source_input
			self.size_bytes=str(int(self.get_size(source_folder)))
		elif type_transfer == "download":
			dest_folder=home+"/"+dest_output
			self.size_bytes=str(int(self.get_size(dest_folder)))
		self.end_time=time.time()
		return self.size_bytes

	def get_transfer_time_length_ms(self):
		return self.end_time - self.start_time

	def get_transfer_time_length_human(self):
		dt=self.end_time - self.start_time
		dd=dt/86400
		dt2=dt-86400*dd
		dh=dt2/3600
		dt3=dt2-3600*dh
		dm=dt3/60
		ds=dt3-60*dm
		human_time=format(dd, ".0f")+":"+format(dh, ".0f")+":"+format(dm, "02.0f")+":"+format(ds, "02.4f")
		return human_time

class Metricspublisher:
	prometheus_server="http://prometheus-pushgateway.test.euxdat.eu"
	def new_metric(self,job_name,instance_name,payload_key,payload_value, team_name):
		response = requests.post(self.prometheus_server+'/metrics/job/{j}/instance/{i}/team/{t}'.format(j=job_name, i=instance_name, t=team_name), data='{k} {v}\n'.format(k=payload_key, v=payload_value))
		return response


