"""Audit saved development rows against the public physical time equation."""
from pathlib import Path
import json
root=Path(__file__).resolve().parents[2]
rows=0;worst=0.
for problem in (3,4):
    for path in (root/f'problem{problem}/results/iterations_v4').glob('unionmass*.json'):
        result=json.loads(path.read_text(encoding='utf8'))
        for branch in result['branches'].values():
            for row in branch['rows']:
                st=row['sim']
                expected=st['movement_m']/5+5*st['measure']+st['switch']+3*st['failed_clear']+5*st['cleared_count']
                error=abs(expected-st['virtual_time_s'])
                if error>1e-6:raise AssertionError((path,row['id'],error))
                if not row['full']:raise AssertionError((path,row['id'],'not full'))
                if not row['policy']['completion_certified']:raise AssertionError((path,row['id'],'no certificate'))
                rows+=1;worst=max(worst,error)
print(json.dumps({'all_rows_full_and_certified':rows,'maximum_time_equation_error_s':worst}))
