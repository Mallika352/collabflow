"""Create tables and insert predictable demo data (safe to re-run)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import Base, Comment, Membership, Priority, Project, ProjectRole, Role, SessionLocal, Task, TaskStatus, User, engine, password_hash
from sqlalchemy import select

Base.metadata.create_all(engine)
with SessionLocal() as s:
    accounts=[
        ("Avery Admin","admin@collabflow.local","Admin123!",Role.ADMIN),
        ("Morgan Manager","manager@collabflow.local","Manager123!",Role.PROJECT_MANAGER),
        ("Taylor Member","member@collabflow.local","Member123!",Role.TEAM_MEMBER),
        ("Robin Viewer","viewer@collabflow.local","Viewer123!",Role.VIEWER),
    ]
    users={}
    for name,email,password,role in accounts:
        user=s.scalar(select(User).where(User.email==email))
        if not user:
            user=User(name=name,email=email,password_hash=password_hash.hash(password),global_role=role)
            s.add(user); s.flush()
        users[email]=user
    project=s.scalar(select(Project).where(Project.name=="Northstar launch"))
    if not project:
        manager=users["manager@collabflow.local"]
        project=Project(name="Northstar launch",description="A focused launch plan for the next product release.",created_by=users["admin@collabflow.local"].id,project_manager_id=manager.id)
        s.add(project); s.flush()
    roles={"manager@collabflow.local":ProjectRole.MANAGER,"member@collabflow.local":ProjectRole.MEMBER,"viewer@collabflow.local":ProjectRole.VIEWER,"admin@collabflow.local":ProjectRole.MANAGER}
    for email,role in roles.items():
        if not s.scalar(select(Membership.id).where(Membership.project_id==project.id,Membership.user_id==users[email].id)):
            s.add(Membership(project_id=project.id,user_id=users[email].id,project_role=role))
    if not s.scalar(select(Task.id).where(Task.project_id==project.id)):
        first=Task(project_id=project.id,title="Finalize launch brief",description="Align the team on scope and launch narrative.",status=TaskStatus.IN_REVIEW,priority=Priority.HIGH,assignee_id=users["member@collabflow.local"].id,created_by=users["manager@collabflow.local"].id)
        second=Task(project_id=project.id,title="Prepare onboarding checklist",description="Document the first-run experience.",status=TaskStatus.IN_PROGRESS,priority=Priority.MEDIUM,assignee_id=users["manager@collabflow.local"].id,created_by=users["manager@collabflow.local"].id)
        done=Task(project_id=project.id,title="Kickoff and team alignment",description="Agree on milestones and owners.",status=TaskStatus.DONE,priority=Priority.LOW,assignee_id=users["member@collabflow.local"].id,created_by=users["admin@collabflow.local"].id)
        s.add_all([first,second,done]); s.flush()
        s.add(Comment(task_id=first.id,user_id=users["manager@collabflow.local"].id,content="Please share the final narrative for review."))
    s.commit()
print("Database ready. Demo users and Northstar launch sample data are available.")
