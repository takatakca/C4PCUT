"""Bounded in-memory single-worker queue for the private editor."""
import secrets
import threading
from collections import deque

class Cancelled(Exception):
    pass

class RenderQueue:
    def __init__(self, capacity=3, retention=24):
        self.capacity=capacity
        self.retention=retention
        self.lock=threading.Lock()
        self.tasks={}
        self.pending=deque()
        self.worker=None
        self.closed=False

    def busy(self):
        with self.lock:
            return any(t["status"] in ("queued","running","cancelling") for t in self.tasks.values())

    def submit(self, project, work):
        with self.lock:
            active=[t for t in self.tasks.values() if t["status"] in ("queued","running","cancelling")]
            if self.closed or len(active)>=self.capacity or any(t["project"]==project for t in active):
                raise ValueError("Render queue full or project already rendering")
            # Existing export URLs refer to the latest export for each project.
            for key,t in list(self.tasks.items()):
                if t["project"]==project and t not in active:
                    del self.tasks[key]
            while len(self.tasks)>=self.retention:
                old=next((k for k,t in self.tasks.items() if t not in active),None)
                if old is None:
                    break
                del self.tasks[old]
            ident=secrets.token_hex(16)
            self.tasks[ident]={"project":project,"status":"queued","progress":0,
                               "cancel":threading.Event(),"work":work,"result":None}
            self.pending.append(ident)
            if self.worker is None:
                self.worker=threading.Thread(target=self._run,daemon=True)
                self.worker.start()
            return ident

    def status(self, ident):
        with self.lock:
            t=self.tasks[ident]
            return {k:t[k] for k in ("status","progress","result")}

    def cancel(self, ident):
        with self.lock:
            t=self.tasks[ident]
            if t["status"]=="queued":
                t["cancel"].set()
                t["status"]="cancelled"
                self.pending.remove(ident)
                t.pop("work",None)
            elif t["status"]=="running":
                t["cancel"].set()
                t["status"]="cancelling"
            return t["status"]

    def _run(self):
        while True:
            with self.lock:
                if not self.pending:
                    self.worker=None
                    return
                ident=self.pending.popleft()
                t=self.tasks[ident]
                t["status"]="running"
            def progress(value):
                with self.lock:
                    t["progress"]=max(t["progress"],min(99,max(0,int(value))))
            try:
                result=t["work"](t["cancel"],progress)
                status="completed"
            except Cancelled:
                result=None
                status="cancelled"
            except Exception:
                result=None
                status="failed"
            with self.lock:
                t["status"]=status
                t["result"]=result
                if status=="completed":
                    t["progress"]=100
                t.pop("work",None)

    def shutdown(self):
        with self.lock:
            self.closed=True
            keys=[k for k,t in self.tasks.items() if t["status"] in ("queued","running")]
            worker=self.worker
        for key in keys:
            self.cancel(key)
        if worker:
            worker.join()
