from __future__ import annotations
import asyncio, uuid, time
from pathlib import Path
from .netpolicy import validate_public_endpoint
from .config import settings

SHOTS = Path(__file__).resolve().parent.parent / 'browser-artifacts'
SHOTS.mkdir(exist_ok=True)

# Viewport size used for all sessions — UI must match this ratio
VIEWPORT_W = 1280
VIEWPORT_H = 800

class BrowserRuntime:
    def __init__(self):
        self._pw = None
        self._browser = None
        self.sessions = {}
        self.lock = asyncio.Lock()

    async def ready(self):
        try:
            await self._ensure()
            return bool(self._browser and self._browser.is_connected())
        except Exception:
            return False

    async def _ensure(self):
        if self._browser:
            return
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=settings.browser_headless,
            args=['--disable-dev-shm-usage', '--no-sandbox']
        )

    async def start(self, user_id):
        async with self.lock:
            await self._ensure()
            sid = str(uuid.uuid4())
            ctx = await self._browser.new_context(
                viewport={'width': VIEWPORT_W, 'height': VIEWPORT_H},
                accept_downloads=False
            )
            async def guard(route):
                try:
                    validate_public_endpoint(route.request.url)
                    await route.continue_()
                except Exception:
                    await route.abort('blockedbyclient')
            await ctx.route('**/*', guard)
            page = await ctx.new_page()
            self.sessions[sid] = {'user_id': user_id, 'context': ctx, 'page': page}
            return sid

    def get(self, sid, user_id):
        s = self.sessions.get(sid)
        if not s or s['user_id'] != user_id:
            raise KeyError('Browser session not found')
        return s

    async def navigate(self, sid, user_id, url):
        validate_public_endpoint(url)
        p = self.get(sid, user_id)['page']
        response = await p.goto(url, wait_until='domcontentloaded', timeout=30000)
        validate_public_endpoint(p.url)
        return await self.state(sid, user_id, response.status if response else None)

    async def state(self, sid, user_id, status=None):
        p = self.get(sid, user_id)['page']
        body = p.locator('body')
        text = (await body.inner_text())[:30000]
        elements = await p.evaluate("""() => {
            let n = 0;
            const q = 'a,button,input,textarea,select,[role],[contenteditable=true],[tabindex]';
            return [...document.querySelectorAll(q)].filter(e => {
                const r = e.getBoundingClientRect(), s = getComputedStyle(e);
                return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
            }).slice(0, 300).map(e => {
                const ref = 'e' + (++n);
                e.setAttribute('data-tillu-ref', ref);
                const label = e.getAttribute('aria-label') || e.getAttribute('title') || e.innerText || e.value || e.getAttribute('placeholder') || '';
                const r = e.getBoundingClientRect();
                return {
                    ref, tag: e.tagName.toLowerCase(),
                    role: e.getAttribute('role') || null,
                    name: String(label).trim().slice(0, 300),
                    type: e.getAttribute('type'),
                    value: ('value' in e ? String(e.value).slice(0, 300) : null),
                    disabled: !!e.disabled,
                    checked: 'checked' in e ? !!e.checked : null,
                    href: e.href || null,
                    x: Math.round(r.left), y: Math.round(r.top),
                    w: Math.round(r.width), h: Math.round(r.height)
                };
            });
        }""")
        try:
            accessibility = (await body.aria_snapshot(timeout=5000))[:30000]
        except Exception:
            accessibility = ''
        return {
            'session_id': sid, 'url': p.url, 'title': await p.title(),
            'status': status, 'text': text, 'accessibility': accessibility,
            'elements': elements, 'screen_mode': 'dom_accessibility_no_vision',
            'viewport': {'width': VIEWPORT_W, 'height': VIEWPORT_H}
        }

    async def screenshot_bytes(self, sid, user_id):
        """Return raw PNG bytes of current page — used by MJPEG streamer."""
        p = self.get(sid, user_id)['page']
        return await p.screenshot(type='jpeg', quality=75, full_page=False)

    async def screenshot(self, sid, user_id):
        p = self.get(sid, user_id)['page']
        name = f'{sid}__{uuid.uuid4().hex}.png'
        await p.screenshot(path=str(SHOTS / name), full_page=False)
        return name

    async def action(self, sid, user_id, action, args):
        p = self.get(sid, user_id)['page']
        selector = str(args.get('selector', ''))[:500]
        if selector.startswith('@'):
            selector = f'[data-tillu-ref="{selector[1:]}"]'
        target = p.locator(selector).first
        if action == 'click':      await target.click(timeout=15000)
        elif action == 'type':     await target.fill(str(args.get('text', ''))[:10000], timeout=15000)
        elif action == 'press':    await target.press(str(args.get('key', 'Enter'))[:50], timeout=15000)
        elif action == 'check':    await target.check(timeout=15000)
        elif action == 'uncheck':  await target.uncheck(timeout=15000)
        elif action == 'select':   await target.select_option(str(args.get('text', ''))[:500], timeout=15000)
        elif action == 'scroll':   await target.scroll_into_view_if_needed(timeout=15000)
        else: raise ValueError('Unsupported browser action')
        await p.wait_for_timeout(300)
        return await self.state(sid, user_id)

    async def mouse_click(self, sid, user_id, x: int, y: int, button: str = 'left'):
        """Direct mouse click at page coordinates."""
        p = self.get(sid, user_id)['page']
        await p.mouse.click(x, y, button=button)
        await p.wait_for_timeout(200)

    async def go_back(self, sid, user_id):
        p = self.get(sid, user_id)['page']
        try:
            await p.go_back(wait_until='domcontentloaded', timeout=15000)
        except Exception:
            pass
        await p.wait_for_timeout(300)
        return await self.state(sid, user_id)

    async def go_forward(self, sid, user_id):
        p = self.get(sid, user_id)['page']
        try:
            await p.go_forward(wait_until='domcontentloaded', timeout=15000)
        except Exception:
            pass
        await p.wait_for_timeout(300)
        return await self.state(sid, user_id)

    async def reload(self, sid, user_id):
        p = self.get(sid, user_id)['page']
        await p.reload(wait_until='domcontentloaded', timeout=30000)
        return await self.state(sid, user_id)

    async def mouse_move(self, sid, user_id, x: int, y: int):
        p = self.get(sid, user_id)['page']
        await p.mouse.move(x, y)

    async def mouse_scroll(self, sid, user_id, x: int, y: int, delta_x: int, delta_y: int):
        p = self.get(sid, user_id)['page']
        await p.mouse.wheel(delta_x, delta_y)

    async def keyboard_type(self, sid, user_id, text: str):
        p = self.get(sid, user_id)['page']
        await p.keyboard.type(text[:500])

    async def keyboard_press(self, sid, user_id, key: str):
        p = self.get(sid, user_id)['page']
        await p.keyboard.press(key[:50])

    async def stream_mjpeg(self, sid, user_id, fps: int = 10):
        """Async generator that yields MJPEG multipart frames."""
        interval = 1.0 / max(1, min(fps, 30))
        boundary = b'--tilluframe'
        while sid in self.sessions and self.sessions[sid]['user_id'] == user_id:
            try:
                data = await self.screenshot_bytes(sid, user_id)
                header = (
                    boundary + b'\r\n'
                    b'Content-Type: image/jpeg\r\n'
                    b'Content-Length: ' + str(len(data)).encode() + b'\r\n\r\n'
                )
                yield header + data + b'\r\n'
            except Exception:
                break
            await asyncio.sleep(interval)

    async def close(self, sid, user_id):
        s = self.get(sid, user_id)
        await s['context'].close()
        self.sessions.pop(sid, None)


browser_runtime = BrowserRuntime()
