const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const cp=require('node:child_process');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'install-7070-replace-v1.sh'),'utf8');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'evolution-tests-'));
let passed=0;
function test(name,fn){fn();passed++;console.log('PASS',name)}
const mock=`#!/bin/sh
printf '%s\\n' "$*" >> "$MOCK_LOG"
case "$1 $2" in
 'container inspect')
  case "$SCENARIO:$3" in
   v1:evolution_api|api-stopped:evolution_v2_api|missing-env:evolution_v2_api|wrong-network:evolution_v2_api|partial:evolution_v2_postgres) exit 0;;
  esac; exit 1;;
 'volume inspect') [ "$SCENARIO" = orphan-volume ]; exit $?;;
 'ps -a') [ "$SCENARIO" != nonstandard ] || echo custom/evolution-api:v1; exit 0;;
 'volume ls') exit 0;;
esac
if [ "$1" = inspect ]; then
 case "$3" in
  *Running*) [ "$SCENARIO" = api-stopped ] && echo false || echo true;;
  *NetworkMode*) echo other_network;;
 esac
 exit 0
fi
echo UNEXPECTED_MUTATION >&2; exit 97
`;
test('POSIX syntax for every shell script',()=>{
 for(const f of fs.readdirSync(root).filter(f=>f.endsWith('.sh'))){const r=cp.spawnSync('sh',['-n',path.join(root,f)],{encoding:'utf8'});assert.equal(r.status,0,r.stderr)}
});
for(const [scenario,message] of [['diagnose',''],['v1','V1 encontrada'],['orphan-volume','volume preexistente'],['nonstandard','nomes diferentes'],['api-stopped','API parada'],['missing-env','ENV ausente'],['wrong-network','topologia nao padrao'],['partial','Estado parcial']]){
 test('preflight '+scenario,()=>{
  const dir=path.join(tmp,scenario);fs.mkdirSync(dir);const bin=path.join(dir,'bin');fs.mkdirSync(bin);fs.writeFileSync(path.join(bin,'id'),'#!/bin/sh\nprintf 0\n',{mode:0o755});fs.writeFileSync(path.join(bin,'docker'),mock,{mode:0o755});
  for(const dep of ['curl','openssl'])fs.writeFileSync(path.join(bin,dep),'#!/bin/sh\necho UNEXPECTED_MUTATION >&2\nexit 97\n',{mode:0o755});
  const project=path.join(dir,'project');
  if(['api-stopped','wrong-network'].includes(scenario)){fs.mkdirSync(project);fs.writeFileSync(path.join(project,'evolution-v2.env'),'TEST=1\n')}
  const script=source.replaceAll('/opt/vpscloud-evolution-v2',project).replaceAll('/root/evolution-v1-backups',path.join(dir,'legacy')).replaceAll('/run/lock/vpscloud-evolution-install.lock',path.join(dir,'lock'));
  const file=path.join(dir,'install.sh');fs.writeFileSync(file,script);const log=path.join(dir,'calls');
  const r=cp.spawnSync('sh',[file],{encoding:'utf8',env:{...process.env,PATH:bin+':'+process.env.PATH,MOCK_LOG:log,SCENARIO:scenario,EVOLUTION_MODE:scenario==='diagnose'?'diagnose':'apply'}});
  assert.equal(r.status,scenario==='diagnose'?0:1,r.stdout+r.stderr);assert.ok(r.stdout.includes(message),r.stdout+r.stderr);
  const calls=fs.readFileSync(log,'utf8');assert.ok(!/UNEXPECTED_MUTATION/.test(r.stderr));assert.ok(!/^(run|stop|rm|pull|exec|rename|start) /m.test(calls),calls);
 });
}
test('repair requires explicit instance confirmation',()=>{
 const r=cp.spawnSync('sh',[path.join(root,'evolution-reconnect.sh'),'MKAUTH'],{encoding:'utf8',env:{...process.env,EVOLUTION_CONFIRM_RECONNECT:''}});assert.equal(r.status,2);assert.ok(r.stdout.includes('novo QR'));
});
test('repair does not log out after failed backup',()=>{
 const helper=path.join(tmp,'failed-backup');fs.writeFileSync(helper,'#!/bin/sh\nexit 17\n',{mode:0o755});
 const r=cp.spawnSync('sh',[path.join(root,'evolution-reconnect.sh'),'MKAUTH'],{encoding:'utf8',env:{...process.env,EVOLUTION_CONFIRM_RECONNECT:'MKAUTH',EVOLUTION_BACKUP_HELPER:helper}});assert.equal(r.status,17);
});
test('backup restarts API after dump failure',()=>{
 const dir=path.join(tmp,'backup-failure');fs.mkdirSync(dir);const bin=path.join(dir,'bin');fs.mkdirSync(bin);fs.writeFileSync(path.join(bin,'id'),'#!/bin/sh\nprintf 0\n',{mode:0o755});const project=path.join(dir,'project');fs.mkdirSync(project);
 const log=path.join(dir,'calls');const docker=`#!/bin/sh
printf '%s\\n' "$*" >> "$MOCK_LOG"
if [ "$1" = inspect ]; then
 case "$3" in
  *Running*) echo true;;
  *Destination*) printf '/var/lib/postgresql/data\\n/data\\n';;
  *Image*) echo sha256:test;;
  *) echo '[]';;
 esac; exit 0
fi
case "$1 $2" in
 'image save') echo fake-image; exit 0;;
esac
if [ "$1" = exec ]; then
 if [ "$3" = pg_dump ]; then exit 22; fi
 case "$*" in *process.stdout.write*) echo fake-test-only-password;; esac
 exit 0
fi
case "$1" in stop|start) exit 0;; esac
exit 97
`;
 fs.writeFileSync(path.join(bin,'docker'),docker,{mode:0o755});
 let s=fs.readFileSync(path.join(root,'evolution-backup.sh'),'utf8').replace('/run/lock/vpscloud-evolution-session.lock',path.join(dir,'lock'));
 const file=path.join(dir,'backup.sh');fs.writeFileSync(file,s);
 const r=cp.spawnSync('sh',[file],{encoding:'utf8',env:{...process.env,PATH:bin+':'+process.env.PATH,MOCK_LOG:log,EVOLUTION_PROJECT_DIR:project}});
 assert.equal(r.status,22,r.stdout+r.stderr);assert.match(fs.readFileSync(log,'utf8'),/start evolution_v2_api/);assert.ok(!fs.existsSync(path.join(project,'backups/LATEST-SESSION-BACKUP')));
});
const patcher=source.split("<<'MANAGER_PATCH'\n")[1].split('\nMANAGER_PATCH')[0];
const patchdir=path.join(tmp,'manager');fs.mkdirSync(patchdir);const bundle=path.join(patchdir,'index-fixture.js');
const original='function fixture(){const d="fixture",f=x=>globalThis.route=x;const m=x=>{f(`/manager/instance/${d}/chat/${x}`)};return globalThis.button={className:"w-full justify-start gap-2 px-2 text-left",children:[]};}fixture();';
const patchfile=path.join(tmp,'patch.cjs');fs.writeFileSync(patchfile,patcher.replace('const dir="/patch"','const dir='+JSON.stringify(patchdir)));
test('Manager patch validates syntax and accepts local number',()=>{
 fs.writeFileSync(bundle,original);const r=cp.spawnSync(process.execPath,[patchfile],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);
 const context={window:{prompt:()=>'(16) 98877-8656',alert:()=>{throw Error('unexpected alert')}}};vm.createContext(context);vm.runInContext(fs.readFileSync(bundle,'utf8'),context);context.button.onClick();assert.equal(context.route,'/manager/instance/fixture/chat/5516988778656@s.whatsapp.net');
});
test('Manager patch is idempotent',()=>{const before=fs.readFileSync(bundle,'utf8');const r=cp.spawnSync(process.execPath,[patchfile]);assert.equal(r.status,0);assert.equal(fs.readFileSync(bundle,'utf8'),before)});
test('Manager unknown bundle is rejected without mutation',()=>{fs.writeFileSync(bundle,'const different=true;');const r=cp.spawnSync(process.execPath,[patchfile]);assert.notEqual(r.status,0);assert.equal(fs.readFileSync(bundle,'utf8'),'const different=true;')});
if(fs.existsSync('/evolution/manager/dist/assets'))test('patch matches Manager from pinned image',()=>{
 const files=fs.readdirSync('/evolution/manager/dist/assets').filter(x=>/^index-.*\.js$/.test(x));assert.equal(files.length,1);
 fs.writeFileSync(bundle,fs.readFileSync('/evolution/manager/dist/assets/'+files[0]));const r=cp.spawnSync(process.execPath,[patchfile],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);
});
if(fs.existsSync('/evolution/manager/dist/assets'))test('fresh Manager phone clipboard and logo transforms',()=>{
 const dir=path.join(tmp,'fresh-manager');const staging=dir+'.new';fs.mkdirSync(staging);fs.mkdirSync(staging+'/assets');
 const asset=fs.readdirSync('/evolution/manager/dist/assets').find(x=>/^index-.*\.js$/.test(x));const target=staging+'/assets/'+asset;fs.copyFileSync('/evolution/manager/dist/assets/'+asset,target);
 const start=source.indexOf('MATCHES="$(\n');const end=source.indexOf('patch_chat_button "$(find "$MANAGER_DIR.new/assets"',start);assert.ok(start>0&&end>start);
 const body=source.slice(start,end);const r=cp.spawnSync('sh',['-eu','-c',body],{encoding:'utf8',env:{...process.env,MANAGER_DIR:dir,OLD_LOGO_URL:'https://evolution-api.com/files/evo/evolution-logo-white.svg',OLD_LOGO_URL_ALT:'https://evolution-api.com/files/evo/evolution-logo.svg'}});assert.equal(r.status,0,r.stdout+r.stderr);
 const js=fs.readFileSync(target,'utf8');const syntax=cp.spawnSync(process.execPath,['--input-type=module','--check'],{input:js,encoding:'utf8'});assert.equal(syntax.status,0,syntax.stderr.slice(-1000));assert.ok(js.includes('document.execCommand("copy")'));assert.ok(js.includes('"55"+h.number.replace'));assert.ok(js.includes('/manager/logo-header.jpg'));
});
test('safety invariants',()=>{
 assert.ok(!source.includes('API_KEY="123456"'));assert.ok(!source.includes('node ./dist/src/main.js'));
 assert.ok(!source.includes('docker rm -f "$API_CONTAINER"'));assert.ok(!source.includes('remove_v1()'));
 assert.ok(source.includes('evolution-api@sha256:'));assert.ok(source.includes('EVOLUTION_MODE:-apply'));
 const cleanup=fs.readFileSync(path.join(root,'cleanup.sh'),'utf8');assert.ok(!/DELETE FROM|FLUSHALL|FLUSHDB|prune|rm -rf/.test(cleanup));
});
console.log(passed+' checks passed. No live deployment or WhatsApp test was performed.');
fs.rmSync(tmp,{recursive:true,force:true});
