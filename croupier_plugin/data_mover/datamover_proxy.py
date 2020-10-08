import traceback

from data_mover import (DataMover, GridFTPServer)
from cloudify import ctx


class DataMoverProxy:
    my_servers = []

    def __init__(self, data_mover_options):
        # Read data_mover_options
        self.hpc_user_id = ctx.instance.runtime_properties['credentials']['user']
        self.hpc_user_ssh_credentials = ctx.instance.runtime_properties['credentials']['private_key']
        self.cloud_user = data_mover_options['cloud_user']
        self.wrls_user = data_mover_options['wrls_user']
        self.wrls_folder = data_mover_options['wrls_folder']
        self.ws_name = data_mover_options['workspace']
        self.create_ws = data_mover_options['create_ws']
        self.ws_lifetime = data_mover_options['ws_lifetime']
        self.grid_userkey = data_mover_options['grid_userkey']
        self.grid_usercert = data_mover_options['grid_usercert']
        self.grid_cert_passwd = data_mover_options['grid_certpass']
        self.cloud_folder = data_mover_options['cloud_folder']
        self.hpc_folder = data_mover_options['hpc_folder']

        self.set_servers()

        # gridproxy is not initialized if userkey=="" or usercert==""
        self.mydatamover = DataMover(self.my_servers, self.create_ws, self.hpc_user_ssh_credentials, self.ws_name,
                                     self.ws_lifetime, self.grid_userkey, self.grid_usercert, self.grid_cert_passwd)

    def set_servers(self):
        self.my_servers.append(
            GridFTPServer(
                "HLRS",
                self.hpc_user_id, #this is the user in Hawk
                "lustre/cray/ws9/6/ws",
                2812,  # the port at hezelhen is not the standard for gridftp (2811)
                "gridftp-fr1.hww.de",
                "hawk.hww.hlrs.de",
                self.hpc_user_id + "-" + self.ws_name + "/"))  # AGAIN THE SAME USER_ID AS WE JUST PLACE IN THE SECOND PARAMETER!!!

        self.my_servers.append(
            GridFTPServer(
                "ATOSFR",
                "euxdat_user",  # <-- this is the same for all the Euxdat partners, DON'T CHANGE
                "home/euxdat_user/user-data",
                2811,
                "gridftp-s1.euxdat.eu",
                "", #FIELDs neededfor creating workspace in Hawk ; empty becasue we don't need to create a WS in ATOSFR
                ""))#FIELDs neededfor creating workspace in Hawk ; empty becasue we don't need to create a WS in ATOSFR


        self.my_servers.append(
            GridFTPServer(
                "WRLS",
                self.wrls_user,
                self.wrls_folder,
                2811,
                "gridftp-s1.euxdat.eu", #needs to be updated
                "", #FIELDs neededfor creating workspace in Hawk ; empty becasue we don't need to create a WS in WRLS
                ""))#FIELDs neededfor creating workspace in Hawk ; empty becasue we don't need to create a WS in WRLS

    def download_data_ATOSFR(self):
        '''Downloads data from Cloud to the HPC workspace'''
        self.move_data( type_transfer='download_ATOFR')

    def upload_data_ATOSFR(self):
        '''Uploads data from the HPC workspace to the Cloud'''
        self.move_data(type_transfer='upload_ATOFR')

    def download_data_WRLS(self):
        '''Downloads data from Cloud to the HPC workspace'''
        self.move_data( type_transfer='download_WRLS')

    def upload_data_WRLS(self):
        '''Uploads data from the HPC workspace to the Cloud'''
        self.move_data(type_transfer='upload_WRLS')

    def move_data(self, type_transfer):
        try:
            if type_transfer == "download_ATOFR":
                source = "ATOSFR"
                destination = "HLRS"
                source_input = self.cloud_folder
                dest_output = self.hpc_folder

            elif type_transfer == "download_WRLS":
                source = "WRLS"
                destination = "HLRS"
                source_input = self.cloud_folder
                dest_output = self.hpc_folder

            elif type_transfer == "upload_ATOFR":
                source = "HLRS"
                destination = "ATOSFR"
                source_input = self.hpc_folder
                dest_output = self.cloud_folder

            elif type_transfer == "upload_WRLS":
                source = "HLRS"
                destination = "WRLS"
                source_input = self.hpc_folder
                dest_output = self.cloud_folder
            else:
                ctx.logger.error('Not support type of transfer')

            size_bytes = self.mydatamover.run_transference(source, destination, source_input, dest_output)
        except Exception as exp:
            print(traceback.format_exc())
            ctx.logger.error(
                'Something happened when trying to invoke DataMover: ' + exp.message)
