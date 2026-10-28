import json, re
from pathlib import Path
from collections import Counter

BASE=Path(__file__).resolve().parents[1]
DATA=BASE/'dist/data'
parts=[json.loads((DATA/name).read_text(encoding='utf-8')) for name in ('china.json','core.json','others.json','cthulhu.json')]
traditions=sum(parts,[])
errors=[]
ids=[]
expansions=[]
for filename in sorted(DATA.glob('expansion-*.json')):
    expansion=json.loads(filename.read_text(encoding='utf-8-sig'))
    expansions.append(expansion)
    for addition in expansion.get('traditions',[]):
        target=next((t for t in traditions if t['id']==addition['id']),None)
        if target is None:
            errors.append(f'{filename.name}: unknown tradition {addition["id"]}')
            continue
        for field in ('entities','events','artifacts','groups','relations','sources'):
            target.setdefault(field,[]).extend(addition.get(field,[]))
global_entities={e['id'] for t in traditions for e in t['entities']}
global_events={e['id'] for t in traditions for e in t['events']}
global_nodes=global_entities|{a['id'] for t in traditions for a in t.get('artifacts',[])}
for t in traditions:
    t.setdefault('artifacts',[])
    t.setdefault('groups',[])
    ids.append(t['id'])
    es=global_entities
    relation_ids=global_nodes
    ss={s['id'] for s in t['sources']}
    for e in t['entities']+t['artifacts']:
        ids.append(e['id'])
        if e['tier'] not in (1,2,3): errors.append(f"{e['id']}: bad tier")
        if not e.get('detail'): errors.append(f"{e['id']}: no detail")
        for source in e['sources']:
            if source not in ss: errors.append(f"{e['id']}: missing source {source}")
    evs=global_events
    for a in t['artifacts']:
        for owner in a.get('owners',[]):
            if owner not in es: errors.append(f'{a["id"]}: missing owner {owner}')
        for event in a.get('events',[]):
            if event not in evs: errors.append(f'{a["id"]}: missing event {event}')
    for group in t['groups']:
        ids.append(group['id'])
        if group['source'] not in ss: errors.append(f'{group["id"]}: missing source {group["source"]}')
        for member in group['members']:
            if member not in es: errors.append(f'{group["id"]}: missing member {member}')
    for key,n in Counter(s['id'] for s in t['sources']).items():
        if n>1: errors.append(f'{t["id"]}: duplicate source {key}')
    for r in t['relations']:
        for endpoint in ('from','to'):
            if r[endpoint] not in relation_ids: errors.append(f"{t['id']}: bad relation {r[endpoint]}")
        if r['source'] not in ss: errors.append(f"{t['id']}: relation missing source {r['source']}")
    for e in t['events']:
        ids.append(e['id'])
        for actor in e['actors']:
            if actor not in es: errors.append(f"{e['id']}: missing actor {actor}")
        if e['source'] not in ss: errors.append(f"{e['id']}: missing source {e['source']}")
    for section in ('worldview','history','quotes'):
        for item in t[section]:
            if item['source'] not in ss: errors.append(f"{t['id']}/{section}: missing source {item['source']}")
    for s in t['sources']:
        if not re.match(r'^https?://[^\s]+$',s['url']): errors.append(f"{s['id']}: invalid URL")
enrichment={}
owners={item['id']:t for t in traditions for item in t['entities']+t['events']+t['artifacts']}
items={item['id']:item for t in traditions for item in t['entities']+t['events']+t['artifacts']}
updates_list=[json.loads(p.read_text(encoding='utf-8-sig')) for p in sorted(DATA.glob('enrichment-*.json'))]
updates_list.extend(expansion.get('enrichment',{}) for expansion in expansions)
for updates in updates_list:
    for key,entry in updates.items():
        if key not in owners:
            errors.append(f'Unknown enrichment ID: {key}')
            continue
        sources={s['id'] for s in owners[key]['sources']}
        for citation in entry.get('citations',[]):
            if citation.get('source') not in sources: errors.append(f'{key}: invalid citation source {citation.get("source")}')
            if not citation.get('locator'): errors.append(f'{key}: citation missing locator')
        for img in entry.get('images',[]):
            for field in ('url','pageUrl','title','credit','license','caption'):
                if not img.get(field): errors.append(f'{key}: image missing {field}')
            if img.get('avatar') and img.get('role')=='document': errors.append(f'{key}: document must not become avatar')
            if img.get('crop'):
                crop=img['crop']
                if len(crop)!=4 or not all(isinstance(n,(int,float)) for n in crop) or min(crop)<0 or min(crop[2:])<=0 or crop[0]+crop[2]>1.001 or crop[1]+crop[3]>1.001: errors.append(f'{key}: invalid crop {crop}')
            if img.get('local'):
                resolved=(BASE/'dist'/img['local']).resolve()
                if not resolved.is_relative_to((BASE/'dist').resolve()) or not resolved.is_file(): errors.append(f'{key}: missing or invalid local image {img["local"]}')
            else: errors.append(f'{key}: visible image must be cached locally; use imageReferences for source-only records')
        target=enrichment.setdefault(key,{})
        for field,values in entry.items():
            if isinstance(values,list):
                current=target.setdefault(field,[])
                known={json.dumps(x,sort_keys=True,ensure_ascii=False) for x in current}
                for value in values:
                    signature=json.dumps(value,sort_keys=True,ensure_ascii=False)
                    if signature not in known:
                        current.append(value)
                        known.add(signature)
            else: target[field]=values
for key,n in Counter(ids).items():
    if n>1: errors.append(f"Duplicate id: {key}")
for t in traditions:
    for a in t['artifacts']:
        if not enrichment.get(a['id'],{}).get('citations'): errors.append(f'{a["id"]}: object requires a source locator')
if errors:
    print('\n'.join(errors))
    raise SystemExit(1)
extra=json.loads((DATA/'images.json').read_text(encoding='utf-8'))
bundle={'china':parts[0],'core':parts[1],'others':parts[2],'cthulhu':parts[3],'land':json.loads((BASE/'dist/assets/land.json').read_text()),'images':extra,'enrichment':enrichment}
(DATA/'bundle.js').write_text('window.MYTH_ATLAS_CONTENT='+json.dumps(bundle,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
report={'traditions':len(traditions),'entities':sum(len(t['entities']) for t in traditions),'events':sum(len(t['events']) for t in traditions),'relations':sum(len(t['relations']) for t in traditions),'source_entries':sum(len(t['sources']) for t in traditions),'unique_source_urls':len({s['url'] for t in traditions for s in t['sources']}),'images':sum(len(t.get('images',[]))+len(extra.get(t['id'],[])) for t in traditions),'quotes':sum(len(t['quotes']) for t in traditions),'characters':sum(len(json.dumps(t,ensure_ascii=False)) for t in traditions),'checks':'Unique IDs, all relation endpoints, event actors, source references, and required content passed.'}
all_images=[img for t in traditions for img in t.get('images',[])+extra.get(t['id'],[])]+[img for entry in enrichment.values() for img in entry.get('images',[])]
report.update({
    'artifacts':sum(len(t['artifacts']) for t in traditions),
    'groups':sum(len(t['groups']) for t in traditions),
    'artifact_links':sum(len(a.get('owners',[])) for t in traditions for a in t['artifacts']),
    'illustrated_artifacts':sum(bool(enrichment.get(a['id'],{}).get('images')) for t in traditions for a in t['artifacts']),
    'images':len({img.get('local') or img['url'] for img in all_images}),
    'entry_citations':sum(len(e.get('citations',[])) for e in enrichment.values()),
    'entry_quotes':sum(bool(c.get('quote')) for e in enrichment.values() for c in e.get('citations',[])),
    'illustrated_entities':sum(bool(enrichment.get(e['id'],{}).get('images')) for t in traditions for e in t['entities']),
    'illustrated_events':sum(bool(enrichment.get(e['id'],{}).get('images')) for t in traditions for e in t['events']),
    'entity_avatars':sum(any(img.get('avatar') for img in enrichment.get(e['id'],{}).get('images',[])) for t in traditions for e in t['entities']),
    'core_illustrated':sum(bool(enrichment.get(key,{}).get('images')) for key,item in items.items() if item['tier']==1),
    'core_total':sum(item['tier']==1 for item in items.values()),
    'important_illustrated':sum(bool(enrichment.get(key,{}).get('images')) for key,item in items.items() if item['tier']<=2),
    'important_total':sum(item['tier']<=2 for item in items.values()),
    'checks':'Unique IDs, relation endpoints, event actors, artifact associations, group members, source references, enrichment references, and local image paths passed.'
})
report['by_tradition']=[{'id':t['id'],**{field:len(t[field]) for field in ('entities','events','artifacts','relations','groups')},**{'illustrated_'+kind:sum(bool(enrichment.get(e['id'],{}).get('images')) for e in t[kind]) for kind in ('entities','events','artifacts')}} for t in traditions]
(BASE/'research/validation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='by_tradition'},ensure_ascii=False,indent=2))
