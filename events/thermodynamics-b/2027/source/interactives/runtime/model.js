/* Original instructional models. No runtime dependencies. See README.md. */
(function (root) {
'use strict';
const num=(v,min,max)=>{v=Number(v); if(!Number.isFinite(v)||v<min||v>max) throw new RangeError('Value outside model domain'); return v;};
function heights(level){return level==='national'?Array.from({length:26},(_,i)=>40+i):level==='state'?[40,45,50,55]:[40,45,50];}
function geometry(o){
 const level=o.level||'regional', lamp=num(o.lamp,40,65), base=num(o.base,16,34), opening=num(o.opening,7,12), rise=num(o.rise,4,24), angle=num(o.angle,30,80);
 if(!heights(level).includes(lamp))throw new RangeError('Height is not allowed at this tournament level');
 const lower=7, panelWidth=opening+2*rise/Math.tan(angle*Math.PI/180), width=Math.max(base,panelWidth), height=Math.max(11.16,lower+rise), gap=lamp-height;
 return {level,lamp,base,opening,rise,angle,lower,panelWidth,width,depth:base,height,gap,fits:width<=30+1e-9&&base<=30&&height<=30,cupClear:opening>7.62,sideMargin:(opening-7.62)/2};
}
function temperature(o,seconds){
 const p=num(o.power,0,20), ua=num(o.loss,0,1), extra=num(o.extra,0,500), start=num(o.start,10,35), room=num(o.room,15,30), t=num(seconds,0,900), c=418+extra;
 return ua===0?start+p*t/c:room+p/ua+(start-room-p/ua)*Math.exp(-ua*t/c);
}
function heat(o){const minutes=num(o.minutes,10,15),end=temperature(o,minutes*60),room=Number(o.room),gain=end-Number(o.start),capacity=418+Number(o.extra),netAtEnd=Number(o.power)-Number(o.loss)*(end-room);return {end,gain,capacity,netAtEnd,waterEnergy:418*gain,deviceEnergy:Number(o.extra)*gain,points:Array.from({length:61},(_,i)=>({t:i*minutes*60/60,T:temperature(o,i*minutes*60/60)}))};}
const api={heights,geometry,temperature,heat}; if(typeof module!=='undefined'&&module.exports)module.exports=api;root.ThermoModels=api;
})(typeof globalThis!=='undefined'?globalThis:this);
