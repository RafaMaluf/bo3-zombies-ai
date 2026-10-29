const test = require('node:test');
const assert = require('node:assert/strict');
const {install, focusInput} = require('../../frontend/viewport.js');

function target(fields = {}) {
  const events = new Map();
  return Object.assign(fields, {
    addEventListener(name, handler) { events.set(name, handler); },
    removeEventListener(name) { events.delete(name); },
    emit(name, event = {}) { events.get(name)?.(event); },
  });
}
function fixture(withVisualViewport = true) {
  let id = 0;
  let now = 0;
  const frames = new Map();
  const props = new Map();
  const viewport = target({height: 740, offsetTop: 0, scale: 1});
  const win = target({innerHeight: 800,
    performance: {now: () => now},
    visualViewport: withVisualViewport ? viewport : undefined,
    requestAnimationFrame(fn) { frames.set(++id, fn); return id; },
    cancelAnimationFrame(id) { frames.delete(id); },
  });
  const doc = target({hidden:false, documentElement: {style: {setProperty(k, v) { props.set(k, v); }}}});
  const stop = install(win, doc);
  const flush = (elapsed = 16) => {
    now += elapsed;
    const pending = [...frames.values()]; frames.clear(); pending.forEach(fn => fn(now));
  };
  return {win, doc, viewport, props, frames, stop, flush};
}

test('keyboard opening, visual panning and closing keep the shell in the visible area', () => {
  const f = fixture();
  assert.equal(f.props.get('--app-height'), '740px');
  f.viewport.height = 380;
  f.viewport.emit('resize');
  f.viewport.offsetTop = 220;
  f.viewport.emit('scroll');
  assert.equal(f.frames.size, 1); // one bounded observer, even after an event burst
  f.flush();
  assert.equal(f.props.get('--app-height'), '380px');
  assert.equal(f.props.get('--app-top'), '220px');
  // Safari can pan without another resize (caret movement / keyboard toolbar).
  f.viewport.offsetTop = 90;
  f.viewport.emit('scroll'); f.flush();
  assert.equal(f.props.get('--app-top'), '90px');
  f.viewport.height = 740; f.viewport.offsetTop = 0;
  f.viewport.emit('resize'); f.flush();
  assert.equal(f.props.get('--app-height'), '740px');
  assert.equal(f.props.get('--app-top'), '0px');
});

test('rotation and back/forward restoration update geometry without a focus event', () => {
  const f = fixture();
  f.viewport.height = 320;
  f.win.emit('resize'); f.flush();
  assert.equal(f.props.get('--app-height'), '320px');
  f.viewport.height = 740;
  f.win.emit('pageshow'); f.flush();
  assert.equal(f.props.get('--app-height'), '740px');
});

test('pinch zoom preserves layout, then resumes tracking at normal scale', () => {
  const f = fixture();
  f.viewport.scale = 2; f.viewport.height = 370; f.viewport.offsetTop = 120;
  f.viewport.emit('resize'); f.flush();
  assert.equal(f.props.get('--app-height'), '740px');
  assert.equal(f.props.get('--app-top'), '0px');
  f.viewport.scale = 1; f.viewport.height = 740; f.viewport.offsetTop = 0;
  f.viewport.emit('scroll'); f.flush();
  assert.equal(f.props.get('--app-top'), '0px');
});

test('fallback without VisualViewport and disposal do not leave callbacks running', () => {
  const f = fixture(false);
  assert.equal(f.props.get('--app-height'), '800px');
  f.win.innerHeight = 400; f.win.emit('resize'); f.flush();
  assert.equal(f.props.get('--app-height'), '400px');
  f.win.emit('resize'); f.stop();
  assert.equal(f.frames.size, 0);
  f.win.emit('resize');
  assert.equal(f.frames.size, 0);
});

test('only a fine pointer with hover may automatically focus the input', () => {
  const calls = [];
  const input = {focus(options) { calls.push(options); }};
  focusInput(input, {matchMedia: () => ({matches: false})});
  focusInput(input, {});
  assert.equal(calls.length, 0);
  focusInput(input, {matchMedia: () => ({matches: true})});
  assert.deepEqual(calls, [{preventScroll: true}]);
});

test('focus tracks changing geometry before a delayed viewport event, then stops reading', () => {
  const f = fixture();
  f.doc.emit('focusin', {target:{tagName:'TEXTAREA'}});
  f.viewport.height = 600;
  f.flush();
  assert.equal(f.props.get('--app-height'), '600px');
  f.viewport.height = 380; f.viewport.offsetTop = 80;
  f.flush();
  assert.equal(f.props.get('--app-height'), '380px');
  assert.equal(f.props.get('--app-top'), '80px');
  for (let i=0; i<40; i++) f.flush();
  assert.equal(f.frames.size, 0); // no permanent animation/polling loop
  f.doc.emit('focusout', {target:{tagName:'TEXTAREA'}});
  f.viewport.height = 740; f.viewport.offsetTop = 0;
  f.flush();
  assert.equal(f.props.get('--app-height'), '740px');
  assert.equal(f.props.get('--app-top'), '0px');
  f.stop();
  assert.equal(f.frames.size, 0);
});

test('resize/scroll geometry is applied in the event, without another animation frame', () => {
  const f = fixture();
  f.viewport.height = 380; f.viewport.offsetTop = 80;
  f.viewport.emit('resize');
  assert.equal(f.props.get('--app-height'), '380px');
  assert.equal(f.props.get('--app-top'), '80px');
});

test('backgrounding cancels transition observation and ordinary buttons do not start it', () => {
  const f = fixture();
  f.doc.emit('focusin', {target:{tagName:'BUTTON'}});
  assert.equal(f.frames.size, 0);
  f.doc.emit('focusin', {target:{tagName:'INPUT',type:'checkbox'}});
  assert.equal(f.frames.size, 0);
  f.doc.emit('focusin', {target:{tagName:'TEXTAREA'}});
  assert.equal(f.frames.size, 1);
  f.doc.hidden = true; f.doc.emit('visibilitychange');
  assert.equal(f.frames.size, 0);
  f.viewport.height = 600;
  f.doc.hidden = false; f.doc.emit('visibilitychange');
  assert.equal(f.props.get('--app-height'), '600px');
  assert.equal(f.frames.size, 0);
  f.stop();
});
