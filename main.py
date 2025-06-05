import random
import time
from web3 import Web3
from eth_account import Account
from eth_utils import to_checksum_address

# Inisialisasi Web3
w3 = Web3(Web3.HTTPProvider('https://testnet.dplabs-internal.com'))  # Ganti dengan URL RPC testnet Anda

# Kunci pribadi dan alamat dompet
private_key = 'YOUR_PKEY_HERE'  # Ganti dengan kunci pribadi Anda
account = Account.from_key(private_key)
wallet_address = account.address

# Alamat kontrak dan token
tokens = {
    'USDC': '0xAD902CF99C2dE2f1Ba5ec4D642Fd7E49cae9EE37',
    'WPHRS': '0x76aaaDA469D23216bE5f7C596fA25F282Ff9b364',
    'USDT': '0xEd59De2D7ad9C043442e381231eE3646FC3C2939',
}

contract_address = '0x1A4DE519154Ae51200b0Ad7c90F7faC75547888a'

token_decimals = {
    'WPHRS': 18,
    'USDC': 6,
    'USDT': 6,
}

# ABI kontrak
contract_abi = [
    {
        'inputs': [
            {'internalType': 'uint256', 'name': 'collectionAndSelfcalls', 'type': 'uint256'},
            {'internalType': 'bytes[]', 'name': 'data', 'type': 'bytes[]'},
        ],
        'name': 'multicall',
        'outputs': [],
        'stateMutability': 'nonpayable',
        'type': 'function',
    },
]

erc20_abi = [
    {
        'constant': True,
        'inputs': [{'name': '_owner', 'type': 'address'}],
        'name': 'balanceOf',
        'outputs': [{'name': 'balance', 'type': 'uint256'}],
        'type': 'function',
    },
    {
        'constant': True,
        'inputs': [
            {'name': '_owner', 'type': 'address'},
            {'name': '_spender', 'type': 'address'},
        ],
        'name': 'allowance',
        'outputs': [{'name': 'remaining', 'type': 'uint256'}],
        'type': 'function',
    },
    {
        'constant': False,
        'inputs': [
            {'name': '_spender', 'type': 'address'},
            {'name': '_value', 'type': 'uint256'},
        ],
        'name': 'approve',
        'outputs': [{'name': 'success', 'type': 'bool'}],
        'type': 'function',
    },
    {
        'constant': False,
        'inputs': [],
        'name': 'deposit',
        'outputs': [],
        'type': 'function',
    },
    {
        'constant': False,
        'inputs': [{'name': 'wad', 'type': 'uint256'}],
        'name': 'withdraw',
        'outputs': [],
        'type': 'function',
    },
]

pair_options = [
    {'id': 1, 'from': 'WPHRS', 'to': 'USDC', 'amount': 0.001},
    {'id': 2, 'from': 'WPHRS', 'to': 'USDT', 'amount': 0.001},
    {'id': 3, 'from': 'USDC', 'to': 'WPHRS', 'amount': 1},
    {'id': 4, 'from': 'USDT', 'to': 'WPHRS', 'amount': 1},
    {'id': 5, 'from': 'USDC', 'to': 'USDT', 'amount': 1},
    {'id': 6, 'from': 'USDT', 'to': 'USDC', 'amount': 1},
]

def check_balance_and_approval(token_address, amount, decimals, spender):
    token_contract = w3.eth.contract(address=to_checksum_address(token_address), abi=erc20_abi)
    balance = token_contract.functions.balanceOf(wallet_address).call()
    required = int(amount * (10 ** decimals))

    if balance < required:
        print(f"Skipping: Insufficient balance: {balance / (10 ** decimals)} < {amount}")
        return False

    allowance = token_contract.functions.allowance(wallet_address, spender).call()
    if allowance < required:
        print(f"Approving {amount} tokens for {spender}...")
        nonce = w3.eth.get_transaction_count(wallet_address)
        tx = token_contract.functions.approve(spender, 2 ** 256 - 1).build_transaction({
            'from': wallet_address,
            'nonce': nonce,
            'gas': 100000,
            'gasPrice': w3.to_wei('1', 'gwei'),
        })
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print("Approval completed")
    return True

def get_multicall_data(pair, amount):
    decimals = token_decimals[pair['from']]
    scaled_amount = int(amount * (10 ** decimals))
    data = w3.codec.encode(
        ['address', 'address', 'uint256', 'address', 'uint256', 'uint256', 'uint256'],
        [
            to_checksum_address(tokens[pair['from']]),
            to_checksum_address(tokens[pair['to']]),
            500,
            to_checksum_address(wallet_address),
            scaled_amount,
            0,
            0,
        ]
    )
    return '0x04e45aaf' + data.hex()

def perform_swap():
    pair = random.choice(pair_options)
    amount = pair['amount']
    print(f"Preparing swap: {pair['from']} -> {pair['to']} ({amount} {pair['from']})")

    decimals = token_decimals[pair['from']]
    token_contract = w3.eth.contract(address=to_checksum_address(tokens[pair['from']]), abi=erc20_abi)
    balance = token_contract.functions.balanceOf(wallet_address).call()
    required = int(amount * (10 ** decimals))

    if balance < required:
        print(f"Skipping swap: Insufficient {pair['from']} balance: {balance / (10 ** decimals)} < {amount}")
        return

    if not check_balance_and_approval(tokens[pair['from']], amount, decimals, contract_address):
        return

    contract = w3.eth.contract(address=to_checksum_address(contract_address), abi=contract_abi)
    multicall_data = [get_multicall_data(pair, amount)]
    deadline = int(time.time()) + 300
    nonce = w3.eth.get_transaction_count(wallet_address)
    tx = contract.functions.multicall(deadline, multicall_data).build_transaction({
        'from': wallet_address,
        'nonce': nonce,
        'gas': 300000,
        'gasPrice': w3.to_wei('1', 'gwei'),
    })
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Swap completed: {receipt.transactionHash.hex()}")
    print(f"Explorer: https://testnet.pharosscan.xyz/tx/{receipt.transactionHash.hex()}")

# Contoh penggunaan
perform_swap()
