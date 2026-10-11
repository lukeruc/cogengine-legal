"""Acceptance of the 2026-10-11 file API and role resources."""
import copy
from datetime import date
from decimal import Decimal
import inspect
import io
from pathlib import Path
import runpy
import socket
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from legal import reader_helpers as h
from legal.formats import Invalid, InvalidBatch, new_id
from legal.initial_reading import export_initial_reading_tasks, export_initial_synthesis_task
from legal.model import write
from legal.query import query
from legal.storage import initialize, register, split

SRC = Path(__file__).resolve().parents[1]
EXAMPLES = SRC / 'skills/legal-case/examples'


class ConstructionAPI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='构造 API-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = h.read_json(EXAMPLES / 'fixture.json')
        self.snapshot = self.fixture['snapshot']
        self.clause = self.snapshot['items'][0]
        self.header = h.header(format_version=1, case_id=self.fixture['case_id'], vocabulary_hash='a'*64,
                               submitted_by='summarizer', phase='preparation', covered_clauses=[], issues=[])
        self.ev = [h.evidence(path='', source=h.source(level=1, anchors=[h.ref(local_id='a')]))]
        self.anchor = h.record(local_id='a', kind='anchor', data={'clause': h.ref(record_id=self.clause['record_id']),
                               'quote': self.clause['data']['text']}, evidence=[])

    def invalid(self, code, function, *args, **kwargs):
        with self.assertRaises((Invalid, InvalidBatch)) as caught:
            function(*args, **kwargs)
        items = [caught.exception.item()] if isinstance(caught.exception, Invalid) else caught.exception.items
        self.assertIn(code, [item['code'] for item in items])

    def test_character_and_text_roundtrips(self):
        text = '\ufeff中"\\\r\n😀e\u0301\r末\n'
        raw = self.root / '原文.txt'
        raw.write_bytes(text.encode('utf-8'))
        self.assertEqual(h.read_text(raw), text)
        result = self.root / '请求.json'
        self.assertEqual(h.write_json(result, {'quote': text}), str(result))
        self.assertEqual(h.read_json(result), {'quote': text})
        self.assertTrue(result.read_bytes().endswith(b'\n'))

    def test_file_paths_decode_and_strict_json(self):
        for func in (h.read_text, h.read_json):
            self.invalid('INVALID_ARGUMENT', func, 'relative')
            self.invalid('FILE_ERROR', func, self.root / 'missing')
        self.invalid('INVALID_ARGUMENT', h.write_json, 'relative', {})
        self.invalid('FILE_ERROR', h.write_json, self.root / 'missing/out.json', {})
        raw = self.root / 'raw'
        raw.write_bytes(b'\xff')
        self.invalid('FILE_ERROR', h.read_text, raw)
        for value in (b'{"a":1,"a":2}', b'[NaN]', b'\xef\xbb\xbf[]', b'[1e999]'):
            raw.write_bytes(value)
            self.invalid('INVALID_JSON', h.read_json, raw)

    def test_write_rejects_conversions_and_preserves_existing_file(self):
        target = self.root / 'out.json'
        for value in ({1: 'x'}, Decimal('1'), date(2026,10,11), {1}, (1,2), object(), h.UNSET,
                      float('nan'), float('inf'), '\ud800'):
            self.invalid('INVALID_JSON', h.write_json, target, value)
            self.assertFalse(target.exists())
        cycle = []; cycle.append(cycle)
        self.invalid('INVALID_JSON', h.write_json, target, cycle)
        h.write_json(target, {'a':1}); before = target.read_bytes()
        self.invalid('FILE_EXISTS', h.write_json, target, {'a':2})
        self.assertEqual(target.read_bytes(), before)

    def test_partial_file_cleanup(self):
        target = self.root / 'out.json'
        with patch('legal.formats.os.fsync', side_effect=OSError('disk failure')):
            self.invalid('FILE_ERROR', h.write_json, target, {'x':1})
        self.assertFalse(target.exists())

    def test_span_selection_and_overlap(self):
        self.clause['data'].update(text='aaaa', end_offset=4)
        original = copy.deepcopy(self.snapshot)
        request = h.quote_from_span(self.snapshot, local_id='a', clause_record_id=self.clause['record_id'], start=1, end=3)
        self.assertEqual((request['quote'],request['occurrence']),('aa',2))
        self.assertEqual(self.snapshot, original)
        for start,end in ((-1,2),(True,2),(0,False),(1,1),(0,5),(1.0,2)):
            self.invalid('INVALID_ARGUMENT', h.quote_from_span, self.snapshot, local_id='a',
                         clause_record_id=self.clause['record_id'], start=start, end=end)
        self.invalid('REFERENCE_NOT_FOUND', h.quote_from_span, self.snapshot, local_id='a',
                     clause_record_id=new_id(), start=0, end=1)

    def test_unicode_span_and_address_checks(self):
        text = '😀e\u0301\r\n中"\\'
        self.clause['data'].update(text=text, end_offset=len(text))
        request = h.quote_from_span(self.snapshot, local_id='a', clause_record_id=self.clause['record_id'], start=1, end=5)
        self.assertEqual(request['quote'], 'e\u0301\r\n')
        self.clause['data']['end_offset'] += 1
        self.invalid('INVALID_ARGUMENT', h.quote_from_span, self.snapshot, local_id='a',
                     clause_record_id=self.clause['record_id'], start=1, end=5)

    def test_reference_and_evidence_shapes(self):
        self.assertEqual(h.ref(local_id='d', value_path='/value/a~1b'), {'local_id':'d','value_path':'/value/a~1b'})
        for kwargs in ({}, {'local_id':None}, {'local_id':'a','object_id':new_id()},
                       {'object_id':new_id(),'value_path':'/value'}, {'record_id':new_id(),'value_path':'/value2'}):
            self.invalid('INVALID_ARGUMENT', h.ref, **kwargs)
        for pointer in ('bad','/a~2',None):
            self.invalid('INVALID_ARGUMENT', h.evidence, path=pointer, source=self.ev[0]['source'])
        for fields in ({'level':True,'anchors':[h.ref(local_id='a')]}, {'level':1,'anchors':[]},
                       {'level':1,'anchors':[h.ref(object_id=new_id())]},
                       {'level':1,'anchors':[h.ref(local_id='a')],'explanation':'bad'},
                       {'level':3,'premises':[h.ref(local_id='a')],'explanation':'','asserted_by':'x'}):
            with self.assertRaises(Invalid): h.source(**fields)
        self.assertEqual(h.source(level=3,premises=[h.ref(local_id='a')],explanation='explicit',asserted_by='tagger')['level'],3)

    def test_level_two_format_structure(self):
        args = {'level':2,'anchors':[h.ref(local_id='a')],'surface':'2026年', 'format_contract':'date.v1',
                'format_parameters':{'precision':'year','component_widths':[4],'separators':[],'prefix':'','suffix':'年'}}
        self.assertEqual(h.source(**args),args)
        del args['format_parameters']['suffix']
        self.invalid('INVALID_ARGUMENT', h.source, **args)
        args['format_contract']='invented'
        self.invalid('UNKNOWN_FORMAT_CONTRACT', h.source, **args)

    def test_format_parameters_reject_invalid_shapes_without_guessing(self):
        base={'level':2,'anchors':[h.ref(local_id='a')],'surface':'2026年', 'format_contract':'date.v1',
              'format_parameters':{'precision':'year','component_widths':[4],'separators':[],'prefix':'','suffix':'年'}}
        for update in ({'component_widths':[True]}, {'component_widths':[]}, {'precision':'unknown'},
                       {'separators':['-']}, {'prefix':'123'}):
            with self.assertRaises(Invalid):
                h.source(**{**base,'format_parameters':{**base['format_parameters'],**update}})

    def test_memory_error_locations_keep_group_order(self):
        a=h.detail(local_id='a',owner=h.ref(local_id='missing'),slot_id=new_id(),value=None,evidence=[])
        b={**a,'local_id':'b'}
        with self.assertRaises(InvalidBatch) as caught:
            h.assemble(header=self.header,record_groups=[[a],[b]])
        self.assertEqual([i['path'] for i in caught.exception.items],
                         ['/record_groups/0/0/data/owner','/record_groups/1/0/data/owner'])

    def test_ordinary_same_named_keys_are_not_references(self):
        business=h.node(local_id='p',node_kind='future',fields={'nested':{'local_id':'ordinary text'}},evidence=[])
        self.assertEqual(h.assemble(header=self.header,record_groups=[[business]])['records'],[business])

    def test_required_parameters_and_explicit_null(self):
        for function in (h.source,h.evidence,h.record,h.node,h.relation,h.reference,h.detail,h.header,h.clause_revision):
            self.assertTrue(any(p.default is inspect.Parameter.empty and p.kind!=p.VAR_KEYWORD
                                for p in inspect.signature(function).parameters.values()))
            with self.assertRaises(TypeError): function()
        result=h.detail(local_id='d',owner=h.ref(local_id='r'),slot_id=new_id(),value=None,evidence=[])
        self.assertIsNone(result['data']['value']); self.assertNotIn('status',result)
        self.invalid('INVALID_ARGUMENT',h.record,local_id='x',kind='node',data={},evidence=[],status=None)
        self.invalid('INVALID_ARGUMENT',h.header,**{**self.header,'overview':None})

    def test_wrappers_have_no_business_defaults(self):
        result=h.relation(local_id='r',relation_kind='party',fields={'unit_id':new_id(),'parties':[]},evidence=[])
        self.assertNotIn('modality',result['data'])
        self.invalid('INVALID_ARGUMENT',h.node,local_id='x',node_kind='subject',fields={'node_kind':'event'},evidence=[])
        self.invalid('INVALID_ARGUMENT',h.relation,local_id='x',relation_kind='party',fields={'relation_kind':'contract'},evidence=[])
        self.invalid('INVALID_ARGUMENT',h.reference,local_id='x',reference_kind='distinct',from_ref={},to_ref={},fields={'from':{}},evidence=[])

    def test_deep_copy_independence(self):
        fields={'canonical_name':'甲','identifiers':[{'scheme':'x','value':'1'}]}; original=copy.deepcopy(fields)
        record=h.node(local_id='p',node_kind='subject',fields=fields,evidence=self.ev)
        record['data']['identifiers'][0]['value']='changed'
        record['evidence'][0]['source']['anchors'][0]['local_id']='changed'
        self.assertEqual(fields,original); self.assertEqual(self.ev[0]['source']['anchors'][0]['local_id'],'a')
        doc=h.assemble(header=self.header,record_groups=[[self.anchor]])
        doc['records'][0]['data']['quote']='changed'; doc['issues'].append('changed')
        self.assertNotEqual(self.anchor['data']['quote'],'changed'); self.assertEqual(self.header['issues'],[])

    def test_complete_clause_revision_and_absence(self):
        original=copy.deepcopy(self.clause)
        result=h.clause_revision(local_id='tag',clause=self.clause,tags=[self.fixture['unit_id']],classification='ordinary',evidence=self.ev)
        self.assertEqual(result['data'],{**original['data'],'tags':[self.fixture['unit_id']],'classification':'ordinary'})
        self.assertEqual(result['object_id'],original['object_id']); self.assertEqual(result['previous_record_id'],original['record_id'])
        self.assertEqual(result['evidence'],self.ev); self.assertNotIn('provenance',result); self.assertNotIn('original_number',result['data'])
        result['data']['tags'].append(new_id()); self.assertEqual(self.clause,original)
        self.clause['data']['original_number']=None
        self.assertIsNone(h.clause_revision(local_id='t',clause=self.clause,tags=[],classification='no_content',evidence=[])['data']['original_number'])

    def test_invalid_clause_revisions(self):
        for tags,classification in (([],'ordinary'),([self.fixture['unit_id']],'unmatched'),([],'unclassified'),(['bad'],'ordinary')):
            with self.assertRaises(Invalid): h.clause_revision(local_id='t',clause=self.clause,tags=tags,classification=classification,evidence=[])
        self.clause['status']='withdrawn'
        self.invalid('INVALID_ARGUMENT',h.clause_revision,local_id='t',clause=self.clause,tags=[],classification='unmatched',evidence=[])

    def test_file_and_memory_equivalence_and_batch_errors(self):
        business=h.node(local_id='p',node_kind='subject',fields={'canonical_name':'甲'},evidence=self.ev)
        first=self.root/'header.json'; second=self.root/'records.json'; third=self.root/'anchors.json'; out=self.root/'out.json'
        for path,value in ((first,self.header),(second,[business]),(third,[self.anchor])): h.write_json(path,value)
        h.build_submission_files(first,[second,third],out)
        self.assertEqual(h.assemble(header=self.header,record_groups=[[business],[self.anchor]]),h.read_json(out))
        for groups,code in (([[business],[business]],'DUPLICATE_LOCAL_ID'),([[business]],'REFERENCE_NOT_FOUND')):
            self.invalid(code,h.assemble,header=self.header,record_groups=groups)
        revised=h.record(local_id='x',kind='node',data={},evidence=[],object_id=new_id(),previous_record_id=new_id())
        self.invalid('DUPLICATE_ID',h.assemble,header=self.header,record_groups=[[revised,{**revised,'local_id':'y'}]])
        records=[h.node(local_id=str(i),node_kind='event',fields={'name':'same','description':str(i),'participants':[]},evidence=[]) for i in range(2)]
        self.assertEqual(len(h.assemble(header=self.header,record_groups=[records])['records']),2)

    def test_no_database_network_process_or_logs(self):
        with patch.object(sqlite3,'connect',side_effect=AssertionError('DB')), patch.object(subprocess,'Popen',side_effect=AssertionError('process')), patch.object(socket,'socket',side_effect=AssertionError('network')), redirect_stdout(io.StringIO()) as stream:
            doc=h.assemble(header=self.header,record_groups=[[self.anchor]])
            h.write_json(self.root/'out.json',doc); h.read_json(self.root/'out.json'); h.read_text(self.root/'out.json')
            h.quote_from_span(self.snapshot,local_id='x',clause_record_id=self.clause['record_id'],start=0,end=2)
            self.assertEqual(stream.getvalue(),'')


class ExamplesAndHandoff(unittest.TestCase):
    def test_templates_share_complete_fixed_boundaries(self):
        boundaries=[]
        for role in ('reader','summarizer','tagger','extractor'):
            template=(SRC/f'skills/legal-case/templates/{role}.md').read_text()
            self.assertEqual([line for line in template.splitlines() if line.startswith('## ')],
                             ['## 一、固定内容','## 二、本次任务要求'])
            fixed=template.split('## 一、固定内容\n\n')[1].split('\n## 二、本次任务要求')[0]
            boundaries.append(fixed.split('按指定格式交付文件和摘要')[0])
        self.assertTrue(all(value==boundaries[0] for value in boundaries))

    def test_examples_formal_write_and_single_reader_handoff(self):
        with tempfile.TemporaryDirectory(prefix='role-workflow-') as tmp:
            root=Path(tmp); fixture=h.read_json(EXAMPLES/'fixture.json')
            unit,slot,condition=fixture['unit_id'],fixture['slot_id'],fixture['shared_ids']['condition_slot']
            vocab=root/'vocabulary.json'
            h.write_json(vocab,{'format_version':1,'units':[{'id':unit,'name':'付款','description':'采购人付款规定'}],
                        'slots':[{'id':slot,'name':'金额','description':'付款金额','value_schema':{'form':'quantity'}},
                                 {'id':condition,'name':'条件','description':'付款前提','value_schema':{'form':'condition'}}],
                        'assignments':[{'unit_id':unit,'slot_id':s} for s in (slot,condition)]})
            db=root/'contract.sqlite'; initialized=initialize(db,vocab)
            original=root/'text.txt'; original.write_bytes(fixture['snapshot']['items'][0]['data']['text'].encode('utf-8'))
            metadata=root/'metadata.json'
            h.write_json(metadata,{'name':'虚构夹具','media_type':'text/plain','conversion_method':'identity','converter_version':'test','anomalies':[]})
            material=register(db,original,original,metadata); split(db,material['text_version']['object_id'])
            (root/'submissions').mkdir()
            exported=export_initial_reading_tasks(db,root/'tasks/0001',SRC,root/'submissions/prep.json',window_chars=20)
            task=exported['tasks'][0]
            self.assertEqual(task['role'],'reading_and_synthesis')
            self.assertIn(str(SRC/'skills/legal-case/templates/reader.md'),task['input_files'])
            self.assertNotIn(str(EXAMPLES/'tagging.py'),task['input_files'])
            Path(task['output_file']).write_text('阅读范围：全部已读，无截断。\n')
            summary=export_initial_synthesis_task(db,exported['manifest_file'],root/'tasks/0001/0002-synthesis.json')
            self.assertEqual(summary['continue_reader_task_id'],task['task_id'])
            self.assertIn(str(EXAMPLES/'preparation.py'),summary['input_files'])
            self.assertTrue(all(Path(p).is_file() for p in summary['input_files']))
            snapshot=h.read_json(root/'tasks/0001/clauses.json'); clauses_path=root/'tasks/0001/clauses.json'
            def anchors_for(snapshot,index):
                clause=snapshot['items'][0]
                request=runpy.run_path(str(EXAMPLES/'quote_requests.py'))['build'](snapshot=snapshot,local_id='a',clause_record_id=clause['record_id'],start=0,end=len(clause['data']['text']))
                request_path=root/f'quotes-{index}.json'; out=root/f'anchors-{index}.json'
                h.write_json(request_path,request); h.find_quote_files(clauses_path,request_path,out)
                return h.read_json(out)
            args={'case_id':initialized['case_id'],'vocabulary_hash':initialized['vocabulary_hash']}
            prep=runpy.run_path(str(EXAMPLES/'preparation.py'))['build'](snapshot=snapshot,anchors=anchors_for(snapshot,1),submitted_by='summarizer',**args)
            receipt=write(db,prep); shared={key:receipt['id_map'][key]['object_id'] for key in ('p','q','delivery')}; shared['condition_slot']=condition
            tag=runpy.run_path(str(EXAMPLES/'tagging.py'))['build'](snapshot=snapshot,anchors=anchors_for(snapshot,2),unit_id=unit,submitted_by='tagger',**args)
            invalid_tag=copy.deepcopy(tag)
            classification_evidence=copy.deepcopy(invalid_tag['records'][-1]['evidence'][0])
            classification_evidence['path']='/classification'
            invalid_tag['records'][-1]['evidence'][0]['path']='/tags/0'
            invalid_tag['records'][-1]['evidence'].append(classification_evidence)
            h.assemble(header={k:v for k,v in invalid_tag.items() if k!='records'},record_groups=[invalid_tag['records']])
            before=db.read_bytes()
            with self.assertRaises((Invalid,InvalidBatch)) as caught:
                write(db,invalid_tag)
            failures=[caught.exception.item()] if isinstance(caught.exception,Invalid) else caught.exception.items
            self.assertTrue(any(i['code']=='MISSING_SOURCE' and i['path'].endswith('/data/tags') for i in failures), failures)
            self.assertEqual(db.read_bytes(),before)
            self.assertTrue(write(db,tag)['ok'])
            current=query(db,{'view':'clauses'})
            snapshot={'case_id':initialized['case_id'],'checked_sequence':current['quality']['current_sequence'],'items':current['items']}
            clauses_path=root/'tagged-clauses.json'; h.write_json(clauses_path,snapshot)
            extracted=runpy.run_path(str(EXAMPLES/'extraction.py'))['build'](snapshot=snapshot,anchors=anchors_for(snapshot,3),shared_ids=shared,unit_id=unit,slot_id=slot,submitted_by='extractor',**args)
            before=db.read_bytes(); bad=copy.deepcopy(extracted); bad['records'][2]['data']['slot_id']=new_id()
            h.assemble(header={k:v for k,v in bad.items() if k!='records'},record_groups=[bad['records']])
            with self.assertRaises((Invalid,InvalidBatch)): write(db,bad)
            self.assertEqual(db.read_bytes(),before); self.assertTrue(write(db,extracted)['ok'])


if __name__=='__main__':
    unittest.main()
