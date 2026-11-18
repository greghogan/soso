(function(root){'use strict';
const model=typeof module!=='undefined'&&module.exports?require('./model.js'):root.ThermoModels;
function svg(g,removed){
 const s=Math.min(4.3,300/(g.width+10)),cx=185,y0=370,x=v=>cx+v*s,y=z=>y0-z*s,f=n=>n.toFixed(1);
 const line=(x1,y1,x2,y2,stroke='#526874',extra='')=>`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" ${/stroke-width=/.test(extra)?'':'stroke-width="2"'} ${extra}/>`;
 const text=(xx,yy,t,extra='')=>`<text x="${xx}" y="${yy}" ${extra}>${t}</text>`;
 const cup=(xx,zz)=>`<path d="M${x(xx-3.81)} ${y(zz+10.16)} L${x(xx-2.7)} ${y(zz)} L${x(xx+2.7)} ${y(zz)} L${x(xx+3.81)} ${y(zz+10.16)} Z" fill="#e2f4f9" stroke="#315f9c" stroke-width="1.8"/><path d="M${x(xx-3.1)} ${y(zz+3.4)} L${x(xx-2.7)} ${y(zz)} L${x(xx+2.7)} ${y(zz)} L${x(xx+3.1)} ${y(zz+3.4)} Z" fill="#8fcdde"/>`;
 let a=`<svg xmlns="http://www.w3.org/2000/svg" class="diagram" viewBox="0 0 720 490" role="img" aria-labelledby="g-title g-desc"><title id="g-title">Lamp and reflector side and plan views</title><desc id="g-desc">Bulb bottom ${g.lamp} centimetres above the testing surface. Proposed device ${f(g.width)} by ${f(g.depth)} by ${f(g.height)} centimetres. The cup is ${removed?'removed and separate':'inserted'}. Maximum envelope is 30 centimetres on each side.</desc><defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto-start-reverse"><path d="M0 0 L7 3.5 L0 7" fill="none" stroke="#526874"/></marker></defs><rect width="720" height="490" fill="white"/><g font-family="system-ui,sans-serif" font-size="13" fill="#15333f">`;
 a+=text(20,25,'SIDE VIEW','font-weight="700"')+line(20,y0,365,y0)+text(20,y0+25,'Testing surface · height datum');
 a+=`<rect x="${x(-15)}" y="${y(30)}" width="${30*s}" height="${30*s}" fill="#edf4fc" fill-opacity=".5" stroke="#315f9c" stroke-width="1.5" stroke-dasharray="6 4"/>`+text(x(-15)-4,y(30)-10,'30 cm rule envelope');
 a+=`<path d="M${x(-8)} ${y(g.lamp+2)} Q${x(0)} ${y(g.lamp+12)} ${x(8)} ${y(g.lamp+2)} Z" fill="#e5e9eb" stroke="#526874"/><ellipse cx="${x(0)}" cy="${y(g.lamp+1)}" rx="9" ry="4.3" fill="#f4d77c" stroke="#a86d16"/>`;
 a+=line(x(0),y(g.lamp),x(0),y0,'#99aeb5','stroke-dasharray="4 5"');
 a+=line(55,y0,55,y(g.lamp),'#315f9c','marker-start="url(#arrow)" marker-end="url(#arrow)"')+line(60,y(g.lamp),x(0),y(g.lamp),'#315f9c','stroke-dasharray="3 3"');
 a+=text(48,(y0+y(g.lamp))/2,`${g.lamp} cm`,'text-anchor="middle" transform="rotate(-90 48 '+((y0+y(g.lamp))/2)+')"')+text(20,y(g.lamp)-16,'Bulb bottom');
 a+=`<rect x="${x(-g.base/2)}" y="${y(1)}" width="${g.base*s}" height="${s}" fill="#087b85"/>`;
 for(const sign of [-1,1]) a+=line(x(sign*g.opening/2),y(g.lower),x(sign*g.panelWidth/2),y(g.lower+g.rise),'#087b85','stroke-width="5"');
 a+=line(x(-g.opening/2),y(g.lower),x(-g.opening/2),y(1),'#087b85')+line(x(g.opening/2),y(g.lower),x(g.opening/2),y(1),'#087b85');
 a+=cup(removed?34:0,1);
 if(removed) a+=text(x(27),y(14),'Cup separate','font-size="11"');
 else a+=line(x(0),y(13),x(0),y(Math.min(g.lamp-3,26)),'#526874','marker-end="url(#arrow)" stroke-dasharray="4 3"');
 a+=line(x(-g.width/2),y0+45,x(g.width/2),y0+45,'#087b85','marker-start="url(#arrow)" marker-end="url(#arrow)"')+text(cx,y0+65,`${f(g.width)} cm overall width`,'text-anchor="middle"');
 a+=text(390,25,'PLAN VIEW','font-weight="700"');
 const px=530,py=205,ps=Math.min(4.5,230/(g.width+10));
 a+=`<circle cx="${px}" cy="${py}" r="${15*ps}" fill="none" stroke="#315f9c" stroke-width="1.5" stroke-dasharray="5 4"/><rect x="${px-15*ps}" y="${py-15*ps}" width="${30*ps}" height="${30*ps}" fill="none" stroke="#315f9c" stroke-dasharray="5 4"/><rect x="${px-g.width/2*ps}" y="${py-g.depth/2*ps}" width="${g.width*ps}" height="${g.depth*ps}" fill="#087b85" fill-opacity=".08" stroke="#087b85"/><circle cx="${px}" cy="${py}" r="${3.81*ps}" fill="#e2f4f9" stroke="#315f9c"/><circle cx="${px}" cy="${py}" r="3" fill="#a86d16"/>`;
 a+=line(px,py,px+15*ps,py,'#315f9c','marker-end="url(#arrow)"')+text(px+20,py-10,'15 cm','font-size="12"');
 a+=`<path d="M${px+21*ps} ${py-45} V${py+45} M${px+21*ps} ${py} H${px+28*ps}" fill="none" stroke="#526874" stroke-width="7"/>`;
 a+=text(392,310,'Stand parts stay outside the circle.')+text(392,332,'Circle centered on bulb axis.')+text(392,354,'Stand shape is an example, not a rule.')+text(392,392,'Opening is fixed during the run.')+text(392,414,'Lift only the cup; leave all device')+text(392,436,'components behind.');
 a+='</g></svg>';return a;
}
if(typeof module!=='undefined'&&module.exports){module.exports={svg};return;}
let removed=false;const ids=['base','opening','rise','angle'];const $=id=>document.getElementById(id);
function populate(){const old=Number($('lamp').value)||45;$('lamp').innerHTML=model.heights($('level').value).map(n=>`<option value="${n}">${n} cm</option>`).join('');$('lamp').value=model.heights($('level').value).includes(old)?old:45;}
function update(){const o={level:$('level').value,lamp:Number($('lamp').value)};ids.forEach(id=>{o[id]=Number($(id).value);$(id+'-out').textContent=o[id]+(id==='angle'?'°':' cm');});const g=model.geometry(o);const drawing=svg(g,removed);$('drawing').innerHTML=drawing.replace('class="diagram"','class="diagram wide-view"')+'<div class="narrow-views">'+drawing.replace('viewBox="0 0 720 490"','viewBox="0 0 380 490"').replace(/g-title/g,'g-title-side').replace(/g-desc/g,'g-desc-side').replace(/arrow/g,'arrow-side')+drawing.replace('viewBox="0 0 720 490"','viewBox="380 0 340 490"').replace(/g-title/g,'g-title-plan').replace(/g-desc/g,'g-desc-plan').replace(/arrow/g,'arrow-plan')+'</div>';$('size').textContent=`${g.width.toFixed(1)} × ${g.depth.toFixed(1)} × ${g.height.toFixed(1)} cm`;$('gap').textContent=g.gap.toFixed(1)+' cm';$('margin').textContent=g.sideMargin.toFixed(2)+' cm';const problems=[];if(!g.fits)problems.push('This proposed geometry exceeds the 30 cm envelope.');if(!g.cupClear)problems.push('The opening is too narrow for the largest approximate cup mouth.');$('status').className='status'+(problems.length?' bad':'');$('status').textContent=problems.length?problems.join(' '):'The simplified geometry fits inside the envelope and has mouth-width clearance. Check the actual cup, fasteners, grip and material safety before building.';}
$('level').addEventListener('change',()=>{populate();update();});$('controls').addEventListener('input',update);$('lamp').addEventListener('change',update);$('reset').addEventListener('click',()=>{$('controls').reset();removed=false;$('cup').textContent='Show cup removed';populate();update();});$('cup').addEventListener('click',()=>{removed=!removed;$('cup').textContent=removed?'Show cup inserted':'Show cup removed';update();});populate();update();
})(typeof globalThis!=='undefined'?globalThis:this);
