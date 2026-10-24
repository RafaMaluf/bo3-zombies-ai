const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function gallery() {
  const controls = new Map();
  const control = id => {
    if (!controls.has(id)) controls.set(id, {
      handlers: {}, addEventListener(name, handler) { this.handlers[name] = handler; },
      removeAttribute(name) { delete this[name]; },
      showModal() { this.open = true; },
      close() { this.open = false; this.handlers.close?.(); },
    });
    return controls.get(id);
  };
  const elements = {imageModal: control('modal'), modalImage: control('image'), modalCaption: control('caption')};
  const source = fs.readFileSync('frontend/app.js', 'utf8');
  const code = source.slice(source.indexOf('let imageGroup ='), source.indexOf('function setPending'));
  const api = vm.runInNewContext(code + ';({openImage, moveImage, closeImage})', {
    elements, document: {getElementById: control, querySelector: control},
    getMap: () => ({display_name: 'Origins'}), imageVariantUrl: image => image.full_url,
  });
  return {api, elements, control};
}

test('image navigation stays inside its source group and hides technical captions', () => {
  const {api, elements, control} = gallery();
  const group = [1, 2, 3].map(id => ({id, map_id:'origins', caption:`internal-file-${id}`, full_url:`full-${id}`}));
  api.openImage(group[0], group, 0);
  assert.equal(elements.imageModal.open, true);
  assert.equal(elements.modalImage.src, 'full-1');
  assert.equal(elements.modalImage.alt, 'internal-file-1');
  assert.equal(elements.modalCaption.textContent, 'Origins · 1 / 3');
  assert.equal(control('image-previous').disabled, true);
  api.moveImage(-1);
  assert.equal(elements.modalImage.src, 'full-1');
  api.moveImage(1); api.moveImage(1); api.moveImage(1);
  assert.equal(elements.modalImage.src, 'full-3');
  assert.equal(control('image-next').disabled, true);
  api.closeImage();
  assert.equal(elements.modalImage.src, undefined);
  const other = {map_id:'origins', caption:'other', full_url:'other-full'};
  api.openImage(other);
  assert.equal(elements.modalImage.src, 'other-full');
  assert.equal(control('.image-navigation').hidden, true);
});

test('arrow keys navigate images without allowing the page to scroll', () => {
  const {api, elements} = gallery();
  const group = [{full_url:'A'}, {full_url:'B'}];
  api.openImage(group[0], group);
  let prevented = false;
  elements.imageModal.handlers.keydown({key:'ArrowRight', preventDefault(){prevented = true;}});
  assert.equal(prevented, true);
  assert.equal(elements.modalImage.src, 'B');
  elements.imageModal.handlers.keydown({key:'ArrowLeft', preventDefault(){}});
  assert.equal(elements.modalImage.src, 'A');
});

test('conversation drawer waits for pending writes before reading and does not open a second modal', async () => {
  const opener = {setAttribute(name, value){this[name] = value;}};
  const History = vm.runInNewContext(fs.readFileSync('frontend/history.js','utf8')+';ConversationHistory', {
    document:{getElementById:()=>opener},
  });
  const instance = Object.create(History.prototype);
  const calls = [];
  let finish;
  instance.queue = new Promise(resolve => {finish = resolve;});
  instance.list = async (append, include) => calls.push(['list', append, include]);
  instance.dialog = {open:false, showModal(){this.open=true;calls.push(['open']);}};
  const opening = instance.show(true);
  assert.equal(calls.length, 0);
  finish(); await opening;
  assert.deepEqual(calls, [['list',false,true],['open']]);
  await instance.show();
  assert.equal(calls.filter(c=>c[0]==='open').length, 1);
  assert.equal(opener['aria-expanded'], 'true');
});
