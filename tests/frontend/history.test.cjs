const test = require('node:test');
const assert = require('node:assert/strict');
require('fake-indexeddb/auto');
const {HistoryStore, transcriptRow, transcriptText} = require('../../frontend/history-store.js');
const fs = require('node:fs');
const vm = require('node:vm');
const {performance} = require('node:perf_hooks');

async function store() { return HistoryStore.open(`test-${crypto.randomUUID()}`); }
test('append and match update commit atomically, without replacing other conversations', async () => {
  const db = await store();
  const a = await db.create('A'), b = await db.create('B');
  const updated = await db.update(a.id, {match:{focus:'step-2'}}, [transcriptRow('user','Terminei')], a.revision);
  assert.equal(updated.count, 1);
  assert.equal((await db.get(a.id)).match.focus, 'step-2');
  assert.equal((await db.get(b.id)).match, null);
  assert.equal((await db.page(a.id))[0].text, 'Terminei');
  db.db.close();
});
test('revision conflict aborts both progress and message; deleted conversation cannot resurrect', async () => {
  const db = await store(); const a = await db.create('A');
  await db.update(a.id, {match:{focus:'new'}}, [], 0);
  await assert.rejects(db.update(a.id, {match:{focus:'stale'}}, [transcriptRow('user','bad')], 0));
  assert.equal((await db.get(a.id)).match.focus, 'new');
  assert.equal((await db.page(a.id)).length, 0);
  await db.remove(a.id);
  await assert.rejects(db.update(a.id, {}, [transcriptRow('user','resurrection')]));
  assert.equal(await db.get(a.id), undefined);
  db.db.close();
});
test('parallel transactions serialize unique message sequence numbers', async () => {
  const db = await store(); const a = await db.create('A');
  await Promise.all(Array.from({length:12},(_,i)=>db.update(a.id,{},[transcriptRow('user',String(i))])));
  const rows = await db.page(a.id);
  assert.deepEqual(rows.map(r=>r.seq), Array.from({length:12},(_,i)=>i+1));
  db.db.close();
});
test('bounded message pages preserve chronology and all data survives reopening', async () => {
  const name = `test-${crypto.randomUUID()}`; let db = await HistoryStore.open(name);
  const a = await db.create('A');
  await db.update(a.id, {}, Array.from({length:85},(_,i)=>transcriptRow('assistant',`message-${i}`)));
  db.db.close(); db = await HistoryStore.open(name);
  const newest = await db.page(a.id), older = await db.page(a.id,newest[0].seq);
  assert.equal(newest.length,30); assert.equal(newest[0].seq,56); assert.equal(newest.at(-1).seq,85);
  assert.equal(older.length,30); assert.equal(older.at(-1).seq,55);
  assert.equal((await db.get(a.id)).count,85);
  await db.remove(a.id); assert.equal((await db.page(a.id)).length,0);
  db.db.close();
});
test('history metadata pagination has no gaps even when timestamps tie', async () => {
  const db = await store();
  const records = await Promise.all(Array.from({length:45},(_,i)=>db.create(`Chat ${i}`)));
  const first = await db.list(), second = await db.list(first.at(-1)), third = await db.list(second.at(-1));
  const ids = [...first,...second,...third].map(r=>r.id);
  assert.equal(ids.length,45); assert.equal(new Set(ids).size,45);
  assert.deepEqual(new Set(ids), new Set(records.map(r=>r.id)));
  db.db.close();
});
test('legacy migration is idempotent across startup tabs and ignores malformed records', async () => {
  const db = await store();
  assert.equal(await db.migrateLegacy('bad json','Recovered'),null);
  const raw=JSON.stringify({version:1,map_id:'origins',catalog_version:'abc',focus:'step'});
  const migrated = await Promise.all([db.migrateLegacy(raw,'Recovered'),db.migrateLegacy(raw,'Recovered')]);
  assert.equal(migrated.filter(Boolean).length,1);
  const records=await db.list(); assert.equal(records.length,1); assert.equal((await db.get(records[0].id)).match.focus,'step');
  db.db.close();
});
test('stored structured response keeps blocks/images but does not duplicate full answer text', () => {
  const blocks=[{title:'Peça',body:'Local A',images:[{id:'img_0123456789abcdef'}]}];
  const row=transcriptRow('assistant','Peça\nLocal A',{blocks,introduction:'Olá'});
  assert.equal(row.text,''); assert.deepEqual(row.options.blocks,blocks);
  assert.equal(transcriptText(row),'Olá\n\nPeça\nLocal A');
});

test('map clarification can be resumed after reload without a separate map picker', async () => {
  const db = await store(); const chat = await db.create('Pack-a-Punch');
  const options = {clarification:true, suggestedMapIds:['shadows_of_evil','origins'],
    suggestedQueries:[], retryMessage:'Como libero o Pack-a-Punch?'};
  await db.update(chat.id, {}, [transcriptRow('assistant','Sobre qual mapa?',options)]);
  const restored = (await db.page(chat.id))[0];
  assert.deepEqual(restored.options.suggestedMapIds, options.suggestedMapIds);
  assert.equal(restored.options.retryMessage, options.retryMessage);
  assert.equal(transcriptText(restored), 'Sobre qual mapa?');
  db.db.close();
});
test('companion commits action and progress before generation, then records answer independently', async () => {
  const Companion = vm.runInNewContext(fs.readFileSync('frontend/companion.js','utf8')+';CompanionUI', {transcriptRow});
  const instance=Object.create(Companion.prototype); const events=[];
  instance.view={catalog:{objectives:[{id:'s1',title:'Escudo'}]}}; instance.deps={locale:'pt-BR'};
  instance.saved={focus:'s1'}; instance.busy=false;
  instance.run=work=>work({aborted:false});
  instance.actionRequest=async()=>({state:{focus:'s2'},can_explain:true});
  instance.accept=async(data,event)=>{events.push(['save',event.text]);instance.saved=data.state;};
  instance.find=()=>({value:''}); instance.tr=key=>key;
  instance.explain=async()=>events.push(['generate',instance.saved.focus]);
  await instance.act('complete');
  assert.deepEqual(events,[['save','done: Escudo'],['generate','s2']]);
});
test('finished companion persists readable completion and automatically leaves focused mode', async () => {
  const Companion=vm.runInNewContext(fs.readFileSync('frontend/companion.js','utf8')+';CompanionUI',{transcriptRow});
  const instance=Object.create(Companion.prototype); let persisted, left=false;
  instance.deps={saveMatch:async(state,rows)=>{persisted={state,rows};}};
  instance.tr=key=>key; instance.banner={}; instance.find=()=>({replaceChildren(){}});
  instance.render=()=>{}; instance.leave=()=>{left=true;};
  const data={catalog:{version:'v',map_name:'Origins',objectives:[{id:'s',title:'Final',main:true}]},
    state:{stage:'finished',language:'pt',statuses:{s:'complete'}},completed_count:1,total_count:1};
  await instance.accept(data,{text:'Terminei: Final'});
  assert.equal(left,true); assert.equal(persisted.rows[0].text,'Terminei: Final');
  assert.match(persisted.rows[1].text,/1 \/ 1/); assert.match(persisted.rows[1].text,/Final/);
});
test('load fixture measures storage and bounded reads for 1000 long answers', async t => {
  const db=await store(); const a=await db.create('Load');
  const body='Uma instrução com locais e condições. '.repeat(400);
  const rows=Array.from({length:1000},()=>transcriptRow('assistant','',{blocks:[{title:'Etapa',body,images:[{id:'img_0123456789abcdef'}]}]}));
  const bytes=Buffer.byteLength(JSON.stringify(rows)); const start=performance.now();
  await db.update(a.id,{},rows); const saved=performance.now();
  const page=await db.page(a.id); const read=performance.now()-saved;
  assert.equal(page.length,30); assert.equal((await db.get(a.id)).count,1000);
  t.diagnostic(JSON.stringify({records:1000,bytes,writeMs:Math.round(saved-start),pageMs:Math.round(read),loaded:page.length}));
  db.db.close();
});

test('cached companion answer is scoped to session, focus and revision', async () => {
  const Controller=vm.runInNewContext(fs.readFileSync('frontend/history.js','utf8')+';ConversationHistory',{transcriptText});
  const db=await store(); const a=await db.create('A');
  await db.update(a.id,{},[transcriptRow('assistant','Saved instructions',{companion:{sessionId:'s',focus:'f',revision:2}})]);
  const instance=Object.create(Controller.prototype); instance.store=db; instance.meta=a;
  assert.equal((await instance.cachedAnswer({session_id:'s',focus:'f',revision:2})).answer,'Saved instructions');
  assert.equal(await instance.cachedAnswer({session_id:'other',focus:'f',revision:2}),null);
  assert.equal(await instance.cachedAnswer({session_id:'s',focus:'f',revision:3}),null);
  db.db.close();
});
test('failed storage write warns and rejects without pretending progress was saved', async () => {
  const Controller=vm.runInNewContext(fs.readFileSync('frontend/history.js','utf8')+';ConversationHistory',{});
  const instance=Object.create(Controller.prototype); let warning='';
  instance.meta={id:'a',revision:0}; instance.queue=Promise.resolve(); instance.copy={storage:'Not saved'};
  instance.store={update:async()=>{throw new Error('QuotaExceededError');}};
  instance.warn=message=>{warning=message;};
  await assert.rejects(instance.write({match:{focus:'new'}})); await instance.flush();
  assert.match(warning,/Not saved/); assert.equal(instance.meta.match,undefined);
});

test('shared chat/PDF renderer escapes markup while preserving multilingual text', () => {
  const render=vm.runInNewContext(fs.readFileSync('frontend/rendering.js','utf8')+';renderMarkdown',{});
  const html=render('## Etapa\n\n<script>alert(1)</script> **Olá 世界**\n\n1. Primeiro\n2. Segundo');
  assert.match(html, /&lt;script&gt;/); assert.doesNotMatch(html, /<script>/);
  assert.match(html, /<strong>Olá 世界<\/strong>/); assert.match(html, /<ol>/);
});
test('plain replies are not duplicated when restoring model context', () => {
  assert.equal(transcriptText(transcriptRow('assistant','Resposta',{introduction:'Resposta'})),'Resposta');
});

test('a failed companion save keeps the previous focus and does not expose the next Done action', async () => {
  const Companion=vm.runInNewContext(fs.readFileSync('frontend/companion.js','utf8')+';CompanionUI',{transcriptRow});
  const instance=Object.create(Companion.prototype); const previous={focus:'old'};
  instance.saved=previous; instance.view={state:previous};
  instance.deps={saveMatch:async()=>{throw new Error('quota');}};
  await assert.rejects(instance.accept({catalog:{version:'v',objectives:[]},state:{focus:'new'}},{text:'Terminei'}));
  assert.equal(instance.saved,previous); assert.equal(instance.view.state.focus,'old');
});

test('failure to create a new conversation retains the previously open record', async () => {
  const Controller=vm.runInNewContext(fs.readFileSync('frontend/history.js','utf8')+';ConversationHistory',{});
  const instance=Object.create(Controller.prototype); const previous={id:'old',revision:2};
  instance.meta=previous; instance.queue=Promise.resolve(); instance.copy={storage:'Not saved',new:'New'};
  instance.warn=()=>{}; instance.deps={cancel(){},reset(){throw new Error('Must not clear old content');}};
  instance.store={create:async()=>{throw new Error('quota');}};
  assert.equal(await instance.newConversation(),false); assert.equal(instance.meta,previous);
  assert.equal(instance.switching,false);
});

test('switching companion conversation clears unsent commands, retry state and language from the previous match', () => {
  const Companion=vm.runInNewContext(fs.readFileSync('frontend/companion.js','utf8')+';CompanionUI',{});
  const instance=Object.create(Companion.prototype); const controls=new Map();
  instance.find=key=>{if(!controls.has(key))controls.set(key,{style:{},value:'Terminei',replaceChildren(){}});return controls.get(key);};
  instance.leave=()=>{}; instance.deps={language:'en'}; instance.banner={}; instance.lastExplanation={message:'old'};
  const match={stage:'active',language:'pt-BR'};
  instance.setMatch(match,['origins']);
  assert.equal(instance.saved,match); assert.equal(instance.find('textarea').value,'');
  assert.equal(instance.find('.companion-retry').hidden,true); assert.equal(instance.offerLanguage,'pt-BR');
  assert.equal(Object.keys(instance.lastExplanation).length,0);
});
