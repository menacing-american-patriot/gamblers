import os
from py_clob_client.client import ClobClient

HOST = "https://clob.polymarket.com"
CHAIN_ID = 137
signing_key = os.environ.get("PRIVATE_KEY")
funder = os.environ.get("PROXY_FUNDER")

client = ClobClient(
    HOST,
    key=signing_key,
    chain_id=CHAIN_ID,
    signature_type=1,   # email/Magic/proxy wallet
    funder=funder,
)

creds = client.create_or_derive_api_creds()
print("POLY_API_KEY=", creds.api_key)
print("POLY_API_SECRET=", creds.api_secret)
print("POLY_API_PASSPHRASE=", creds.api_passphrase)
