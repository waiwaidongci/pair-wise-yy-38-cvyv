import tempfile, unittest
from pathlib import Path
from src.repository import Repository
from src.service import Service
from src.rules import STATES, TRANSITION_ROLES
class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.repo=Repository(str(Path(self.tmp.name)/"test.db")); self.service=Service(self.repo)
    def tearDown(self): self.repo.close(); self.tmp.cleanup()
    def test_complete_workflow_and_audit(self):
        item=self.service.create_item({"title":"workflow item","description":"complete business flow","severity":'urgent',"quantity":12,"threshold":6,"external_ref":"WF-1"},"creator",'duty_officer')
        self.assertEqual(item["status"],STATES[0])
        self.assertIsNone(item["reviewer"]); self.assertIsNone(item["last_feedback_by"])
        review=self.service.add_record(item["id"],{"kind":"review","reviewer":"张工","opinion":"同意按方案泄洪","detail":"复核材料齐全","status":"open","external_ref":"RV-1"},"recorder",'duty_officer')
        self.assertEqual(review["reviewer"],"张工"); self.assertEqual(review["opinion"],"同意按方案泄洪")
        review=self.service.close_record(item["id"],review["id"],"recorder",'duty_officer')
        self.assertEqual(review["status"],"closed")
        current=self.service.get_item(item["id"],"viewer")
        for target in STATES[1:4]:
            current=self.service.transition(current["id"],target,current["version"],"reviewer",TRANSITION_ROLES[target][0])
        feedback=self.service.add_record(current["id"],{"kind":"feedback","contact":"李现场","discharge":850.5,"detail":"下游河道正常","status":"open","external_ref":"FB-1"},"dispatcher1",'dispatcher')
        self.assertEqual(feedback["contact"],"李现场"); self.assertEqual(feedback["discharge"],850.5)
        self.service.close_record(current["id"],feedback["id"],"dispatcher1",'dispatcher')
        current=self.service.transition(current["id"],STATES[4],current["version"],"reviewer",TRANSITION_ROLES[STATES[4]][0])
        self.assertEqual(current["status"],STATES[-1])
        self.assertEqual(current["reviewer"],"张工"); self.assertEqual(current["last_feedback_by"],"dispatcher1")
        listed=self.service.list_items("viewer")[0]
        self.assertEqual(listed["reviewer"],"张工"); self.assertEqual(listed["last_feedback_by"],"dispatcher1")
        self.assertEqual(len(self.service.list_records(current["id"],"viewer")),2)
        events=self.service.audit("viewer",current["id"]); self.assertGreaterEqual(len(events),len(STATES)+2); self.assertTrue(self.repo.verify_audit_chain())
if __name__=="__main__": unittest.main()
