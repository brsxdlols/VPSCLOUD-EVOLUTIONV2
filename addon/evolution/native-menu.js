/* VPSCLOUD-EVOLUTION-BEGIN */
;(function(){
 if(window.__vpscloudEvolutionMenu)return;window.__vpscloudEvolutionMenu=true;
 if(typeof add_menu!=='undefined'&&typeof add_menu.provedor==='function'){
  add_menu.provedor(JSON.stringify({plink:location.origin+'/admin/addons/evolution/',ptext:'Evolution API',picone:'fa fa-whatsapp'}));
  add_menu.provedor(JSON.stringify({plink:location.origin+'/admin/addons/evolution/?view=monitor',ptext:'Evolution \xb7 Alertas Telegram',picone:'fa fa-bell'}));
 }
 function fill(){
  if(!/\/admin\/conf_zap_serv\.hhvm$/.test(location.pathname))return;
  const host=document.querySelector('input[name="wapp_host"],input#wapp_host,input[name="host"],input[name="servidor"]');
  const type=document.querySelector('select[name="wappservidor"],select[name="wapp_servidor"],select#wapp_servidor')||Array.from(document.querySelectorAll('select')).find(s=>Array.from(s.options).some(o=>o.value==='evolution2_api'));
  if(!host||host.type==='password')return;
  const instance=document.querySelector('input[name="wapp_login"]')||document.querySelector('input[name="instancia"]');
  const key=document.querySelector('input[name="wapp_pass"]')||document.querySelector('input[name="instancia_token"]');
  if(instance&&key){
   const button=document.createElement('button');button.type='button';button.textContent='Ver inst\xe2ncias do Evolution';button.className='button is-info';button.style.margin='10px 0';
   const note=document.createElement('p');note.setAttribute('role','status');
   host.insertAdjacentElement('afterend',button);button.insertAdjacentElement('afterend',note);
   button.onclick=async()=>{
    const dialog=document.createElement('dialog');dialog.setAttribute('aria-label','Inst\xe2ncias do Evolution');dialog.style.cssText='width:min(620px,90vw);padding:24px;border:1px solid #bdd3df;border-radius:10px';
    const title=document.createElement('h2');title.textContent='Inst\xe2ncias do Evolution';
    const message=document.createElement('p');message.setAttribute('role','status');message.textContent='Consultando WhatsApp\u2026';
    const list=document.createElement('div');const close=document.createElement('button');close.type='button';close.textContent='Fechar';close.className='button';close.onclick=()=>dialog.close();
    dialog.append(title,message,list,close);document.body.append(dialog);dialog.onclose=()=>dialog.remove();dialog.showModal();
    const endpoint='/admin/addons/evolution/index.php?instances=1';
    async function request(options){const r=await fetch(endpoint,{credentials:'same-origin',cache:'no-store',...options});let data;try{data=await r.json();}catch{throw Error('Sess\xe3o expirada ou resposta inv\xe1lida. Entre novamente no MK-AUTH.');}if(!r.ok)throw Error(data.error||'Falha na consulta.');return data;}
    try{
     const data=await request();message.textContent=data.instances.length?'Selecione para preencher os campos. Depois clique em Gravar.':'Nenhuma inst\xe2ncia WhatsApp encontrada na Evolution local.';
     for(const item of data.instances){
      const row=document.createElement('div');row.style.cssText='display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 0;border-bottom:1px solid #ddd';
      const label=document.createElement('span');label.textContent=item.name+' \u2014 '+(item.state==='open'?'\u25cf WhatsApp conectado':item.state==='connecting'?'\u25d0 Conectando':'\u25cb WhatsApp desconectado');label.style.color=item.state==='open'?'#087b40':'#a13927';
      const select=document.createElement('button');select.type='button';select.className='button is-info';select.textContent='Usar esta inst\xe2ncia';
      select.onclick=async()=>{select.disabled=true;try{
       const chosen=await request({method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({name:item.name,csrf:data.csrf})});
       host.value=chosen.address;instance.value=chosen.name;key.value=chosen.token;if(type)type.value='evolution2_api';
       for(const input of [host,instance,key,type].filter(Boolean))for(const event of ['input','change'])input.dispatchEvent(new Event(event,{bubbles:true}));
       note.textContent='Inst\xe2ncia '+chosen.name+' preenchida \u2014 '+(chosen.state==='open'?'WhatsApp conectado.':'WhatsApp desconectado.')+' Clique em Gravar para salvar.';dialog.close();
      }catch(error){message.textContent=error.message;select.disabled=false;}};
      row.append(label,select);list.append(row);
     }
    }catch(error){message.textContent=error.message;}
   };
  }
  if(host.value.trim()&&!new URLSearchParams(location.search).has('vpscloud_evolution'))return;
  host.value=__EVOLUTION_NATIVE_ADDRESS__;
  if(type){type.value='evolution2_api';type.dispatchEvent(new Event('change',{bubbles:true}));}
  host.dispatchEvent(new Event('input',{bubbles:true}));host.dispatchEvent(new Event('change',{bubbles:true}));
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',fill);else fill();
})();
/* VPSCLOUD-EVOLUTION-END */
