"""Reduce repeated fixed-position reads and optional negative neighbor reads.

All source regions and completeness rules are retained. Repeated readings at
exactly the current coordinate add no information under the fixed-error model.
Nearby negative cooldown applies only to optional known-source neighbor reads.
"""
from problem3.geometry import distance
from problem4.experiments_v3.coverage_ring_policy import Ring12CoverPolicy
from problem4.experiments_v3.routing_shared import SharedBaselineMixin


class ReadEconomyMixin:
    read_cache=True
    read_negative_cooldown=0.
    read_stop_at_16=True
    read_shadow_certificate=False

    def _provably_negative(self,ch,point):
        """Prove a proposed point is in a previous negative's direction shadow.

        Write A=p-g for an old positive, B=q-g for an in-range negative.
        If C=new-g=alpha*B-beta*A with alpha>0,beta>=0, every compatible
        emitting half-plane also excludes C. The three determinants defining
        the cone are affine in g, so testing all polygon vertices suffices.
        """
        polygon=self.regions[ch]
        for negative in getattr(self,'_negative_history',{}).get(ch,[]):
            if not self._history_point_in_range(negative,polygon,ch):continue
            for positive,_ in self.observations[ch]:
                determinants=[]
                for g in polygon:
                    ax,ay=positive[0]-g[0],positive[1]-g[1]
                    bx,by=negative[0]-g[0],negative[1]-g[1]
                    cx,cy=point[0]-g[0],point[1]-g[1]
                    determinants.append((ax*by-ay*bx,ax*cy-ay*cx,bx*cy-by*cx))
                # A strict square-metre margin avoids collinear corner cases.
                if all(min(values)>1e-4 for values in determinants):return True
                if all(max(values)<-1e-4 for values in determinants):return True
        return False

    def _update_neighbors(self,client):
        self._read_neighbor_mode=True
        try:return super()._update_neighbors(client)
        finally:self._read_neighbor_mode=False

    def _scan(self,client,point):
        self._read_scan_mode=True
        try:return super()._scan(client,point)
        finally:self._read_scan_mode=False

    def _measure(self,client,point,ch):
        if (self.read_stop_at_16 and getattr(self,'_read_scan_mode',False)
                and ch not in self.regions and ch not in self.cleared
                and len(set(self.regions)|self.cleared)==16):
            self._read_incomplete_station=True
            self.stats['read_stop16_skips']=self.stats.get('read_stop16_skips',0)+1
            return 'no_signal'
        if not hasattr(self,'_read_cache'):self._read_cache={}
        key=(ch,tuple(point))
        if (self.read_cache and tuple(point)==tuple(client.position)
                and ch not in self.cleared and key in self._read_cache):
            result=self._read_cache[key]
            if result in ('direction','no_signal'):
                self.stats['read_cache_hits']=self.stats.get('read_cache_hits',0)+1
                return result
        if (self.read_negative_cooldown and getattr(self,'_read_neighbor_mode',False)
                and ch in self.regions and ch not in self.cleared):
            old=getattr(self,'_negative_history',{}).get(ch,[])
            if any(distance(point,p)<self.read_negative_cooldown for p in old):
                self.stats['read_negative_cooldown_skips']=self.stats.get('read_negative_cooldown_skips',0)+1
                return 'no_signal'
        if (self.read_shadow_certificate and getattr(self,'_read_neighbor_mode',False)
                and ch in self.regions and ch not in self.cleared and self._provably_negative(ch,point)):
            self.stats['read_shadow_certificate_skips']=self.stats.get('read_shadow_certificate_skips',0)+1
            return 'no_signal'
        result=super()._measure(client,point,ch)
        self._read_cache[key]=result
        return result

    def _result(self,reason,coverage_complete):
        # A partially scanned final station must not masquerade as an all-
        # channel coverage certificate. Actual16 clears remain sufficient.
        if getattr(self,'_read_incomplete_station',False):coverage_complete=False
        return super()._result(reason,coverage_complete)


def get_class(name):
    tokens=set(name.split('_'))
    attrs=dict(shared_min_channels=1,shared_radius_m=50.,shared_fresh_only=True)
    if 'base' in tokens:attrs.update(read_cache=False,read_stop_at_16=False)
    if 'cache' in tokens:attrs['read_stop_at_16']=False
    if 'stop' in tokens:attrs['read_cache']=False
    if 'shadow' in tokens:attrs['read_shadow_certificate']=True
    for value in (25,75,150):
        if f'cool{value}' in tokens:attrs['read_negative_cooldown']=float(value)
    return type(name,(ReadEconomyMixin,SharedBaselineMixin,Ring12CoverPolicy),attrs)
