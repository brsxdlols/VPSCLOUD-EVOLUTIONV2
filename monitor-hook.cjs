'use strict';
// Loaded by NODE_OPTIONS before the existing API. No changes to upstream bundles.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const dir=__dirname,configPath=path.join(dir,'config.json'),statePath=path.join(dir,'state.json');
const bridge=require('./mkauth-bridge.cjs');bridge.install(dir);
function read(p,fallback){try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return fallback}}
function auth(req,res,next){const a=Buffer.from(String(req.headers.apikey||'')),b=Buffer.from(process.env.AUTHENTICATION_API_KEY||'');if(!b.length||a.length!==b.length||!crypto.timingSafeEqual(a,b))return res.status(401).json({error:'Chave global da API invalida'});if(req.headers.origin){try{if(new URL(req.headers.origin).host!==req.headers.host)return res.status(403).end()}catch{return res.status(403).end()}}next()}
function validateTarget(input,previous){
 const token=String(input.token||'').trim()||String(previous.telegram_bot_token||'');
 const chat=String(input.chat||'').trim();
 if(token&&!/^\d+:[A-Za-z0-9_-]{20,}$/.test(token))throw Error('Formato do token invalido');
 if(chat&&!/^(?:-?\d+|@[A-Za-z0-9_]+)$/.test(chat))throw Error('Chat ID invalido');
 return {telegram_bot_token:input.clearToken?'':token,telegram_chat_id:chat};
}
function redacted(c){return {label:c.label||'MK-AUTH / Evolution',docker:{chat:c.telegram_chat_id||'',hasToken:!!c.telegram_bot_token},instances:(c.instances||[]).map(x=>({name:x.name,enabled:x.enabled!==false,chat:x.telegram_chat_id||'',hasToken:!!x.telegram_bot_token}))}}
async function send(target,text){if(!target.telegram_bot_token||!target.telegram_chat_id)throw Error('Configure token e chat primeiro');const r=await fetch('https://api.telegram.org/bot'+target.telegram_bot_token+'/sendMessage',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({chat_id:target.telegram_chat_id,text}),signal:AbortSignal.timeout(10000)});const o=await r.json();if(!r.ok||!o.ok)throw Error('Telegram recusou o envio. Confira token, chat e acesso do bot.');}
const express=require('express'),original=express.application.use;
express.application.use=function(...args){
 if(!this.__vpscloudMonitor){
  this.__vpscloudMonitor=true;
  original.call(this,bridge.middleware(dir));
  const router=express.Router();
  router.get('/',(req,res)=>res.type('html').send(fs.readFileSync(path.join(dir,'monitor.html'),'utf8')));
  router.use('/api',auth,express.json({limit:'32kb'}));
  router.get('/api/config',async(req,res)=>{
   try{const r=await fetch('http://127.0.0.1:8080/instance/fetchInstances',{headers:{apikey:process.env.AUTHENTICATION_API_KEY},signal:AbortSignal.timeout(5000)});if(!r.ok)throw Error();const values=await r.json();const names=(Array.isArray(values)?values:[]).map(x=>x.name||x.instance?.instanceName).filter(Boolean);res.json({config:redacted(read(configPath,{})),names,status:read(statePath,{})})}catch{res.status(503).json({error:'Nao foi possivel consultar as instancias da API'})}
  });
  router.post('/api/config',(req,res)=>{
   try{const old=read(configPath,{}),v=req.body;if(!Array.isArray(v.instances)||v.instances.length>100)throw Error('Lista de instancias invalida');const names=new Set();const instances=v.instances.map(x=>{const name=String(x.name||'');if(!name||name.length>100||names.has(name))throw Error('Nome de instancia invalido ou duplicado');names.add(name);return {name,enabled:!!x.enabled,...validateTarget(x,(old.instances||[]).find(i=>i.name===name)||{})}});const c={label:String(v.label||'MK-AUTH / Evolution').slice(0,100),...validateTarget(v.docker||{},old),instances};fs.writeFileSync(configPath+'.tmp',JSON.stringify(c,null,2),{mode:0o600});fs.chmodSync(configPath+'.tmp',0o600);fs.renameSync(configPath+'.tmp',configPath);res.json({saved:true,config:redacted(c)})}catch(e){res.status(400).json({error:e.message})}
  });
  router.post('/api/test',async(req,res)=>{
   try{const c=read(configPath,{}),name=req.body.instance;const target=name?(c.instances||[]).find(x=>x.name===name):c;if(!target)throw Error('Destino nao encontrado');const effective={telegram_bot_token:target.telegram_bot_token||c.telegram_bot_token,telegram_chat_id:target.telegram_chat_id||c.telegram_chat_id};await send(effective,(c.label||'Evolution')+'\nTeste de alertas: '+(name||'Docker / API')+'.');res.json({sent:true})}catch(e){res.status(400).json({error:/^Configure|^Telegram|^Destino/.test(e.message)?e.message:'Nao foi possivel entregar o teste ao Telegram'})}
  });
  router.use((err,req,res,next)=>res.status(400).json({error:'Requisicao invalida'}));
  original.call(this,'/monitor',router);
  original.call(this,'/ops/monitor',router);
 }
 return original.apply(this,args);
};
