def download_data(data_mover_options):
    '''Downloads data from Cloud to the HPC workspace'''
    move_data(data_mover_options, type_transfer='download')

def upload_data(data_mover_options):
    '''Uploads data from the HPC workspace to the Cloud'''
    move_data(data_mover_options, type_transfer='upload')

def move_data(data_mover_options, type_transfer):
    '''Invokes the data mover to transfer data'''
    #Read data_mover_options
    server = data_mover_options['server']
    hpc_user_id = ctx.instance.runtime_properties['credentials']['user']
    hpc_user_ssh_credentials = ctx.instance.runtime_properties['credentials']['private_key']
    ws_name = data_mover_options['workspace']
    ws_lifetime = data_mover_options['ws_lifetime']
    userkey = data_mover_options['grid_userkey']
    usercert = data_mover_options['grid_usercert']
    grid_cert_passwd = data_mover_options['grid_certpass']
    cloud_folder = data_mover_options['cloud_folder']
    local_folder = data_mover_options['local_folder']

    try:
        # gridproxy is not initialized if userkey=="" or usercert==""
        mydatamover = DataMover(server, hpc_user_id, hpc_user_ssh_credentials, ws_name, ws_lifetime, userkey,
                                usercert, grid_cert_passwd)
        if type_transfer == "download":
            source_input = cloud_folder
            dest_output = local_folder
        else:
            source_input = local_folder
            dest_output = cloud_folder

        size_bytes = mydatamover.run_transference(type_transfer, source_input, dest_output)
    except Exception as exp:
        print(traceback.format_exc())
        ctx.logger.error(
            'Something happend when trying to invoke DataMover: ' + exp.message)
