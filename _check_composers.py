import json

# ASMA cache
with open('asma_cache.json') as f:
    asma = json.load(f)
tracks = asma.get('tracks', [])
print(f'ASMA tracks: {len(tracks)}')
# ASMA paths contain composer info like GAMES/A-F/Airball/Follin_Tim/
follin_asma = [t for t in tracks if 'follin' in t.get('path','').lower()]
tel_asma = [t for t in tracks if 'jeroen' in t.get('path','').lower() or 'tel_jeroen' in t.get('path','').lower()]
# Also check name field
follin_asma2 = [t for t in tracks if 'follin' in t.get('name','').lower()]
tel_asma2 = [t for t in tracks if ('jeroen' in t.get('name','').lower() and 'tel' in t.get('name','').lower())]
print(f'ASMA - Tim Follin (path): {len(follin_asma)}')
print(f'ASMA - Tim Follin (name): {len(follin_asma2)}')
print(f'ASMA - Jeroen Tel (path): {len(tel_asma)}')
if follin_asma:
    for t in follin_asma[:10]:
        print(f'  {t.get("name","?")} — {t.get("path","?")}')

# AY cache
print()
with open('ay_cache.json') as f:
    ay = json.load(f)
print(f'AY cache: {type(ay)}')
if isinstance(ay, dict):
    print(f'  keys: {list(ay.keys())[:5]}')
elif isinstance(ay, list):
    print(f'  len: {len(ay)}')
    if ay:
        print(f'  sample: {ay[0]}')

# Check ay directory more thoroughly
import os
ay_dir = 'archiwum/ay'
ay_files = os.listdir(ay_dir)
print(f'AY files on disk: {len(ay_files)}')
follin_ay = [f for f in ay_files if 'follin' in f.lower()]
tel_ay = [f for f in ay_files if 'tel_' in f.lower() or 'jeroen' in f.lower()]
print(f'AY - Tim Follin: {len(follin_ay)}')
for f in follin_ay[:5]: print(f'  {f}')
print(f'AY - Jeroen Tel: {len(tel_ay)}')
for f in tel_ay[:5]: print(f'  {f}')
