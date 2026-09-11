"""Bounded optical repair after an accepted failed clearance.

Adapted from phase3_optical.py in the preserved teammate third-round ZIP.
Failed 20 m disks are removed conservatively from an auxiliary union of convex
fragments. The hard bearing region and the certified final fallback remain.
The optional area / cost score never establishes successful clearance.
"""
from __future__ import annotations
import math
from problem3.geometry import clip_halfplane, distance, enclosing_circle



def area(poly):
    return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,poly[1:]+poly[:1])))/2


NORMALS = [(math.cos(k*math.tau/16),math.sin(k*math.tau/16)) for k in range(16)]


def subtract_failed_disk(poly,center):
    """Outer representation of P minus the actual closed 20 m failed disk."""
    bound=19.999*math.cos(math.pi/16);inside=list(poly);outside=[]
    for nx,ny in NORMALS:
        c=nx*center[0]+ny*center[1]+bound
        piece=clip_halfplane(inside,-nx,-ny,-c)
        if piece:outside.append(piece)
        inside=clip_halfplane(inside,nx,ny,c)
        if not inside:break
    return outside


def bounding_strip(poly):
    a,b=max(((a,b) for a in poly for b in poly),key=lambda pair:distance(*pair))
    length=distance(a,b);ux,uy=((b[0]-a[0])/length,(b[1]-a[1])/length) if length else (1.,0.)
    xy=[(p[0]*ux+p[1]*uy,-p[0]*uy+p[1]*ux) for p in poly]
    return (ux,uy),(min(p[0] for p in xy),max(p[0] for p in xy)),(min(p[1] for p in xy),max(p[1] for p in xy))


def fragment_centers(poly):
    center,radius=enclosing_circle(poly)
    if radius<=19.8:return [(center,area(poly))]
    (ux,uy),(lo,hi),(bottom,top)=bounding_strip(poly)
    width=top-bottom
    if width>=39.6:return []
    spacing=2*math.sqrt(19.8**2-(width/2)**2)
    count=max(1,math.ceil((hi-lo)/spacing))
    if count>40:return []
    centers=[]
    for i in range(count):
        low=lo+(hi-lo)*i/count;high=lo+(hi-lo)*(i+1)/count
        piece=clip_halfplane(clip_halfplane(poly,ux,uy,high),-ux,-uy,-low)
        if not piece:continue
        center,radius=enclosing_circle(piece)
        if radius>19.999:
            x,y=(low+high)/2,(bottom+top)/2
            center=(x*ux-y*uy,x*uy+y*ux)
        centers.append((center,area(piece)))
    return centers


def disk_mass(fragments,center):
    bound=19.999*math.cos(math.pi/16);total=0.
    for fragment in fragments:
        if all(distance(p,center)<=bound for p in fragment):
            total+=area(fragment);continue
        piece=fragment
        for nx,ny in NORMALS:
            piece=clip_halfplane(piece,nx,ny,nx*center[0]+ny*center[1]+bound)
            if not piece:break
        total+=area(piece)
    return total


class UnionmassMixin:
    union_length=200.
    union_width=32.
    union_mode='unionmass'
    union_maximum=16

    def _union_point(self,channel,client):
        poly=self.regions.get(channel)
        failures=self._union_failures.get(channel,[])
        if not poly or not failures:return None
        if self._union_counts.get(channel,0)>=self.union_maximum:return None
        _,(lo,hi),(bottom,top)=bounding_strip(poly)
        if hi-lo>self.union_length or top-bottom>self.union_width:return None
        key=(tuple(poly),tuple(failures));cached=self._union_cache.get(channel)
        if cached and cached[0]==key:candidates=cached[1]
        else:
            fragments=[poly]
            for failed in failures:
                fragments=[piece for fragment in fragments for piece in subtract_failed_disk(fragment,failed)]
                if len(fragments)>200:return None
            self.stats['union_fragment_peak']=max(self.stats.get('union_fragment_peak',0),len(fragments))
            candidates=[row for fragment in fragments for row in fragment_centers(fragment)]
            candidates=[(p,mass) for p,mass in candidates if all(distance(p,f)>3. for f in failures)]
            if self.union_mode=='unionmass':candidates=[(p,disk_mass(fragments,p)) for p,_ in candidates]
            self._union_cache[channel]=(key,candidates)
        if not candidates:return None
        if self.union_mode=='nearest':return min(candidates,key=lambda row:distance(client.position,row[0]))[0]
        return max(candidates,key=lambda row:max(1e-8,row[1])/(3.+distance(client.position,row[0])/5.))[0]

    def _clear(self,client,point,channel):
        if not hasattr(self,'_union_failures'):
            self._union_failures={};self._union_counts={};self._union_cache={}
        result=super()._clear(client,point,channel)
        if result:return True
        self._union_failures.setdefault(channel,[]).append(tuple(point))
        while True:
            point=self._union_point(channel,client)
            if point is None:return False
            self._union_counts[channel]=self._union_counts.get(channel,0)+1
            self.stats['union_clear_actions']=self.stats.get('union_clear_actions',0)+1
            # Bypass this wrapper to prevent recursive retries. Success is the
            # only condition returning True to the inherited controller.
            if super()._clear(client,point,channel):return True
            self._union_failures[channel].append(tuple(point))
