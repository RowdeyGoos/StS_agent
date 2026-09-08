"""Strict semantic discriminator and transform-only public descriptor tests."""
import copy
import unittest
from test_generic_event_host import host, Script, run
from test_generic_event_removal_host import removal, drive


def transform(count=2):
    rows=removal(count,count,tuple(reversed(range(count))))
    for _,value in rows:
        if value['child'] is not None:
            value['child']['operation']='transform'
            value['child']['contract_version']='card_transform_v2'
            value['payload']['version']='card_transform_v2'
            if 'operation' in value['payload'] and value['payload']['operation']:
                value['payload']['operation']='transform'
    return rows


class TransformHostTests(unittest.TestCase):
    def test_all_fixed_counts_and_original_results(self):
        for count in range(1,9):
            result,script=drive(transform(count))
            self.assertEqual(result['status'],'resolved',result)
            self.assertEqual(result['child_attempted'],count+1)
            self.assertEqual(result['completed_card_children'],1)
            self.assertEqual(result['effects'],'unverified')
            self.assertFalse(script.rows)

    def test_each_payload_kind_wrong_version_rejected(self):
        for index in (2,3,8):
            rows=transform();rows[index][1]['payload']['version']='card_selection_v1'
            result,script=drive(rows)
            self.assertEqual(result['code'],'invalid_response')
            self.assertEqual(result['completed_card_children'],0)
            self.assertEqual(len(script.calls),index+1)

    def test_wrong_failure_version_is_invalid_not_uncertain(self):
        for version,code in [('card_transform_v2','uncertain_action'),('card_selection_v1','invalid_response')]:
            rows=transform();p=rows[3][1]['payload']
            rows[3][1]['payload']={k:p[k] for k in ('schema_version','kind','version','session_nonce','parent_ordinal')}
            rows[3][1]['payload'].update(kind='child_failure',version=version,outcome='uncertain')
            script=Script(rows);actions=iter(['choose:0','select:1'])
            result=run(script,provider=lambda _:next(actions))
            self.assertEqual(result['code'],code,result)
            self.assertEqual(result['child_attempted'],1)
            self.assertEqual(result['completed_card_children'],0)
            self.assertEqual(len(script.calls),4)

    def test_old_family_cannot_claim_transform_version(self):
        rows=removal();rows[2][1]['payload']['version']='card_transform_v2'
        result,script=drive(rows)
        self.assertEqual(result['code'],'invalid_response')
        self.assertEqual(result['child_attempted'],0)

    def test_exact_admission_exclusions(self):
        for field,value in [('min_select',0),('min_select',1),('max_select',9),('domain_count',2),('domain_count',65),('commit_mode','auto_at_max'),('operation','unknown')]:
            rows=transform();rows[2][1]['child'][field]=value
            result,_=drive(rows)
            self.assertEqual(result['code'],'invalid_response')
            self.assertEqual(result['child_attempted'],0)

    def test_no_invented_early_or_selecting_max_preview(self):
        for index in (4,6):
            rows=transform();rows[index][1]['payload']['phase']='preview' if index==4 else 'selecting'
            rows[index][1]['payload']['legal_actions']=['confirm'] if index==4 else ['preview']
            self.assertEqual(drive(rows)[0]['code'],'invalid_response')

    def test_lost_confirm_no_retry(self):
        rows=transform();rows[7]=('POST',host.TransportFailure())
        script=Script(rows);actions=iter(['choose:0','select:1','select:0','confirm'])
        result=run(script,provider=lambda _:next(actions))
        self.assertEqual(result['code'],'transport_failure')
        self.assertEqual(result['child_attempted'],3)
        self.assertEqual(result['completed_card_children'],0)
        self.assertEqual(len(script.calls),8)

    def test_waiting_payload_version_is_checked(self):
        rows=transform();p=copy.deepcopy(rows[2][1]['payload'])
        p.update(status='waiting',phase='submitted',operation='',commit_mode='',min_select=0,max_select=0,decision_id='',candidates=[],selected_slots=[],legal_actions=[])
        p['version']='card_selection_v1';rows[2][1]['payload']=p
        self.assertEqual(drive(rows)[0]['code'],'invalid_response')

    def test_explicit_routes(self):
        self.assertEqual(host.DECISION_ROUTE,'/probe/generic-event-v7/public/decision')
        self.assertEqual(host.ACTION_ROUTE,'/probe/generic-event-v7/public/action')
