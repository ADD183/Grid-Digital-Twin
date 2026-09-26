import sys
sys.path.insert(0, r'd:\Projects\Grid-Digital-Twin')
from src.engine import trigger_scenario

for scale in [1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 2.8, 3.0, 3.5, 4.0]:
    try:
        net, meta = trigger_scenario('infeasible', magnitude=scale)
        v = meta['initial_violations']
        print('SCALE', scale, 'conv=', v['converged'], 'total=', v['total_violations'], 'min=', v['summary'].get('min_vm_pu'), 'max=', v['summary'].get('max_vm_pu'), 'max_load=', v['summary'].get('max_line_loading_percent'))
    except Exception as e:
        print('ERR', scale, type(e).__name__, e)
