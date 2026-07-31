"""HTTP digest authentication helper for aiohttp.

Based on https://github.com/requests/requests/blob/v2.18.4/requests/auth.py
Rewritten to be safe for concurrent requests: the original implementation
stored the request arguments on the instance (self.args), which caused
wrong retries when multiple requests were in flight at the same time.
"""

import hashlib
import os
import time

from aiohttp import client_exceptions
from yarl import URL


def parse_pair(pair):
    """Ein Schlüssel-Wert-Paar aus dem Digest-Header zerlegen."""
    key, value = pair.split("=", 1)
    if value[-1] == ",":
        value = value[:-1]
    if value[0] == value[-1] == '"':
        value = value[1:-1]
    return key, value


def parse_key_value_list(header):
    """Digest-Header in ein Wörterbuch überführen."""
    return {
        key: value for key, value in [parse_pair(header_pair) for header_pair in header.split(" ")]
    }


class DigestAuth:
    """HTTP digest authentication helper (concurrency-safe)."""

    def __init__(self, username, password, session):
        self.username = username
        self.password = password
        self.session = session
        self.last_nonce = ""
        self.nonce_count = 0
        self.challenge = None

    async def request(self, method, url, *, headers=None, retry=True, **kwargs):
        headers = {} if headers is None else dict(headers)

        if self.challenge:
            headers["Authorization"] = self._build_digest_header(method.upper(), url)

        response = await self.session.request(method, url, headers=headers, **kwargs)

        if 400 <= response.status < 500 and retry:
            auth_header = response.headers.get("www-authenticate", "")
            parts = auth_header.split(" ", 1)
            if parts[0].lower() == "digest" and len(parts) > 1:
                self.challenge = parse_key_value_list(parts[1])
                response.release()
                return await self.request(method, url, headers=headers, retry=False, **kwargs)

        return response

    def _build_digest_header(self, method, url):
        realm = self.challenge["realm"]
        nonce = self.challenge["nonce"]
        qop = self.challenge.get("qop")
        algorithm = self.challenge.get("algorithm", "MD5").upper()
        opaque = self.challenge.get("opaque")

        if qop and not (qop == "auth" or "auth" in qop.split(",")):
            raise client_exceptions.ClientError("Unsupported qop value: %s" % qop)

        if algorithm in ("MD5", "MD5-SESS"):
            hash_fn = hashlib.md5
        elif algorithm == "SHA":
            hash_fn = hashlib.sha1
        else:
            return ""

        def H(x):
            return hash_fn(x.encode()).hexdigest()

        def KD(s, d):
            return H("%s:%s" % (s, d))

        path = URL(url).path_qs
        HA1 = H("%s:%s:%s" % (self.username, realm, self.password))
        HA2 = H("%s:%s" % (method, path))

        # NOTE: no await between read and write -> atomic within the event loop
        if nonce == self.last_nonce:
            self.nonce_count += 1
        else:
            self.nonce_count = 1
        self.last_nonce = nonce
        ncvalue = "%08x" % self.nonce_count

        cnonce_data = "".join(
            [
                str(self.nonce_count),
                nonce,
                time.ctime(),
                os.urandom(8).decode(errors="ignore"),
            ]
        ).encode()
        cnonce = hashlib.sha1(cnonce_data).hexdigest()[:16]

        if algorithm == "MD5-SESS":
            HA1 = H("%s:%s:%s" % (HA1, nonce, cnonce))

        if qop:
            noncebit = ":".join([nonce, ncvalue, cnonce, "auth", HA2])
            response_digest = KD(HA1, noncebit)
        else:
            response_digest = KD(HA1, "%s:%s" % (nonce, HA2))

        base = ", ".join(
            [
                'username="%s"' % self.username,
                'realm="%s"' % realm,
                'nonce="%s"' % nonce,
                'uri="%s"' % path,
                'response="%s"' % response_digest,
                'algorithm="%s"' % algorithm,
            ]
        )
        if opaque:
            base += ', opaque="%s"' % opaque
        if qop:
            base += ', qop="auth", nc=%s, cnonce="%s"' % (ncvalue, cnonce)

        return "Digest %s" % base
