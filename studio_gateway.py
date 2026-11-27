"""Private service-to-service request authentication precursor.

The trusted gateway must independently verify user, membership, permission,
and product entitlement for every request. Never share the signing key with
the browser. This is not an OAuth/OIDC identity provider.
"""
import base64
import binascii
import hashlib
import hmac
import json
import re
import threading
import time
from pathlib import Path
from dataclasses import dataclass

UUID=re.compile(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}")
NONCE=re.compile(r"[a-f0-9]{32}")
B64=re.compile(r"[A-Za-z0-9_-]+")
AUDIENCE="c4pcut-private-v1"
ISSUER="takatak-studio-gateway"
MAX_TTL=30
MAX_NONCES=10000

def decode(value):
    if not B64.fullmatch(value):
        raise ValueError("Invalid encoding")
    raw=base64.urlsafe_b64decode(value+"="*(-len(value)%4))
    if base64.urlsafe_b64encode(raw).decode().rstrip("=")!=value:
        raise ValueError("Noncanonical encoding")
    return raw

@dataclass(frozen=True)
class Principal:
    client_id: str
    profile_id: str
    workspace: str

class Gateway:
    def __init__(self,key,mapping,registry,clock=time.time):
        if not isinstance(key,bytes) or len(key)!=32:
            raise ValueError("Gateway signing key must be 32 random bytes")
        if not isinstance(mapping,dict) or not 1<=len(mapping)<=len(registry):
            raise ValueError("Invalid gateway workspace mapping")
        if any(not isinstance(client,str) or not UUID.fullmatch(client) or not isinstance(slug,str) or slug not in registry for client,slug in mapping.items()):
            raise ValueError("Unknown client or workspace mapping")
        if len(set(mapping.values()))!=len(mapping):
            raise ValueError("Workspace mappings must be one-to-one")
        self.key=key
        self.mapping=dict(mapping)
        self.clock=clock
        self.seen={}
        self.lock=threading.Lock()

    def verify(self,header,method,target):
        # Verify signature before parsing untrusted claims. The exact signed
        # request target includes any query string. Never normalize it here.
        try:
            if not isinstance(header,str) or len(header)>4096:
                return None
            encoded,signature=header.split(".")
            raw=decode(encoded)
            sig=decode(signature)
            expected=hmac.digest(self.key,encoded.encode("ascii"),"sha256")
            if not hmac.compare_digest(expected,sig):
                return None
            c=json.loads(raw)
            keys={"iss","aud","sub","client_id","permission","entitlement","iat","exp","nonce","method","target"}
            if not isinstance(c,dict) or set(c)!=keys:
                return None
            if c["iss"]!=ISSUER or c["aud"]!=AUDIENCE or c["permission"]!="create_content" or c["entitlement"]!="c4pcut_active":
                return None
            if not isinstance(c["sub"],str) or not UUID.fullmatch(c["sub"]) or not isinstance(c["client_id"],str) or c["client_id"] not in self.mapping:
                return None
            if method not in {"GET","POST"} or c["method"]!=method or c["target"]!=target:
                return None
            if not isinstance(c["nonce"],str) or not NONCE.fullmatch(c["nonce"]):
                return None
            iat,exp=c["iat"],c["exp"]
            now=self.clock()
            if type(iat) is not int or type(exp) is not int or not iat<=now<exp or not 0<exp-iat<=MAX_TTL:
                return None
            with self.lock:
                # Fail closed when capacity is exhausted, never evict a live nonce.
                self.seen={nonce:end for nonce,end in self.seen.items() if end>now}
                if c["nonce"] in self.seen or len(self.seen)>=MAX_NONCES:
                    return None
                self.seen[c["nonce"]]=exp
            return Principal(c["client_id"],c["sub"],self.mapping[c["client_id"]])
        except (ValueError,TypeError,KeyError,UnicodeError,binascii.Error):
            return None

def load(config,key_file,registry):
    path=Path(config)
    secret=Path(key_file)
    if not path.is_file() or path.stat().st_size>16384 or not secret.is_file() or secret.stat().st_size>128:
        raise ValueError("Invalid gateway configuration")
    value=secret.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[a-f0-9]{64}",value):
        raise ValueError("Gateway key must be 64 lowercase hexadecimal digits")
    return Gateway(bytes.fromhex(value),json.loads(path.read_text(encoding="utf-8")),registry)
