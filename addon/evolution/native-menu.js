/* VPSCLOUD-EVOLUTION-BEGIN */
;(function(){
 if(window.__vpscloudEvolutionMenu)return;window.__vpscloudEvolutionMenu=true;
 if(typeof add_menu!=='undefined'&&typeof add_menu.provedor==='function'){
  add_menu.provedor(JSON.stringify({plink:location.origin+'/admin/addons/evolution/',ptext:'Evolution API',picone:'fa fa-whatsapp'}));
  add_menu.provedor(JSON.stringify({plink:location.origin+'/admin/addons/evolution/?view=monitor',ptext:'Evolution · Alertas Telegram',picone:'fa fa-bell'}));
 }
 function fill(){
  if(!/\/admin\/conf_zap_serv\.hhvm$/.test(location.pathname))return;
  const host=document.querySelector('input[name="wapp_host"],input#wapp_host,input[name="host"],input[name="servidor"]');
  const type=document.querySelector('select[name="wapp_servidor"],select#wapp_servidor')||Array.from(document.querySelectorAll('select')).find(s=>Array.from(s.options).some(o=>o.value==='evolution2_api'));
  if(!host||host.type==='password')return;
  if(host.value.trim()&&!new URLSearchParams(location.search).has('vpscloud_evolution'))return;
  host.value=__EVOLUTION_NATIVE_ADDRESS__;
  if(type){type.value='evolution2_api';type.dispatchEvent(new Event('change',{bubbles:true}));}
  host.dispatchEvent(new Event('input',{bubbles:true}));host.dispatchEvent(new Event('change',{bubbles:true}));
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',fill);else fill();
})();
/* VPSCLOUD-EVOLUTION-END */
