from web3 import Web3, HTTPProvider
import json
import time
from web3.exceptions import ContractLogicError

# Colors for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
CYAN = '\033[96m'
MAGENTA = '\033[95m'
RESET = '\033[0m'

# Setup Web3
web3 = Web3(Web3.HTTPProvider("https://tea-sepolia.g.alchemy.com/public"))
chainId = web3.eth.chain_id

# Staking Contract ABI (Example - Replace with actual staking contract ABI)
staking_abi = json.loads('''[
    {
        "inputs": [
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "stake",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "unstake",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "stakingToken",
        "outputs": [{"internalType": "contract IERC20", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]''')

# ERC20 Token ABI
token_abi = json.loads('''[
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]''')

def get_gas_parameters():
    """Get gas parameters with automatic adjustment"""
    try:
        base_fee = web3.eth.get_block('latest')['baseFeePerGas']
        max_priority = int(base_fee * 0.25)  # 25% of base fee
        max_fee = base_fee + max_priority
        
        return {
            'maxFeePerGas': min(max_fee, web3.to_wei(150, 'gwei')),
            'maxPriorityFeePerGas': min(max_priority, web3.to_wei(3, 'gwei')),
            'gas': 200000  # Default gas limit
        }
    except Exception as e:
        print(f"{YELLOW}Using fallback gas parameters: {e}{RESET}")
        return {
            'maxFeePerGas': web3.to_wei(50, 'gwei'),
            'maxPriorityFeePerGas': web3.to_wei(2, 'gwei'),
            'gas': 200000
        }

def check_allowance(owner, spender, token_address):
    """Check token allowance"""
    token_contract = web3.eth.contract(address=token_address, abi=token_abi)
    allowance = token_contract.functions.allowance(owner, spender).call()
    return allowance

def approve_token(key, owner, spender, token_address, amount):
    """Approve token spending"""
    try:
        token_contract = web3.eth.contract(address=token_address, abi=token_abi)
        
        gas_params = get_gas_parameters()
        tx = token_contract.functions.approve(
            spender,
            amount
        ).build_transaction({
            'chainId': chainId,
            'from': owner,
            'nonce': web3.eth.get_transaction_count(owner),
            **gas_params
        })
        
        signed_tx = web3.eth.account.sign_transaction(tx, key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        print(f"{CYAN}Approving {amount} tokens for staking contract...{RESET}")
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt.status == 1:
            print(f"{GREEN}Approval successful! TX: {web3.to_hex(tx_hash)}{RESET}")
            return True
        return False
        
    except Exception as e:
        print(f"{RED}Approval failed: {e}{RESET}")
        return False

def stake_tokens(key, staking_contract_address, amount):
    """Stake tokens in the staking contract"""
    try:
        account = web3.eth.account.from_key(key)
        staking_contract = web3.eth.contract(address=staking_contract_address, abi=staking_abi)
        
        # Get staking token address
        token_address = staking_contract.functions.stakingToken().call()
        token_contract = web3.eth.contract(address=token_address, abi=token_abi)
        
        # Get token decimals
        try:
            decimals = token_contract.functions.decimals().call()
        except:
            decimals = 18
            
        amount_wei = int(amount * (10 ** decimals))
        
        # Check allowance and approve if needed
        allowance = check_allowance(account.address, staking_contract_address, token_address)
        if allowance < amount_wei:
            if not approve_token(key, account.address, staking_contract_address, token_address, amount_wei):
                return False
            time.sleep(5)  # Wait for approval to be confirmed
        
        # Stake tokens
        gas_params = get_gas_parameters()
        tx = staking_contract.functions.stake(
            amount_wei
        ).build_transaction({
            'chainId': chainId,
            'from': account.address,
            'nonce': web3.eth.get_transaction_count(account.address),
            **gas_params
        })
        
        signed_tx = web3.eth.account.sign_transaction(tx, key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        print(f"{CYAN}Staking {amount} tokens...{RESET}")
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt.status == 1:
            print(f"{GREEN}Staking successful! TX: {web3.to_hex(tx_hash)}{RESET}")
            return True
        print(f"{RED}Staking failed (status 0){RESET}")
        return False
        
    except ContractLogicError as e:
        print(f"{RED}Contract error: {str(e)}{RESET}")
        return False
    except Exception as e:
        print(f"{RED}Staking error: {e}{RESET}")
        return False

def unstake_tokens(key, staking_contract_address, amount):
    """Unstake tokens from the staking contract"""
    try:
        account = web3.eth.account.from_key(key)
        staking_contract = web3.eth.contract(address=staking_contract_address, abi=staking_abi)
        
        # Get token decimals
        token_address = staking_contract.functions.stakingToken().call()
        token_contract = web3.eth.contract(address=token_address, abi=token_abi)
        
        try:
            decimals = token_contract.functions.decimals().call()
        except:
            decimals = 18
            
        amount_wei = int(amount * (10 ** decimals))
        
        # Check staked balance
        staked_balance = staking_contract.functions.balanceOf(account.address).call()
        if staked_balance < amount_wei:
            print(f"{RED}Insufficient staked balance: {staked_balance/(10**decimals)} tokens staked{RESET}")
            return False
        
        # Unstake tokens
        gas_params = get_gas_parameters()
        tx = staking_contract.functions.unstake(
            amount_wei
        ).build_transaction({
            'chainId': chainId,
            'from': account.address,
            'nonce': web3.eth.get_transaction_count(account.address),
            **gas_params
        })
        
        signed_tx = web3.eth.account.sign_transaction(tx, key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        print(f"{CYAN}Unstaking {amount} tokens...{RESET}")
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt.status == 1:
            print(f"{GREEN}Unstaking successful! TX: {web3.to_hex(tx_hash)}{RESET}")
            return True
        print(f"{RED}Unstaking failed (status 0){RESET}")
        return False
        
    except ContractLogicError as e:
        print(f"{RED}Contract error: {str(e)}{RESET}")
        return False
    except Exception as e:
        print(f"{RED}Unstaking error: {e}{RESET}")
        return False

def get_staked_balance(address, staking_contract_address):
    """Check staked balance"""
    staking_contract = web3.eth.contract(address=staking_contract_address, abi=staking_abi)
    token_address = staking_contract.functions.stakingToken().call()
    token_contract = web3.eth.contract(address=token_address, abi=token_abi)
    
    try:
        decimals = token_contract.functions.decimals().call()
    except:
        decimals = 18
        
    balance = staking_contract.functions.balanceOf(address).call()
    return balance / (10 ** decimals)

def main():
    print(f"{CYAN}Tea Sepolia Staking/Unstaking Script{RESET}")
    
    # User inputs
    private_key = input(f"{YELLOW}Enter your private key: {RESET}")
    staking_contract_address = web3.to_checksum_address(input(f"{YELLOW}Enter staking contract address: {RESET}"))
    
    while True:
        print(f"\n{MAGENTA}==== Menu ===={RESET}")
        print(f"1. Stake tokens")
        print(f"2. Unstake tokens")
        print(f"3. Check staked balance")
        print(f"4. Exit")
        
        choice = input(f"{YELLOW}Select an option (1-4): {RESET}")
        
        try:
            if choice == '1':
                amount = float(input(f"{YELLOW}Enter amount to stake: {RESET}"))
                stake_tokens(private_key, staking_contract_address, amount)
                
            elif choice == '2':
                amount = float(input(f"{YELLOW}Enter amount to unstake: {RESET}"))
                unstake_tokens(private_key, staking_contract_address, amount)
                
            elif choice == '3':
                account = web3.eth.account.from_key(private_key)
                balance = get_staked_balance(account.address, staking_contract_address)
                print(f"{GREEN}Staked balance: {balance} tokens{RESET}")
                
            elif choice == '4':
                print(f"{CYAN}Exiting...{RESET}")
                break
                
            else:
                print(f"{RED}Invalid choice{RESET}")
                
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")

if __name__ == "__main__":
    main()
