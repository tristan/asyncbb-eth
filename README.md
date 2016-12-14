# Ethereum Node Extras for asyncbb

Provides a tornado handler mixin that provides a simple jsonrpc client for
communicating with an ethereum jsonrpc node

# Usage

## Extra config

add the following to your config.ini

```
[ethereum]
url=http://localhost:8545
```

## Handler Example

```
from asyncbb.handlers import BaseHandler
from asyncbb.ethereum import EthereumMixin

class Handler(EthereumMixin, BaseHandler):

    async def get(self):

        balance = await self.eth.eth_getBalance("0xde3d2d9dd52ea80f7799ef4791063a5458d13913")
        self.write(str(balance))
```

# Testing

Writing tests for ethereum requires both `parity` and `ethminer` be installed on your system

## Installing parity

https://ethcore.io/parity.html

## Installing ethminer

https://github.com/ethereum/go-ethereum/wiki/Mining#mining-software

## Example test

```
from asyncbb.test.base import AsyncHandlerTest
from asyncbb.ethereum.test.parity import requires_parity
from tornado.testing import gen_test

class EthTest(AsyncHandlerTest):

    def get_urls(self):
        return [(r'^/$', Handler)]

    @gen_test
    @requires_parity
    async def test_jsonrpc_connection(self):

        resp = await self.fetch('/')
        self.assertEqual(resp.body, b'100000000000000000000000000000')
```
