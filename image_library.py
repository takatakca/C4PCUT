"""Project-local normalized PNG library, independent of the saved edit revision."""
import hashlib
import os
import re
import shutil
import tempfile
from pathlib import Path
import logos

MAX_IMAGES=8
MAX_TOTAL_BYTES=16*1024*1024
MAX_IMAGE_BYTES=5*1024*1024
ID=re.compile(r"[a-f0-9]{64}")

def root(job,create=False):
    folder=Path(job["folder"])/"image-library"
    if folder.is_symlink():raise ValueError("Invalid image library")
    if create:folder.mkdir(exist_ok=True)
    if folder.exists() and not folder.is_dir():raise ValueError("Invalid image library")
    return folder

def inventory(job):
    folder=root(job)
    result=[]
    if not folder.exists():return result
    for path in sorted(folder.iterdir()):
        if path.suffix!=".png" or not ID.fullmatch(path.stem):continue
        if path.is_symlink() or not path.is_file():raise ValueError("Invalid library asset")
        size=path.stat().st_size
        if not 0<size<=MAX_IMAGE_BYTES:raise ValueError("Invalid library asset size")
        width,height=logos.dimensions(path)
        result.append({"id":path.stem,"bytes":size,"width":width,"height":height})
        if len(result)>MAX_IMAGES or sum(x["bytes"] for x in result)>MAX_TOTAL_BYTES:
            raise ValueError("Library exceeds storage limits")
    return result

def copy_atomic(source,target):
    if target.is_symlink():raise ValueError("Invalid destination")
    with tempfile.NamedTemporaryFile(dir=target.parent,prefix=".image-",delete=False) as tmp:
        pending=Path(tmp.name)
        try:
            with source.open("rb") as inp:shutil.copyfileobj(inp,tmp)
            tmp.flush();os.fsync(tmp.fileno())
        except Exception:
            pending.unlink(missing_ok=True);raise
    try:pending.replace(target)
    finally:pending.unlink(missing_ok=True)

def archive(job):
    source=Path(job["folder"])/"logo.png"
    if source.is_symlink() or not source.is_file():raise ValueError("Import a PNG logo first")
    size=source.stat().st_size
    if not 0<size<=MAX_IMAGE_BYTES:raise ValueError("Invalid logo size")
    logos.dimensions(source)
    ident=hashlib.sha256(source.read_bytes()).hexdigest()
    items=inventory(job)
    if any(x["id"]==ident for x in items):return items
    if len(items)>=MAX_IMAGES or sum(x["bytes"] for x in items)+size>MAX_TOTAL_BYTES:
        raise ValueError("Image library limit: 8 PNGs and 16 MiB total")
    target=root(job,True)/(ident+".png")
    copy_atomic(source,target)
    return inventory(job)

def asset(job,ident):
    if not isinstance(ident,str) or not ID.fullmatch(ident):raise ValueError("Invalid image ID")
    path=root(job)/(ident+".png")
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=MAX_IMAGE_BYTES:
        raise ValueError("Image not found")
    logos.dimensions(path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=ident:raise ValueError("Invalid image content")
    return path

def activate(job,ident):
    path=asset(job,ident)
    copy_atomic(path,Path(job["folder"])/"logo.png")

def delete(job,ident):
    asset(job,ident).unlink()
    return inventory(job)
