from croupier_plugin.ssh import SshClient, SFtpClient
credentials = {
    'host': 'arisrv20.atosresearch.eu',
    'user': 'jesus.gorronogoitia',
    'password': 'Tek=jocudr2thU_e',
    'auth-header': 'Authorization',
    'auth-header-label': 'Authorization',
    'ssh_port': 22}
ssh_client = SshClient(credentials)
