import tempfile, unittest
from pathlib import Path
from src.domain import ConflictError, NotFoundError, PermissionDenied, ValidationError
from src.repository import Repository
from src.service import Service
from src.rules import STATES, TRANSITION_ROLES
class FailureTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.repo=Repository(str(Path(self.tmp.name)/"test.db")); self.service=Service(self.repo)
        self.item=self.service.create_item({"title":"failure item","description":"failure scenarios","severity":'urgent',"quantity":5,"threshold":10,"external_ref":"FAIL-1"},"creator",'duty_officer')
    def tearDown(self): self.repo.close(); self.tmp.cleanup()
    def test_permission_version_duplicate_and_invariant(self):
        with self.assertRaises(PermissionDenied): self.service.transition(self.item["id"],STATES[1],1,"attacker","viewer")
        with self.assertRaises(ConflictError): self.service.transition(self.item["id"],STATES[1],99,"reviewer",TRANSITION_ROLES[STATES[1]][0],{"reviewer":"张工","opinion":"复核通过"})
        payload={"kind":"action","detail":"same reference","status":"open","external_ref":"DUP-1"}
        self.service.add_record(self.item["id"],payload,"recorder",'duty_officer')
        with self.assertRaises(ConflictError): self.service.add_record(self.item["id"],payload,"recorder",'duty_officer')
        current=self.service.get_item(self.item["id"],"viewer")
        current=self.service.transition(current["id"],"checked",current["version"],"officer",'duty_officer',{"reviewer":"张工","opinion":"复核通过"})
        review=[r for r in self.service.list_records(current["id"],"viewer") if r["kind"]=="review"][0]
        self.service.close_record(current["id"],review["id"],"officer",'duty_officer')
        current=self.service.transition(current["id"],"authorized",current["version"],"chief",'chief_engineer')
        current=self.service.transition(current["id"],"executed",current["version"],"disp",'dispatcher',{"contact":"李现场","discharge":500})
        with self.assertRaises(ConflictError): self.service.transition(current["id"],STATES[-1],current["version"],"chief",'chief_engineer')
    def test_review_and_feedback_guards(self):
        with self.assertRaises(ValidationError): self.service.transition(self.item["id"],"checked",1,"officer",'duty_officer')
        with self.assertRaises(ValidationError): self.service.transition(self.item["id"],"checked",1,"officer",'duty_officer',{"reviewer":"张工"})
        current=self.service.transition(self.item["id"],"checked",1,"officer",'duty_officer',{"reviewer":"张工","opinion":"复核通过"})
        with self.assertRaises(ConflictError): self.service.transition(current["id"],"authorized",current["version"],"chief",'chief_engineer')
        review=[r for r in self.service.list_records(current["id"],"viewer") if r["kind"]=="review"][0]
        with self.assertRaises(PermissionDenied): self.service.close_record(current["id"],review["id"],"disp",'dispatcher')
        self.service.close_record(current["id"],review["id"],"officer",'duty_officer')
        with self.assertRaises(ConflictError): self.service.close_record(current["id"],review["id"],"officer",'duty_officer')
        with self.assertRaises(NotFoundError): self.service.close_record(current["id"],9999,"officer",'duty_officer')
        current=self.service.transition(current["id"],"authorized",current["version"],"chief",'chief_engineer')
        with self.assertRaises(ValidationError): self.service.transition(current["id"],"executed",current["version"],"disp",'dispatcher')
        with self.assertRaises(ValidationError): self.service.transition(current["id"],"executed",current["version"],"disp",'dispatcher',{"contact":"李现场"})
        current=self.service.transition(current["id"],"executed",current["version"],"disp",'dispatcher',{"contact":"李现场","discharge":500})
        with self.assertRaises(ConflictError): self.service.transition(current["id"],"closed",current["version"],"chief",'chief_engineer')
        feedback=[r for r in self.service.list_records(current["id"],"viewer") if r["kind"]=="feedback"][0]
        with self.assertRaises(PermissionDenied): self.service.close_record(current["id"],feedback["id"],"officer",'duty_officer')
        self.service.close_record(current["id"],feedback["id"],"disp",'dispatcher')
        current=self.service.transition(current["id"],"closed",current["version"],"chief",'chief_engineer')
        self.assertEqual(current["status"],STATES[-1]); self.assertTrue(self.repo.verify_audit_chain())
if __name__=="__main__": unittest.main()
