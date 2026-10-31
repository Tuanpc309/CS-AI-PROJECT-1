"""All 30 committed levels solve through the real engine and required mechanics."""
from collections import deque, Counter
import json
from pathlib import Path
import pytest
from engine import available_actions, transition, is_goal, occupied_cells
from loader import load_level, level_from_dict, LevelFormatError
from models import Action, Algorithm, SearchConfig, TransitionStatus
from solvers import solve

ROOT=Path(__file__).resolve().parents[1]/'web'/'levels'
MANIFEST=json.loads((ROOT/'campaign.json').read_text(encoding='utf-8'))
PROOFS=json.loads((ROOT/'solutions.json').read_text(encoding='utf-8'))

def reachable_goal(level,start,allow):
 queue=deque([start]);seen={start}
 while queue:
  state=queue.popleft()
  if is_goal(level,state):return True
  for action in available_actions(state):
   step=transition(level,state,action)
   if step.status in (TransitionStatus.VALID,TransitionStatus.WIN) and allow(step) and step.next_state not in seen:
    seen.add(step.next_state);queue.append(step.next_state)
 return False

def test_thirty_unique_maps_group_into_five_ordered_chapters():
 items=MANIFEST['levels'];assert len(items)==30
 assert [i['id'] for i in items]==[f'campaign_{i:02d}' for i in range(1,31)]
 assert Counter(i['biomeId'] for i in items)==dict.fromkeys(['forest','dusk','neon','cavern','celestial'],6)
 signatures=[]
 for index,item in enumerate(items):
  assert item['chapter']==index//6+1 and item['chapterLevel']==index%6+1
  level,_=load_level(ROOT/item['file']);assert level.biome_id==item['biomeId']
  signatures.append((level.grid,level.start,level.goal))
 assert len(set(signatures))==30

@pytest.mark.parametrize('item',MANIFEST['levels'],ids=lambda item:item['id'])
def test_all_levels_have_bfs_optimal_replay_and_use_introduced_mechanics(item):
 level,state=load_level(ROOT/item['file']);proof=PROOFS[item['id']]
 result=solve(level,state,Algorithm.BFS,SearchConfig(time_limit_seconds=2,measure_memory=False))
 assert result.found and result.solution_length==proof['optimal']
 pressed=set();touched_orange=False;split=False
 for direction in proof['solution']:
  step=transition(level,state,Action(direction));assert step.status in (TransitionStatus.VALID,TransitionStatus.WIN)
  state=step.next_state;split|=state.mode.value=='SPLIT'
  touched_orange|=any(level.tile_at(cell)=='O' for cell in occupied_cells(state))
  pressed.update(e.object_id for e in step.events if e.kind=='SWITCH_PRESSED')
 assert is_goal(level,state) and len(proof['solution'])==proof['optimal']
 assert pressed=={switch.id for switch in level.switches}
 if item['chapter'] in (2,5):assert touched_orange
 if item['chapter']>=4:assert split
 if item['chapter']==1:assert not level.bridges and not level.switches and 'O' not in ''.join(level.grid)

@pytest.mark.parametrize('number',[7,12,25,30])
def test_orange_bands_cannot_be_bypassed(number):
 level,start=load_level(ROOT/f'campaign_{number:02d}.json')
 assert not reachable_goal(level,start,lambda step:all(level.tile_at(cell)!='O' for cell in occupied_cells(step.next_state)))

@pytest.mark.parametrize('number',[13,18,19,24,25,30])
def test_each_switch_is_necessary_in_representative_maps(number):
 level,start=load_level(ROOT/f'campaign_{number:02d}.json')
 for switch in level.switches:
  assert not reachable_goal(level,start,lambda step:not any(e.kind=='SWITCH_PRESSED' and e.object_id==switch.id for e in step.events)),switch.id

def test_biome_metadata_is_optional_for_legacy_and_rejects_unknown_values():
 legacy=json.loads((ROOT/'quiet_01.json').read_text(encoding='utf-8'))
 assert level_from_dict(legacy)[0].biome_id=='forest'
 for invalid in ['desert',None,[],123]:
  with pytest.raises(LevelFormatError):level_from_dict({**legacy,'biomeId':invalid})
