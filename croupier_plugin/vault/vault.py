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


def revoke_token(vault_config):
    vault_token = vault_config["token"]
    vault_address = vault_config["address"]
    auth_header = {"x-vault-token": vault_token}
    endpoint = vault_address + "/v1/auth/token/revoke-self"
    response = post(endpoint, headers=auth_header)
    if response.ok:
        return None
    else:
        return {"error": response.status_code,
                "content": response.json()}
