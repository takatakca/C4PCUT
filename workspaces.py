"""Private, explicitly provisioned workspace boundary. No public SSO."""
import json
import re
import secrets
from pathlib import Path
from dataclasses import dataclass, field
import owner_auth
import usage

SLUG=re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
DIGEST=re.compile(r"[a-f0-9]{64}")
MAX_WORKSPACES=8

@dataclass
class Workspace:
    slug: str
    storage: Path
    digest: bytes
    ledger: usage.Ledger
    token: str=field(default_factory=lambda:secrets.token_urlsafe(32))
    jobs: dict=field(default_factory=dict)

def load(config, storage):
    """Read administrator-provisioned SHA-256 digests of high-entropy passwords.
    Workspace slugs cannot choose paths or override the trusted storage root.
    """
    path=Path(config)
    if not path.is_file() or path.stat().st_size>32768:
        raise ValueError("Invalid workspace configuration")
    records=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records,dict) or not 1<=len(records)<=MAX_WORKSPACES:
        raise ValueError("Configure 1–8 private workspaces")
    validated=[]
    for slug,record in records.items():
        if not isinstance(slug,str) or not SLUG.fullmatch(slug) or slug=="owner":
            raise ValueError("Invalid workspace slug")
        if not isinstance(record,dict) or set(record)-{"password_sha256","monthly_render_seconds"}:
            raise ValueError("Invalid workspace record")
        digest=record.get("password_sha256")
        if not isinstance(digest,str) or not DIGEST.fullmatch(digest):
            raise ValueError("Workspace requires a password digest")
        limit=record.get("monthly_render_seconds")
        if limit is not None and (type(limit) is not int or not 0<=limit<=999999999):
            raise ValueError("Invalid workspace quota")
        validated.append((slug,bytes.fromhex(digest),limit))
    root=Path(storage)/"workspaces"
    if root.is_symlink():
        raise ValueError("Unsafe workspace root")
    root.mkdir(mode=0o700,exist_ok=True)
    result={}
    for slug,digest,limit in validated:
        folder=root/slug
        if folder.is_symlink():
            raise ValueError("Unsafe workspace directory")
        folder.mkdir(mode=0o700,exist_ok=True)
        result[slug]=Workspace(slug,folder,digest,usage.Ledger(folder,limit))
    return result

def authenticate(header, registry):
    parsed=owner_auth.parse_basic(header)
    if parsed is None:
        return None
    user,_=parsed
    try:
        slug=user.decode("ascii")
    except UnicodeError:
        return None
    workspace=registry.get(slug)
    if workspace and owner_auth.authorized(header,workspace.digest,user):
        return workspace
    return None
