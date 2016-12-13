import asyncio
import os
import tornado.httpclient
import tornado.escape
import subprocess
import re

from testing.common.database import (
    Database, DatabaseFactory, get_path_of
)
from string import Template

from .faucet import FAUCET_PRIVATE_KEY, FAUCET_ADDRESS

from .ethminer import EthMiner

instantseal_chaintemplate = Template("""{
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


mining_chaintemplate = Template("""{
    "name": "Dev",
    "engine": {
        "Ethash": {
            "params": {
                "gasLimitBoundDivisor": "0x0400",
                "minimumDifficulty": "0x020000",
                "difficultyBoundDivisor": "0x0800",
                "durationLimit": "0x0a",
                "blockReward": "0x4563918244F40000",
                "registrar": "",
                "homesteadTransition": "0x0"
            }
        }
    },
    "params": {
        "accountStartNonce": "0x0100000",
        "maximumExtraDataSize": "0x20",
        "minGasLimit": "0x1388",
        "networkID" : "0x42"
    },
    "genesis": {
        "seal": {
            "ethereum": {
                "nonce": "0x00006d6f7264656e",
                "mixHash": "0x00000000000000000000000000000000000000647572616c65787365646c6578"
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

def write_chain_file(version, fn, author):

    if author.startswith('0x'):
        author = author[2:]

    if version < (1, 5, ):
        chaintemplate = mining_chaintemplate
    else:
        chaintemplate = instantseal_chaintemplate

    with open(fn, 'w') as f:
        f.write(chaintemplate.substitute(author=author))

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

        p = subprocess.Popen([self.parity_server, '-v'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        outs, errs = p.communicate(timeout=15)

        for line in errs.split(b'\n'):
            m = re.match("^\s+version\sParity\/v([0-9.]+).*$", line.decode('utf-8'))
            if m:
                v = tuple(int(i) for i in m.group(1).split('.'))
                break
        else:
            raise Exception("Unable to figure out Parity version")

        self.version = v
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
        write_chain_file(self.version, self.config['chainfile'], self.author)

    def get_server_commandline(self):
        if self.author.startswith("0x"):
            author = self.author[2:]
        else:
            author = self.author
        return [self.parity_server,
                "--no-discovery",
                "--no-ui",
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
            if parity.version < (1, 5, ):
                ethminer = EthMiner(jsonrpc_url=parity.dsn()['url'])

            self._app.config['ethereum'] = parity.dsn()

            f = fn(self, *args, **kwargs)
            if asyncio.iscoroutine(f):
                await f

            if parity.version < (1, 5, ):
                ethminer.stop()
            parity.stop()

        return wrapper

    if func is not None:
        return wrap(func)
    else:
        return wrap
