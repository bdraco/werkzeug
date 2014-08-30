# -*- coding: utf-8 -*-
"""
    tests.serving
    ~~~~~~~~~~~~~

    Added serving tests.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import os
import ssl
import textwrap

try:
    import httplib
except ImportError:
    from http import client as httplib
try:
    from urllib2 import urlopen, HTTPError
except ImportError:  # pragma: no cover
    from urllib.request import urlopen
    from urllib.error import HTTPError

try:
    import OpenSSL
except ImportError:
    OpenSSL = None


import pytest

from werkzeug import __version__ as version, serving


def test_serving(dev_server):
    server, addr = dev_server('from werkzeug.testapp import test_app as app')
    rv = urlopen('http://%s/?foo=bar&baz=blah' % addr).read()
    assert b'WSGI Information' in rv
    assert b'foo=bar&amp;baz=blah' in rv
    assert b'Werkzeug/' + version.encode('ascii') in rv


def test_broken_app(dev_server):
    server, addr = dev_server('''
    def app(environ, start_response):
        1 // 0
    ''')

    with pytest.raises(HTTPError) as excinfo:
        urlopen('http://%s/?foo=bar&baz=blah' % addr).read()

    rv = excinfo.value.read()
    assert b'Internal Server Error' in rv


def test_absolute_requests(dev_server):
    server, addr = dev_server('''
    def app(environ, start_response):
        assert environ['HTTP_HOST'] == 'surelynotexisting.example.com:1337'
        assert environ['PATH_INFO'] == '/index.htm'
        addr = environ['HTTP_X_WERKZEUG_ADDR']
        assert environ['SERVER_PORT'] == addr.split(':')[1]
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'YES']
    ''')

    conn = httplib.HTTPConnection(addr)
    conn.request('GET', 'http://surelynotexisting.example.com:1337/index.htm',
                 headers={'X-Werkzeug-Addr': addr})
    res = conn.getresponse()
    assert res.read() == b'YES'


@pytest.mark.skipif(not hasattr(ssl, 'SSLContext'),
                    reason='Missing PEP 466 (Python 2.7.9+) or Python 3.')
@pytest.mark.skipif(OpenSSL is None,
                    reason='OpenSSL is required for cert generation.')
def test_stdlib_ssl_contexts(dev_server, tmpdir):
    certificate, private_key = \
        serving.make_ssl_devcert(str(tmpdir.mkdir('certs')))

    server, addr = dev_server('''
    def app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'hello']

    import ssl
    ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ctx.load_cert_chain("%s", "%s")
    kwargs['ssl_context'] = ctx
    ''' % (certificate, private_key))

    assert addr is not None
    connection = httplib.HTTPSConnection(addr)
    connection.request('GET', '/')
    response = connection.getresponse()
    assert response.read() == b'hello'


@pytest.mark.skipif(OpenSSL is None, reason='OpenSSL is not installed.')
def test_ssl_context_adhoc(dev_server):
    server, addr = dev_server('''
    def app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [b'hello']

    kwargs['ssl_context'] = 'adhoc'
    ''')
    assert addr is not None
    connection = httplib.HTTPSConnection(addr)
    connection.request('GET', '/')
    response = connection.getresponse()
    assert response.read() == b'hello'


@pytest.mark.skipif(OpenSSL is None, reason='OpenSSL is not installed.')
def test_make_ssl_devcert(tmpdir):
    certificate, private_key = \
        serving.make_ssl_devcert(str(tmpdir))
    assert os.path.isfile(certificate)
    assert os.path.isfile(private_key)
