// Exercise the shipped client's request handling without a browser dependency.
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const source=readFileSync(join(__dirname,'../../game/agent/analysis/assets/app.js'),'utf8');
const route='decision?id=227d63d4cd9141a4820bfa17def8b425&step=56';
const decision={step:56,action:{kind:'leave_rewards'}};

function client(responses,onWait=()=>{}) {
  let booting=true;
  const calls=[],waits=[];
  const context={URLSearchParams,
    fetch:async(url,options)=>{
      // Leave start() pending; these tests need no DOM or initial report.
      if(booting)return new Promise(()=>{});
      calls.push({url,options});
      assert.ok(responses.length,'Request count exceeded the supplied responses');
      const next=responses.shift();
      if(next instanceof Error)throw next;
      const {body,status=200}=next;
      return {ok:status>=200&&status<300,status,json:async()=>JSON.parse(body)};
    },
    setTimeout:callback=>{waits.push(true);onWait();callback();}
  };
  vm.runInNewContext(source,context);
  booting=false;
  return {api:context.api,calls,waits};
}

test('a valid decision loads once, without delay or changes to its contents',async()=>{
  const c=client([{body:JSON.stringify(decision)}]);
  assert.deepEqual(await c.api(route),decision);
  assert.equal(c.calls.length,1);
  assert.equal(c.calls[0].url,'/api/'+route);
  assert.equal(c.calls[0].options.cache,'no-store');
  assert.equal(c.waits.length,0);
});

for(const body of ['', '{"step":56', '<html>Bad Gateway</html>', 'null', '[]']) {
  test(`an incomplete or invalid response recovers on one retry: ${body}`,async()=>{
    const c=client([{body},{body:JSON.stringify(decision)}]);
    assert.deepEqual(await c.api(route),decision);
    assert.equal(c.calls.length,2);
    assert.equal(c.waits.length,1);
    assert.equal(c.calls[0].url,c.calls[1].url);
  });
}

test('an interrupted connection recovers on one retry',async()=>{
  const c=client([new TypeError('Failed to fetch'),{body:JSON.stringify(decision)}]);
  assert.deepEqual(await c.api(route),decision);
  assert.equal(c.calls.length,2);
});

for(const body of ['{"error":"Temporarily unavailable"}', '<html>Bad Gateway</html>']) {
  test(`a temporary server failure retries: ${body}`,async()=>{
    const c=client([{status:502,body},{body:JSON.stringify(decision)}]);
    assert.deepEqual(await c.api(route),decision);
    assert.equal(c.calls.length,2);
  });
}

test('a persistent incomplete response stops after two attempts and names the displayed step',async()=>{
  const c=client([{body:''},{body:'{"step":'}]);
  await assert.rejects(c.api(route),/Unable to load step 57:.*empty, incomplete or invalid.*Try loading it again/);
  assert.equal(c.calls.length,2);
});

test('a persistent connection failure names the failed comparison',async()=>{
  const c=client([new TypeError('Failed to fetch'),new TypeError('Failed to fetch')]);
  await assert.rejects(c.api(route.replace('decision?','compare?')),/checkpoint comparison for step 57:.*connection/);
  assert.equal(c.calls.length,2);
});

test('a definitive integrity error remains visible without retry',async()=>{
  const c=client([{status:400,body:'{"error":"Decision chunk digest mismatch; rebuild the export"}'}]);
  await assert.rejects(c.api(route),/Decision chunk digest mismatch; rebuild the export \(HTTP 400\)/);
  assert.equal(c.calls.length,1);
  assert.equal(c.waits.length,0);
});

test('a non-JSON rejection shows its HTTP status without retry',async()=>{
  const c=client([{status:403,body:'<html>Forbidden</html>'}]);
  await assert.rejects(c.api(route),/server rejected the request \(HTTP 403\)/);
  assert.equal(c.calls.length,1);
});

test('obsolete navigation requests do not retry',async()=>{
  const c=client([{body:''}]);
  await assert.rejects(c.api(route,()=>false),/Unable to load step 57/);
  assert.equal(c.calls.length,1);
  assert.equal(c.waits.length,0);
});

test('navigation during the retry delay also stops the obsolete request',async()=>{
  let current=true;
  const c=client([{body:''}],()=>{current=false;});
  await assert.rejects(c.api(route,()=>current),/Unable to load step 57/);
  assert.equal(c.calls.length,1);
  assert.equal(c.waits.length,1);
});
