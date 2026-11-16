const assert=require('assert/strict'),{createStore}=require('../manual-title-media.cjs');
let now=100;const s=createStore({now:()=>now,ttl:10,maxItems:1});const media=Buffer.from([137,80,78,71,13,10,26,10,0]).toString('base64');const photo=s.put({media,mimetype:'image/png',instance:'MKAUTH'});
assert.throws(()=>s.put({media,mimetype:'image/png',instance:'MKAUTH'}));
const req={method:'POST',url:'/message/sendText/MKAUTH',body:{text:'Mensagem\n[VPSCLOUD_TITLE_PHOTO:'+photo.token+']',number:'5511999999999'}};s.rewrite(req);assert.equal(req.url,'/message/sendMedia/MKAUTH');assert.equal(req.body.caption,'Mensagem');assert.equal(req.body.media,media);
const unchanged={method:'POST',url:'/message/sendText/MKAUTH',body:{text:'Mensagem automatica',number:'5511999999999'}};const before=JSON.stringify(unchanged);s.rewrite(unchanged);assert.equal(JSON.stringify(unchanged),before);
const expired={method:'POST',url:'/message/sendText/MKAUTH',body:{text:'[VPSCLOUD_TITLE_PHOTO:'+photo.token+']'}};now=111;assert.throws(()=>s.rewrite(expired),e=>e.status===409);assert.ok(!expired.url.includes('sendMedia'));
assert.throws(()=>s.put({media:'not-base64',mimetype:'image/png',instance:'MKAUTH'}));assert.throws(()=>s.put({media,mimetype:'image/jpeg',instance:'MKAUTH'}));
console.log('PASS manual photo storage limits, expiry, image types and unchanged automatic text');
