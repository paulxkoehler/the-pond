"""Two-player test for The Pond.

Runs two headless browsers against the game and checks that each duck shows up
on the other screen, follows its movement, and hears its calls and dabbles.

Two connection paths are tested:
  room  - the shared room used when the game is opened inside Claude
          (stood in for here by a small BroadcastChannel mock)
  relay - the pond-name pairing used on Netlify (MQTT relay), against a local
          broker: a third duck joining, separate ponds staying separate,
          leaving and rejoining

Usage:
  pip install playwright && npm i three@0.128.0 mqtt@5.10.1 aedes@0.51.3 aedes-server-factory@0.2.1
  python tests/two_player.py --libs ./node_modules
"""
import argparse, asyncio, http.server, os, subprocess, sys, threading, time
from functools import partial
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MOCK_ROOM = r"""
(() => {
  const id = Math.random().toString(36).slice(2);
  const bc = new BroadcastChannel('mock-room');
  let mine = {}; const others = new Map(); let cb = null;
  const list = () => [
    {peer:id,by:null,isMe:true,sameTab:true,kind:'viewer',guest:false,presence:mine,updatedAt:Date.now()},
    ...[...others].map(([p,pr]) => ({peer:p,by:'u_'+p,isMe:false,sameTab:false,kind:'viewer',guest:false,presence:pr,updatedAt:Date.now()}))
  ];
  const fire = () => { if (cb) cb({peers:list(),joined:[],left:[],updated:[]}); };
  bc.onmessage = e => { const m = e.data;
    if (m.t === 'p') { others.set(m.id, m.pr); fire(); }
    else if (m.t === 'bye') { others.delete(m.id); fire(); }
    else if (m.t === 'hello') bc.postMessage({t:'p', id, pr:mine}); };
  addEventListener('pagehide', () => bc.postMessage({t:'bye', id}));
  const room = {
    presence: async patch => { mine = Object.assign({}, mine, patch); bc.postMessage({t:'p', id, pr:mine}); },
    peers: list, onPeers: f => { cb = f; setTimeout(fire, 0); return () => { cb = null; }; },
    join: async () => room, emit: async () => {}, on: () => () => {}, connected: () => true };
  bc.postMessage({t:'hello'});
  window.claude = { use: async n => n === 'room' ? room
    : n === 'user' ? { profiles: async ids => Object.fromEntries(ids.map(i => [i, {name:'Jess Tester'}])) } : null };
})();
"""

results = []
def check(name, ok, detail=''):
    results.append((name, ok))
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else ''))

async def wait_for(fn, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        v = await fn()
        if v: return v
        await asyncio.sleep(0.25)
    return await fn()

async def new_ctx(browser, libs, mock):
    ctx = await browser.new_context(viewport={'width': 900, 'height': 600})
    if mock: await ctx.add_init_script(MOCK_ROOM)
    await ctx.route('**/three.min.js', lambda r: r.fulfill(path=os.path.join(libs, 'three/build/three.min.js'), content_type='text/javascript'))
    await ctx.route('**/mqtt.min.js', lambda r: r.fulfill(path=os.path.join(libs, 'mqtt/dist/mqtt.min.js'), content_type='text/javascript'))
    await ctx.route('https://fonts.**', lambda r: r.abort())
    return ctx

async def open_duck(browser, url, libs, sex, mock, errors, label, ctx=None):
    # room mode: the mock room relays between pages of ONE browser session, so pass a shared ctx
    ctx = ctx or await new_ctx(browser, libs, mock)
    pg = await ctx.new_page()
    pg.on('pageerror', lambda e: errors.append(f'{label}: {e}'))
    await pg.goto(url, wait_until='domcontentloaded', timeout=60000)
    await pg.wait_for_timeout(600)  # tap in early on purpose: pairing must still start
    await pg.click('#optHen' if sex == 'hen' else '#optDrake')
    await pg.click('#enter')
    return pg

async def run_pair(browser, url, libs, mode, errors):
    mock = mode == 'room'
    shared = await new_ctx(browser, libs, True) if mock else None
    a = await open_duck(browser, url, libs, 'drake', mock, errors, f'{mode}-A', shared)
    b = await open_duck(browser, url, libs, 'hen', mock, errors, f'{mode}-B', shared)
    rem = lambda p: p.evaluate('window.__pond.remotes()')
    ok = await wait_for(lambda: _both(a, b), 20)
    check(f'[{mode}] each duck sees the other', bool(ok), f"A state={await a.evaluate('window.__pond.state()')} B state={await b.evaluate('window.__pond.state()')}")
    if not ok: return a, b
    ra, rb = await rem(a), await rem(b)
    check(f'[{mode}] drake sees a hen, hen sees a drake', ra[0]['sex'] == 'hen' and rb[0]['sex'] == 'drake')

    await a.keyboard.down('w'); await a.wait_for_timeout(2200); await a.keyboard.up('w'); await a.wait_for_timeout(1500)
    me = await a.evaluate('(()=>{const m=window.__pond.me();return {x:m.x,z:m.z}})()')
    r = (await rem(b))[0]
    dist = ((me['x'] - r['x'])**2 + (me['z'] - r['z'])**2) ** .5
    check(f'[{mode}] movement shows up on the other screen', dist < 0.35, f'gap {dist:.2f}m')

    before = (await rem(b))[0]['callN']
    await a.keyboard.press('q')
    called = await wait_for(lambda: _gt(b, 'callN', before), 5)
    check(f'[{mode}] call is heard', bool(called))

    await b.keyboard.press(' ')
    dabble = await wait_for(lambda: _act(a, 'dabble'), 5)
    check(f'[{mode}] dabble plays on the other screen', bool(dabble))
    return a, b


JS_TELEPORT = """([x,z]) => { const m = window.__pond.me(); m.x = x; m.z = z; m.spd = 0; m.hop = null; m.perch = -1; m.yS = null; }"""
JS_SHORE_POINT = """(target) => { const P = window.__pond; // walk out from the pond centre at angle 0.9 until edgeD == target
  let lo = 20, hi = 150; for (let i = 0; i < 40; i++) { const r = (lo + hi) / 2, d = P.edgeD(Math.cos(.9)*r, Math.sin(.9)*r); if (d < target) lo = r; else hi = r; }
  return [Math.cos(.9)*lo, Math.sin(.9)*lo]; }"""

async def wait_game(p, secs, timeout=90):
    """Wait for `secs` of in-game time. Software-rendered test browsers can run at a few frames a second,
    and the game caps each frame's step, so wall-clock waits undercount badly."""
    t0 = await p.evaluate('window.__pond.t()'); end = time.time() + timeout
    while time.time() < end and (await p.evaluate('window.__pond.t()')) - t0 < secs:
        await asyncio.sleep(0.1)

async def run_extras(a, b, mode):
    await a.bring_to_front()
    me = lambda p: p.evaluate('(()=>{const m=window.__pond.me();return {x:m.x,z:m.z,y:m.g.position.y,perch:m.perch,onLand:m.onLand,hop:!!m.hop}})()')
    # steering: right key moves along the camera's right vector, left key the other way
    for key, sign, label in (('d', 1, 'right'), ('a', -1, 'left')):
        await a.evaluate(JS_TELEPORT, [0, 0]); await wait_game(a, 1.2)
        cr = await a.evaluate('window.__pond.camRight()'); p0 = await me(a)
        await a.keyboard.down(key); await wait_game(a, 1.1); await a.keyboard.up(key)
        p1 = await me(a); side = (p1['x'] - p0['x']) * cr['x'] + (p1['z'] - p0['z']) * cr['z']
        check(f'[{mode}] {label} key moves the duck to screen-{label}', side * sign > 0.15, f'{side:+.2f} m along camera right')
    # shore: a duck 2 m up the bank stands on land; one dropped 12 m inland is pulled back
    pt = await a.evaluate(JS_SHORE_POINT, 2.0); await a.evaluate(JS_TELEPORT, pt); await wait_game(a, 0.7)
    m = await me(a); gh = await a.evaluate('([x,z])=>window.__pond.terrainH(x,z)', [m['x'], m['z']])
    check(f'[{mode}] duck can stand on the shore', m['onLand'] and m['y'] > gh + 0.15, f"onLand={m['onLand']} y={m['y']:.2f} ground={gh:.2f}")
    pt = await a.evaluate(JS_SHORE_POINT, 12.0); await a.evaluate(JS_TELEPORT, pt); await wait_game(a, 0.4)
    m = await me(a); d = await a.evaluate('([x,z])=>window.__pond.edgeD(x,z)', [m['x'], m['z']])
    check(f'[{mode}] duck stays within a few metres of the water', d <= 4.6, f'{d:.2f} m past the waterline')
    # perch on the log, partner sees it, hop down
    log = (await a.evaluate('window.__pond.perches()'))[0]
    mx, mz = (log['a']['x'] + log['b']['x']) / 2, (log['a']['z'] + log['b']['z']) / 2
    await a.evaluate(JS_TELEPORT, [mx + 1.0, mz]); await wait_game(a, 0.5)
    await a.keyboard.press('e'); await wait_game(a, 1.6)
    m = await me(a)
    check(f'[{mode}] perch: hops up onto the log', m['perch'] == 0 and m['y'] > 0.5, f"perch={m['perch']} y={m['y']:.2f}")
    seen = await wait_for(lambda: _perched(b, 0), 6)
    check(f'[{mode}] partner sees you up on the perch', bool(seen))
    await a.keyboard.down('w'); await wait_game(a, 0.9); await a.keyboard.up('w'); await wait_game(a, 0.8)
    m = await me(a)
    check(f'[{mode}] pushing to swim hops back down', m['perch'] == -1 and not m['hop'], f"perch={m['perch']}")
    # the high one: nest box roof
    box = (await a.evaluate('window.__pond.perches()'))[4]
    await a.evaluate(JS_TELEPORT, [box['a']['x'] - 1.2, box['a']['z']]); await wait_game(a, 0.5)
    await a.keyboard.press('e'); await wait_game(a, 2.2)
    m = await me(a)
    check(f'[{mode}] perch: flies up onto the nest box', m['perch'] == 4 and m['y'] > box['a']['y'], f"y={m['y']:.2f} roof={box['a']['y']:.2f}")
    await a.keyboard.press('e'); await wait_game(a, 1.8)

async def _perched(p, idx):
    r = await p.evaluate('window.__pond.remotes()')
    return r and r[0]['perch'] == idx and r[0]['y'] > 0.45

async def _both(a, b):
    return len(await a.evaluate('window.__pond.remotes()')) == 1 and len(await b.evaluate('window.__pond.remotes()')) == 1

async def _gt(p, key, before):
    r = await p.evaluate('window.__pond.remotes()')
    return r and r[0][key] is not None and r[0][key] != before

async def _act(p, act):
    r = await p.evaluate('window.__pond.remotes()')
    return r and r[0]['act'] == act

async def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--libs', required=True); ap.add_argument('--chrome', default='/usr/bin/google-chrome')
    args = ap.parse_args(); libs = os.path.abspath(args.libs)

    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8765), partial(http.server.SimpleHTTPRequestHandler, directory=ROOT))
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    relay = subprocess.Popen(['node', os.path.join(ROOT, 'tests/local_relay.js'), '8899'], env={**os.environ, 'NODE_PATH': libs}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(2)

    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=args.chrome, args=[
            '--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist',
            '--autoplay-policy=no-user-gesture-required'])

        # inside Claude
        a, b = await run_pair(browser, 'http://127.0.0.1:8765/index.html', libs, 'room', errors)
        await run_extras(a, b, 'room')
        await b.close(run_before_unload=True)
        gone = await wait_for(lambda: _none(a), 8)
        check('[room] partner leaving clears their duck', bool(gone))
        await a.context.close()

        # Netlify path
        url = 'http://127.0.0.1:8765/index.html?relay=ws://127.0.0.1:8899&pond=test-pond'
        a, b = await run_pair(browser, url, libs, 'relay', errors)
        await run_extras(a, b, 'relay')
        c = await open_duck(browser, url, libs, 'drake', False, errors, 'relay-C')
        three = await wait_for(lambda: _count(c, 2), 60)
        check('[relay] a third duck joining sees both others', bool(three))
        d = await open_duck(browser, url.replace('test-pond', 'other-pond'), libs, 'hen', False, errors, 'relay-D')
        await d.wait_for_timeout(4000)
        check('[relay] a different pond name stays separate', await _count(d, 0) and await _count(a, 2))
        await c.context.close(); await d.context.close()
        await b.context.close()
        gone = await wait_for(lambda: _none(a), 15)
        check('[relay] partner leaving clears their duck', bool(gone))
        b2 = await open_duck(browser, url, libs, 'hen', False, errors, 'relay-B2')
        back = await wait_for(lambda: _one(a), 20)
        check('[relay] partner can rejoin the same pond', bool(back))
        await browser.close()

    relay.terminate(); srv.shutdown()
    check('no script errors on any page', not errors, '; '.join(errors[:3]))
    failed = [n for n, ok in results if not ok]
    print(f'\n{len(results) - len(failed)}/{len(results)} passed')
    sys.exit(1 if failed else 0)

async def _none(p): return len(await p.evaluate('window.__pond.remotes()')) == 0
async def _one(p): return len(await p.evaluate('window.__pond.remotes()')) == 1
async def _state(p, s): return (await p.evaluate('window.__pond.state()')) == s
async def _count(p, n): return len(await p.evaluate('window.__pond.remotes()')) == n

asyncio.run(main())
