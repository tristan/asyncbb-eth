import asyncio
import rlp
import bitcoin
from ethereum import utils
from ethereum.transactions import Transaction
from asyncbb.ethereum.client import JsonRPCClient

FAUCET_PRIVATE_KEY = "0x0164f7c7399f4bb1eafeaae699ebbb12050bc6a50b2836b9ca766068a9d000c0"
FAUCET_ADDRESS = "0xde3d2d9dd52ea80f7799ef4791063a5458d13913"

DEFAULT_STARTGAS = 21000
DEFAULT_GASPRICE = 20000000000

def data_decoder(data):
    """Decode `data` representing unformatted data."""
    if not data.startswith('0x'):
        data = '0x' + data

    if len(data) % 2 != 0:
        # workaround for missing leading zeros from netstats
        assert len(data) < 64 + 2
        data = '0x' + '0' * (64 - (len(data) - 2)) + data[2:]

    try:
        return utils.decode_hex(data[2:])
    except TypeError:
        raise Exception('Invalid data hex encoding', data[2:])

def data_encoder(data, length=None):
    """Encode unformatted binary `data`.

    If `length` is given, the result will be padded like this: ``data_encoder('\xff', 3) ==
    '0x0000ff'``.
    """
    s = utils.encode_hex(data).decode('ascii')
    if length is None:
        return '0x' + s
    else:
        return '0x' + s.rjust(length * 2, '0')

def private_key_to_address(private_key):
    """Extracts the address from the given private key, returning the
    hex representation of the address"""

    if isinstance(private_key, str):
        private_key = data_decoder(private_key)

    bcpub = bitcoin.privtopub(private_key)
    # remove prefix (https://en.bitcoin.it/wiki/Elliptic_Curve_Digital_Signature_Algorithm)
    pub_key = bcpub[1:]
    # generate address from key
    addr = utils.sha3(pub_key)[12:]
    return data_encoder(addr)

class FaucetMixin:

    async def faucet(self, to, value, *, from_private_key=FAUCET_PRIVATE_KEY, startgas=DEFAULT_STARTGAS,
                     gasprice=DEFAULT_GASPRICE, nonce=None, data=b"", wait_on_confirmation=True):

        if isinstance(from_private_key, str):
            from_private_key = data_decoder(from_private_key)
        from_address = private_key_to_address(from_private_key)

        ethclient = JsonRPCClient(self._app.config['ethereum']['url'])

        to = data_decoder(to)
        if len(to) not in (20, 0):
            raise Exception('Addresses must be 20 or 0 bytes long (len was {})'.format(len(to)))

        if nonce is None:
            nonce = await ethclient.eth_getTransactionCount(from_address)
        balance = await ethclient.eth_getBalance(from_address)

        tx = Transaction(nonce, gasprice, startgas, to, value, data, 0, 0, 0)

        if balance < (tx.value + (tx.startgas * tx.gasprice)):
            raise Exception("Faucet doesn't have enough funds")

        tx.sign(from_private_key)

        tx_encoded = data_encoder(rlp.encode(tx, Transaction))

        tx_hash = await ethclient.eth_sendRawTransaction(tx_encoded)

        while wait_on_confirmation:
            resp = await ethclient.eth_getTransactionByHash(tx_hash)
            if resp is None or resp['blockNumber'] is None:
                await asyncio.sleep(0.1)
            else:
                break

        if to == b'':
            print("contract address: {}".format(data_encoder(tx.creates)))

        return tx_hash

    async def deploy_contract(self, bytecode, *, from_private_key=FAUCET_PRIVATE_KEY,
                              startgas=None, gasprice=DEFAULT_GASPRICE, wait_on_confirmation=True):

        if isinstance(from_private_key, str):
            from_private_key = data_decoder(from_private_key)
        from_address = private_key_to_address(from_private_key)

        ethclient = JsonRPCClient(self._app.config['ethereum']['url'])

        nonce = await ethclient.eth_getTransactionCount(from_address)
        balance = await ethclient.eth_getBalance(from_address)

        gasestimate = await ethclient.eth_estimateGas(from_address, '', data=bytecode, nonce=nonce, value=0, gasprice=gasprice)

        if startgas is None:
            startgas = gasestimate
        elif gasestimate > startgas:
            raise Exception("Estimated gas usage is larger than the provided gas")

        tx = Transaction(nonce, gasprice, startgas, '', 0, bytecode, 0, 0, 0)

        if balance < (tx.value + (tx.startgas * tx.gasprice)):
            raise Exception("Faucet doesn't have enough funds")

        tx.sign(from_private_key)

        tx_encoded = data_encoder(rlp.encode(tx, Transaction))

        tx_hash = await ethclient.eth_sendRawTransaction(tx_encoded)

        contract_address = data_encoder(tx.creates)

        while wait_on_confirmation:
            resp = await ethclient.eth_getTransactionByHash(tx_hash)
            if resp is None or resp['blockNumber'] is None:
                await asyncio.sleep(0.1)
            else:
                code = await ethclient.eth_getCode(contract_address)
                if code == '0x':
                    raise Exception("Failed to deploy contract")
                break

        return tx_hash, contract_address
