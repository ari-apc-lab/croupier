#!/usr/bin/env python

# Author: Jose Miguel Montanana, montanana@hlrs.de
# version 1.23, 24-Apr-2020.

# Author: Jesus Gorronogoitia, jesus.gorronogoitia@atos.net
# version 1.24, 19-Nov-2020.

# This script has to be executed with the vendor account it is assumed that the vendor has GridFtp credentials,
# and it is installed the grid-proxy in the machine where this script is executed.

# NOTICE: If -p provide a filename, and the Destination is a folder end with '/', then the file is copied in that
# folder at destination. WARNING: If -p provide a filename, and the Destination does not ended with '/' then the file
# will be uploaded renamed as the Destination provided. NOTICE: If -p provide a directory, then the Destination will
# be considered as a directory at destination even not ended with '/'.

# Tested with python3.6.9 in Ubuntu 18.04 64bits, and Hezelhen system.
# TODO: Before use it need to test the input parameters are correct received from the Cloudify blueprint/yaml file.
# TODO: modify to support 2 different GridFTP servers, current version only uses the hezelhen GridFtp.

import os
import wget
import os.path
import tarfile
import time
import requests
import subprocess
from os.path import expanduser

home = expanduser("~")

# ATTENTION FOR THE ERRORS LIKE NEXT, CAN BE SOLVED ADDING ENTRIES TO /etc/hosts GSS Minor Status Error Chain:
# globus_gsi_gssapi: Authorization denied: The expected name for the remote host (XXXXX) does not match the
# authenticated name of the remote host (ZZZZ). This happens when the name in the host certificate does not match the
# information obtained from DNS and is often a DNS configuration problem.

# please add the next 2 lines:
# 80.158.5.38	 gridftp-s1.euxdat.eu
# 193.196.155.183 gridftp-fr1.hww.de


def isDirectory(dirname):
    return dirname.endswith('/')


class Workspaces:
    # Allocate workspace via SSH
    # The workspace will be reused if it already exists, and the lifetime will not be extended
    def create_ws(self, user_id, SSH_HOST, user_ssh_credentials, ws_name, lifetime):
        # example of exec: ssh $user_id@$SSH_HOST -i $user_ssh_credentials "module load system/ws_tools; ws_allocate
        # $ws_name $LIFETIME;";
        command = "ssh -tt " + user_id + "@" + SSH_HOST + " -i " + user_ssh_credentials + \
                  " \"/opt/hlrs/non-spack/system/ws/0df75f1/bin/ws_allocate " + ws_name + " " + \
                  format(lifetime, "d") + "\""

        try:
            srv_response = subprocess.check_output(command, shell=True)
        except subprocess.CalledProcessError as grepexc:
            raise Exception("Error creating workspace. Error code", grepexc.returncode, grepexc.output)
        response = srv_response.decode("utf-8")
        return response

    # TODO: need a timeout for not whilisted ip_addresses
    # delete the workspace via SSH after end the application and we collected the outputs
    # Warning this must be done ONLY after the output result-files are copied in a external storage!
    # example: ssh user_id@SSH_HOST -i user_ssh_credentials "module load system/ws_tools ws_release ws_name"
    def delete_ws(self, user_id, SSH_HOST, user_ssh_credentials, ws_name):
        command = "ssh " + user_id + "@" + SSH_HOST + " -i " + user_ssh_credentials + \
                  " \"module load system/ws_tools; ws_release " + ws_name + "\""
        try:
            srv_response = subprocess.check_output(command, shell=True)
        except subprocess.CalledProcessError as grepexc:
            raise Exception("Error removing workspace. Error code", grepexc.returncode, grepexc.output)
        response = srv_response.decode("utf-8")
        return response


class Local_gridftp_conf:
    # constructor of class, need place the mandatory generic files if missing
    def __init__(self):
        if not os.path.exists(home + "/.globus/certificates"):
            os.mkdir(home + "/.globus/certificates", 0o0755)
            download_folder = home + "/.globus/certificates/"
            os.chdir(download_folder)
            url = " https://winnetou.surfsara.nl/prace/certs/globuscerts.tar.gz"
            wget.download(url, download_folder)
            if not os.path.isfile(download_folder + "globuscerts.tar.gz"):
                raise Exception("Error: file globuscerts.tar.gz not found.")
            tar = tarfile.open("globuscerts.tar.gz")
            tar.extractall(path=os.path.dirname(download_folder))  # untar file into same directory
            tar.close()
            os.remove("globuscerts.tar.gz")
        elif not os.path.isdir(home + "/.globus/certificates"):
            raise Exception("Error: " + home + "/.globus/certificates must be a folder.")

    def start_proxy(self, grid_cert_passwd):
        command = "echo \"" + grid_cert_passwd + "\" | grid-proxy-init -pwstdin"  # -debug for verbose output
        print (command)
        try:
            subprocess.check_output(command, shell=True)
        except subprocess.CalledProcessError as grepexc:
            raise Exception("Error creating loading credentials, Error code", grepexc.returncode, grepexc.output)

    def place_certificates(self, userkey, usercert, grid_cert_passwd):
        if not os.path.exists(home + "/.globus"):
            os.mkdir(home + "/.globus")
        elif not os.path.isdir(home + "/.globus"):
            raise Exception("Error: " + home + "/.globus must be a folder.")
        text_file = open(home + "/.globus/userkey.pem", "w")
        text_file.write("{0}".format(userkey))
        text_file.close()

        text_file = open(home + "/.globus/usercert.pem", "w")
        text_file.write("{0}".format(usercert))
        text_file.close()

        thecertpath = home + "/.globus/usercert.pem"
        thecertkey = home + "/.globus/userkey.pem"

        if not os.path.isfile(thecertpath):
            raise Exception("Error: missing credentials (cert)")

        if not os.path.isfile(thecertkey):
            raise Exception("Error: missing credentials (key)")

        os.chmod(home + "/.globus/usercert.pem", 0o0644)
        os.chmod(home + "/.globus/userkey.pem", 0o0600)
        self.start_proxy(grid_cert_passwd)


class GridFTPServer:
    # The parameters SSH_HOST is optional, it can left as empty string ""
    def __init__(self, name, user_id, WS_BASE_PATH, GRIDFTP_PORT, GRIDFTP_HOST, SSH_HOST, srv_path):
        self.name = name
        self.user_id = user_id
        self.WS_BASE_PATH = WS_BASE_PATH
        self.GRIDFTP_PORT = GRIDFTP_PORT
        self.GRIDFTP_HOST = GRIDFTP_HOST
        self.SSH_HOST = SSH_HOST
        self.srv_path = srv_path

    def get_user_id(self):
        return self.user_id

    def get_name(self):
        return self.name

    def get_WS_BASE_PATH(self):
        return self.WS_BASE_PATH

    def get_GRIDFTP_PORT(self):
        return self.GRIDFTP_PORT

    def get_GRIDFTP_HOST(self):
        return self.GRIDFTP_HOST

    def get_SSH_HOST(self):
        return self.SSH_HOST

    def get_srv_path(self):
        return self.srv_path


# Set a new instance of the class DataMover, it creates the workspace and takes the credentials to use.


class DataMover:
    def __init__(self, my_server, new_ws, usersshkey, ws_name, ws_lifetime, userkey, usercert, grid_cert_passwd):
        self.size_bytes = 0
        self.start_time = 0
        self.end_time = 0
        self.new_wspath = ""

        # DEBUG
        from celery.contrib import rdb
        rdb.set_trace()

        home = expanduser("~")
        # this path is not needed if we receive the ssh credentials as parameter
        user_ssh_credentials = home + "/.ssh/id_rsa_euxdat"
        f = open(user_ssh_credentials, "w+")
        f.write(usersshkey)
        f.close()
        os.chmod(user_ssh_credentials, 0600)

        hlrs_workspace = Workspaces()

        i = 0
        print (" len(my_server) " + str(len(my_server)))
        if new_ws:
            if 'HAWK' in my_server:
                hpc_server = my_server["HAWK"]
            if new_ws:
                new_wspath = hlrs_workspace.create_ws(hpc_server.get_user_id(), hpc_server.get_SSH_HOST(),
                                                      user_ssh_credentials, ws_name, ws_lifetime)

        if userkey and usercert:  # if both certificates are not empty
            # PREPARATION OF THE GRIDFTP CERTIFICATES
            # notice that starting the grid-proxy-init may ask for a password if the keys are encrypted.
            # it should not be needed it if the gridftp proxy be already running, and not need change credentials
            local_grdiftpconf = Local_gridftp_conf()
            local_grdiftpconf.place_certificates(userkey, usercert, grid_cert_passwd)

    def wspath(self):
        return self.new_wspath

    def get_size(self, start_path):
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

    def make_destination_folder(self, dest_server, server,
                                dest_output):  # needed because gridFTP transfer will fail it it not exists.
        # first, need to know if the destination is a folder, then we remove the end before the last character "/"

        new_folder = dest_output
        if "/" in new_folder:
            while new_folder and new_folder[-1] != "/":
                new_folder = new_folder[:-1]
            if new_folder != '/':
                # now, request to create that folder at destination
                # Using the GSI security files created by grid-init-proxy
                command = "uberftp -mkdir gsiftp://" + dest_server.get_GRIDFTP_HOST() + ":" + str(
                    dest_server.get_GRIDFTP_PORT()) + "/" + dest_server.get_WS_BASE_PATH() + "/" + \
                          dest_server.get_srv_path() + dest_output

                print ("cmd " + command)
                try:
                    srv_response = subprocess.check_output(command, shell=True)
                except subprocess.CalledProcessError as grepexc:
                    raise Exception("Error creating folder in the workspace. Error code",
                                    grepexc.returncode, grepexc.output)

    # source and destination define the machines, values can be "localhost" or a name in the data-structure my_server
    def run_transference(self, source_server, dest_server, source, destination, source_input, dest_output, logger):
        self.size_bytes = 0
        self.start_time = time.time()
        # FIND THE PARAMETERS OF THE SOURCE
        if source != "localhost":
            src_user_id = source_server.get_user_id()
            src_WS_BASE_PATH = source_server.get_WS_BASE_PATH()
            src_GRIDFTP_PORT = source_server.get_GRIDFTP_PORT()
            src_GRIDFTP_HOST = source_server.get_GRIDFTP_HOST()
            src_path = source_server.get_srv_path() + source_input

        # FIND THE PARAMETERS OF THE DESTINATION
        if destination != "localhost":
            dst_user_id = dest_server.get_user_id()
            dst_WS_BASE_PATH = dest_server.get_WS_BASE_PATH()
            dst_GRIDFTP_PORT = dest_server.get_GRIDFTP_PORT()
            dst_GRIDFTP_HOST = dest_server.get_GRIDFTP_HOST()
            dst_path = dest_server.get_srv_path() + dest_output

        if destination != "localhost":
            if isDirectory(dest_output):
                self.make_destination_folder(dest_server, destination, dest_output)
        if source == "localhost":
            command = "globus-url-copy" + \
                      " file://" + source_input + \
                      " gsiftp://" + dst_user_id + "@" + dst_GRIDFTP_HOST + ":" + \
                      str(dst_GRIDFTP_PORT) + "/" + dst_WS_BASE_PATH + "/" + dst_path
        elif destination == "localhost":
            command = "globus-url-copy" + \
                      " gsiftp://" + src_user_id + "@" + src_GRIDFTP_HOST + ":" + \
                      str(src_GRIDFTP_PORT) + "/" + src_WS_BASE_PATH + "/" + src_path + \
                      " file://" + dest_output
        else:
            command = "uberftp -size " + \
                      " gsiftp://" + src_user_id + "@" + src_GRIDFTP_HOST + ":" + \
                      str(src_GRIDFTP_PORT) + "/" + src_WS_BASE_PATH + "/" + src_path
            try:
                self.size_bytes = str(int(subprocess.check_output(command, shell=True)))
            except subprocess.CalledProcessError as grepexc:
                logger.error("Error measuring data. Error code: {error_code}. Error message: {error_message}".
                             format(error_code=grepexc.returncode, error_message=grepexc.output))

            command = "globus-url-copy" + \
                      " gsiftp://" + src_user_id + "@" + src_GRIDFTP_HOST + ":" + \
                      str(src_GRIDFTP_PORT) + "/" + src_WS_BASE_PATH + "/" + src_path + \
                      " gsiftp://" + dst_user_id + "@" + dst_GRIDFTP_HOST + ":" + \
                      str(dst_GRIDFTP_PORT) + "/" + dst_WS_BASE_PATH + "/" + dst_path

        try:
            subprocess.check_output(command, shell=True)
        except subprocess.CalledProcessError as grepexc:
            raise Exception("Error transfering data. Error code", grepexc.returncode, grepexc.output)
        if source == "localhost":
            source_folder = source_input
            self.size_bytes = str(int(self.get_size(source_folder)))
        elif destination == "localhost":
            dest_folder = dest_output
            self.size_bytes = str(int(self.get_size(dest_folder)))
        self.end_time = time.time()
        return self.size_bytes

    def get_transfer_time_length_ms(self):
        return self.end_time - self.start_time

    def get_transfer_time_length_human(self):
        dt = self.end_time - self.start_time
        dd = dt / 86400
        dt2 = dt - 86400 * dd
        dh = dt2 / 3600
        dt3 = dt2 - 3600 * dh
        dm = dt3 / 60
        ds = dt3 - 60 * dm
        human_time = format(dd, ".0f") + ":" + format(dh, ".0f") + ":" + format(dm, "02.0f") + ":" + format(ds, "02.4f")
        return human_time


class Metricspublisher:
    def __init__(self, prometheus_server):
        self.prometheus_server = prometheus_server

    def new_metric(self, job_name, instance_name, app, datasize, time_sec, user, source, destination):
        wspace = "demo_python"
        bandwidth = float(datasize) / float(time_sec)
        # register datasize
        data = "transfered_bytes{hlrs_user_id=\"" + user + "\"," "wspace=\"" + wspace + "\", " "app=\"" \
               + app + "\"," "source=\"" + source + "\", " "destination=\"" + destination + "\"}" + str(datasize)

        response = requests.post(
            self.prometheus_server + '/metrics/job/{j}/instance/{i}'.format(j=job_name, i=instance_name),
            data='{k}\n'.format(k=data))
        # register duration of the transference
        data = "transfer_time_seconds{hlrs_user_id=\"" + user + "\"," "wspace=\"" + wspace + "\", " "app=\"" \
               + app + "\"," "source=\"" + source + "\", " "destination=\"" + destination + "\"}" + str(time_sec)

        response = requests.post(
            self.prometheus_server + '/metrics/job/{j}/instance/{i}'.format(j=job_name, i=instance_name),
            data='{k}\n'.format(k=data))
        # register bandwidth
        data = "bandwidth{hlrs_user_id=\"" + user + "\"," "wspace=\"" + wspace + "\", " "app=\"" \
               + app + "\"," "source=\"" + source + "\", " "destination=\"" + destination + "\"}" + str(bandwidth)

        response = requests.post(
            self.prometheus_server + '/metrics/job/{j}/instance/{i}'.format(j=job_name, i=instance_name),
            data='{k}\n'.format(k=data))
        print ("-------------------------------------------------\n\n\n")
        return response
