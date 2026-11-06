const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const html=fs.readFileSync(path.join(__dirname,'../monitor.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
function setup(failSave=false){
 const elements={};const node=()=>({value:'',textContent:'',disabled:false,hidden:false,checked:false,append(){},replaceChildren(){},addEventListener(){},showModal(){this.open=true},close(){this.open=false}});
 const document={getElementById(id){return elements[id]||(elements[id]=node())},createElement:node};
 const calls=[];
 const fetch=async(url,options)=>{
  calls.push({url,options});const isSave=options.method==='POST'&&url.endsWith('/config');
  const data=failSave&&isSave?{error:'Falha de validacao'}:options.method==='GET'?{config:{label:'Test',docker:{chat:'-100',hasToken:true},instances:[]},names:[],status:{healthy:true,last_check:Date.now()/1000}}:{saved:true,sent:true};
  return {ok:!(failSave&&isSave),json:async()=>data};
 };
 const context={document,location:{reload(){}},Date,Set,fetch};
 vm.createContext(context);vm.runInContext(script,context);document.getElementById('dockerToken').value='fake-test-token';document.getElementById('dockerChat').value='-100';
 return {context,calls,elements,document};
}
(async()=>{
 const a=setup();await a.context.saveAndTest(null,a.document.getElementById('testDocker'));
 assert.deepEqual(a.calls.map(x=>x.options.method+' '+x.url),['POST /monitor/api/config','POST /monitor/api/test','GET /monitor/api/config']);assert.ok(a.elements.notice.textContent.includes('teste enviado'));assert.equal(a.elements.testDocker.disabled,false);
 const b=setup(true);await b.context.saveAndTest(null,b.document.getElementById('testDocker'));assert.equal(b.calls.length,1);assert.ok(b.elements.notice.textContent.includes('Não foi possível salvar'));assert.equal(b.elements.testDocker.disabled,false);
 assert.ok(html.includes('id="openGuide"'));assert.ok(html.indexOf('id="openGuide"')>html.indexOf('id="panel" hidden'));assert.ok(html.includes('id="guide"'));assert.ok(html.includes('https://t.me/BotFather'));assert.ok(html.includes('getUpdates'));assert.ok(!html.includes('>Testar Telegram</button>'));
 a.elements.openGuide.onclick();assert.equal(a.elements.guide.open,true);a.elements.closeGuide.onclick();assert.equal(a.elements.guide.open,false);
 console.log('PASS save-before-test ordering, no send after save failure, feedback, and post-login bot tutorial');
})().catch(e=>{console.error(e);process.exitCode=1});
