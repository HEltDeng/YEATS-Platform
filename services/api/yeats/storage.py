"""Private blob adapter boundary. Stable keys in DB, never signed URLs."""
from pathlib import Path
from typing import Protocol
from .config import settings

class BlobStore(Protocol):
    def put(self,key:str,data:bytes)->None: ...
    def path(self,key:str)->Path: ...
    def delete(self,key:str)->None: ...

class LocalPrivateStore:
    def path(self,key):
        root=settings.file_root.resolve();p=(root/key).resolve()
        if not key or p==root or not p.is_relative_to(root):raise ValueError('Invalid resource key')
        return p
    def put(self,key,data):
        p=self.path(key);p.parent.mkdir(parents=True,exist_ok=True)
        # Immutable resource identifiers; a retry must not overwrite other data.
        with p.open('xb') as out:out.write(data)
    def delete(self,key):self.path(key).unlink(missing_ok=True)

store:BlobStore=LocalPrivateStore()
