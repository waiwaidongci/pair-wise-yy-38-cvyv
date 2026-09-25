import unittest
from src import rules
from src.domain import ConflictError, ValidationError
class RulesTest(unittest.TestCase):
    def test_priority_deadline_and_escalation(self):
        low=rules.priority_score(rules.SEVERITIES[0],1,10,0); high=rules.priority_score(rules.SEVERITIES[-1],30,10,3)
        self.assertGreater(high,low); self.assertLessEqual(rules.response_deadline_hours(rules.SEVERITIES[-1],30,10),rules.response_deadline_hours(rules.SEVERITIES[0],1,10))
        self.assertTrue(rules.escalation_required(rules.SEVERITIES[-1],1,10)); self.assertTrue(rules.escalation_required(rules.SEVERITIES[0],10,10))
    def test_transition_guards(self):
        self.assertTrue(rules.can_transition(rules.STATES[0],rules.STATES[1]))
        with self.assertRaises(ConflictError): rules.validate_transition(rules.STATES[0],rules.STATES[-1])
        with self.assertRaises(ValidationError): rules.priority_score("not-a-severity",1,1)
    def test_review_feedback_and_close_rules(self):
        self.assertEqual(rules.authorization_blockers('authorized',0),["复核记录未关闭，不能授权"])
        self.assertEqual(rules.authorization_blockers('authorized',1),[])
        self.assertEqual(rules.authorization_blockers('executed',0),[])
        self.assertEqual(rules.completion_blockers('closed',0),[])
        self.assertEqual(rules.completion_blockers('closed',1),["仍有未关闭事项"])
        blockers=rules.completion_blockers('closed',1,1)
        self.assertIn("现场反馈未关闭，不能归档",blockers); self.assertIn("仍有未关闭事项",blockers)
        self.assertEqual(rules.completion_blockers('executed',2,2),[])
        self.assertEqual(rules.record_close_roles(rules.REVIEW_KIND),set(['duty_officer']))
        self.assertEqual(rules.record_close_roles(rules.FEEDBACK_KIND),set(['dispatcher']))
        self.assertEqual(rules.record_close_roles('evidence'),rules.RECORD_ROLES)
if __name__=="__main__": unittest.main()
