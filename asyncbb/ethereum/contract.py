import asyncio
import subprocess
import os
import rlp
from tornado.escape import json_decode
from ethutils import data_decoder, data_encoder, private_key_to_address
from ethereum.abi import ContractTranslator
from ethereum.transactions import Transaction
from asyncbb.ethereum.client import JsonRPCClient

class ContractMethod:

    def __init__(self, name, contract, *, from_key=None):
        self.name = name
        self.contract = contract
        self.is_constant = self.contract.translator.function_data[name]['is_constant']
        if from_key:
            if isinstance(from_key, str):
                self.from_key = data_decoder(from_key)
            else:
                self.from_key = from_key
            self.from_address = private_key_to_address(from_key)
        else:
            self.from_address = None

    def set_sender(self, key):
        return ContractMethod(self.name, self.contract, from_key=key)

    async def __call__(self, *args):

        # TODO: figure out if we can validate args

        ethurl = os.environ.get('ETHEREUM_NODE_URL')
        if not ethurl:
            raise Exception("requires 'ETHEREUM_NODE_URL' environment variable to be set")

        ethclient = JsonRPCClient(ethurl)

        data = self.contract.translator.encode_function_call(self.name, args)
        # TODO: figure out if there's a better way to tell if the function needs to be called via sendTransaction
        if self.is_constant:
            result = await ethclient.eth_call(from_address=self.from_address or '', to_address=self.contract.address,
                                              data=data)
            return self.contract.translator.decode_function_result(self.name, data_decoder(result))
        else:
            if self.from_address is None:
                raise Exception("Cannot call non-constant function without a sender")

            nonce = await ethclient.eth_getTransactionCount(self.from_address)
            balance = await ethclient.eth_getBalance(self.from_address)

            gasprice = 20000000000
            value = 0

            startgas = await ethclient.eth_estimateGas(self.from_address, self.contract.address, data=data, nonce=nonce, value=0, gasprice=gasprice)
            if startgas == 50000000:
                # TODO: this is not going to always be the case!
                raise Exception("Unable to estimate gas cost, possibly something wrong with the transaction arguments")

            if balance < (startgas * gasprice):
                raise Exception("Given account doesn't have enough funds")

            tx = Transaction(nonce, gasprice, startgas, self.contract.address, value, data, 0, 0, 0)
            tx.sign(self.from_key)

            tx_encoded = data_encoder(rlp.encode(tx, Transaction))
            try:
                tx_hash = await ethclient.eth_sendRawTransaction(tx_encoded)
            except:
                print(balance, startgas * gasprice, startgas)
                raise

            # wait for the contract to be deployed
            while True:
                resp = await ethclient.eth_getTransactionByHash(tx_hash)
                if resp is None or resp['blockNumber'] is None:
                    await asyncio.sleep(0.1)
                else:
                    break

            # TODO: is it possible for non-const functions to have return types?
            return None


class Contract:

    def __init__(self, *, abi, code, address, translator=None):
        self.abi = abi
        self.valid_funcs = [part['name'] for part in abi if part['type'] == 'function']
        self.translator = translator or ContractTranslator(abi)
        self.address = address

    def __getattr__(self, name):

        if name in self.valid_funcs:
            return ContractMethod(name, self)

        raise AttributeError("'Contract' object has no attribute '{}'".format(name))

    @classmethod
    async def from_source_code(cls, sourcecode, contract_name, constructor_data=None, *, address=None, deployer_private_key=None):

        ethurl = os.environ.get('ETHEREUM_NODE_URL')
        if not ethurl:
            raise Exception("requires 'ETHEREUM_NODE_URL' environment variable to be set")

        if address is None and deployer_private_key is None:
            raise TypeError("requires either address or deployer_private_key")
        if address is None and not isinstance(constructor_data, list):
            raise TypeError("must supply constructor_data as a list (hint: use [] if args should be empty)")

        args = ['solc', '--combined-json', 'bin,abi', '--add-std']
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, stderrdata = process.communicate(input=sourcecode)
        output = json_decode(output)

        contract = output['contracts']['<stdin>:{}'.format(contract_name)]
        abi = json_decode(contract['abi'])

        ethclient = JsonRPCClient(ethurl)

        if address is not None:
            # verify there is code at the given address
            code = await ethclient.eth_getCode(address)
            if code == "0x":
                raise Exception("No code found at given address")
            return Contract(abi=abi,
                            code=data_decoder(code),
                            address=address)

        # deploy contract
        translator = ContractTranslator(abi)
        bytecode = data_decoder(contract['bin'])
        constructor_call = translator.encode_constructor_arguments(constructor_data)
        bytecode += constructor_call

        if isinstance(deployer_private_key, str):
            deployer_private_key = data_decoder(deployer_private_key)
        deployer_address = private_key_to_address(deployer_private_key)
        nonce = await ethclient.eth_getTransactionCount(deployer_address)
        balance = await ethclient.eth_getBalance(deployer_address)

        gasprice = 20000000000
        value = 0

        startgas = await ethclient.eth_estimateGas(deployer_address, '', data=bytecode, nonce=nonce, value=0, gasprice=gasprice)

        if balance < (startgas * gasprice):
            raise Exception("Given account doesn't have enough funds")

        tx = Transaction(nonce, gasprice, startgas, '', value, bytecode, 0, 0, 0)
        tx.sign(deployer_private_key)

        tx_encoded = data_encoder(rlp.encode(tx, Transaction))
        tx_hash = await ethclient.eth_sendRawTransaction(tx_encoded)

        contract_address = data_encoder(tx.creates)

        # wait for the contract to be deployed
        while True:
            resp = await ethclient.eth_getTransactionByHash(tx_hash)
            if resp is None or resp['blockNumber'] is None:
                await asyncio.sleep(0.1)
            else:
                code = await ethclient.eth_getCode(contract_address)
                if code == '0x':
                    raise Exception("Failed to deploy contract: resulting address '{}' has no code".format(contract_address))
                break

        return Contract(abi=abi, code=code, address=contract_address, translator=translator)
