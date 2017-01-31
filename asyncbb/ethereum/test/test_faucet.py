from asyncbb.handlers import BaseHandler
from asyncbb.ethereum import EthereumMixin
from asyncbb.test.base import AsyncHandlerTest
from tornado.testing import gen_test

from .parity import requires_parity
from .faucet import FaucetMixin
from .geth import requires_geth

class Handler(EthereumMixin, BaseHandler):

    async def get(self, addr):

        balance = await self.eth.eth_getBalance(addr)
        self.write(str(balance))

class FaucetTest(FaucetMixin, AsyncHandlerTest):

    def get_urls(self):
        return [(r'^/(0x.+)$', Handler)]

    @gen_test(timeout=10)
    @requires_parity
    async def test_parity_faucet_connection(self):

        addr = '0x39bf9e501e61440b4b268d7b2e9aa2458dd201bb'
        val = 761751855997712

        await self.faucet(addr, val)

        resp = await self.fetch('/{}'.format(addr))
        self.assertEqual(resp.body.decode('utf-8'), str(val))

    @gen_test(timeout=10)
    @requires_geth
    async def test_geth_faucet(self):

        addr = '0x39bf9e501e61440b4b268d7b2e9aa2458dd201bb'
        val = 761751855997712

        await self.faucet(addr, val)

        resp = await self.fetch('/{}'.format(addr))
        self.assertEqual(resp.body.decode('utf-8'), str(val))
