"use client";

type Task = { id:number; project_id:number; status:string };
type Project = { id:number; name:string };

export function StatusDonut({tasks}:{tasks:Task[]}) {
  const counts=[{label:"To do",value:tasks.filter(t=>t.status==="TODO").length,color:"#c8c3f5"},{label:"In progress",value:tasks.filter(t=>t.status==="IN_PROGRESS").length,color:"#7869dc"},{label:"In review",value:tasks.filter(t=>t.status==="IN_REVIEW").length,color:"#b59ce8"},{label:"Completed",value:tasks.filter(t=>t.status==="DONE").length,color:"#64b99a"}];
  const total=tasks.length;let cursor=0;
  const segments=counts.map(item=>{const start=cursor;cursor+=item.value/total*100;return {...item,start,end:cursor}});
  return <section className="panel insight-panel"><div className="panel-heading"><div><h2>Task status</h2><p>Distribution across your accessible projects</p></div><span className="chart-period">All tasks</span></div><div className="donut-wrap"><svg className="donut-chart" viewBox="0 0 120 120" role="img" aria-label={`Task status: ${counts.map(x=>`${x.label} ${x.value}`).join(", ")}`}><circle cx="60" cy="60" r="48" fill="none" stroke="#f1f0f8" strokeWidth="13"/>{segments.map(segment=><circle key={segment.label} cx="60" cy="60" r="48" fill="none" stroke={segment.color} strokeWidth="13" strokeDasharray={`${(segment.end-segment.start)*3.016} ${301.6-(segment.end-segment.start)*3.016}`} strokeDashoffset={`${-segment.start*3.016}`} transform="rotate(-90 60 60)"/>)}<text x="60" y="56" textAnchor="middle" className="donut-total">{total}</text><text x="60" y="70" textAnchor="middle" className="donut-caption">TASKS</text></svg><div className="chart-legend">{counts.map(item=><div key={item.label}><i style={{background:item.color}}/><span>{item.label}</span><b>{item.value}</b></div>)}</div></div></section>;
}

export function ProjectBars({projects,tasks}:{projects:Project[];tasks:Task[]}) {
  const rows=projects.map(project=>{const items=tasks.filter(task=>task.project_id===project.id);return {project,done:items.filter(task=>task.status==="DONE").length,progress:items.filter(task=>task.status==="IN_PROGRESS").length,pending:items.filter(task=>task.status==="TODO"||task.status==="IN_REVIEW").length,total:items.length}});
  const max=Math.max(1,...rows.map(row=>row.total));
  return <section className="panel insight-panel"><div className="panel-heading"><div><h2>Project progress</h2><p>Completed, in progress, and pending tasks</p></div><span className="chart-period">{projects.length} projects</span></div><div className="bar-chart">{rows.map(row=><div className="bar-row" key={row.project.id}><div className="bar-label"><span>{row.project.name}</span><small>{row.done}/{row.total}</small></div><div className="bar-track" role="img" aria-label={`${row.project.name}: ${row.done} completed, ${row.progress} in progress, ${row.pending} pending`}><i className="bar-done" style={{width:`${row.done/max*100}%`}}/><i className="bar-progress" style={{width:`${row.progress/max*100}%`}}/><i className="bar-pending" style={{width:`${row.pending/max*100}%`}}/></div></div>)}</div><div className="bar-legend"><span><i className="bar-done"/>Completed</span><span><i className="bar-progress"/>In progress</span><span><i className="bar-pending"/>Pending</span></div></section>;
}
