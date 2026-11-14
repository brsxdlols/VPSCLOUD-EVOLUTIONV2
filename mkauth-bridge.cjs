'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),http=require('http');
const BASE='/admin/addons/evolution/app',COOKIE='vpscloud_evolution_bridge';
function valid(req,secret,now=Date.now()){
 if(!/^[a-f0-9]{64}$/.test(secret||''))return false;
 const item=String(req.headers.cookie||'').split(';').map(s=>s.trim()).find(s=>s.startsWith(COOKIE+'='));
 if(!item)return false;
 const token=item.slice(COOKIE.length+1),parts=token.split('.');
 if(parts.length!==3||!/^\d{10}$/.test(parts[0])||!/^\w{32}$/.test(parts[1])||! /^[a-f0-9]{64}$/.test(parts[2]))return false;
 const expiry=Number(parts[0]);if(expiry<Math.floor(now/1000)||expiry>Math.floor(now/1000)+240)return false;
 const expected=crypto.createHmac('sha256',secret).update(parts[0]+'.'+parts[1]).digest('hex');
 if(!crypto.timingSafeEqual(Buffer.from(expected),Buffer.from(parts[2])))return false;
 if(req.headers.origin){try{if(new URL(req.headers.origin).host!==req.headers.host)return false}catch{return false}}
 return expiry;
}
function browserShim(){
 return `(()=>{const base=${JSON.stringify(BASE)};function mapped(value){const u=new URL(String(value),location.href);if(!['http:','https:','ws:','wss:'].includes(u.protocol))return value;u.host=location.host;u.port=new URL(location.href).port;u.protocol=/^ws/.test(u.protocol)?(location.protocol==='https:'?'wss:':'ws:'):location.protocol;if(!u.pathname.startsWith(base+'/')&&u.pathname!==base)u.pathname=base+u.pathname;return u.href}const fetch0=window.fetch;window.fetch=function(input,init){return fetch0.call(this,input instanceof Request?new Request(mapped(input.url),input):mapped(input),init)};const open=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(method,url,...rest){return open.call(this,method,mapped(url),...rest)};const WS=window.WebSocket;window.WebSocket=class extends WS{constructor(url,protocols){super(mapped(url),...(protocols===undefined?[]:[protocols]))}};})();`;
}
function transform(body,type){
 let text=String(body).split('/manager').join(BASE+'/manager');
 if(type==='html')text=text.replace(/<head[^>]*>/i,m=>m+'<base href="'+BASE+'/manager/"><script>'+browserShim()+'</script>');
 return text;
}
function install(dir){
 if(http.Server.prototype.__vpscloudBridge)return;
 http.Server.prototype.__vpscloudBridge=true;
 const emit=http.Server.prototype.emit;
 http.Server.prototype.emit=function(event,...args){
  if((event==='request'||event==='upgrade')&&args[0]&&String(args[0].url||'').split('?')[0].startsWith(BASE+'/')){
   const req=args[0];let secret='';try{secret=JSON.parse(fs.readFileSync(path.join(dir,'bridge-secret.json'),'utf8')).secret}catch{}
   const expiry=valid(req,secret);
   if(!expiry){if(event==='request'){args[1].writeHead(401,{'Content-Type':'text/plain; charset=utf-8','Cache-Control':'no-store'});args[1].end('Entre novamente pelo addon Evolution no MK-AUTH.')}else args[1].destroy();return true}
   req.__vpscloudBridge=true;req.url=req.url.slice(BASE.length)||'/';
   if(event==='upgrade'){const timer=setTimeout(()=>args[1].destroy(),Math.max(1,expiry*1000-Date.now()));timer.unref();args[1].once('close',()=>clearTimeout(timer))}
  }
  return emit.call(this,event,...args);
 };
}
function middleware(dir){return function(req,res,next){
 if(!req.__vpscloudBridge)return next();
 res.setHeader('Cache-Control','no-store');res.setHeader('X-Frame-Options','SAMEORIGIN');res.setHeader('X-Content-Type-Options','nosniff');
 const url=req.url.split('?')[0];
 if(url==='/monitor'||url==='/monitor/'||url==='/ops/monitor/'||url==='/ops/monitor'){
  let text=fs.readFileSync(path.join(dir,'monitor.html'),'utf8');
  text=text.replace(/<head[^>]*>/i,m=>m+'<script>'+browserShim()+'</script>');return res.type('html').send(text);
 }
 if(url!=='/manager'&&!url.startsWith('/manager/'))return next();
 if(req.method!=='GET'&&req.method!=='HEAD')return res.status(405).end();
 const root='/evolution/manager/dist';let file;
 try{const part=decodeURIComponent(url.slice('/manager'.length));file=path.resolve(root,'.'+part);if(!file.startsWith(root+'/')&&file!==root)return res.status(403).end()}catch{return res.status(400).end()}
 if(!path.extname(file)||file===root)file=path.join(root,'index.html');
 if(!fs.existsSync(file)||!fs.statSync(file).isFile()){if(url.startsWith('/manager/assets/'))return res.status(404).end();file=path.join(root,'index.html')}
 const ext=path.extname(file).toLowerCase();
 if(['.html','.js','.css','.json','.svg'].includes(ext))return res.type(ext.slice(1)).send(transform(fs.readFileSync(file,'utf8'),ext==='.html'?'html':ext));
 return res.sendFile(file);
};}
module.exports={BASE,COOKIE,valid,transform,browserShim,install,middleware};
