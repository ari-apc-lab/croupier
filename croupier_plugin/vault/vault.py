from cloudify.exceptions import NonRecoverableError
from requests import get, post


def get_secret(vault_token, secret_endpoint):
    auth_header = {"X-Vault-Token": vault_token}
    secret_response = get(secret_endpoint, headers=auth_header)
    json = secret_response.json()
    if secret_response.ok and "data" in json and json["data"]:
        return json["data"]
    else:
        return {"error": secret_response.status_code,
                "content": secret_response.json()}


def revoke_token(vault_token,vault_address):
    auth_header = {"x-vault-token": vault_token}
    endpoint = vault_address + "/v1/auth/token/revoke-self"
    response = post(endpoint, headers=auth_header)
    if response.ok:
        return None
    else:
        return {"error": response.status_code,
                "content": response.json()}


def download_keycloak_credentials(keycloak_credentials, vault_token, vault_user, vault_address):
    secret_endpoint = vault_address + "/v1/keycloak/" + vault_user
    secret = get_secret(vault_token, secret_endpoint)
    if "error" not in secret:
        keycloak_credentials["user"] = vault_user
        keycloak_credentials["pw"] = secret["password"]
        return keycloak_credentials
    else:
        raise NonRecoverableError("Could not get keycloak credentials from vault for user " + vault_user +
                                  "\n Status code: " + str(secret["error"]) +
                                  "\n Content: " + str(secret["content"]))


def download_ssh_credentials(ssh_config, vault_token, vault_user, vault_address):
    host = ssh_config['host']
    secret_endpoint = vault_address + "/v1/ssh/" + vault_user + "/" + host
    secret = get_secret(vault_token, secret_endpoint)
    if "error" not in secret:
        ssh_config["password"] = secret["ssh_password"] if "ssh_password" in secret else ""
        ssh_config["private_key"] = secret["ssh_pkey"] if "ssh_pkey" in secret else ""
        ssh_config["user"] = secret["ssh_user"]
        return ssh_config
    else:
        raise NonRecoverableError("Could not get ssh_config from vault for ssh host " + host +
                                  "\n Status code: " + str(secret["error"]) +
                                  "\n Content: " + str(secret["content"]))