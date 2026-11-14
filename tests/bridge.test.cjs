'use strict';
const assert=require('assert/strict'),crypto=require('crypto'),vm=require('vm'),http=require('http'),fs=require('fs'),os=require('os'),path=require('path');
const b=require('../mkauth-bridge.cjs'),secret='ab'.repeat(32),now=Math.floor(Date.now()/1000);
function ticket(expiry=now+180){const s=expiry+'.'+'12'.repeat(16);return s+'.'+crypto.createHmac('sha256',secret).update(s).digest('hex')}
function request(token,origin){return {headers:{cookie:b.COOKIE+'='+token,host:'mk.test',...(origin?{origin}:{})}}}
assert.ok(b.valid(request(ticket()),secret));assert.equal(b.valid(request(ticket(now-1)),secret),false);assert.equal(b.valid(request(ticket(now+999)),secret),false);assert.equal(b.valid(request(ticket()+'a'),secret),false);assert.equal(b.valid(request(ticket(),'https://other.test'),secret),false);assert.equal(b.valid(request(ticket()),''),false);
const html=b.transform('<html><head></head><script src="/manager/assets/app.js"></script></html>','html');assert.ok(html.includes(b.BASE+'/manager/assets/app.js'));assert.ok(html.includes('<base href="'+b.BASE+'/manager/">'));
const calls=[];class XHR{open(...args){calls.push(args)}}class WS{constructor(...args){calls.push(args)}}
const location={href:'https://mk.test'+b.BASE+'/manager/',host:'mk.test',protocol:'https:'};
const context={URL,Request,location,XMLHttpRequest:XHR,window:{fetch:(...args)=>{calls.push(args);return Promise.resolve()},WebSocket:WS}};
vm.runInNewContext(b.browserShim(),context);context.window.fetch('http://172.16.30.25:7070/instance/fetchInstances');new XHR().open('GET','/monitor/api/config');new context.window.WebSocket('ws://mk.test/socket.io/?EIO=4');
assert.equal(calls[0][0],'https://mk.test'+b.BASE+'/instance/fetchInstances');assert.equal(calls[1][1],'https://mk.test'+b.BASE+'/monitor/api/config');assert.equal(calls[2][0],'wss://mk.test'+b.BASE+'/socket.io/?EIO=4');
const dir=fs.mkdtempSync(path.join(os.tmpdir(),'bridge-'));fs.writeFileSync(path.join(dir,'bridge-secret.json'),JSON.stringify({secret}));b.install(dir);
const server=http.createServer((req,res)=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify({url:req.url,bridge:!!req.__vpscloudBridge}))});
(async()=>{try{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base='http://127.0.0.1:'+server.address().port;
 assert.equal((await fetch(base+b.BASE+'/instance/fetchInstances')).status,401);
 const r=await fetch(base+b.BASE+'/instance/fetchInstances?x=1',{headers:{cookie:b.COOKIE+'='+ticket()}});assert.equal(r.status,200);assert.deepEqual(await r.json(),{url:'/instance/fetchInstances?x=1',bridge:true});
 const normal=await fetch(base+'/instance/fetchInstances');assert.equal((await normal.json()).bridge,false);
 console.log('PASS authenticated bridge tickets, expiry, origin, HTTP routing and browser REST/WebSocket mapping');
}finally{server.close();fs.rmSync(dir,{recursive:true,force:true})}})().catch(e=>{console.error(e);process.exitCode=1});
