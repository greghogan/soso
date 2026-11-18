"""Native SVG cues shared by the offline HTML renderers."""
from pathlib import Path
import re
def icon(kind):
 s=(Path(__file__).parent/'learning-icons'/(kind+'.svg')).read_text()
 s=re.sub(r'<title>.*?</title>','',s)
 s=s.replace('stroke="#17313c"','stroke="currentColor"')
 s=re.sub(r' role="[^"]*"','',s)
 return s.replace('<svg ','<svg aria-hidden="true" focusable="false" style="width:1.44em;height:1.44em;vertical-align:-.29em;display:inline-block;margin-right:.4em" ',1)
