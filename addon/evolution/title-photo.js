;(function(){
 if(window.__vpscloudTitlePhoto||!/\/admin\/send_titulo\.hhvm$/.test(location.pathname))return;window.__vpscloudTitlePhoto=true;
 const form=document.getElementById('form'),text=document.getElementById('texto_wapp'),kind=document.getElementById('tiposend');if(!form||!text||!kind)return;
 const panel=document.createElement('section');panel.style.cssText='background:white;padding:16px;border:1px solid #b9cddb;border-radius:8px;margin:12px 0';panel.id='vpscloud-title-photo';
 const label=document.createElement('label');label.style.cssText='display:flex;gap:10px;align-items:center;font-weight:bold';const enabled=document.createElement('input');enabled.type='checkbox';enabled.id='vpscloud-title-photo-enabled';label.append(enabled,document.createTextNode('Anexar foto \xe0 mensagem'));
 const help=document.createElement('p');help.textContent='A mensagem abaixo ser\xe1 a legenda da foto. Voc\xea pode manter ENVIAR PDF para enviar tamb\xe9m o boleto.';
 const upload=document.createElement('input');upload.type='file';upload.accept='image/jpeg,image/png,image/gif';upload.setAttribute('aria-label','Foto do envio manual');upload.hidden=true;
 const preview=document.createElement('img');preview.alt='Pr\xe9via da foto';preview.hidden=true;preview.style.cssText='max-width:180px;max-height:130px;margin:12px 0';
 const status=document.createElement('p');status.setAttribute('role','status');status.style.cssText='margin-top:8px;color:#345367';panel.append(label,help,upload,preview,status);(text.closest('.field')||text).insertAdjacentElement('beforebegin',panel);
 const endpoint='/admin/addons/evolution/index.php?titlephoto=1',nativeSubmit=HTMLFormElement.prototype.submit.bind(form);let busy=false,blob='';
 function active(){return enabled.checked&&kind.value==='wapp'}
 function refresh(){panel.hidden=kind.value!=='wapp';upload.hidden=!enabled.checked;if(!enabled.checked)preview.hidden=true;else if(blob)preview.hidden=false;}
 enabled.onchange=refresh;kind.addEventListener('change',refresh);refresh();
 upload.onchange=()=>{if(blob)URL.revokeObjectURL(blob);blob='';preview.hidden=true;const file=upload.files[0];if(!file)return;if(file.size>2*1024*1024){upload.value='';status.textContent='Selecione uma foto PNG, JPG ou GIF de at\xe9 2 MiB.';return;}blob=URL.createObjectURL(file);preview.src=blob;preview.hidden=false;status.textContent='Foto selecionada. Ela ser\xe1 anexada quando voc\xea clicar em Enviar.';};
 async function request(options){const r=await fetch(endpoint,{credentials:'same-origin',cache:'no-store',...options});let body;try{body=await r.json();}catch{throw Error('Atualize o instalador para habilitar fotos no envio de t\xedtulos.');}if(!r.ok)throw Error(body.error||'N\xe3o foi poss\xedvel preparar a foto.');return body;}
 async function send(){
  if(!active()){nativeSubmit();return;}if(busy)return;busy=true;const original=text.value;
  try{
   const file=upload.files[0];if(!file||file.size>2*1024*1024)throw Error('Selecione uma foto PNG, JPG ou GIF de at\xe9 2 MiB.');
   status.textContent='Preparando a foto\u2026';const challenge=await request();const data=new FormData();data.set('csrf',challenge.csrf);data.set('photo',file);
   const photo=await request({method:'POST',body:data});if(!/^\[VPSCLOUD_TITLE_PHOTO:[a-f0-9]{48}\]$/.test(photo.marker))throw Error('Resposta inv\xe1lida ao preparar a foto.');
   text.value=original+'\n'+photo.marker;nativeSubmit();
  }catch(error){text.value=original;status.textContent=error.message;busy=false;const button=document.getElementById('enviar_msg');if(button){button.disabled=false;button.removeAttribute('disabled');}}
 }
 form.addEventListener('submit',event=>{if(active()){event.preventDefault();event.stopImmediatePropagation();send();}},true);form.submit=send;
 window.addEventListener('pageshow',()=>{busy=false;text.value=text.value.replace(/\r?\n\[VPSCLOUD_TITLE_PHOTO:[a-f0-9]{48}\]\s*$/,'');refresh();});
 window.addEventListener('beforeunload',()=>{if(blob)URL.revokeObjectURL(blob)});
})();
