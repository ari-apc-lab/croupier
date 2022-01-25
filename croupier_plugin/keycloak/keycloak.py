from requests import get, post
import os
import configparser


def get_jwt(user, password):
    kc_conf = get_keycloak_config()
    endpoint = kc_conf['address'] + '/auth/realms/{0}/protocol/openid-connect/token'.format(kc_conf['realm'])
    data = {
        "grant_type": 'password',
        "username": user,
        "password": password,
        "client_id": kc_conf['client_id'],
        "client_secret": kc_conf['client_secret']
    }

    r = post(endpoint, data=data)
    if r.ok:
        r_json = r.json()
        return r_json['access_token']
    else:
        raise Exception('Could not get JWT from Keycloak ({0}):\n{1}'.format(r.status_code, r.content))


def get_keycloak_config():
    kc_conf = {}
    config_file = str(os.path.dirname(os.path.realpath(__file__))) + '/Croupier.cfg'
    config = configparser.RawConfigParser()
    config.read(config_file)
    parameters = ['keycloak_address', 'client_id', 'client_secret']
    try:
        for parameter in parameters:
            kc_conf[parameter] = config.get('Keycloak', parameter)
            if kc_conf[parameter] is None:
                raise Exception('Could not find Keycloak {0} in the croupier config file.'.format(parameter))

    except configparser.NoSectionError:
        raise Exception('Could not find Keycloak section in the croupier config file.')
    return kc_conf
