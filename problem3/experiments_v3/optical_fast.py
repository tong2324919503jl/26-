"""Cheap optical attempts at points already selected for radio observations."""
from problem3.geometry import distance,enclosing_circle,polygon_centroid
from problem3.experiments_v3.negative_disks import AnnularNegativePolicy
from problem3.experiments_v3.journey import ClearRegionMixin


class OpticalFirstMixin:
    optical_first_radius=100.
    optical_first_offset=25.
    def _clear(self,client,point,channel):
        result=super()._clear(client,point,channel)
        if not hasattr(self,'_fast_clear_attempts'):self._fast_clear_attempts={}
        attempts=self._fast_clear_attempts.setdefault(channel,[])
        if all(distance(client.position,old)>1e-5 for old in attempts):attempts.append(client.position)
        return result
    def _measure(self,client,point,channel):
        if channel in self.regions and channel not in self.cleared:
            polygon=self.regions[channel]
            center,radius=enclosing_circle(polygon)
            if radius<self.optical_first_radius and distance(point,polygon_centroid(polygon))<self.optical_first_offset:
                if not hasattr(self,'_fast_clear_attempts'):self._fast_clear_attempts={}
                attempts=self._fast_clear_attempts.setdefault(channel,[])
                if all(distance(point,old)>5 for old in attempts):
                    attempts.append(point)
                    self.stats['optical_first_attempts']=self.stats.get('optical_first_attempts',0)+1
                    if self._clear(client,point,channel):
                        self.stats['optical_first_successes']=self.stats.get('optical_first_successes',0)+1
                        return 'near'
        return super()._measure(client,point,channel)


class OpticalFastPolicy(OpticalFirstMixin,ClearRegionMixin,AnnularNegativePolicy):pass
