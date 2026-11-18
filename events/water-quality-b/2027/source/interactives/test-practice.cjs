const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const root=path.join(__dirname,'runtime');
const nodes={};const document={getElementById:id=>nodes[id]||(nodes[id]={value:'',textContent:'',hidden:false,focus(){this.focused=true;}}),querySelectorAll:()=>[]};
const html=fs.readFileSync(path.join(root,'calibration.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const context=vm.createContext({document,Number,Math});vm.runInContext(script,context);
assert.strictEqual(vm.runInContext('interpolate(20).value',context),1);
assert.strictEqual(vm.runInContext('interpolate(42).value',context),6);
assert.strictEqual(vm.runInContext('interpolate(64).value',context),10);
assert.strictEqual(vm.runInContext('interpolate(19)',context),null);
assert.strictEqual(vm.runInContext('interpolate(NaN)',context),null);
document.getElementById('reading').value='42';document.getElementById('estimate').value='6.0';nodes.check.onclick();assert(nodes.feedback.textContent.includes('agrees'));
nodes.reading.value='';nodes.check.onclick();assert(nodes.feedback.textContent.includes('Choose a reading'));
nodes.reset.onclick();assert.strictEqual(nodes.estimate.value,'');assert.strictEqual(nodes.feedback.textContent,'');
console.log('Water Quality calibration: 9 checks passed (not browser execution)');
// Exercise retrieval reveal/reset and monitoring feedback without a browser.
function page(name,replacement){
 const els={},details=[{open:true}];
 const document={getElementById:id=>els[id]||(els[id]={value:'',textContent:'',hidden:false,focus(){this.focused=true;}}),querySelectorAll:()=>details};
 let script=fs.readFileSync(path.join(root,name),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
 if(replacement)script=script.replace('@@ORGANISMS@@',JSON.stringify(replacement));
 vm.runInNewContext(script,{document,Number,Math});return {els,details};
}
const project=path.resolve(__dirname,'../../../../..');
const records=JSON.parse(require('child_process').execFileSync('python3',['-c',
 "import json,sys;from pathlib import Path;sys.path.insert(0,'shared');from identification_practice import practice_records;from provenance import atlas,supplemental;p=Path('events/water-quality-b/2027');print(json.dumps(practice_records(atlas(p)['organisms'],supplemental(p))))"],{cwd:project,encoding:'utf8'}));
const expectedCount=JSON.parse(fs.readFileSync(path.join(__dirname,'../organisms.json'),'utf8')).organisms.filter(r=>r.practice!==false&&r.image).length+JSON.parse(fs.readFileSync(path.join(__dirname,'../supplemental-images.json'),'utf8')).photos.filter(r=>r.practice!==false).length;
assert.strictEqual(records.length,expectedCount);
assert(records.filter(r=>r.organism_id==='snapper').length>=4);
assert(records.filter(r=>r.organism_id==='sweetlips').length>=2);
const practice=page('practice.html',records).els;
assert(!practice.photo.alt.includes(records[0].name));
assert(practice.answer.hidden && practice.credit.hidden && practice['credit-links'].hidden);
practice.reveal.onclick();assert(!practice.answer.hidden && !practice.credit.hidden && !practice['credit-links'].hidden);
assert(practice['image-source'].href.startsWith('https://'));assert(practice['image-license'].href.startsWith('https://'));
practice.guess.value='test';practice.next.onclick();assert(practice.answer.hidden);assert.strictEqual(practice.guess.value,'');assert(practice.progress.textContent.startsWith('Example 2'));
practice.reset.onclick();assert(practice.progress.textContent.startsWith('Example 1'));assert(practice.answer.hidden);
practice['practice-mode'].value='fish';practice['practice-mode'].onchange();
const fishCount=records.filter(r=>['snapper','sweetlips'].includes(r.organism_id)).length;
assert(practice.progress.textContent.endsWith('of '+fishCount));
const seen=new Set();
for(let i=0;i<fishCount;i++){
 assert(practice.answer.hidden && practice.credit.hidden && practice['credit-links'].hidden);
 assert(practice.photo.alt.startsWith('Unlabeled'));seen.add(practice.photo.src);
 practice.reveal.onclick();assert(!practice.answer.hidden);assert(practice.credit.textContent.length>0);
 assert(practice['image-license'].href.startsWith('https://'));
 practice.next.onclick();
}
assert.strictEqual(seen.size,fishCount);assert(practice.progress.textContent.startsWith('Example 1'));
practice['practice-mode'].value='all';practice['practice-mode'].onchange();
assert(practice.progress.textContent.endsWith('of '+records.length));
// Every added photograph must retain its own rights metadata and avoid pre-reveal answers.
const allSeen=new Set();
for(const record of records){
 assert.strictEqual(practice.photo.src,record.image);
 assert(practice.photo.alt.startsWith('Unlabeled'));
 assert(practice.answer.hidden && practice.credit.hidden && practice['credit-links'].hidden);
 allSeen.add(practice.photo.src);
 practice.reveal.onclick();
 assert.strictEqual(practice.photo.alt,record.alt||record.diagnostic);
 assert.strictEqual(practice.credit.textContent,record.caption);
 assert(record.caption.length>0);
 assert.strictEqual(practice['image-source'].href,record.image_source);
 assert.strictEqual(practice['image-license'].href,record.image_license_url);
 assert(record.image_source.startsWith('https://'));
 assert(record.image_license_url.startsWith('https://'));
 practice.next.onclick();
}
assert.strictEqual(allSeen.size,records.length);
assert(practice.progress.textContent.startsWith('Example 1'));
console.log(`Water Quality identification: all ${records.length} photos retain neutral prompts and reveal credits`);

const monitoring=page('monitoring.html');
for(const [value,expected] of [['','Select'],['cause','Too strong'],['compare','Supported'],['safe','Equal temperature']]){
 monitoring.els.claim.value=value;monitoring.els.check.onclick();assert(monitoring.els.feedback.textContent.startsWith(expected));
}
monitoring.els.reset.onclick();assert.strictEqual(monitoring.els.claim.value,'');assert.strictEqual(monitoring.els.feedback.textContent,'');assert(!monitoring.details[0].open);
console.log('Water Quality retrieval reveal/reset, credits and monitoring branches passed (not browser execution)');

practice['exercise-mode'].value='described';practice['exercise-mode'].onchange();
assert.strictEqual(practice.photo.alt,records[0].alt||records[0].diagnostic);
assert.strictEqual(practice['image-description'].textContent,practice.photo.alt);
assert(!practice['image-description'].hidden && practice.answer.hidden);
practice.next.onclick();assert.strictEqual(practice.photo.alt,records[1].alt||records[1].diagnostic);
practice['exercise-mode'].value='photo';practice['exercise-mode'].onchange();
assert(practice['image-description'].hidden && practice.photo.alt.startsWith('Unlabeled'));
assert(fs.readFileSync(path.join(root,'practice.html'),'utf8').includes('aria-live="polite" aria-atomic="true"'));
console.log('Described-image alternative and answer announcement markup passed');

practice.reveal.onclick();assert(practice.answer.focused);
