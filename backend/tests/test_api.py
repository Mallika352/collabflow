"""Run with: python -m unittest discover -s tests"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import Base, Membership, Project, ProjectRole, Role, Task, TaskStatus, User, app, db, password_hash

class ApiBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=create_engine("sqlite+pysqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
        Base.metadata.create_all(cls.engine)
        cls.TestSession=sessionmaker(bind=cls.engine,expire_on_commit=False)
        def override_db():
            session=cls.TestSession()
            try: yield session
            finally: session.close()
        app.dependency_overrides[db]=override_db

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(cls.engine)
        cls.engine.dispose()

    def setUp(self):
        with self.TestSession() as s:
            self.admin=User(name="Admin",email="admin@test.local",password_hash=password_hash.hash("Admin123!"),global_role=Role.ADMIN)
            self.manager=User(name="Manager",email="manager@test.local",password_hash=password_hash.hash("Manager123!"),global_role=Role.PROJECT_MANAGER)
            self.other_manager=User(name="Other Manager",email="other-manager@test.local",password_hash=password_hash.hash("OtherManager123!"),global_role=Role.PROJECT_MANAGER)
            self.member=User(name="Member",email="member@test.local",password_hash=password_hash.hash("Member123!"),global_role=Role.TEAM_MEMBER)
            self.viewer=User(name="Viewer",email="viewer@test.local",password_hash=password_hash.hash("Viewer123!"),global_role=Role.VIEWER)
            s.add_all([self.admin,self.manager,self.other_manager,self.member,self.viewer]); s.flush()
            self.project=Project(name="Test project",description="",created_by=self.manager.id,project_manager_id=self.manager.id); s.add(self.project); s.flush()
            other_project=Project(name="Private project",description="",created_by=self.other_manager.id,project_manager_id=self.other_manager.id); s.add(other_project); s.flush()
            self.other_project_id=other_project.id
            s.add_all([Membership(project_id=self.project.id,user_id=self.manager.id,project_role=ProjectRole.MANAGER),Membership(project_id=self.project.id,user_id=self.member.id,project_role=ProjectRole.MEMBER),Membership(project_id=self.project.id,user_id=self.viewer.id,project_role=ProjectRole.VIEWER)])
            self.task=Task(project_id=self.project.id,title="Concurrent task",description="",status=TaskStatus.TODO,created_by=self.manager.id,assignee_id=self.member.id); s.add(self.task); s.commit()
            self.task_id=self.task.id
        self.client=TestClient(app)

    def tearDown(self):
        self.client.close()
        with self.TestSession() as s:
            s.query(Task).delete(); s.query(Membership).delete(); s.query(Project).delete(); s.query(User).delete(); s.commit()

    def headers(self,email,password):
        r=self.client.post("/api/auth/login",json={"email":email,"password":password})
        self.assertEqual(r.status_code,200,r.text)
        return {"Authorization":f"Bearer {r.json()['access_token']}"}

    def test_invalid_login_and_anonymous_access_are_rejected(self):
        self.assertEqual(self.client.post("/api/auth/login",json={"email":"manager@test.local","password":"wrong-password"}).status_code,401)
        self.assertEqual(self.client.get(f"/api/tasks/{self.task_id}").status_code,401)

    def test_admin_can_access_unrelated_project_and_manage_users(self):
        headers=self.headers("admin@test.local","Admin123!")
        self.assertEqual(self.client.get(f"/api/projects/{self.other_project_id}",headers=headers).status_code,200)
        r=self.client.post("/api/users",headers=headers,json={"name":"New teammate","email":"new@test.local","password":"NewMember123!","global_role":"TEAM_MEMBER"})
        self.assertEqual(r.status_code,201,r.text)

    def test_viewer_cannot_change_task(self):
        headers=self.headers("viewer@test.local","Viewer123!")
        r=self.client.patch(f"/api/tasks/{self.task_id}",headers=headers,json={"version":1,"status":"DONE"})
        self.assertEqual(r.status_code,403)

    def test_viewer_cannot_comment(self):
        headers=self.headers("viewer@test.local","Viewer123!")
        r=self.client.post(f"/api/tasks/{self.task_id}/comments",headers=headers,json={"content":"This should be denied"})
        self.assertEqual(r.status_code,403)

    def test_local_frontend_origin_is_allowed_by_cors(self):
        r=self.client.options("/health",headers={"Origin":"http://localhost:3000","Access-Control-Request-Method":"GET"})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers.get("access-control-allow-origin"),"http://localhost:3000")

    def test_manager_cannot_access_an_unrelated_project_by_id(self):
        headers=self.headers("manager@test.local","Manager123!")
        r=self.client.get(f"/api/projects/{self.other_project_id}",headers=headers)
        self.assertEqual(r.status_code,403)

    def test_team_member_can_change_assigned_status_but_not_task_details(self):
        headers=self.headers("member@test.local","Member123!")
        url=f"/api/tasks/{self.task_id}"
        status_update=self.client.patch(url,headers=headers,json={"version":1,"status":"DONE"})
        self.assertEqual(status_update.status_code,200,status_update.text)
        detail_update=self.client.patch(url,headers=headers,json={"version":2,"title":"Unauthorized rename"})
        self.assertEqual(detail_update.status_code,403)

    def test_stale_task_version_returns_latest_task_with_conflict(self):
        headers=self.headers("manager@test.local","Manager123!")
        url=f"/api/tasks/{self.task_id}"
        first=self.client.patch(url,headers=headers,json={"version":1,"status":"IN_PROGRESS"})
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(first.json()["version"],2)
        stale=self.client.patch(url,headers=headers,json={"version":1,"status":"DONE"})
        self.assertEqual(stale.status_code,409)
        self.assertEqual(stale.json()["detail"]["latest"]["status"],"IN_PROGRESS")
        self.assertEqual(stale.json()["detail"]["latest"]["version"],2)

if __name__=="__main__": unittest.main()
