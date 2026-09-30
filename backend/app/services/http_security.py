from collections import OrderedDict, deque
from time import monotonic
from starlette.responses import JSONResponse

class RequestGuards:
    def __init__(self, app):
        self.app = app
        self.auth_requests = OrderedDict()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        async def reject(code, message):
            await JSONResponse({"detail": message}, status_code=code)(scope, receive, send)
        if scope["path"].startswith("/api/auth/") and scope["method"] == "POST":
            now = monotonic()
            key = (scope.get("client") or ("unknown",))[0]
            while self.auth_requests and next(iter(self.auth_requests.values()))[-1] < now - 60:
                self.auth_requests.popitem(last=False)
            if key not in self.auth_requests and len(self.auth_requests) >= 10_000:
                return await reject(429, "Too many authentication requests. Please retry later.")
            events = self.auth_requests.setdefault(key, deque())
            while events and events[0] < now - 60:
                events.popleft()
            if len(events) >= 20:
                return await reject(429, "Too many authentication requests. Please retry later.")
            events.append(now)
            self.auth_requests.move_to_end(key)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > 64 * 1024:
                return await reject(413, "Request body is too large.")
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()
        await self.app(scope, bounded_receive, send)
