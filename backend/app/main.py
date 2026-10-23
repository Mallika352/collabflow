"""Local-first CollabFlow API. Authorization is checked at every route."""
from datetime import date, datetime, timedelta, timezone
from enum import Enum
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, Field
from pwdlib import PasswordHash
from sqlalchemy import Boolean, Date, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, select, update, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:change-me@127.0.0.1:3306/collabflow")
JWT_SECRET = os.getenv("JWT_SECRET", "local-development-secret-change-before-deployment")
TOKEN_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "720"))
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
password_hash = PasswordHash.recommended()
oauth = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
def utcnow() -> datetime:
    """Naive UTC for MySQL DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Base(DeclarativeBase): pass
class Role(str, Enum): ADMIN="ADMIN"; PROJECT_MANAGER="PROJECT_MANAGER"; TEAM_MEMBER="TEAM_MEMBER"; VIEWER="VIEWER"
class ProjectRole(str, Enum): MANAGER="MANAGER"; MEMBER="MEMBER"; VIEWER="VIEWER"
class TaskStatus(str, Enum): TODO="TODO"; IN_PROGRESS="IN_PROGRESS"; IN_REVIEW="IN_REVIEW"; DONE="DONE"
class Priority(str, Enum): LOW="LOW"; MEDIUM="MEDIUM"; HIGH="HIGH"; URGENT="URGENT"

class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(primary_key=True); name: Mapped[str]=mapped_column(String(120)); email: Mapped[str]=mapped_column(String(255), unique=True, index=True); password_hash: Mapped[str]=mapped_column(String(255)); global_role: Mapped[Role]=mapped_column(SqlEnum(Role)); is_active: Mapped[bool]=mapped_column(Boolean, default=True); created_at: Mapped[datetime]=mapped_column(DateTime, default=utcnow); updated_at: Mapped[datetime]=mapped_column(DateTime, default=utcnow, onupdate=utcnow)
class Project(Base):
    __tablename__="projects"
    id: Mapped[int]=mapped_column(primary_key=True); name: Mapped[str]=mapped_column(String(180)); description: Mapped[str]=mapped_column(Text, default=""); status: Mapped[str]=mapped_column(String(24), default="ACTIVE"); created_by: Mapped[int]=mapped_column(ForeignKey("users.id")); project_manager_id: Mapped[int|None]=mapped_column(ForeignKey("users.id"), nullable=True); archived_at: Mapped[datetime|None]=mapped_column(DateTime, nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime, default=utcnow); updated_at: Mapped[datetime]=mapped_column(DateTime, default=utcnow, onupdate=utcnow)
class Membership(Base):
    __tablename__="project_members"; __table_args__=(UniqueConstraint("project_id","user_id"),)
    id: Mapped[int]=mapped_column(primary_key=True); project_id: Mapped[int]=mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True); user_id: Mapped[int]=mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True); project_role: Mapped[ProjectRole]=mapped_column(SqlEnum(ProjectRole)); joined_at: Mapped[datetime]=mapped_column(DateTime, default=utcnow)
class Task(Base):
    __tablename__="tasks"
    id: Mapped[int]=mapped_column(primary_key=True); project_id: Mapped[int]=mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True); title: Mapped[str]=mapped_column(String(240)); description: Mapped[str]=mapped_column(Text, default=""); status: Mapped[TaskStatus]=mapped_column(SqlEnum(TaskStatus), default=TaskStatus.TODO); priority: Mapped[Priority]=mapped_column(SqlEnum(Priority), default=Priority.MEDIUM); assignee_id: Mapped[int|None]=mapped_column(ForeignKey("users.id"), nullable=True); created_by: Mapped[int]=mapped_column(ForeignKey("users.id")); due_date: Mapped[date|None]=mapped_column(Date, nullable=True); version: Mapped[int]=mapped_column(Integer, default=1); created_at: Mapped[datetime]=mapped_column(DateTime, default=utcnow); updated_at: Mapped[datetime]=mapped_column(DateTime, default=utcnow, onupdate=utcnow)
class Comment(Base):
    __tablename__="comments"
    id: Mapped[int]=mapped_column(primary_key=True); task_id: Mapped[int]=mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True); user_id: Mapped[int]=mapped_column(ForeignKey("users.id")); content: Mapped[str]=mapped_column(String(2000)); created_at: Mapped[datetime]=mapped_column(DateTime, default=utcnow); updated_at: Mapped[datetime]=mapped_column(DateTime, default=utcnow, onupdate=utcnow)

class Input(BaseModel): model_config=ConfigDict(from_attributes=True)
class Login(Input): email: str=Field(pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",max_length=255); password: str
class UserCreate(Input): name: str=Field(min_length=1,max_length=120); email: str=Field(pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",max_length=255); password: str=Field(min_length=8); global_role: Role
class UserPatch(Input): name: str|None=Field(default=None,min_length=1,max_length=120); global_role: Role|None=None; is_active: bool|None=None
class ProjectCreate(Input): name: str=Field(min_length=1,max_length=180); description: str=""; project_manager_id: int|None=None
class ProjectPatch(Input): name: str|None=Field(default=None,min_length=1,max_length=180); description: str|None=None; project_manager_id: int|None=None
class MemberInput(Input): user_id: int; project_role: ProjectRole=ProjectRole.MEMBER
class MemberPatch(Input): project_role: ProjectRole
class TaskCreate(Input): title: str=Field(min_length=1,max_length=240); description: str=""; status: TaskStatus=TaskStatus.TODO; priority: Priority=Priority.MEDIUM; assignee_id: int|None=None; due_date: date|None=None
class TaskPatch(Input): version: int=Field(ge=1); title: str|None=Field(default=None,min_length=1,max_length=240); description: str|None=None; status: TaskStatus|None=None; priority: Priority|None=None; assignee_id: int|None=None; due_date: date|None=None
class CommentInput(Input): content: str=Field(min_length=1,max_length=2000)

app=FastAPI(title="CollabFlow API", version="1.0.0", description="Local project collaboration API with role checks and optimistic task concurrency.")
app.add_middleware(CORSMiddleware, allow_origins=[FRONTEND_ORIGIN,"http://127.0.0.1:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()
def user_data(u): return {"id":u.id,"name":u.name,"email":u.email,"global_role":u.global_role.value,"is_active":u.is_active,"created_at":u.created_at}
def project_data(p,s):
    count=s.scalar(select(func.count(Task.id)).where(Task.project_id==p.id)) or 0
    done=s.scalar(select(func.count(Task.id)).where(Task.project_id==p.id,Task.status==TaskStatus.DONE)) or 0
    return {"id":p.id,"name":p.name,"description":p.description,"status":p.status,"created_by":p.created_by,"project_manager_id":p.project_manager_id,"archived_at":p.archived_at,"created_at":p.created_at,"task_count":count,"completed_count":done}
def task_data(t,s):
    assignee=s.get(User,t.assignee_id) if t.assignee_id else None
    return {"id":t.id,"project_id":t.project_id,"title":t.title,"description":t.description,"status":t.status.value,"priority":t.priority.value,"assignee_id":t.assignee_id,"assignee_name":assignee.name if assignee else None,"created_by":t.created_by,"due_date":t.due_date,"version":t.version,"created_at":t.created_at,"updated_at":t.updated_at}
def current_user(token: str=Depends(oauth), s: Session=Depends(db)):
    try: uid=int(jwt.decode(token,JWT_SECRET,algorithms=["HS256"]).get("sub",0))
    except (JWTError,ValueError): raise HTTPException(401,"Invalid or expired session")
    u=s.get(User,uid)
    if not u or not u.is_active: raise HTTPException(401,"Account unavailable")
    return u
def admin(u):
    if u.global_role!=Role.ADMIN: raise HTTPException(403,"Administrator access required")
def project_access(s,pid,u,write=False):
    p=s.get(Project,pid)
    if not p: raise HTTPException(404,"Project not found")
    m=s.scalar(select(Membership).where(Membership.project_id==pid,Membership.user_id==u.id))
    manager=u.global_role==Role.ADMIN or (u.global_role==Role.PROJECT_MANAGER and p.project_manager_id==u.id) or bool(u.global_role!=Role.VIEWER and m and m.project_role==ProjectRole.MANAGER)
    if u.global_role!=Role.ADMIN and not m and not manager: raise HTTPException(403,"Project access denied")
    if write and not manager: raise HTTPException(403,"Project manager access required")
    return p,m,manager
def task_access(s,tid,u,write=False):
    t=s.get(Task,tid)
    if not t: raise HTTPException(404,"Task not found")
    p,m,manager=project_access(s,t.project_id,u)
    if write and (m and m.project_role==ProjectRole.VIEWER and not manager): raise HTTPException(403,"Viewer project access is read-only")
    if write and not manager and not (u.global_role==Role.TEAM_MEMBER and t.assignee_id==u.id): raise HTTPException(403,"Task update not permitted")
    return t,p,m,manager
def valid_assignee(s,pid,uid):
    if uid is not None and not s.scalar(select(Membership.id).join(User,User.id==Membership.user_id).where(Membership.project_id==pid,Membership.user_id==uid,Membership.project_role!=ProjectRole.VIEWER,User.global_role!=Role.VIEWER,User.is_active.is_(True))):
        raise HTTPException(400,"Assignee must be an active non-viewer member of this project")

@app.get("/")
def root(): return {"message":"CollabFlow API","docs":"/docs"}
@app.get("/health")
def health(): return {"status":"ok"}
@app.post("/api/auth/login")
def login(data: Login,s:Session=Depends(db)):
    u=s.scalar(select(User).where(User.email==str(data.email).lower()))
    if not u or not u.is_active or not password_hash.verify(data.password,u.password_hash): raise HTTPException(401,"Incorrect email or password")
    token=jwt.encode({"sub":str(u.id),"exp":datetime.now(timezone.utc)+timedelta(minutes=TOKEN_MINUTES)},JWT_SECRET,algorithm="HS256")
    return {"access_token":token,"token_type":"bearer","user":user_data(u)}
@app.get("/api/auth/me")
def me(u:User=Depends(current_user)): return user_data(u)
@app.post("/api/auth/logout",status_code=204)
def logout(): return Response(status_code=204)

@app.get("/api/users")
def users(s:Session=Depends(db),u:User=Depends(current_user)):
    admin(u); return [user_data(x) for x in s.scalars(select(User).order_by(User.name))]
@app.post("/api/users",status_code=201)
def create_user(data:UserCreate,s:Session=Depends(db),u:User=Depends(current_user)):
    admin(u); email=str(data.email).lower()
    if s.scalar(select(User.id).where(User.email==email)): raise HTTPException(409,"Email already exists")
    x=User(name=data.name,email=email,password_hash=password_hash.hash(data.password),global_role=data.global_role); s.add(x); s.commit(); s.refresh(x); return user_data(x)
@app.get("/api/users/{uid}")
def get_user(uid:int,s:Session=Depends(db),u:User=Depends(current_user)):
    admin(u); x=s.get(User,uid)
    if not x: raise HTTPException(404,"User not found")
    return user_data(x)
@app.patch("/api/users/{uid}")
def patch_user(uid:int,data:UserPatch,s:Session=Depends(db),u:User=Depends(current_user)):
    admin(u); x=s.get(User,uid)
    if not x: raise HTTPException(404,"User not found")
    if x.global_role==Role.ADMIN and x.is_active and (data.is_active is False or data.global_role not in (None,Role.ADMIN)) and (s.scalar(select(func.count(User.id)).where(User.global_role==Role.ADMIN,User.is_active.is_(True))) or 0)<=1: raise HTTPException(400,"Cannot remove the last active administrator")
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(x,k,v)
    s.commit(); return user_data(x)
@app.post("/api/users/{uid}/deactivate")
def deactivate(uid:int,s:Session=Depends(db),u:User=Depends(current_user)):
    admin(u); x=s.get(User,uid)
    if not x: raise HTTPException(404,"User not found")
    if x.global_role==Role.ADMIN and x.is_active and (s.scalar(select(func.count(User.id)).where(User.global_role==Role.ADMIN,User.is_active.is_(True))) or 0)<=1: raise HTTPException(400,"Cannot deactivate the last active administrator")
    x.is_active=False; s.commit(); return {"ok":True}

@app.get("/api/projects")
def projects(s:Session=Depends(db),u:User=Depends(current_user)):
    q=select(Project).where(Project.archived_at.is_(None))
    if u.global_role!=Role.ADMIN:
        visible=Project.id.in_(select(Membership.project_id).where(Membership.user_id==u.id))
        if u.global_role==Role.PROJECT_MANAGER: visible=visible | (Project.project_manager_id==u.id)
        q=q.where(visible)
    return [project_data(p,s) for p in s.scalars(q.order_by(Project.updated_at.desc()))]
@app.post("/api/projects",status_code=201)
def create_project(data:ProjectCreate,s:Session=Depends(db),u:User=Depends(current_user)):
    if u.global_role not in (Role.ADMIN,Role.PROJECT_MANAGER): raise HTTPException(403,"Only admins and project managers can create projects")
    pm=data.project_manager_id or u.id
    manager_user=s.get(User,pm)
    if not manager_user or not manager_user.is_active or manager_user.global_role not in (Role.PROJECT_MANAGER,Role.ADMIN): raise HTTPException(400,"Project manager must be an active Project Manager or Admin")
    p=Project(name=data.name,description=data.description,created_by=u.id,project_manager_id=pm); s.add(p); s.flush(); s.add(Membership(project_id=p.id,user_id=pm,project_role=ProjectRole.MANAGER)); s.commit(); s.refresh(p); return project_data(p,s)
@app.get("/api/projects/{pid}")
def get_project(pid:int,s:Session=Depends(db),u:User=Depends(current_user)):
    p,_,_=project_access(s,pid,u); return project_data(p,s)
@app.patch("/api/projects/{pid}")
def patch_project(pid:int,data:ProjectPatch,s:Session=Depends(db),u:User=Depends(current_user)):
    p,_,_=project_access(s,pid,u,True)
    if data.project_manager_id is not None:
        x=s.get(User,data.project_manager_id)
        if not x or not x.is_active or x.global_role not in (Role.PROJECT_MANAGER,Role.ADMIN): raise HTTPException(400,"Project manager must be an active Project Manager or Admin")
    old_manager=p.project_manager_id
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(p,k,v)
    if data.project_manager_id is not None:
        new_membership=s.scalar(select(Membership).where(Membership.project_id==pid,Membership.user_id==data.project_manager_id))
        if new_membership: new_membership.project_role=ProjectRole.MANAGER
        else: s.add(Membership(project_id=pid,user_id=data.project_manager_id,project_role=ProjectRole.MANAGER))
        if old_manager and old_manager!=data.project_manager_id:
            old_membership=s.scalar(select(Membership).where(Membership.project_id==pid,Membership.user_id==old_manager))
            if old_membership and old_membership.project_role==ProjectRole.MANAGER: old_membership.project_role=ProjectRole.MEMBER
    s.commit(); return project_data(p,s)
@app.post("/api/projects/{pid}/archive")
def archive(pid:int,s:Session=Depends(db),u:User=Depends(current_user)):
    p,_,_=project_access(s,pid,u,True); p.archived_at=utcnow(); p.status="ARCHIVED"; s.commit(); return project_data(p,s)
@app.delete("/api/projects/{pid}",status_code=204)
def delete_project(pid:int,s:Session=Depends(db),u:User=Depends(current_user)):
    admin(u); p=s.get(Project,pid)
    if not p: raise HTTPException(404,"Project not found")
    s.delete(p); s.commit(); return Response(status_code=204)

@app.get("/api/projects/{pid}/team")
def team(pid:int,s:Session=Depends(db),u:User=Depends(current_user)):
    project_access(s,pid,u)
    rows=s.execute(select(User,Membership).join(Membership,Membership.user_id==User.id).where(Membership.project_id==pid)).all()
    return [{**user_data(person),"project_role":membership.project_role.value,"joined_at":membership.joined_at} for person,membership in rows]
@app.get("/api/projects/{pid}/available-members")
def available_members(pid:int,s:Session=Depends(db),u:User=Depends(current_user)):
    project_access(s,pid,u,True)
    existing=select(Membership.user_id).where(Membership.project_id==pid)
    return [user_data(person) for person in s.scalars(select(User).where(User.is_active.is_(True),~User.id.in_(existing)).order_by(User.name))]
@app.post("/api/projects/{pid}/team",status_code=201)
def add_member(pid:int,data:MemberInput,s:Session=Depends(db),u:User=Depends(current_user)):
    project_access(s,pid,u,True); x=s.get(User,data.user_id)
    if not x or not x.is_active: raise HTTPException(404,"Active user not found")
    if data.project_role==ProjectRole.MANAGER and x.global_role not in (Role.ADMIN,Role.PROJECT_MANAGER): raise HTTPException(400,"Only Admins and Project Managers can have the project Manager role")
    if s.scalar(select(Membership.id).where(Membership.project_id==pid,Membership.user_id==x.id)): raise HTTPException(409,"User already belongs to this project")
    m=Membership(project_id=pid,user_id=x.id,project_role=data.project_role); s.add(m); s.commit(); return {**user_data(x),"project_role":m.project_role.value}
@app.patch("/api/projects/{pid}/team/{uid}")
def change_member(pid:int,uid:int,data:MemberPatch,s:Session=Depends(db),u:User=Depends(current_user)):
    project_access(s,pid,u,True); m=s.scalar(select(Membership).where(Membership.project_id==pid,Membership.user_id==uid))
    if not m: raise HTTPException(404,"Membership not found")
    x=s.get(User,uid)
    if data.project_role==ProjectRole.MANAGER and x.global_role not in (Role.ADMIN,Role.PROJECT_MANAGER): raise HTTPException(400,"Only Admins and Project Managers can have the project Manager role")
    m.project_role=data.project_role; s.commit(); return {"user_id":uid,"project_role":m.project_role.value}
@app.delete("/api/projects/{pid}/team/{uid}",status_code=204)
def remove_member(pid:int,uid:int,s:Session=Depends(db),u:User=Depends(current_user)):
    p,_,_=project_access(s,pid,u,True); m=s.scalar(select(Membership).where(Membership.project_id==pid,Membership.user_id==uid))
    if not m: raise HTTPException(404,"Membership not found")
    if p.project_manager_id==uid: raise HTTPException(409,"Assign a different project manager before removing this member")
    if s.scalar(select(Task.id).where(Task.project_id==pid,Task.assignee_id==uid).limit(1)): raise HTTPException(409,"Reassign this member’s tasks before removing them")
    s.delete(m); s.commit(); return Response(status_code=204)

@app.get("/api/projects/{pid}/tasks")
def tasks(pid:int,status_filter:TaskStatus|None=Query(default=None,alias="status"),priority:Priority|None=None,assignee_id:int|None=None,offset:int=0,limit:int=100,s:Session=Depends(db),u:User=Depends(current_user)):
    project_access(s,pid,u); q=select(Task).where(Task.project_id==pid)
    if status_filter: q=q.where(Task.status==status_filter)
    if priority: q=q.where(Task.priority==priority)
    if assignee_id: q=q.where(Task.assignee_id==assignee_id)
    return [task_data(t,s) for t in s.scalars(q.order_by(Task.updated_at.desc()).offset(offset).limit(min(limit,100)))]
@app.post("/api/projects/{pid}/tasks",status_code=201)
def create_task(pid:int,data:TaskCreate,s:Session=Depends(db),u:User=Depends(current_user)):
    project_access(s,pid,u,True); valid_assignee(s,pid,data.assignee_id); t=Task(project_id=pid,created_by=u.id,**data.model_dump()); s.add(t); s.commit(); s.refresh(t); return task_data(t,s)
@app.get("/api/tasks/{tid}")
def get_task(tid:int,s:Session=Depends(db),u:User=Depends(current_user)):
    t,_,_,_=task_access(s,tid,u); return task_data(t,s)
@app.patch("/api/tasks/{tid}")
def patch_task(tid:int,data:TaskPatch,s:Session=Depends(db),u:User=Depends(current_user)):
    t,p,m,manager=task_access(s,tid,u,True); values=data.model_dump(exclude={"version"},exclude_unset=True)
    if not manager and set(values)-{"status"}: raise HTTPException(403,"Team members may only change task status")
    if "assignee_id" in values: valid_assignee(s,t.project_id,values["assignee_id"])
    values["version"]=Task.version+1; values["updated_at"]=utcnow()
    result=s.execute(update(Task).where(Task.id==tid,Task.version==data.version).values(**values))
    if result.rowcount!=1:
        s.rollback(); latest=s.get(Task,tid)
        raise HTTPException(409,detail=jsonable_encoder({"message":"This task changed after you opened it. Reload the latest version before saving.","latest":task_data(latest,s) if latest else None}))
    s.commit(); s.refresh(t); return task_data(t,s)
@app.delete("/api/tasks/{tid}",status_code=204)
def delete_task(tid:int,s:Session=Depends(db),u:User=Depends(current_user)):
    t,_,_,manager=task_access(s,tid,u)
    if not manager: raise HTTPException(403,"Project manager access required")
    s.delete(t); s.commit(); return Response(status_code=204)
@app.get("/api/tasks/{tid}/comments")
def comments(tid:int,s:Session=Depends(db),u:User=Depends(current_user)):
    task_access(s,tid,u); rows=s.execute(select(Comment,User).join(User,Comment.user_id==User.id).where(Comment.task_id==tid).order_by(Comment.created_at)).all()
    return [{"id":c.id,"task_id":c.task_id,"user_id":c.user_id,"author":x.name,"content":c.content,"created_at":c.created_at} for c,x in rows]
@app.post("/api/tasks/{tid}/comments",status_code=201)
def add_comment(tid:int,data:CommentInput,s:Session=Depends(db),u:User=Depends(current_user)):
    t,_,m,manager=task_access(s,tid,u)
    if u.global_role==Role.VIEWER or (m and m.project_role==ProjectRole.VIEWER and not manager): raise HTTPException(403,"Viewers cannot comment")
    c=Comment(task_id=tid,user_id=u.id,content=data.content.strip())
    if not c.content: raise HTTPException(422,"Comment cannot be blank")
    s.add(c); s.commit(); s.refresh(c); return {"id":c.id,"task_id":tid,"user_id":u.id,"author":u.name,"content":c.content,"created_at":c.created_at}
@app.delete("/api/comments/{cid}",status_code=204)
def delete_comment(cid:int,s:Session=Depends(db),u:User=Depends(current_user)):
    c=s.get(Comment,cid)
    if not c: raise HTTPException(404,"Comment not found")
    task_access(s,c.task_id,u)
    if u.global_role!=Role.ADMIN and c.user_id!=u.id: raise HTTPException(403,"You can only delete your own comments")
    s.delete(c); s.commit(); return Response(status_code=204)

@app.get("/api/dashboard")
def dashboard(s:Session=Depends(db),u:User=Depends(current_user)):
    ps=projects(s,u); ids=[p["id"] for p in ps]
    ts=list(s.scalars(select(Task).where(Task.project_id.in_(ids)).order_by(Task.updated_at.desc()).limit(100))) if ids else []
    today=date.today()
    return {"projects":len(ps),"tasks":len(ts),"completed":sum(t.status==TaskStatus.DONE for t in ts),"overdue":sum(bool(t.due_date and t.due_date<today and t.status!=TaskStatus.DONE) for t in ts),"recent_tasks":[task_data(t,s) for t in ts[:6]]}

@app.on_event("startup")
def initialize():
    if os.getenv("AUTO_CREATE_TABLES","false").lower()=="true": Base.metadata.create_all(engine)
