const test = require('node:test');
const assert = require('node:assert/strict');
const {install, focusInput} = require('../../frontend/viewport.js');

function target(fields = {}) {
  const events = new Map();
  return Object.assign(fields, {
    addEventListener(name, handler) { events.set(name, handler); },
    removeEventListener(name) { events.delete(name); },
    emit(name) { events.get(name)?.(); },
  });
}
function fixture(withVisualViewport = true) {
  let id = 0;
  const frames = new Map();
  const props = new Map();
  const viewport = target({height: 740, offsetTop: 0, scale: 1});
  const win = target({innerHeight: 800,
    visualViewport: withVisualViewport ? viewport : undefined,
    requestAnimationFrame(fn) { frames.set(++id, fn); return id; },
    cancelAnimationFrame(id) { frames.delete(id); },
  });
  const stop = install(win, {documentElement: {style: {setProperty(k, v) { props.set(k, v); }}}});
  const flush = () => { const pending = [...frames.values()]; frames.clear(); pending.forEach(fn => fn()); };
  return {win, viewport, props, frames, stop, flush};
}

test('keyboard opening, visual panning and closing keep the shell in the visible area', () => {
  const f = fixture();
  assert.equal(f.props.get('--app-height'), '740px');
  f.viewport.height = 380;
  f.viewport.emit('resize');
  f.viewport.offsetTop = 220;
  f.viewport.emit('scroll');
  assert.equal(f.frames.size, 1); // one update for a burst of keyboard events
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
