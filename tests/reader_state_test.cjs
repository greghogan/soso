"use strict";
/* Unit-level DOM/history doubles: not a browser or device execution test. */
const fs=require("node:fs"),vm=require("node:vm"),path=require("node:path"),assert=require("node:assert/strict");
const support=process.argv[2]; let checks=0;
function check(value,message){assert.ok(value,message);checks++;}
class Element {
  constructor(tag){this.tag=tag;this.listeners={};this.children=[];this.attrs={};this.hidden=false;this.disabled=false;this.textContent="";this.contentWindow={messages:[],state:{},postMessage(message){this.messages.push(message);},focus(){},print(){}};}
  addEventListener(type,fn){this.listeners[type]=fn;}
  appendChild(child){this.children.push(child);}
  setAttribute(name,value){this.attrs[name]=value;}
}
const elements={};
for(const id of ["bundle-data","reader-status","pages","page-title","back","forward","home","print","pdf-list","pdf-menu"])elements[id]=new Element("div");
elements["bundle-data"].textContent=JSON.stringify({title:"2027 Thermodynamics B",entry:"web/index.html",pages:{"web/index.html":{html:"<p>Home</p>",title:"Study guide | 2027 Thermodynamics B"},"web/model.html":{html:"<p>Model</p>",title:"Model | Thermodynamics B 2027"}},assets:{},pdfs:[]});
const events={},location={hash:"",href:"file:///tmp/one-standalone.html"},entries=[{state:null,hash:""}];let cursor=0;
const window={addEventListener(type,fn){events[type]=fn;}};
const history={get state(){return entries[cursor].state;},replaceState(state){entries[cursor].state=state;},pushState(state,_,hash){entries.splice(cursor+1);entries.push({state,hash});cursor++;location.hash=hash;},back(){if(cursor){cursor--;location.hash=entries[cursor].hash;events.popstate();}},forward(){if(cursor+1<entries.length){cursor++;location.hash=entries[cursor].hash;events.popstate();}}};
const document={getElementById(id){return elements[id];},createElement(tag){return new Element(tag);},body:new Element("body")};
vm.runInNewContext(fs.readFileSync(path.join(support,"reader.js"),"utf8"),{window,document,history,location,URLSearchParams,URL:{createObjectURL(){return "blob:unit";}},Blob,Uint8Array,atob});
const home=elements.pages.children[0];home.listeners.load();home.contentWindow.state.radius=.2;
check(elements["page-title"].textContent==="Study guide | Thermodynamics B","toolbar omits repeated event year");
check(home.title==="Study guide | 2027 Thermodynamics B","frame metadata keeps event year");
const send=(frame,page,fragment="")=>events.message({source:frame.contentWindow,data:{channel:"science-olympiad-standalone-v1",type:"navigate",page,fragment}});
check(elements.back.disabled,"no back before first internal navigation");
send(home,"web/model.html");
const model=elements.pages.children[1];model.listeners.load();model.contentWindow.state.power=12;
check(elements["page-title"].textContent==="Model | Thermodynamics B","toolbar handles event-first metadata too");
check(!elements.back.disabled&&home.hidden&&!model.hidden,"model selected");
history.back();
check(!home.hidden&&model.hidden&&home.contentWindow.state.radius===.2,"back restores original frame and control state");
history.forward();
check(model.contentWindow.state.power===12&&!model.hidden,"forward preserves model state");
send(model,"web/index.html","answer");
check(elements.pages.children.length===2,"repeated flow reuses frames");
check(home.contentWindow.messages.at(-1).fragment==="answer","fragment delivered");
history.back();history.forward();
check(home.contentWindow.state.radius===.2,"repeated back/forward preserves control value");
const current=elements["page-title"].textContent;
events.message({source:{},data:{channel:"science-olympiad-standalone-v1",type:"navigate",page:"web/model.html"}});
check(elements["page-title"].textContent===current,"foreign frame navigation rejected");
send(home,"missing.html");
check(elements["page-title"].textContent===current,"unknown route rejected");
elements.home.listeners.click();
check(elements.pages.children.length===2,"contents does not duplicate readers");

const posted=[],opened=[],bridgeEvents={},ancestor={tagName:"DETAILS",open:false,parentElement:null},target={parentElement:ancestor,tagName:"DIV",scrollIntoView(){this.scrolled=true;}};
const parent={postMessage(message){posted.push(message);},location:{href:"file:///tmp/one-standalone.html#old"}};
const bridgeDoc={addEventListener(type,fn){bridgeEvents[type]=fn;},getElementById(){return target;}};
vm.runInNewContext(fs.readFileSync(path.join(support,"bridge.js"),"utf8"),{document:bridgeDoc,parent,window:{addEventListener(type,fn){bridgeEvents[type]=fn;},open(url){opened.push(url);}}});
function click(attributes,modified=false){const e={target:{closest(){return {hasAttribute(k){return k in attributes;},getAttribute(k){return attributes[k];}};}},ctrlKey:modified,preventDefault(){this.prevented=true;}};bridgeEvents.click(e);return e;}
check(click({"data-so-page":"web/model.html","data-so-fragment":"plot"}).prevented,"native subframe navigation suppressed");
check(posted.at(-1).page==="web/model.html","cross-page route message");
click({"data-so-page":"web/model.html","data-so-fragment":"plot"},true);
check(opened[0].startsWith("file:///tmp/one-standalone.html#page="),"modified click opens same standalone file");
click({"data-so-separate-pdf":""});
check(posted.at(-1).type==="pdf-separate","separate PDF produces a notice, not a missing-file request");
bridgeEvents.message({source:parent,data:{channel:"science-olympiad-standalone-v1",type:"scroll",fragment:"answer"}});
check(ancestor.open&&target.scrolled,"anchor reveals its enclosing answer");

if(process.argv[3]){
  const dir=process.argv[3],m=require(path.join(dir,"model.js"));
  const g={level:"regional",lamp:45,base:28,opening:9,rise:10,angle:50};
  check(m.geometry(g).fits&&m.geometry(g).cupClear,"embedded geometry default");
  check(!m.geometry({...g,base:31}).fits,"embedded oversize flag");
  check(!m.geometry({...g,opening:7}).cupClear,"embedded cup-removal flag");
  const h={power:7,loss:.3,extra:100,start:22,room:22,minutes:10};
  check(Math.abs(m.temperature({...h,loss:0},600)-(22+4200/518))<1e-10,"embedded zero-loss energy balance");
  check(m.heat({...h,extra:500}).end<m.heat(h).end,"embedded thermal-mass control trend");
  const nodes={};
  function node(value){return {value:String(value),defaultValue:String(value),textContent:"",attrs:{},handlers:{},addEventListener(t,fn){this.handlers[t]=fn;},setAttribute(k,v){this.attrs[k]=v;}};}
  const initial={"radius-ratio":.1,"distance-ratio":1,"temperature-ratio":300};
  const outputs=["ratio-value","depth-value","radius-explain","transit-planet","transit-curve","transit-bottom","distance-value","flux-value","temperature-value","flux-planet","flux-explain","thermal-value","power-value","peak-value"];
  for(const [id,value] of Object.entries(initial))nodes[id]=node(value);
  for(const id of outputs)nodes[id]=node("");
  const doc={getElementById(id){return nodes[id]||null;},querySelectorAll(){return [];}};
  vm.runInNewContext(fs.readFileSync(path.join(dir,"solar-guide.js"),"utf8"),{document:doc});
  check(nodes["depth-value"].textContent==="1.00%","embedded transit initialized");
  nodes["radius-ratio"].value=".2";nodes["radius-ratio"].handlers.input();
  check(nodes["depth-value"].textContent==="4.00%"&&nodes["transit-bottom"].textContent==="0.9600","embedded transit input updates");
  nodes["distance-ratio"].value="2";nodes["distance-ratio"].handlers.input();
  check(nodes["flux-value"].textContent==="0.250 ×","embedded flux input updates");
  nodes["temperature-ratio"].value="600";nodes["temperature-ratio"].handlers.input();
  check(nodes["power-value"].textContent==="16.00 ×","embedded thermal input updates");
}
console.log(JSON.stringify({unit_checks:checks,passed:true,browser_execution:false}));

