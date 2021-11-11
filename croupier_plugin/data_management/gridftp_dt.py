from croupier_plugin.data_management.data_management import DataTransfer
from croupier_plugin.data_mover.datamover_proxy import DataMoverProxy


class GridFTPDataTransfer(DataTransfer):
    def __init__(self, data_transfer_config, logger):
        super().__init__(data_transfer_config, logger)

    def process(self):
        try:
            _download = self.dt_config['toTarget']['type'] == 'croupier.nodes.HPCDataSource'
            workspace = self.dt_config['toTarget']['properties']['workspace']['name'] if 'workspace' in self.dt_config['toTarget']['properties'] else None
            create_ws = self.dt_config['toTarget']['properties']['workspace']['create'] if 'workspace' in self.dt_config['toTarget']['properties'] else None
            ws_lifetime = self.dt_config['toTarget']['properties']['workspace']['lifetime'] if 'workspace' in self.dt_config['toTarget']['properties'] else None

            source = self.dt_config['fromSource']['properties']['filepath']
            target = self.dt_config['toTarget']['properties']['filepath']

            if _download:
                hpc_target = self.dt_config['toTarget']['properties']['located_at']['endpoint']
                cloud_target = self.dt_config['fromSource']['properties']['located_at']['endpoint']
                cloud_user = self.dt_config['fromSource']['properties']['located_at']['credentials']['username']
                grid_userkey = self.dt_config['toTarget']['properties']['located_at']['credentials']['key']
                grid_usercert = self.dt_config['toTarget']['properties']['located_at']['credentials']['cert']
                grid_certpass = self.dt_config['toTarget']['properties']['located_at']['credentials']['cert_password']
            else:
                hpc_target = self.dt_config['fromSource']['properties']['located_at']['endpoint']
                cloud_target = self.dt_config['toTarget']['properties']['located_at']['endpoint']
                cloud_user = self.dt_config['toTarget']['properties']['located_at']['credentials']['username']
                grid_userkey = self.dt_config['fromSource']['properties']['located_at']['credentials']['key']
                grid_usercert = self.dt_config['fromSource']['properties']['located_at']['credentials']['cert']
                grid_certpass = self.dt_config['fromSource']['properties']['located_at']['credentials']['cert_password']
            data_mover_options = {
                'workspace': workspace,
                'create_ws': create_ws,
                'ws_lifetime': ws_lifetime,
                'download': {
                    'source': source,
                    'target': target
                } if _download else None,
                'upload': {
                    'source': source,
                    'target': target
                } if not _download else None,
                'hpc_target': hpc_target,
                'cloud_target': cloud_target,
                'cloud_user': cloud_user,
                'grid_userkey': grid_userkey,
                'grid_usercert': grid_usercert,
                'grid_certpass': grid_certpass
            }

            # Source Gridftp server
            source_gridftp_endpoint = self.dt_config['fromSource']['properties']['located_at']['endpoint']
            source_gridftp_server = source_gridftp_endpoint[:source_gridftp_endpoint.index(':')]
            source_gridftp_port = source_gridftp_endpoint[source_gridftp_endpoint.index(':') + 1:]
            source_gridftp_user = self.dt_config['fromSource']['properties']['located_at']['credentials']['username']
            source_ssh_server = self.dt_config['fromSource']['properties']['located_at']['ssh_endpoint']
            source_workspace_basepath = self.dt_config['fromSource']['properties']['located_at']['workspace_basepath']
            source_workspace_name = self.dt_config['fromSource']['properties']['workspace']['name'] \
                if "workspace" in self.dt_config['fromSource']['properties'] else None

            source_server = {
                'name': source_gridftp_server, 'user': source_gridftp_user, 'ws_basepath': source_workspace_basepath,
                'gridftp_port': source_gridftp_port, 'gripftp_server': source_gridftp_server,
                'ssh_server': source_ssh_server, 'ws_name': source_workspace_name
            }

            # Target Gridftp server
            target_gridftp_endpoint = self.dt_config['toTarget']['properties']['located_at']['endpoint']
            target_gridftp_server = target_gridftp_endpoint[:target_gridftp_endpoint.index(':')]
            target_gridftp_port = target_gridftp_endpoint[target_gridftp_endpoint.index(':') + 1:]
            target_gridftp_user = self.dt_config['toTarget']['properties']['located_at']['credentials']['username']
            target_ssh_server = self.dt_config['toTarget']['properties']['located_at']['ssh_endpoint']
            target_workspace_basepath = self.dt_config['toTarget']['properties']['located_at']['workspace_basepath']
            target_workspace_name = self.dt_config['toTarget']['properties']['workspace']['name'] \
                if "workspace" in self.dt_config['toTarget']['properties'] else None

            target_server = {
                'name': target_gridftp_server, 'user': target_gridftp_user, 'ws_basepath': target_workspace_basepath,
                'gridftp_port': target_gridftp_port, 'gripftp_server': target_gridftp_server,
                'ssh_server': target_ssh_server, 'ws_name': target_workspace_name
            }

            dmp = DataMoverProxy(data_mover_options, source_server, target_server, self.logger)
            source = data_mover_options['cloud_target']
            destination = data_mover_options['hpc_target']
            source_input = data_mover_options['download']['source']
            dest_output = data_mover_options['download']['target']
            dmp.move_data(source, destination, source_input, dest_output)
        except Exception as exp:
            self.logger.error("Error using GridFTP data transfer: {}".format(str(exp)))
