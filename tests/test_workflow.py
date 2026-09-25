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
        self.service.add_record(item["id"],{"kind":"evidence","detail":"evidence registered","status":"closed","external_ref":"EV-1"},"recorder",'duty_officer')
        payloads={"checked":{"reviewer":"张工","opinion":"复核通过，同意泄洪"},"executed":{"contact":"李现场","discharge":800}}
        close_roles={"review":'duty_officer',"feedback":'dispatcher'}
        current=item
        for target in STATES[1:]:
            current=self.service.transition(current["id"],target,current["version"],"actor-"+target,TRANSITION_ROLES[target][0],payloads.get(target))
            if target in ("checked","executed"):
                kind="review" if target=="checked" else "feedback"
                record=[r for r in self.service.list_records(current["id"],"viewer") if r["kind"]==kind][-1]
                self.assertEqual(record["status"],"open")
                self.service.close_record(current["id"],record["id"],"closer",close_roles[kind])
        self.assertEqual(current["status"],STATES[-1])
        self.assertEqual(len(self.service.list_records(current["id"],"viewer")),3)
        listed=[i for i in self.service.list_items("viewer") if i["id"]==current["id"]][0]
        self.assertEqual(listed["reviewer"],"张工"); self.assertEqual(listed["last_feedback_by"],"李现场")
        detail=self.service.get_item(current["id"],"viewer")
        self.assertEqual(detail["reviewer"],"张工"); self.assertEqual(detail["last_feedback_by"],"李现场")
        events=self.service.audit("viewer",current["id"]); self.assertGreaterEqual(len(events),len(STATES)+1); self.assertTrue(self.repo.verify_audit_chain())
if __name__=="__main__": unittest.main()
