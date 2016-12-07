from .client import JsonRPCClient

def prepare_ethereum_jsonrpc_client(config):
    if 'url' in config:
        url = config['url']
    elif 'host' in config:
        ssl = config.get('ssl', 'false')
        if ssl is True or (isinstance(ssl, str) and ssl.lower() == 'true'):
            protocol = 'https://'
        else:
            protocol = 'http://'
        port = config.get('port', '8545')
        host = config.get('host', 'localhost')
        path = config.get('path', '/')
        if not path.startswith('/'):
            path = "/{}".format(path)

        url = "{}{}:{}{}".format(protocol, host, port, path)
    return JsonRPCClient(url)
