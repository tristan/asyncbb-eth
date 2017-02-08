import binascii
import random
import regex
import tornado.httpclient

from asyncbb.jsonrpc import JsonRPCError

JSON_RPC_VERSION = "2.0"

HEX_RE = regex.compile("(0x)?([0-9a-fA-F]+)")

def validate_hex(value):
    if isinstance(value, int):
        return hex(value)
    if isinstance(value, bytes):
        return "0x{}".format(binascii.b2a_hex(value).decode('ascii'))
    # else assume string
    m = HEX_RE.match(value)
    if m:
        return "0x{}".format(m.group(2))
    raise ValueError("Unable to convert value to valid hex string")

def validate_block_param(param):

    if param not in ("earliest", "latest", "pending"):
        return validate_hex(param)
    return param

class JsonRPCClient:

    def __init__(self, url):

        self._url = url
        self._httpclient = tornado.httpclient.AsyncHTTPClient()

    async def _fetch(self, method, params=None):
        id = random.randint(0, 1000000)

        if params is None:
            params = []

        data = {
            "jsonrpc": JSON_RPC_VERSION,
            "id": id,
            "method": method,
            "params": params
        }

        # NOTE: letting errors fall through here for now as it means
        # there is something drastically wrong with the jsonrpc server
        # which means something probably needs to be fixed
        resp = await self._httpclient.fetch(
            self._url,
            method="POST",
            headers={'Content-Type': "application/json"},
            body=tornado.escape.json_encode(data)
        )

        rval = tornado.escape.json_decode(resp.body)

        # verify the id we got back is the same as what we passed
        if id != rval['id']:

            raise JsonRPCError(-1, "returned id was not the same as the inital request")

        if "error" in rval:

            raise JsonRPCError(rval['id'], rval['error']['code'], rval['error']['message'], rval['error']['data'] if 'data' in rval['error'] else None)

        return rval['result']

    async def eth_getBalance(self, address, block="latest"):

        address = validate_hex(address)
        block = validate_block_param(block)

        result = await self._fetch("eth_getBalance", [address, block])

        if result.startswith("0x"):
            result = result[2:]

        return int(result, 16)

    async def eth_getTransactionCount(self, address, block="latest"):

        address = validate_hex(address)
        block = validate_block_param(block)

        result = await self._fetch("eth_getTransactionCount", [address, block])

        if result.startswith("0x"):
            result = result[2:]

        return int(result, 16)

    async def eth_estimateGas(self, source_address, target_address, **kwargs):

        source_address = validate_hex(source_address)
        hexkwargs = {"from": source_address}

        if target_address != '':
            target_address = validate_hex(target_address)
            hexkwargs["to"] = target_address

        for k, value in kwargs.items():
            hexkwargs[k] = validate_hex(value)

        result = await self._fetch("eth_estimateGas", [hexkwargs])

        return int(result, 16)

    async def eth_sendRawTransaction(self, tx):

        tx = validate_hex(tx)
        result = await self._fetch("eth_sendRawTransaction", [tx])

        return result

    async def eth_getTransactionReceipt(self, tx):

        tx = validate_hex(tx)
        result = await self._fetch("eth_getTransactionReceipt", [tx])

        return result

    async def eth_getTransactionByHash(self, tx):

        tx = validate_hex(tx)
        result = await self._fetch("eth_getTransactionByHash", [tx])

        return result

    async def eth_blockNumber(self):

        result = await self._fetch("eth_blockNumber", [])

        if result.startswith("0x"):
            result = result[2:]

        return int(result, 16)

    async def eth_getBlockByNumber(self, number, with_transactions=True):

        number = validate_block_param(number)

        result = await self._fetch("eth_getBlockByNumber", [number, with_transactions])

        return result

    async def eth_newPendingTransactionFilter(self):

        result = await self._fetch("eth_newPendingTransactionFilter", [])

        return result

    async def eth_newBlockFilter(self):

        result = await self._fetch("eth_newBlockFilter", [])

        return result

    async def eth_getFilterChanges(self, filter_id):

        result = await self._fetch("eth_getFilterChanges", [filter_id])

        return result

    async def eth_uninstallFilter(self, filter_id):

        result = await self._fetch("eth_uninstallFilter", [filter_id])

        return result

    async def eth_getCode(self, address, block="latest"):

        address = validate_hex(address)
        block = validate_block_param(block)
        result = await self._fetch("eth_getCode", [address, block])

        return result

    async def eth_call(self, *, to_address, from_address=None, gas=None, gasprice=None, value=None, data=None, block="latest"):

        to_address = validate_hex(to_address)
        block = validate_block_param(block)

        callobj = {"to": to_address}
        if from_address:
            callobj['from'] = validate_hex(from_address)
        if gas:
            callobj['gas'] = validate_hex(gas)
        if gasprice:
            callobj['gasprice'] = validate_hex(gasprice)
        if value:
            callobj['value'] = validate_hex(value)
        if data:
            callobj['data'] = validate_hex(data)

        result = await self._fetch("eth_call", [callobj, block])
        return result
