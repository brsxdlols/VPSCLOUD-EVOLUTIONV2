const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../addon/Recibo_Evolution/index.php'),'utf8');
const start=source.indexOf("document.getElementById('toggleReceipts').onchange="),end=source.indexOf("document.getElementById('importNative').onclick",start);
assert(start>0&&end>start);const control={dataset:{enabled:'1'},checked:false,attributes:{},setAttribute(k,v){this.attributes[k]=v}},nodes={toggleReceipts:control,receiptSwitchLabel:{},receiptMasterStatus:{}};
let calls=0,fail=false,consent=true,lastValue;
const context={document:{getElementById:k=>nodes[k]},confirm:()=>consent,payload:()=>new Map(),request:async d=>{calls++;lastValue=d.get('enabled');if(fail)throw Error('simulated save failure');return {enabled:lastValue==='1'}}};
vm.runInNewContext(source.slice(start,end),context);
(async()=>{
 await control.onchange();assert.equal(lastValue,'0');assert.equal(control.dataset.enabled,'0');assert.equal(control.attributes['aria-checked'],'false');
 control.checked=true;consent=false;const before=calls;await control.onchange();assert.equal(calls,before);assert.equal(control.checked,false);
 consent=true;fail=true;control.checked=true;await control.onchange();assert.equal(control.checked,false);assert.equal(control.dataset.enabled,'0');
 fail=false;control.checked=true;await control.onchange();assert.equal(control.checked,true);assert.equal(control.dataset.enabled,'1');assert.equal(control.attributes['aria-checked'],'true');assert.equal(nodes.receiptSwitchLabel.textContent,'Ativado');
 console.log('PASS receipt switch saves state, cancels activation, restores after failure and updates accessible status');
})().catch(e=>{console.error(e);process.exitCode=1});
