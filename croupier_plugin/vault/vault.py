import os

from cloudify import ctx
from cloudify.exceptions import NonRecoverableError
from requests import get, post
from requests.auth import HTTPBasicAuth
import configparser


def get_secret(vault_token, secret_endpoint):
    auth_header = {"X-Vault-Token": vault_token}
    secret_response = get(secret_endpoint, headers=auth_header)
    json = secret_response.json()
    if secret_response.ok and "data" in json and json["data"]:
        return json["data"]
    else:
        return {"error": secret_response.status_code,
                "content": secret_response.json()}


def revoke_token(vault_token, vault_address):
    auth_header = {"x-vault-token": vault_token}
    endpoint = vault_address + "/v1/auth/token/revoke-self"
    response = post(endpoint, headers=auth_header)
    if response.ok:
        return None
    else:
        return {"error": response.status_code,
                "content": response.json()}


def download_credentials(host, vault_token, vault_user, vault_address, cubbyhole):
    host.replace('/', '').replace(':', '')
    if cubbyhole:
        secret_endpoint = vault_address + "/v1/cubbyhole/" + host
    else:
        secret_endpoint = vault_address + "/v1/croupier/" + vault_user + "/" + host
    secret = get_secret(vault_token, secret_endpoint)
    if "error" not in secret:
        return secret
    else:
        raise Exception("Could not get credentials from vault for host " + host + " and user " + vault_user +
                        "\n Status code: " + str(secret["error"]) +
                        "\n Content: " + str(secret["content"]))


def get_token(vault_user, vault_address, jwt):
    token_endpoint = vault_address + "/v1/auth/jwt/login"
    auth_header = {
        "Content-Type": "application/json"
    }
    payload = {
        "jwt": jwt,
        "role": vault_user
    }
    introspection_client, introspection_secret = getKeyCloakIntrospectionFromConfiguration()
    token_response = post(
        token_endpoint,
        headers=auth_header,
        auth=HTTPBasicAuth(introspection_client, introspection_secret),
        json=payload)
    json = token_response.json()
    if token_response.ok and "auth" in json and json["auth"]:
        return json["auth"]["client_token"]
    else:
        raise Exception("Could not get token from Vault at {} for user {}\nStatus: {}"
                        .format(vault_address, vault_user, token_response.status_code))


def getVaultAddressFromConfiguration():
    config = configparser.RawConfigParser()
    config_file = str(os.path.dirname(os.path.realpath(__file__))) + '/../Croupier.cfg'
    config.read(config_file)
    try:
        address = config.get('Vault', 'vault_address')
        if address is None:
            raise NonRecoverableError('Could not find Vault address in the croupier config file.')
        return address
    except configparser.NoSectionError:
        raise NonRecoverableError('Could not find the Vault section in the croupier config file.')


def getKeyCloakIntrospectionFromConfiguration():
    config = configparser.RawConfigParser()
    config_file = str(os.path.dirname(os.path.realpath(__file__))) + '/../Croupier.cfg'
    config.read(config_file)
    try:
        introspection_client = config.get('KeyCloak', 'introspection_client')
        if introspection_client is None:
            raise NonRecoverableError('Could not find Keycloak introspection_client in the croupier config file.')
        introspection_secret = config.get('KeyCloak', 'introspection_secret')
        if introspection_secret is None:
            raise NonRecoverableError('Could not find Keycloak introspection_secret in the croupier config file.')
        return introspection_client, introspection_secret
    except configparser.NoSectionError:
        raise NonRecoverableError('Could not find the KeyCloak section in the croupier config file.')
