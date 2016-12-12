import asyncio
import rlp
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

class FaucetMixin:

    async def faucet(self, to, value):

        ethclient = JsonRPCClient(self._app.config['ethereum']['url'])

        to = data_decoder(to)
        if len(to) not in (20, 0):
            raise Exception('Addresses must be 20 or 0 bytes long (len was {})'.format(len(to)))

        nonce = await ethclient.eth_getTransactionCount(FAUCET_ADDRESS)
        balance = await ethclient.eth_getBalance(FAUCET_ADDRESS)

        tx = Transaction(nonce, DEFAULT_GASPRICE, DEFAULT_STARTGAS, to, value, b"", 0, 0, 0)

        if balance < (tx.value + (tx.startgas * tx.gasprice)):
            raise Exception("Faucet doesn't have enough funds")

        tx.sign(data_decoder(FAUCET_PRIVATE_KEY))

        tx_encoded = data_encoder(rlp.encode(tx, Transaction))

        tx_hash = await ethclient.eth_sendRawTransaction(tx_encoded)

        while True:
            resp = await ethclient.eth_getTransactionByHash(tx_hash)
            if resp is None or resp['blockNumber'] is None:
                await asyncio.sleep(0.1)
            else:
                break
