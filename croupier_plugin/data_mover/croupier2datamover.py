import traceback

from data_mover import (DataMover)
from cloudify import ctx

def download_data(data_mover_options):
    '''Downloads data from Cloud to the HPC workspace'''
    move_data(data_mover_options, type_transfer='download')

def upload_data(data_mover_options):
    '''Uploads data from the HPC workspace to the Cloud'''
    move_data(data_mover_options, type_transfer='upload')

def move_data(data_mover_options, type_transfer):
    '''Invokes the data mover to transfer data'''
    #Read data_mover_options
    hpc_user_id = ctx.instance.runtime_properties['credentials']['user']
    hpc_user_ssh_credentials = ctx.instance.runtime_properties['credentials']['private_key']
    cloud_user = data_mover_options['cloud_user']
    ws_name = data_mover_options['workspace']
    create_ws = data_mover_options['create_ws']
    ws_lifetime = data_mover_options['ws_lifetime']
    grid_userkey = data_mover_options['grid_userkey']
    grid_usercert = data_mover_options['grid_usercert']
    grid_cert_passwd = data_mover_options['grid_certpass']
    cloud_folder = data_mover_options['cloud_folder']
    hpc_folder = data_mover_options['local_folder']

    # try:
    #     # gridproxy is not initialized if userkey=="" or usercert==""
    #     mydatamover = DataMover(create_ws, hpc_user_id, cloud_user, hpc_user_ssh_credentials,
    #                             ws_name, ws_lifetime, grid_userkey, grid_usercert, grid_cert_passwd)
    #     if type_transfer == "download":
    #         source = "ATOSFR"
    #         destination = "HLRS"
    #         source_input = cloud_folder
    #         dest_output = hpc_folder
    #     else:
    #         source = "HLRS"
    #         destination = "ATOSFR"
    #         source_input = hpc_folder
    #         dest_output = cloud_folder
    #
    #     size_bytes = mydatamover.run_transference(source, destination, source_input, dest_output)
    # except Exception as exp:
    #     print(traceback.format_exc())
    #     ctx.logger.error(
    #         'Something happend when trying to invoke DataMover: ' + exp.message)
