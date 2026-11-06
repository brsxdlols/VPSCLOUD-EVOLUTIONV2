const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert/strict'),cp=require('child_process');
const root=path.resolve(__dirname,'..'),tmp=fs.mkdtempSync(path.join(os.tmpdir(),'monitor-test-'));
for(const f of ['monitor-hook.cjs','monitor.html'])fs.copyFileSync(path.join(root,f),path.join(tmp,f));
const key='test-administrator-key',fakeToken='123456:'+('A'.repeat(35));
fs.writeFileSync(path.join(tmp,'config.json'),JSON.stringify({telegram_bot_token:fakeToken,telegram_chat_id:'-100123',instances:[]}));
const server=cp.spawn(process.execPath,['-r',path.join(tmp,'monitor-hook.cjs'),'-e',`const e=require('express'),a=e();a.use((r,s,n)=>n());a.get('/',(r,s)=>s.send('OK'));a.get('/instance/fetchInstances',(r,s)=>s.json([{name:'MKAUTH',token:'do-not-return-this'}]));a.listen(8080,'127.0.0.1')`],{env:{...process.env,AUTHENTICATION_API_KEY:key,NODE_PATH:'/evolution/node_modules'},stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{try{
 let ready=false;for(let i=0;i<50;i++){try{let r=await fetch('http://127.0.0.1:8080/ops/monitor/');if(r.ok){ready=true;break}}catch{}await sleep(100)}assert.ok(ready,'monitor did not start');
 const base='http://127.0.0.1:8080/ops/monitor/api';assert.equal((await fetch(base+'/config')).status,401);
 const r=await fetch(base+'/config',{headers:{apikey:key}}),text=await r.text();assert.equal(r.status,200);assert.ok(!text.includes(fakeToken));assert.ok(!text.includes('do-not-return-this'));assert.ok(JSON.parse(text).names.includes('MKAUTH'));
 const body={label:'Unit test',docker:{chat:'-100123',token:''},instances:[{name:'MKAUTH',enabled:true,chat:'-200',token:''}]};
 assert.equal((await fetch(base+'/config',{method:'POST',headers:{apikey:key,'Content-Type':'application/json',Origin:'https://foreign.invalid'},body:JSON.stringify(body)})).status,403);
 const saved=await fetch(base+'/config',{method:'POST',headers:{apikey:key,'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(saved.status,200);const data=JSON.parse(fs.readFileSync(path.join(tmp,'config.json')));assert.equal(data.telegram_bot_token,fakeToken);assert.equal(data.instances[0].name,'MKAUTH');assert.equal(fs.statSync(path.join(tmp,'config.json')).mode&0o777,0o600);
 console.log('PASS monitor HTTP authentication, redaction, origin check, token preservation, permissions and instance configuration');
}finally{server.kill();fs.rmSync(tmp,{recursive:true,force:true})}})().catch(e=>{console.error(e.message);process.exitCode=1});
