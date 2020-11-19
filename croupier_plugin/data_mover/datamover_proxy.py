import traceback

from data_mover import (DataMover, GridFTPServer)
from cloudify import ctx


class DataMoverProxy:
    my_servers = {}
    logger = None

    def __init__(self, data_mover_options, logger):
        # Read data_mover_options
        self.hpc_user_id = ctx.instance.runtime_properties['credentials']['user']
        self.hpc_user_ssh_credentials = ctx.instance.runtime_properties['credentials']['private_key']
        if 'cloud_user' in data_mover_options:
            self.cloud_user = data_mover_options['cloud_user']
        if 'workspace' in data_mover_options:
            self.ws_name = data_mover_options['workspace']
        if 'create_ws' in data_mover_options:
            self.create_ws = data_mover_options['create_ws']
        if 'ws_lifetime' in data_mover_options:
            self.ws_lifetime = data_mover_options['ws_lifetime']
        if 'grid_userkey' in data_mover_options:
            self.grid_userkey = data_mover_options['grid_userkey']
        if 'grid_usercert' in data_mover_options:
            self.grid_usercert = data_mover_options['grid_usercert']
        if 'grid_certpass' in data_mover_options:
            self.grid_cert_passwd = data_mover_options['grid_certpass']
        if 'download' in data_mover_options:
            self.download = True
            if 'source' in data_mover_options['download']:
                self.download_source = data_mover_options['download']["source"]
                self.download_target = data_mover_options['download']["target"]
        if 'upload' in data_mover_options:
            self.upload = True
            if 'source' in data_mover_options['upload']:
                self.upload_source = data_mover_options['upload']["source"]
                self.upload_target = data_mover_options['upload']["target"]
        self.set_servers(data_mover_options)
        self.logger = logger

        # gridproxy is not initialized if userkey=="" or usercert==""
        self.mydatamover = DataMover(self.my_servers, self.create_ws, self.hpc_user_ssh_credentials, self.ws_name,
                                     self.ws_lifetime, self.grid_userkey, self.grid_usercert, self.grid_cert_passwd)

    def set_servers(self, data_mover_options):
        if ('hpc_target' in data_mover_options and data_mover_options['hpc_target']) == 'HAWK':
            if self.hpc_user_id is not None and self.ws_name:
                self.my_servers["HAWK"] = GridFTPServer(
                    "HAWK",
                    self.hpc_user_id,  # this is the user in Hawk
                    "lustre/cray/ws9/6/ws",
                    2812,  # the port at hezelhen is not the standard for gridftp (2811)
                    "gridftp-fr1.hww.de",
                    "hawk.hww.hlrs.de",
                    self.hpc_user_id + "-" + self.ws_name + "/")  # AGAIN THE SAME USER_ID AS WE JUST PLACE IN THE SECOND PARAMETER!!!
            else:
                raise Exception("GridFTPServer for HAWK could not be set. Check datamover options (ws_name")

        if ('cloud_target' in data_mover_options and data_mover_options['cloud_target']) == 'ATOSFR':
            if self.cloud_user is not None:
                self.my_servers["ATOSFR"] = GridFTPServer(
                    "ATOSFR",
                    "euxdat_user",  # <-- this is the same for all the Euxdat partners, DON'T CHANGE
                    "home/euxdat_user",
                    2811,
                    "gridftp-s1.euxdat.eu",
                    "",
                    # FIELDs neededfor creating workspace in Hawk ; empty becasue we don't need to create a WS in ATOSFR
                    "")  # FIELDs neededfor creating workspace in Hawk ; empty becasue we don't need to create a WS in ATOSFR

        if ('cloud_target' in data_mover_options and data_mover_options['cloud_target']) == 'WRLS':
            if self.cloud_user is not None:
                self.my_servers["WRLS"] = GridFTPServer(
                    "WRLS",
                    "euxdat_user",
                    "home/euxdat_user",
                    2811,
                    "gridftp-s1.euxdat.eu",  # needs to be updated
                    "",
                    # FIELDs needed for creating workspace in Hawk ; empty becasue we don't need to create a WS in WRLS
                    "")  # FIELDs needed for creating workspace in Hawk ; empty becasue we don't need to create a WS in WRLS
            else:
                raise Exception(
                    "GridFTPServer for WRLS could not be set. Check datamover options wrls_user, wrls_folder")

    def move_data(self, source, destination, source_input, dest_output):
        try:
            source_server = self.my_servers[source]
            dest_server = self.my_servers[destination]

            self.mydatamover.run_transference(
                source_server, dest_server, source, destination, source_input, dest_output, self.logger)
        except Exception as exp:
            raise Exception(
                'Something happened when trying to invoke DataMover: ' + exp.message)
