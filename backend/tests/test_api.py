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
        cls.test_password_hash=password_hash.hash("Password123!")
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
            self.admin=User(name="Admin",email="admin@test.local",password_hash=self.test_password_hash,global_role=Role.ADMIN)
            self.manager=User(name="Manager",email="manager@test.local",password_hash=self.test_password_hash,global_role=Role.PROJECT_MANAGER)
            self.other_manager=User(name="Other Manager",email="other-manager@test.local",password_hash=self.test_password_hash,global_role=Role.PROJECT_MANAGER)
            self.member=User(name="Member",email="member@test.local",password_hash=self.test_password_hash,global_role=Role.TEAM_MEMBER)
            self.viewer=User(name="Viewer",email="viewer@test.local",password_hash=self.test_password_hash,global_role=Role.VIEWER)
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
        headers=self.headers("admin@test.local","Password123!")
        self.assertEqual(self.client.get(f"/api/projects/{self.other_project_id}",headers=headers).status_code,200)
        r=self.client.post("/api/users",headers=headers,json={"name":"New teammate","email":"new@test.local","password":"NewMember123!","global_role":"TEAM_MEMBER"})
        self.assertEqual(r.status_code,201,r.text)

    def test_admin_user_details_and_account_controls(self):
        headers=self.headers("admin@test.local","Password123!")
        detail=self.client.get(f"/api/users/{self.member.id}",headers=headers)
        self.assertEqual(detail.status_code,200)
        update=self.client.patch(f"/api/users/{self.member.id}",headers=headers,json={"name":"Updated Member","global_role":"VIEWER"})
        self.assertEqual(update.status_code,200)
        self.assertEqual(update.json()["name"],"Updated Member")
        self.assertEqual(self.client.post(f"/api/users/{self.member.id}/deactivate",headers=headers).status_code,200)

    def test_admin_created_project_becomes_visible_through_membership(self):
        headers=self.headers("admin@test.local","Password123!")
        created=self.client.post("/api/projects",headers=headers,json={"name":"Admin launch","description":"Shared launch"})
        self.assertEqual(created.status_code,201,created.text)
        project_id=created.json()["id"]
        member_headers=self.headers("member@test.local","Password123!")
        self.assertNotIn(project_id,[p["id"] for p in self.client.get("/api/projects",headers=member_headers).json()])
        add=self.client.post(f"/api/projects/{project_id}/team",headers=headers,json={"user_id":self.member.id,"project_role":"MEMBER"})
        self.assertEqual(add.status_code,201,add.text)
        self.assertIn(project_id,[p["id"] for p in self.client.get("/api/projects",headers=member_headers).json()])
        self.assertEqual(self.client.get(f"/api/projects/{project_id}",headers=member_headers).status_code,200)

    def test_project_managers_can_add_and_remove_existing_users(self):
        headers=self.headers("manager@test.local","Password123!")
        candidates=self.client.get(f"/api/projects/{self.project.id}/available-members",headers=headers)
        self.assertEqual(candidates.status_code,200,candidates.text)
        self.assertIn(self.other_manager.id,[person["id"] for person in candidates.json()])
        add=self.client.post(f"/api/projects/{self.project.id}/team",headers=headers,json={"user_id":self.other_manager.id,"project_role":"MEMBER"})
        self.assertEqual(add.status_code,201,add.text)
        duplicate=self.client.post(f"/api/projects/{self.project.id}/team",headers=headers,json={"user_id":self.other_manager.id,"project_role":"MEMBER"})
        self.assertEqual(duplicate.status_code,409)
        invalid=self.client.post(f"/api/projects/{self.project.id}/team",headers=headers,json={"user_id":99999,"project_role":"MEMBER"})
        self.assertEqual(invalid.status_code,404)
        other_headers=self.headers("other-manager@test.local","Password123!")
        self.assertEqual(self.client.get(f"/api/projects/{self.project.id}",headers=other_headers).status_code,200)
        self.assertEqual(self.client.delete(f"/api/projects/{self.project.id}/team/{self.other_manager.id}",headers=headers).status_code,204)
        self.assertEqual(self.client.get(f"/api/projects/{self.project.id}",headers=other_headers).status_code,403)
        self.assertEqual(self.client.delete(f"/api/projects/{self.project.id}/team/{self.member.id}",headers=headers).status_code,409)
        viewer_headers=self.headers("viewer@test.local","Password123!")
        self.assertEqual(self.client.post(f"/api/projects/{self.project.id}/team",headers=viewer_headers,json={"user_id":self.other_manager.id,"project_role":"MEMBER"}).status_code,403)

    def test_task_assignee_must_be_an_existing_project_member(self):
        headers=self.headers("manager@test.local","Password123!")
        invalid=self.client.post(f"/api/projects/{self.project.id}/tasks",headers=headers,json={"title":"Invalid assignment","assignee_id":self.other_manager.id})
        self.assertEqual(invalid.status_code,400)
        viewer_assignment=self.client.post(f"/api/projects/{self.project.id}/tasks",headers=headers,json={"title":"Viewer assignment","assignee_id":self.viewer.id})
        self.assertEqual(viewer_assignment.status_code,400)
        self.client.post(f"/api/projects/{self.project.id}/team",headers=headers,json={"user_id":self.other_manager.id,"project_role":"MEMBER"})
        valid=self.client.post(f"/api/projects/{self.project.id}/tasks",headers=headers,json={"title":"Eligible assignment","assignee_id":self.other_manager.id})
        self.assertEqual(valid.status_code,201,valid.text)
        self.assertEqual(valid.json()["assignee_id"],self.other_manager.id)

    def test_viewer_cannot_change_task(self):
        headers=self.headers("viewer@test.local","Password123!")
        r=self.client.patch(f"/api/tasks/{self.task_id}",headers=headers,json={"version":1,"status":"DONE"})
        self.assertEqual(r.status_code,403)

    def test_viewer_cannot_comment(self):
        headers=self.headers("viewer@test.local","Password123!")
        r=self.client.post(f"/api/tasks/{self.task_id}/comments",headers=headers,json={"content":"This should be denied"})
        self.assertEqual(r.status_code,403)
        self.assertEqual(self.client.get("/api/users",headers=headers).status_code,403)

    def test_local_frontend_origin_is_allowed_by_cors(self):
        r=self.client.options("/health",headers={"Origin":"http://localhost:3000","Access-Control-Request-Method":"GET"})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers.get("access-control-allow-origin"),"http://localhost:3000")

    def test_manager_cannot_access_an_unrelated_project_by_id(self):
        headers=self.headers("manager@test.local","Password123!")
        r=self.client.get(f"/api/projects/{self.other_project_id}",headers=headers)
        self.assertEqual(r.status_code,403)

    def test_team_member_can_change_assigned_status_but_not_task_details(self):
        headers=self.headers("member@test.local","Password123!")
        url=f"/api/tasks/{self.task_id}"
        status_update=self.client.patch(url,headers=headers,json={"version":1,"status":"DONE"})
        self.assertEqual(status_update.status_code,200,status_update.text)
        detail_update=self.client.patch(url,headers=headers,json={"version":2,"title":"Unauthorized rename"})
        self.assertEqual(detail_update.status_code,403)

    def test_task_completion_can_be_toggled_and_updates_project_dashboard(self):
        headers=self.headers("manager@test.local","Password123!")
        url=f"/api/tasks/{self.task_id}"
        completed=self.client.patch(url,headers=headers,json={"version":1,"status":"DONE"})
        self.assertEqual(completed.status_code,200,completed.text)
        self.assertEqual(completed.json()["status"],"DONE")
        self.assertEqual(completed.json()["version"],2)
        dashboard=self.client.get("/api/dashboard",headers=headers).json()
        self.assertEqual(dashboard["completed"],1)
        self.assertEqual(self.client.get(f"/api/projects/{self.project.id}",headers=headers).json()["completed_count"],1)
        todo=self.client.patch(url,headers=headers,json={"version":2,"status":"TODO"})
        self.assertEqual(todo.status_code,200,todo.text)
        self.assertEqual(todo.json()["status"],"TODO")
        self.assertEqual(todo.json()["version"],3)
        self.assertEqual(self.client.get("/api/dashboard",headers=headers).json()["completed"],0)
        self.assertEqual(self.client.get(f"/api/projects/{self.project.id}",headers=headers).json()["completed_count"],0)

    def test_stale_task_version_returns_latest_task_with_conflict(self):
        headers=self.headers("manager@test.local","Password123!")
        url=f"/api/tasks/{self.task_id}"
        first=self.client.patch(url,headers=headers,json={"version":1,"status":"IN_PROGRESS"})
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(first.json()["version"],2)
        stale=self.client.patch(url,headers=headers,json={"version":1,"status":"DONE"})
        self.assertEqual(stale.status_code,409)
        self.assertEqual(stale.json()["detail"]["latest"]["status"],"IN_PROGRESS")
        self.assertEqual(stale.json()["detail"]["latest"]["version"],2)

if __name__=="__main__": unittest.main()
