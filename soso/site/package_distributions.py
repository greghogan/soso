"""Create current ordinary ZIP distributions; never generate standalone HTML files."""
from pathlib import Path
import argparse,hashlib,json,re,zipfile
from .build_catalog import discover,event_landing,portable_navigation
from .build_standalone import Compiler, license_files
ROOT=Path(__file__).resolve().parents[2]
def zipped(files):
 import io
 stream=io.BytesIO()
 with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for name,data in sorted(files.items()):
   info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(0o100755 if name.endswith('.sh') and data.startswith(b'#!') else 0o100644)<<16
   z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
 return stream.getvalue()
def inventory(files):return {name:{"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()} for name,data in sorted(files.items())}
def runtime(root,event):
 base=Path(root)/event['path'];compiler=Compiler(base,include_pdfs=True);bundle=compiler.compile()
 files={name:(base/name).read_bytes() for name in bundle['sources']}
 for name,data in list(files.items()):
  if name.endswith('.html'):files[name]=portable_navigation(data.decode()).encode()
 landing=portable_navigation(event_landing(root,event))
 landing=landing.replace('href="../../../shared/reader-navigation.css"','href="web/navigation.css"')
 landing=re.sub(r'<a class="back-link"[^>]*>All events</a>','<span class="site-name">Science Olympiad</span>',landing)
 landing=landing.replace('</footer>','<p><a href="LICENSE.md">Licensing &amp; exceptions</a></p></footer>')
 files.update(license_files(root))
 files['index.html']=landing.encode()
 files['README.txt']=('Open index.html after extracting this event folder. All guide pages, model pages, assets and current PDFs are local. External source citations optionally use the internet. These ZIPs are ordinary multi-file offline bundles; a separate on-demand script can produce a single embedded HTML.\n').encode()
 files['MANIFEST.json']=json.dumps(inventory(files),sort_keys=True,indent=2).encode()+b'\n'
 return files
def verify(path):
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  names=z.namelist();assert len(names)==len(set(names))
  key='MANIFEST.json'
  prefix=''
  records=json.loads(z.read(key))
  assert set(names)=={prefix+n for n in records}|{key}
  for name,record in records.items():
   data=z.read(prefix+name);assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256']
 return len(records)
def packages(root):
 if not discover(root):raise ValueError('No generated events found; run ./build.sh first or select a candidate directory with --project-root.')
 result={}
 for event in discover(root):
  result[event['slug']+'-'+event['year']+'-offline.zip']=runtime(root,event)
 return result
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-directory',type=Path,default=ROOT/'build/distributions',help='ZIP output directory (default: build/distributions)')
 parser.add_argument('--project-root',type=Path,default=ROOT/'build/candidates',help='Generated candidate tree (default: build/candidates)')
 args=parser.parse_args();out=args.output_directory.resolve()
 if out.is_relative_to(ROOT) and not out.is_relative_to(ROOT/'build'):
  parser.error('Choose an output directory under build/ or outside the source project')
 out.mkdir(parents=True,exist_ok=True)
 built=packages(args.project_root);results=[]
 for name,files in built.items():
  target=out/name
  if target.exists():parser.error('Refusing to overwrite '+str(target)+'; use a new explicit output directory')
 for name,files in built.items():
  target=out/name;data=zipped(files);target.write_bytes(data);count=verify(target)
  results.append({'path':str(target),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'verified_members':count})
 print(json.dumps(results,indent=2))
if __name__=='__main__':main()

