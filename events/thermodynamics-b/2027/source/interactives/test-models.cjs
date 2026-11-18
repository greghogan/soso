'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const dir=path.resolve(__dirname,'runtime'),m=require(path.join(dir,'model.js')),gsvg=require(path.join(dir,'geometry.js')),hsvg=require(path.join(dir,'heat-flow.js'));
const xmlSamples=[];
let checks=0;const check=(x,msg)=>{assert.ok(x,msg);checks++;};
const g={level:'regional',lamp:45,base:28,opening:9,rise:10,angle:50};
check(m.geometry(g).fits,'default fits');check(m.geometry(g).cupClear,'default cup clearance');check(m.geometry({...g,base:31}).fits===false,'oversize base rejected');check(m.geometry({...g,opening:7}).cupClear===false,'small opening flagged');check(m.geometry({...g,rise:24}).height===31,'height includes lower reflector edge');check(m.geometry({...g,rise:4}).height===11.16,'cup top includes 1 cm base');check(m.geometry({...g,angle:70}).width<=m.geometry({...g,angle:40}).width,'steeper panels reduce footprint');assert.throws(()=>m.geometry({...g,lamp:41}));checks++;check(m.geometry({...g,level:'national',lamp:41}).lamp===41,'national one-cm steps');
for(const level of ['regional','state','national'])for(const lamp of m.heights(level))for(const angle of [30,50,80])for(const rise of [4,10,24]){let z=m.geometry({...g,level,lamp,angle,rise});check(Number.isFinite(z.width)&&Number.isFinite(z.gap),'finite geometry');check(z.gap===lamp-z.height,'correct bottom-bulb datum');for(const removed of [false,true]){const svg=gsvg.svg(z,removed);xmlSamples.push(svg);check(!/NaN|Infinity|undefined/.test(svg),'finite svg strings');}}
const h={power:7,loss:.3,extra:100,start:22,room:22,minutes:10};
check(m.temperature(h,0)===22,'initial condition');check(Math.abs(m.temperature({...h,loss:0},600)-(22+4200/518))<1e-10,'zero-loss energy balance');check(m.heat({...h,power:0}).end===22,'equilibrium unchanged');check(m.heat({...h,extra:500}).end<m.heat(h).end,'extra capacity slows same-start heating');check(m.heat({...h,loss:.8}).end<m.heat(h).end,'greater loss lowers temperature');check(m.heat({...h,power:12}).end>m.heat(h).end,'more absorbed power warms more');check(m.heat({...h,power:0,start:10,room:22}).end>10,'room heats a colder system');check(m.heat({...h,power:0,start:35,room:22}).end<35,'hot system cools');
for(const power of [0,7,20])for(const loss of [0,.05,1])for(const extra of [0,100,500])for(const start of [10,22,35])for(const room of [15,22,30])for(const minutes of [10,15]){let o={power,loss,extra,start,room,minutes},r=m.heat(o);check(Number.isFinite(r.end),'finite heat solution');check(r.points.length===61,'curve samples');const eq=loss?room+power/loss:Infinity;check(r.end>=Math.min(start,eq)-1e-9&&r.end<=Math.max(start,eq)+1e-9,'approaches equilibrium without overshoot');const svg=hsvg.svg(o,h);xmlSamples.push(svg);check(!/NaN|Infinity|undefined/.test(svg),'finite chart svg');}
assert.throws(()=>m.heat({...h,power:-1}));assert.throws(()=>m.geometry({...g,angle:0}));checks+=2;
for(const fn of ['geometry.html','heat-flow.html']){const s=fs.readFileSync(path.join(dir,fn),'utf8');check(!/(?:src=["']https?:|<link\b[^>]*href=["']https?:)/i.test(s),'no remote runtime asset');check(!s.includes('type="module"'),'classic scripts');}
// Parse generated SVG as XML, not forgiving HTML. Python stdlib rejects duplicate attributes.
for(const name of ['geometry-default.svg','geometry-removal.svg','heat-flow-default.svg'])xmlSamples.push(fs.readFileSync(path.resolve(__dirname,'../../assets/diagrams',name),'utf8'));
const parsed=Number(require('node:child_process').execFileSync('python3',['-c',
'import json,sys,xml.etree.ElementTree as ET; samples=json.load(sys.stdin); [ET.fromstring(s) for s in samples]; print(len(samples))'
],{input:JSON.stringify(xmlSamples),encoding:'utf8',maxBuffer:1024*1024}));
check(parsed===xmlSamples.length,'all generated SVG strings and static files parse as XML');
checks+=parsed;
const result={checks,xml_documents_parsed:parsed,passed:true,geometry_default:m.geometry(g),heat_default:m.heat(h).end,notes:['Finite model domain and rule geometry checked.','Browser UI and real hardware performance are separate checks.']};
const reportDir=path.resolve(__dirname,'../../../../../build/interactive-qa/thermodynamics-b/2027');
fs.mkdirSync(reportDir,{recursive:true});fs.writeFileSync(path.join(reportDir,'model-tests.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
