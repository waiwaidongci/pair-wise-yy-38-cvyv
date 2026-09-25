import tempfile, unittest
from pathlib import Path
from src.domain import ConflictError, PermissionDenied, ValidationError
from src.repository import Repository
from src.service import Service
from src.rules import STATES, TRANSITION_ROLES
class FailureTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.repo=Repository(str(Path(self.tmp.name)/"test.db")); self.service=Service(self.repo)
        self.item=self.service.create_item({"title":"failure item","description":"failure scenarios","severity":'urgent',"quantity":5,"threshold":10,"external_ref":"FAIL-1"},"creator",'duty_officer')
    def tearDown(self): self.repo.close(); self.tmp.cleanup()
    def _closed_review(self,external_ref="RV-F1"):
        review=self.service.add_record(self.item["id"],{"kind":"review","reviewer":"张工","opinion":"同意按方案泄洪","detail":"复核材料齐全","status":"open","external_ref":external_ref},"recorder",'duty_officer')
        self.service.close_record(self.item["id"],review["id"],"recorder",'duty_officer')
    def _reach_executed(self):
        self._closed_review()
        current=self.service.get_item(self.item["id"],"viewer")
        for target in STATES[1:4]: current=self.service.transition(current["id"],target,current["version"],"reviewer",TRANSITION_ROLES[target][0])
        return current
    def test_permission_version_duplicate_and_invariant(self):
        with self.assertRaises(PermissionDenied): self.service.transition(self.item["id"],STATES[1],1,"attacker","viewer")
        with self.assertRaises(ConflictError): self.service.transition(self.item["id"],STATES[1],99,"reviewer",TRANSITION_ROLES[STATES[1]][0])
        payload={"kind":"action","detail":"same reference","status":"open","external_ref":"DUP-1"}
        self.service.add_record(self.item["id"],payload,"recorder",'duty_officer')
        with self.assertRaises(ConflictError): self.service.add_record(self.item["id"],payload,"recorder",'duty_officer')
        current=self._reach_executed()
        feedback=self.service.add_record(current["id"],{"kind":"feedback","contact":"李现场","discharge":320,"detail":"现场正常","status":"open","external_ref":"FB-F0"},"recorder",'dispatcher')
        self.service.close_record(current["id"],feedback["id"],"recorder",'dispatcher')
        with self.assertRaises(ConflictError): self.service.transition(current["id"],STATES[-1],current["version"],"reviewer",TRANSITION_ROLES[STATES[-1]][0])
    def test_review_required_before_authorization(self):
        current=self.service.transition(self.item["id"],STATES[1],self.item["version"],"reviewer",TRANSITION_ROLES[STATES[1]][0])
        with self.assertRaises(ConflictError): self.service.transition(current["id"],STATES[2],current["version"],"chief",TRANSITION_ROLES[STATES[2]][0])
        review=self.service.add_record(self.item["id"],{"kind":"review","reviewer":"张工","opinion":"同意","detail":"复核材料","status":"open","external_ref":"RV-F2"},"recorder",'duty_officer')
        with self.assertRaises(ConflictError): self.service.transition(current["id"],STATES[2],current["version"],"chief",TRANSITION_ROLES[STATES[2]][0])
        self.service.close_record(self.item["id"],review["id"],"recorder",'duty_officer')
        current=self.service.transition(current["id"],STATES[2],current["version"],"chief",TRANSITION_ROLES[STATES[2]][0])
        self.assertEqual(current["status"],STATES[2])
    def test_review_and_feedback_fields_validated(self):
        with self.assertRaises(ValidationError): self.service.add_record(self.item["id"],{"kind":"review","opinion":"同意","detail":"缺复核人"},"recorder",'duty_officer')
        with self.assertRaises(ValidationError): self.service.add_record(self.item["id"],{"kind":"review","reviewer":"张工","detail":"缺意见"},"recorder",'duty_officer')
        with self.assertRaises(ConflictError): self.service.add_record(self.item["id"],{"kind":"feedback","contact":"李现场","discharge":100,"detail":"未执行"},"recorder",'dispatcher')
        current=self._reach_executed()
        with self.assertRaises(ValidationError): self.service.add_record(current["id"],{"kind":"feedback","discharge":100,"detail":"缺联系人"},"recorder",'dispatcher')
        with self.assertRaises(ValidationError): self.service.add_record(current["id"],{"kind":"feedback","contact":"李现场","discharge":-1,"detail":"泄量非法"},"recorder",'dispatcher')
    def test_open_feedback_blocks_archive(self):
        current=self._reach_executed()
        with self.assertRaises(ConflictError): self.service.transition(current["id"],STATES[-1],current["version"],"chief",TRANSITION_ROLES[STATES[-1]][0])
        feedback=self.service.add_record(current["id"],{"kind":"feedback","contact":"李现场","discharge":320,"detail":"现场正常","status":"open","external_ref":"FB-F1"},"recorder",'dispatcher')
        with self.assertRaises(ConflictError): self.service.transition(current["id"],STATES[-1],current["version"],"chief",TRANSITION_ROLES[STATES[-1]][0])
        with self.assertRaises(PermissionDenied): self.service.close_record(current["id"],feedback["id"],"attacker","viewer")
        self.service.close_record(current["id"],feedback["id"],"recorder",'dispatcher')
        with self.assertRaises(ConflictError): self.service.close_record(current["id"],feedback["id"],"recorder",'dispatcher')
        current=self.service.transition(current["id"],STATES[-1],current["version"],"chief",TRANSITION_ROLES[STATES[-1]][0])
        self.assertEqual(current["status"],STATES[-1])
if __name__=="__main__": unittest.main()
