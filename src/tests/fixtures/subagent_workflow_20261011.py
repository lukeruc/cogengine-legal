"""Host-side fixture operations for one observed role-workflow acceptance run."""
from pathlib import Path
import json
import subprocess

from legal.initial_reading import export_initial_reading_tasks, export_initial_synthesis_task
from legal.reader_helpers import read_json, write_json


def call(root, label, arguments):
    root=Path(root)
    result=subprocess.run([str(a) for a in arguments],cwd=root/'contract',capture_output=True)
    logs=root/'logs'; logs.mkdir(exist_ok=True)
    (logs/(label+'.stdout.txt')).write_bytes(result.stdout)
    (logs/(label+'.stderr.txt')).write_bytes(result.stderr)
    write_json(logs/(label+'.process.json'),{'argv':[str(a) for a in arguments],'exit_code':result.returncode})
    if result.returncode:
        raise RuntimeError(result.stdout.decode('utf-8')+result.stderr.decode('utf-8'))
    return json.loads(result.stdout)


def setup(root):
    root=Path(root); install=root/'install'; contract=root/'contract'
    for name in ('inputs','submissions','receipts','tasks','reports','groups'):
        (contract/name).mkdir(parents=True,exist_ok=True)
    runtime=read_json(install/'runtime.json')
    unit_delivery='10000001-1111-4111-8111-111111111111'
    unit_payment='10000002-1111-4111-8111-111111111111'
    slot_text='10000003-1111-4111-8111-111111111111'
    slot_amount='10000004-1111-4111-8111-111111111111'
    slot_condition='10000005-1111-4111-8111-111111111111'
    vocabulary={'format_version':1,'units':[
        {'id':unit_delivery,'name':'交付','description':'货物交付及双方身份和称谓规定'},
        {'id':unit_payment,'name':'付款','description':'采购人支付货款及付款条件规定'}],
        'slots':[{'id':slot_text,'name':'规定原文','description':'具体规定原文','value_schema':{'form':'text'}},
                 {'id':slot_amount,'name':'付款金额','description':'应付款货款金额','value_schema':{'form':'quantity'}},
                 {'id':slot_condition,'name':'条件','description':'规定生效或履行前提','value_schema':{'form':'condition'}}],
        'assignments':[{'unit_id':unit_payment,'slot_id':slot_amount}]}
    write_json(contract/'inputs/vocabulary.json',vocabulary)
    original=contract/'inputs/contract.txt'
    original.write_bytes('第一条 甲方为采购人，乙方为供应商。\r\n乙方应向甲方交付货物。\r\n乙方交付货物后，甲方应向乙方支付100元。\r\n'.encode('utf-8'))
    write_json(contract/'inputs/metadata.json',{'name':'行为回归虚构合同','media_type':'text/plain',
               'conversion_method':'identity','converter_version':'test.1','anomalies':[]})
    case=runtime['commands']['legal-case']; db=contract/'contract.sqlite'
    identity=call(root,'01-init',[case,'init','--db',db,'--vocabulary',contract/'inputs/vocabulary.json'])
    registered=call(root,'02-register',[case,'register','--db',db,'--original',original,'--text',original,'--metadata',contract/'inputs/metadata.json'])
    call(root,'03-split',[case,'split','--db',db,'--text-version',registered['text_version']['object_id']])
    exported=export_initial_reading_tasks(db,contract/'tasks/0001-reading',install,contract/'submissions/0001-preparation.json',window_chars=40)
    write_json(root/'identity.json',identity); write_json(root/'reading-export.json',exported)
    # This sibling is deliberately absent from all role input lists.
    write_json(contract/'tasks/other-parallel-private.json',{'not_authorized':'do not read for format'})
    return exported


def synthesis(root):
    root=Path(root); contract=root/'contract'
    return export_initial_synthesis_task(contract/'contract.sqlite',contract/'tasks/0001-reading/manifest.json',contract/'tasks/0001-reading/0002-synthesis.json')


def submit(root, phase, filename):
    root=Path(root); contract=root/'contract'; runtime=read_json(root/'install/runtime.json')
    receipt=call(root,phase+'-write',[runtime['commands']['legal-case'],'write','--db',contract/'contract.sqlite','--input',contract/'submissions'/filename])
    write_json(contract/'receipts'/(phase+'.json'),receipt)
    for view in ('overview','events','records','clauses','vocabulary'):
        extra=['--kind','node'] if view=='records' else []
        result=call(root,phase+'-'+view,[runtime['commands']['legal-case'],'query','--db',contract/'contract.sqlite','--view',view,'--limit','100',*extra])
        if result['next_offset'] is not None:
            raise RuntimeError('fixture unexpectedly paginated')
        write_json(contract/'reports'/(phase+'-'+view+'.json'),{'case_id':result['case_id'],'checked_sequence':result['quality']['current_sequence'],'items':result['items']})
    return receipt


def dispatch(root, role, task_id, dynamic):
    root=Path(root); template=(root/'install/skills/legal-case/templates'/(role+'.md')).read_text()
    fixed=template.split('## 一、固定内容\n\n',1)[1].split('\n## 二、本次任务要求',1)[0]
    text=f'# {role}：{task_id}\n\n## 一、固定内容\n\n{fixed}\n## 二、本次任务要求\n\n{dynamic}\n'
    file=root/'contract/tasks'/(task_id+'-dispatch.md')
    file.write_text(text,encoding='utf-8')
    return text
