import os
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, ApiCreds
from dotenv import load_dotenv
load_dotenv()
from ollama_client import OllamaClient

host: str = "https://clob.polymarket.com"
chain_id: int = 137 
key: str = os.environ.get("PRIVATE_KEY")
POLYMARKET_PROXY_ADDRESS: str = os.environ.get('POLYMARKET_PROXY_ADDRESS')


client = ClobClient(host, key=key, chain_id=chain_id, signature_type=1, funder=POLYMARKET_PROXY_ADDRESS)

client.set_api_creds(client.create_or_derive_api_creds()) 