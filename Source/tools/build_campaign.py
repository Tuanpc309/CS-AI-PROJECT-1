"""Reproducible campaign authoring: variations are accepted only after BFS replay.

Run from repository root: python Source/tools/build_campaign.py
No runtime generation: players load the reviewed, committed JSON files.
"""
from __future__ import annotations
from collections import deque
from copy import deepcopy
import json
from pathlib import Path
import random
import sys

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
from loader import level_from_dict
from engine import available_actions, transition, is_goal, occupied_cells
from models import TransitionStatus

OUT = SOURCE / 'web' / 'levels'
BIOMES = ['forest', 'dusk', 'neon', 'cavern', 'celestial']
TITLES = [
 ['Mầm xanh','Nắng qua lá','Lối rêu','Đảo nhỏ','Khúc quanh','Tán rừng'],
 ['Gạch hoàng hôn','Mây qua cầu','Dải hổ phách','Bước chân nhẹ','Đền mây','Sau ánh chiều'],
 ['Tín hiệu đầu','Đèn qua mưa','Một kết nối','Hai tín hiệu','Mạch sáng','Giao lộ đêm'],
 ['Hai mảnh pha lê','Tiếng vọng','Hai bờ','Đường hội ngộ','Hồ ký ức','Hợp âm'],
 ['Quỹ đạo','Bản đồ sao','Điểm giao','Vòng thiên thể','Mê cung tĩnh','Qua miền sao']]
SUBTITLES = ['Lăn khối giữa những tán cây. Đứng thẳng vào ô đích.',
 'Nằm xuống trên gạch cam, căn lại tư thế qua những cây cầu hẹp.',
 'Theo các tín hiệu: nút tròn nhận mọi tư thế, nút X cần đứng thẳng.',
 'Hai nửa, hai con đường. Đổi khối bằng Space rồi tìm nơi hội ngộ.',
 'Kết hợp những điều đã học: tách khối, công tắc, cầu và gạch cam.']

def search(data):
    level, start = level_from_dict(data)
    queue = deque([start]); parent = {start: None}; edge = {}; expanded=0
    while queue:
        state=queue.popleft(); expanded+=1
        if is_goal(level,state):
            actions=[]; states=[state]
            while parent[state] is not None:
                actions.append(edge[state].value);state=parent[state];states.append(state)
            return {'optimal':len(actions),'solution':actions[::-1], 'expanded':expanded}, states
        for action in available_actions(state):
            step=transition(level,state,action)
            if step.status in (TransitionStatus.VALID,TransitionStatus.WIN) and step.next_state not in parent:
                parent[step.next_state]=state;edge[step.next_state]=action;queue.append(step.next_state)
        if expanded>100000: return None, []
    return None, []

def raw(grid,start,goal):
    grid=[list(row) for row in grid];grid[goal[0]][goal[1]]='G'
    return dict(id='candidate',grid=[''.join(row) for row in grid],start=list(start),goal=list(goal),bridges=[],switches=[])

def candidate(stage, seed):
    rng=random.Random(seed)
    if stage==0:
        h,w=rng.randint(5,9),rng.randint(7,13)
        grid=[['.']*w for _ in range(h)]
        for r in range(1,h-1):
            for c in range(1,w-1): grid[r][c]='F'
        # Different clearings/corners, with a broad starting terrace.
        for _ in range(seed%8):
            r,c=rng.randrange(1,h-1),rng.randrange(3,w-1)
            grid[r][c]='.'
        return raw(grid,(1,1),(h-2,w-2))
    if stage==1:
        data=json.loads((OUT/'templates/fragile.json').read_text(encoding='utf-8'))
        grid=[list(row.replace('G','F')) for row in data['grid']]
        for _ in range(seed%5):
            r,c=rng.choice([(r,c) for r in range(1,7) for c in [1,2,9,10]])
            grid[r][c]='.'
        for r in [7,8]: grid[r][7]='B'
        start=rng.choice([(1,1),(2,1),(1,2),(3,1),(4,1)])
        goal=rng.choice([(1,9),(1,10),(2,10),(2,9),(3,10)])
        grid[start[0]][start[1]]='F';grid[goal[0]][goal[1]]='G'
        data.update(grid=[''.join(row) for row in grid],start=list(start),goal=list(goal),
          bridges=[dict(id='cloud_walk',cells=[[7,7],[8,7]],initial_enabled=True)])
        return data
    if stage==2:
        data=json.loads((OUT/'templates/switches.json').read_text(encoding='utf-8'))
        grid=[list(row.replace('G','F')) for row in data['grid']]
        start=rng.choice([(7,1),(6,1),(7,2),(5,1)])
        goal=rng.choice([(7,13),(8,13),(6,13),(7,12)])
        grid[start[0]][start[1]]='F';grid[goal[0]][goal[1]]='G'
        if seed%2==0:
            # First half introduces one signal; second half will select dual ones.
            heavy=data['switches'].pop(); r,c=heavy['cell'];grid[r][c]='F'
            data['switches'][0]['effects'].append(dict(bridge_id='exit_bridge',operation='SET_OPEN'))
        for _ in range(seed%4):
            r,c=rng.choice([(5,2),(6,2),(8,2),(5,12),(6,12),(8,12)])
            if [r,c] not in [list(start),list(goal)]: grid[r][c]='.'
        data.update(grid=[''.join(row) for row in grid],start=list(start),goal=list(goal))
        return data
    base='split_01' if stage==3 and seed%2==0 else 'split_02' if stage==3 else 'combined_02'
    data=json.loads((SOURCE/'levels'/f'{base}.json').read_text(encoding='utf-8'))
    width=(rng.randint(10,16) if stage==3 else rng.randint(17,22));height=8
    grid=[list(row.replace('G','F').ljust(width,'.')) for row in data['grid']]
    grid.extend([['.']*width for _ in range(height-len(grid))])
    if stage==3:
        for c in range(4,width-1): grid[4][c]='F' if grid[4][c]=='.' else grid[4][c]
        for c in range(rng.randint(5,7),width-1):grid[5][c]='F'
        if seed%3==0:
            for c in range(6,width-2):grid[6][c]='F'
        goal=(rng.choice([4,5]),width-2)
    else:
        # The split puzzle feeds a two-row fragile crossing, a heavy signal and
        # a final closed bridge. No side path bypasses the amber band.
        for c in range(4,7):grid[4][c]='F' if grid[4][c]=='.' else grid[4][c]
        for c in range(4,width-1):grid[5][c]='F'
        for c in range(4,7):grid[6][c]='F'
        for r in [4,5]:
            for c in range(7,11):grid[r][c]='O'
            for c in [11,12]:grid[r][c]='B'
            for c in range(13,width-1):grid[r][c]='F'
        for c in range(13,width-1):grid[6][c]='F'
        signal=rng.choice([(4,4),(4,5),(4,6),(5,5),(5,6)])
        if grid[signal[0]][signal[1]]!='F':signal=(5,5)
        grid[signal[0]][signal[1]]='X'
        data['bridges'].append(dict(id='stellar_exit',cells=[[r,c] for r in [4,5] for c in [11,12]],initial_enabled=False))
        data['switches'].append(dict(id='stellar_signal',cell=list(signal),type='HEAVY',effects=[dict(bridge_id='stellar_exit',operation='SET_OPEN')]))
        goal=(rng.choice([4,5,6]),width-2)
    grid[goal[0]][goal[1]]='G'
    data.update(grid=[''.join(row) for row in grid],goal=list(goal))
    return data

def main():
    manifest={'version':1,'levels':[]};proofs={};pending={}
    for stage,biome in enumerate(BIOMES):
        pool=[];signatures=set()
        for seed in range(1,161):
            data=candidate(stage,seed)
            data['biomeId']=biome
            signature=(tuple(data['grid']),tuple(data['start']),tuple(data['goal']))
            if signature in signatures:continue
            signatures.add(signature)
            try: proof,states=search(data)
            except ValueError:continue
            if not proof or proof['optimal']<4:continue
            if stage in [1,4]:
                level,_=level_from_dict(data)
                if not any(level.tile_at(cell)=='O' for state in states for cell in occupied_cells(state)):continue
            if stage>=3 and not any(state.mode.value=='SPLIT' for state in states):continue
            pool.append((data,proof))
            if len(pool)>=48:break
        if len(pool)<6:raise RuntimeError(f'Not enough valid maps for {biome}: {len(pool)}')
        if stage==2:
            singles=sorted([p for p in pool if len(p[0]['switches'])==1],key=lambda p:p[1]['optimal'])
            doubles=sorted([p for p in pool if len(p[0]['switches'])==2],key=lambda p:p[1]['optimal'])
            chosen=[singles[int((len(singles)-1)*i/2)] for i in range(3)]+[doubles[int((len(doubles)-1)*i/2)] for i in range(3)]
        else:
            pool.sort(key=lambda p:(p[1]['optimal'],p[1]['expanded']))
            chosen=[pool[int((len(pool)-1)*i/5)] for i in range(6)]
        for local,(data,proof) in enumerate(chosen):
            number=stage*6+local+1;key=f'campaign_{number:02d}';data['id']=key
            pending[key]=data
            mechanics=['floor']+(['fragile','narrow-bridge'] if stage==1 else ['soft-switch','bridge'] if stage==2 else ['split'] if stage==3 else ['fragile','split','soft-switch','heavy-switch','bridge'] if stage==4 else [])
            if stage==2 and len(data['switches'])==2:mechanics.append('heavy-switch')
            proof['difficultyScore']=proof['optimal']+len(data['switches'])*5+stage*8
            proofs[key]=proof
            manifest['levels'].append(dict(id=key,file=f'{key}.json',title=TITLES[stage][local],subtitle=SUBTITLES[stage],difficulty=stage+1,difficultyLabel=['Làm quen','Căn tư thế','Kết nối','Phân mảnh','Tổng hợp'][stage],mechanics=mechanics,biomeId=biome,chapter=stage+1,chapterLevel=local+1))
        print(biome,[p[1]['optimal'] for p in chosen],flush=True)
    # Validate all five groups before touching the campaign on disk.
    for key,data in pending.items():
        (OUT/f'{key}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'solutions.json').write_text(json.dumps(proofs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'campaign.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
