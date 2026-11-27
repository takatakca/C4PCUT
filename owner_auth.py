"""Optional owner-only access for the private SSH-tunnel deployment.

Not a multi-tenant account system. Basic authentication must never be
transmitted across an untrusted plaintext network.
"""
import base64
import binascii
import hmac
import hashlib

def password_digest(password):
    if not isinstance(password,str) or len(password)<24 or len(password.encode("utf-8"))>256 or any(ord(c)<32 for c in password):
        raise ValueError("Owner password must contain 24–256 bytes and no control characters")
    return hashlib.sha256(password.encode("utf-8")).digest()

def parse_basic(header):
    if not isinstance(header,str) or len(header)>1024:
        return None
    scheme, sep, encoded=header.partition(" ")
    if not sep or scheme.lower()!="basic":
        return None
    try:
        raw=base64.b64decode(encoded,validate=True)
    except (ValueError,binascii.Error):
        return None
    user, sep, password=raw.partition(b":")
    if not sep:
        return None
    return user,password

def authorized(header, expected_digest, expected_user=b"owner"):
    if expected_digest is None:
        return True
    parsed=parse_basic(header)
    if parsed is None:
        return False
    user,password=parsed
    user_ok=hmac.compare_digest(user,expected_user)
    secret_ok=hmac.compare_digest(hashlib.sha256(password).digest(),expected_digest)
    return user_ok and secret_ok

def allowed_origin(origin, host, fetch_site=None):
    # Non-browser clients can omit Origin but still need authorization and CSRF token.
    return fetch_site not in {"cross-site","same-site"} and (origin is None or origin=="http://"+host)
