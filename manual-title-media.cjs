'use strict';
const crypto=require('crypto');
const PREFIX='[VPSCLOUD_TITLE_PHOTO:';
function createStore({now=Date.now,ttl=30*60*1000,maxItems=10,maxBytes=2*1024*1024}={}){
 const items=new Map();
 function clean(){for(const [key,value] of items)if(value.expires<=now())items.delete(key)}
 function put(input){
  clean();if(items.size>=maxItems)throw Error('Aguarde os envios anteriores para anexar outra foto.');
  const media=input.media,instance=input.instance,mime=input.mimetype;
  if(typeof instance!=='string'||!instance||instance.length>100||/[\r\n]/.test(instance))throw Error('Instancia invalida.');
  if(typeof media!=='string'||media.length>Math.ceil(maxBytes/3)*4||!/^[A-Za-z0-9+/]*={0,2}$/.test(media))throw Error('Imagem invalida ou maior que 2 MiB.');
  const bytes=Buffer.from(media,'base64');if(!bytes.length||bytes.length>maxBytes||bytes.toString('base64')!==media)throw Error('Imagem invalida.');
  const detected=bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))?'image/png':bytes[0]===255&&bytes[1]===216&&bytes[2]===255?'image/jpeg':/^GIF8[79]a$/.test(bytes.subarray(0,6).toString('ascii'))?'image/gif':'';
  if(!detected||mime!==detected)throw Error('Use uma foto PNG, JPG ou GIF.');
  const token=crypto.randomBytes(24).toString('hex'),expires=now()+ttl;
  items.set(token,{media,mimetype:mime,instance,expires,fileName:'foto.'+({'image/png':'png','image/jpeg':'jpg','image/gif':'gif'}[mime])});return {token,expires};
 }
 function rewrite(req){
  const route=req.url.match(/^\/message\/(sendText|sendMedia)\/([^/?]+)(?:\?|$)/);const field=route?.[1]==='sendMedia'?'caption':'text';
  if(req.method!=='POST'||!route||typeof req.body?.[field]!=='string'||!req.body[field].includes(PREFIX))return;
  clean();const text=req.body[field],match=text.match(/\[VPSCLOUD_TITLE_PHOTO:([a-f0-9]{48})\]\s*$/);
  const photo=match&&items.get(match[1]);let instance='';try{instance=decodeURIComponent(route[2])}catch{}
  if(!photo||photo.instance!==instance||text.indexOf(PREFIX)!==match.index){const error=Error('Foto temporaria indisponivel. Reabra o envio manual e anexe a foto novamente.');error.status=409;throw error}
  const caption=text.slice(0,match.index).replace(/\r?\n$/,'');
  if(route[1]==='sendMedia'){req.body={...req.body,caption};return;}
  const {text:ignored,linkPreview,...rest}=req.body;
  req.body={...rest,mediatype:'image',mimetype:photo.mimetype,caption,media:photo.media,fileName:photo.fileName};
  req.url=req.url.replace('/message/sendText/','/message/sendMedia/');
 }
 return {put,rewrite,clean};
}
const store=createStore();
function install(express){
 if(express.__vpscloudTitleMedia)return;express.__vpscloudTitleMedia=true;
 const json=express.json;
 express.json=function(...args){const parser=json.apply(this,args);return function(req,res,next){parser(req,res,error=>{if(error)return next(error);try{store.rewrite(req);next()}catch(e){res.status(e.status||400).json({error:e.message})}})}};
 const timer=setInterval(store.clean,60000);timer.unref();
}
function router(express,auth){
 const r=express.Router();r.use(auth);
 r.get('/',(req,res)=>res.json({ready:true,maxBytes:2*1024*1024}));
 r.post('/',express.json({limit:'3mb'}),(req,res)=>{try{res.json(store.put(req.body||{}))}catch(e){res.status(400).json({error:e.message})}});
 r.use((error,req,res,next)=>res.status(400).json({error:'Imagem invalida ou maior que 2 MiB.'}));return r;
}
module.exports={createStore,install,router};
