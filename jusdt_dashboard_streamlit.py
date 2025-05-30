# jusdt_dashboard_streamlit.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json
import requests
import os
from web3 import Web3
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

st.set_page_config(page_title="JUSDT Ecosystem Dashboard", layout="wide")
st.title("💵 JUSDT Ecosystem Dashboard")

# === Wallet and Web3 Config ===
INFURA_URL = os.getenv("INFURA_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
JUSDT = os.getenv("JUSDT_CONTRACT")
WETH = os.getenv("WETH_CONTRACT")
CWETH = os.getenv("CWETH_CONTRACT", "0xEF2720FF0094230b4f97dE8C8822D1dF5c221f18")
CWETHP = os.getenv("CWETHP_CONTRACT", "0xCE6CB8b368ab4CFdb82113248e5a80EeB2B94b8F")
JUSDC = os.getenv("JUSDC_CONTRACT", "0x01A96E026f62299FA6004C431C23D326D9d92718")
ROUTER_ADDRESS = os.getenv("ROUTER_ADDRESS")

w3 = Web3(Web3.HTTPProvider(INFURA_URL))
account = w3.eth.account.from_key(PRIVATE_KEY)

# === Load ABIs ===
with open("abis/ERC20.json") as f:
    erc20_abi = json.load(f)

with open("abis/UniswapV3SwapRouter.json") as f:
    router_abi = json.load(f)

# === Swap Router Contract ===
swap_router = w3.eth.contract(address=Web3.to_checksum_address(ROUTER_ADDRESS), abi=router_abi)

# === Token Contracts ===
jusdt_token = w3.eth.contract(address=Web3.to_checksum_address(JUSDT), abi=erc20_abi)
weth_token = w3.eth.contract(address=Web3.to_checksum_address(WETH), abi=erc20_abi)
cweth_token = w3.eth.contract(address=Web3.to_checksum_address(CWETH), abi=erc20_abi)
cwethp_token = w3.eth.contract(address=Web3.to_checksum_address(CWETHP), abi=erc20_abi)
jusdc_token = w3.eth.contract(address=Web3.to_checksum_address(JUSDC), abi=erc20_abi)

# === Live JUSDT Data Source ===
IPFS_URL = "https://gateway.pinata.cloud/ipfs/QmdD3rn1Tf9KrvPTnTaNsBHEf5SQ8tob1eRWAtvYJeb4Rn"

@st.cache_data(ttl=300)
def load_ipfs_data():
    try:
        response = requests.get(IPFS_URL)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch IPFS data: {e}")
        return {}

data = load_ipfs_data()

# === Token Liquidity Data ===
st.subheader("📊 JUSDT/WETH Liquidity Breakdown")
amount_a = data.get("amount_a")
amount_b = data.get("amount_b")

if amount_a is not None and amount_b is not None:
    df_liq = pd.DataFrame({
        "Token": ["JUSDT", "WETH"],
        "Amount": [float(amount_a), float(amount_b)]
    })
    st.table(df_liq)

    fig, ax = plt.subplots()
    ax.bar(df_liq["Token"], df_liq["Amount"], color=["#00ccff", "#ff6600"])
    ax.set_title("Current Liquidity (JUSDT / WETH)")
    st.pyplot(fig)
else:
    st.warning("⚠️ amount_a or amount_b missing in IPFS JSON")

# === Wallet Balances ===
st.subheader("💼 Wallet Balances")

def get_balance(contract, decimals=18):
    try:
        balance = contract.functions.balanceOf(WALLET_ADDRESS).call()
        return round(balance / (10 ** decimals), 4)
    except:
        return "N/A"

balances = {
    "JUSDT": get_balance(jusdt_token),
    "WETH": get_balance(weth_token),
    "CWETH": get_balance(cweth_token),
    "CWETHP": get_balance(cwethp_token),
    "JUSDC": get_balance(jusdc_token)
}

df_bal = pd.DataFrame({"Token": list(balances.keys()), "Balance": list(balances.values())})
st.table(df_bal)

# === Pool Metadata ===
st.subheader("📟 Pool Metadata & Ticks")
fields = [
    ("Token A Address", str(data.get("token_a", "N/A"))),
    ("Token B Address", str(data.get("token_b", "N/A"))),
    ("Fee Tier", str(data.get("fee", "N/A"))),
    ("Tick Lower", str(data.get("tick_lower", "N/A"))),
    ("Tick Upper", str(data.get("tick_upper", "N/A"))),
    ("Currency", str(data.get("currency", "N/A"))),
    ("Status", str(data.get("status", "N/A")))
]
df_proof = pd.DataFrame(fields, columns=["Field", "Value"])
st.table(df_proof)

# === Reference Note ===
st.subheader("📌 Reference Note")
note = data.get("note", "No reference note found in IPFS JSON")
st.info(note)

# === Raw JSON Preview ===
st.subheader("🧪 Raw IPFS JSON Preview")
st.json(data)

# === Swap Interface ===
st.subheader("🔁 Live Uniswap Swap")
token_in = "JUSDT"
token_out = "WETH"
amount = st.number_input("Amount to swap (JUSDT)", min_value=1.0, step=1.0)

if st.button("Swap JUSDT for WETH"):
    try:
        amount_in = int(amount * (10 ** 18))
        nonce = w3.eth.get_transaction_count(account.address)

        approve_tx = jusdt_token.functions.approve(ROUTER_ADDRESS, amount_in).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': 100000,
            'gasPrice': w3.to_wei('5', 'gwei')
        })
        signed_approve = w3.eth.account.sign_transaction(approve_tx, private_key=PRIVATE_KEY)
        tx_hash_approve = w3.eth.send_raw_transaction(signed_approve.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash_approve)

        params = {
            "tokenIn": Web3.to_checksum_address(JUSDT),
            "tokenOut": Web3.to_checksum_address(WETH),
            "fee": 3000,
            "recipient": WALLET_ADDRESS,
            "deadline": int(w3.eth.get_block('latest')['timestamp']) + 1200,
            "amountIn": amount_in,
            "amountOutMinimum": 0,
            "sqrtPriceLimitX96": 0
        }
        swap_tx = swap_router.functions.exactInputSingle(params).build_transaction({
            'from': account.address,
            'nonce': nonce + 1,
            'gas': 300000,
            'gasPrice': w3.to_wei('50', 'gwei')
        })
        signed_swap = w3.eth.account.sign_transaction(swap_tx, private_key=PRIVATE_KEY)
        tx_hash_swap = w3.eth.send_raw_transaction(signed_swap.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash_swap)

        st.success(f"✅ Swap complete! Tx Hash: {tx_hash_swap.hex()}")
    except Exception as e:
        st.error(f"Swap failed: {e}")
