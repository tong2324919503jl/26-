"""Continuous scanner placement with convex Voronoi-cell coverage constraints.

Offline prototype uses SciPy SLSQP. Acceptance separately checks all cell
vertices and a global finite coverage certificate; no source truth is used.
"""
from __future__ import annotations
import math
import numpy as np
from scipy.optimize import minimize
from problem3.geometry import initial_region,clip_halfplane,distance,polygon_centroid,certified_covering_radius
from problem4.routing import two_opt,or_opt,nearest_seed,insertion_seed,route_length
from problem3.experiments_v3.policy import CombinedPolicy,IncrementalPolicy

def voronoi_cells(points):
    cells=[]
    for i,p in enumerate(points):
        cell=initial_region(sides=96)
        for j,q in enumerate(points):
            if i==j:continue
            ax,ay=q[0]-p[0],q[1]-p[1]
            cell=clip_halfplane(cell,ax,ay,(ax*(q[0]+p[0])+ay*(q[1]+p[1]))/2)
            if not cell:break
        cells.append(cell)
    return cells

def remove_covered_disks(cell,covered,sides=24):
    parts=[cell] if cell else []
    for center in covered:
        remaining=[]
        # An inscribed polygon lies strictly inside the guaranteed 1000m
        # empty disk of every as-yet-undetected omnidirectional channel.
        radius=999.99*math.cos(math.pi/sides)
        for part in parts:
            inside=part
            for k in range(sides):
                a,b=math.cos(math.tau*k/sides),math.sin(math.tau*k/sides)
                c=a*center[0]+b*center[1]+radius
                outside=clip_halfplane(inside,-a,-b,-c)
                if outside:remaining.append(outside)
                inside=clip_halfplane(inside,a,b,c)
                if not inside:break
        parts=remaining
        if not parts:break
    return [p for part in parts for p in part]

class CellPlanningMixin:
    cell_iterations=2
    cell_max_solver_steps=40
    cell_clear_nodes=True
    joint_route=False
    subtract_covered=False

    def _route_goal(self,client,pending):
        if not pending or len(set(self.regions)|self.cleared)==16:
            return super()._route_goal(client,pending)
        if self.subtract_covered:
            for i in reversed(range(len(pending))):
                if certified_covering_radius(self.coverage_visited+pending[:i]+pending[i+1:])<=999.9999:
                    pending.pop(i)
            if not pending:return super()._route_goal(client,pending)
            cells=[remove_covered_disks(cell,self.coverage_visited) for cell in voronoi_cells(pending)]
        else:
            cells=voronoi_cells(self.coverage_visited+pending)[len(self.coverage_visited):]
        movable=[i for i,c in enumerate(cells) if c]
        goals=[(p,'scan',i) for i,p in enumerate(pending)]
        goals += [(polygon_centroid(p),'clear',ch) for ch,p in self.regions.items() if ch not in self.cleared]
        if not self.cell_clear_nodes and len(goals)>len(pending):
            return super()._route_goal(client,pending)
        poses=np.array([g[0] for g in goals],dtype=float)/1000
        start=np.array(client.position)/1000
        bounds=[np.array(cells[i])/1000 for i in movable]
        initial_poses=poses.copy()
        last_route=None
        for iteration in range(self.cell_iterations):
            pts=[tuple(p*1000) for p in poses]+[client.position]
            matrix=[[distance(a,b) for b in pts] for a in pts]
            seeds=[nearest_seed(matrix),insertion_seed(matrix)]
            if last_route is not None:seeds.append(last_route)
            route=min((two_opt(seed,matrix) for seed in seeds),key=lambda r:route_length(r,matrix))
            route=or_opt(route,matrix)
            def objective(z):
                current=poses.copy();current[movable]=z.reshape(-1,2)
                path=np.vstack((start,current[route]))
                segments=path[1:]-path[:-1]
                lengths=np.sqrt((segments*segments).sum(axis=1)+1e-20)
                grad=np.zeros_like(current)
                for k,node in enumerate(route):
                    grad[node]+=segments[k]/lengths[k]
                    if k+1<len(route):grad[node]-=segments[k+1]/lengths[k+1]
                return lengths.sum(),grad[movable].ravel()
            def constraint(z):
                return np.concatenate([.999998**2-((z.reshape(-1,2)[j]-vs)**2).sum(axis=1)
                                       for j,vs in enumerate(bounds)])
            def jacobian(z):
                rows=[]
                for j,vs in enumerate(bounds):
                    block=np.zeros((len(vs),2*len(movable)))
                    block[:,2*j:2*j+2]=-2*(z.reshape(-1,2)[j]-vs)
                    rows.extend(block)
                return np.array(rows)
            solution=minimize(objective,poses[movable].ravel(),jac=True,method='SLSQP',
                              constraints={'type':'ineq','fun':constraint,'jac':jacobian},
                              options={'maxiter':self.cell_max_solver_steps,'ftol':1e-8})
            if constraint(solution.x).min()>=-1e-9:
                poses[movable]=solution.x.reshape(-1,2)
            last_route=route
        proposal=[tuple(p*1000) for p in poses[:len(pending)]]
        if certified_covering_radius(self.coverage_visited+proposal)<=999.9999:
            self.stats['cell_scanner_updates']=self.stats.get('cell_scanner_updates',0)+1
            self.stats['cell_total_shift']=self.stats.get('cell_total_shift',0)+sum(distance(a,b) for a,b in zip(pending,proposal))
            pending[:]=proposal
            if self.joint_route:
                idx=last_route[0]
                return (tuple(poses[idx]*1000),goals[idx][1],goals[idx][2])
        return super()._route_goal(client,pending)

class CellPolicy(CellPlanningMixin,CombinedPolicy):
    pass

class CellIncrementalPolicy(CellPlanningMixin,IncrementalPolicy):
    pass

class SingleCellPolicy(CellPolicy):
    cell_iterations=1

class JointCellPolicy(CellPolicy):
    joint_route=True

class ResidualCellPolicy(CellPolicy):
    subtract_covered=True
    joint_route=True

class ResidualIncrementalPolicy(CellIncrementalPolicy):
    subtract_covered=True
    joint_route=True

from problem3.experiments_v3.candidate import SearchPolicy as BatchCandidate

class CandidateCellPolicy(CellPlanningMixin,BatchCandidate):
    pass

class CandidateJointPolicy(CandidateCellPolicy):
    joint_route=True
