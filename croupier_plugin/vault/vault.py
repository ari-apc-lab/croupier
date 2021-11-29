from cloudify import ctx
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
    if cubbyhole:
        secret_endpoint = vault_address + "/v1/cubbyhole/" + host
    else:
        secret_endpoint = vault_address + "/v1/" + vault_user + "/" + host
    secret = get_secret(vault_token, secret_endpoint)
    if "error" not in secret:
        return secret
    else:
        ctx.logger.warning("Could not get credentials from vault for host " + host + " and user " + vault_user +
                           "\n Status code: " + str(secret["error"]) +
                           "\n Content: " + str(secret["content"]))
        return ""
