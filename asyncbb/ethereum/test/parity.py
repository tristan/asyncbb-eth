import asyncio
import os
import tornado.httpclient
import tornado.escape

from testing.common.database import (
    Database, DatabaseFactory, get_path_of
)
from string import Template

chaintemplate = Template("""{
  "name": "GethTranslation",
  "engine": {
    "Ethash": {
      "params": {
        "gasLimitBoundDivisor": "0x400",
        "minimumDifficulty": "0x20000",
        "difficultyBoundDivisor": "0x800",
        "durationLimit": "0xd",
        "blockReward": "0x4563918244F40000",
        "registrar": "0x81a4b044831c4f12ba601adb9274516939e9b8a2",
        "homesteadTransition": 0,
        "eip150Transition": 0,
        "eip155Transition": 0,
        "eip160Transition": 0,
        "eip161abcTransition": 0,
        "eip161dTransition": 0
      }
    }
  },
  "params": {
    "accountStartNonce": "0x0",
    "maximumExtraDataSize": "0x20",
    "minGasLimit": "0x1388",
    "networkID": 0
  },
  "genesis": {
    "seal": {
      "ethereum": {
        "nonce": "0x0000000000000042",
        "mixHash": "0x0000000000000000000000000000000000000000000000000000000000000000"
      }
    },
    "difficulty": "0x400",
    "author": "0x3333333333333333333333333333333333333333",
    "timestamp": "0x0",
    "parentHash": "0x0000000000000000000000000000000000000000000000000000000000000000",
    "extraData": "0x0",
    "gasLimit": "0x8000000"
  },
  "accounts": {
        "$author": {
      "balance": "100000000000000000000000000000"
    }
  }
}""")

chaintemplate2 = Template("""{
    "name": "Development",
    "engine": {
        "InstantSeal": null
    },
    "params": {
        "accountStartNonce": "0x0100000",
        "maximumExtraDataSize": "0x20",
        "minGasLimit": "0x1388",
        "networkID" : "0x2"
    },
    "genesis": {
        "seal": {
            "generic": {
                "fields": 0,
                "rlp": "0x0"
            }
        },
        "difficulty": "0x20000",
        "author": "0x0000000000000000000000000000000000000000",
        "timestamp": "0x00",
        "parentHash": "0x0000000000000000000000000000000000000000000000000000000000000000",
        "extraData": "0x",
        "gasLimit": "0x2fefd8"
    },
    "accounts": {
        "0000000000000000000000000000000000000001": { "balance": "1", "nonce": "1048576", "builtin": { "name": "ecrecover", "pricing": { "linear": { "base": 3000, "word": 0 } } } },
        "0000000000000000000000000000000000000002": { "balance": "1", "nonce": "1048576", "builtin": { "name": "sha256", "pricing": { "linear": { "base": 60, "word": 12 } } } },
        "0000000000000000000000000000000000000003": { "balance": "1", "nonce": "1048576", "builtin": { "name": "ripemd160", "pricing": { "linear": { "base": 600, "word": 120 } } } },
        "0000000000000000000000000000000000000004": { "balance": "1", "nonce": "1048576", "builtin": { "name": "identity", "pricing": { "linear": { "base": 15, "word": 3 } } } },
        "$author": { "balance": "1606938044258990275541962092341162602522202993782792835301376", "nonce": "1048576" }
    }
}""")

FAUCET_PRIVATE_KEY = "0x0164f7c7399f4bb1eafeaae699ebbb12050bc6a50b2836b9ca766068a9d000c0"
FAUCET_ADDRESS = "0xde3d2d9dd52ea80f7799ef4791063a5458d13913"

def write_chain_file(fn, author):

    with open(fn, 'w') as f:
        f.write(chaintemplate2.substitute(author=author))

class ParityServer(Database):

    DEFAULT_SETTINGS = dict(auto_start=2,
                            base_dir=None,
                            parity_server=None,
                            author=FAUCET_ADDRESS,
                            port=None,
                            copy_data_from=None)

    subdirectories = ['data', 'tmp']

    def initialize(self):
        self.parity_server = self.settings.get('parity_server')
        if self.parity_server is None:
            self.parity_server = get_path_of('parity')

        self.config = self.settings.get('parity_conf', {})
        self.config['chainfile'] = os.path.join(self.base_dir, 'chain.json')
        self.author = self.settings.get('author')

    def dsn(self, **kwargs):
        return {'url': "http://localhost:{}/".format(self.config['rpcport'])}

    def get_data_directory(self):
        return os.path.join(self.base_dir, 'data')

    def prestart(self):
        super(ParityServer, self).prestart()
        if 'rpcport' not in self.config:
            self.config['rpcport'] = self.settings['port']

        # write chain file
        write_chain_file(self.config['chainfile'], self.author)

    def get_server_commandline(self):
        if self.author.startswith("0x"):
            author = self.author[2:]
        else:
            author = self.author
        return [self.parity_server,
                "--no-network",
                "--rpcport", str(self.config['rpcport']),
                "--datadir", self.get_data_directory(),
                "--no-color",
                "--chain", self.config['chainfile'],
                "--author", author]

    def is_server_available(self):
        try:
            tornado.httpclient.HTTPClient().fetch(
                self.dsn()['url'],
                method="POST",
                headers={'Content-Type': "application/json"},
                body=tornado.escape.json_encode({
                    "jsonrpc": "2.0",
                    "id": "1234",
                    "method": "POST",
                    "params": ["0x{}".format(self.author), "latest"]
                })
            )
            return True
        except:
            return False

class ParityServerFactory(DatabaseFactory):
    target_class = ParityServer

def requires_parity(func=None):
    """Used to ensure all database connections are returned to the pool
    before finishing the test"""

    def wrap(fn):

        async def wrapper(self, *args, **kwargs):

            parity = ParityServer()

            self._app.config['ethereum'] = parity.dsn()

            f = fn(self, *args, **kwargs)
            if asyncio.iscoroutine(f):
                await f

            parity.stop()

        return wrapper

    if func is not None:
        return wrap(func)
    else:
        return wrap
