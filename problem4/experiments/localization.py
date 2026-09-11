"""Development-only localization branches; never inspect simulator truth."""
from __future__ import annotations

import math

from problem4.legacy_policy import SearchPolicy as LegacyPolicy
from problem3.geometry import clip_halfplane, distance, enclosing_circle, optical_cover, polygon_centroid


class LocalizationMixin:
    localization_quantile = .5
    localization_width_fraction = .18
    localization_width_min = 35.
    localization_width_max = 140.
    localization_rounds = 5
    localization_ls = False
    localization_nearest_clear = False
    localization_exploratory_radius = None
    localization_enforce_range = False
    localization_history = False
    localization_history_slices = 8
    localization_positive_range = False
    localization_partition_range = False

    def _history_point_in_range(self, point, cell, channel):
        if max(distance(point, vertex) for vertex in cell) < 999.999:
            return True
        if not self.localization_positive_range:
            return False
        # A previous positive P gives R >= |P-source|.  Thus Q is also
        # within the same unknown R whenever |Q-source| < |P-source|.
        # Squaring cancels the quadratic source terms, so this is a linear
        # half-plane whose maximum on a convex cell occurs at a vertex.
        qx,qy=point
        for positive, _ in self.observations[channel]:
            px,py=positive
            aa,bb=2*(px-qx),2*(py-qy)
            cc=px*px+py*py-qx*qx-qy*qy
            if max(aa*v[0]+bb*v[1]-cc for v in cell) < -.002:
                return True
        if self.localization_partition_range:
            residual = cell
            for positive, _ in self.observations[channel]:
                px,py=positive
                aa,bb=2*(px-qx),2*(py-qy)
                cc=px*px+py*py-qx*qx-qy*qy
                # Only points at which Q is at least as far away as P
                # still require the fixed 1000m lower bound on R.
                residual=clip_halfplane(residual,-aa,-bb,-cc)
                if not residual:
                    return True
            if max(distance(point,vertex) for vertex in residual)<999.999:
                return True
        return False

    def _measure(self, client, point, channel):
        result = super()._measure(client, point, channel)
        if not hasattr(self, '_negative_history'):
            self._negative_history = {}
        if result == 'no_signal':
            history = self._negative_history.setdefault(channel, [])
            if not history or point not in history:
                history.append(point)
        elif result == 'direction' and self.localization_history:
            self._clip_history(channel)
        return result

    def _clip_history(self, channel):
        negatives = self._negative_history.get(channel, [])
        if len(negatives) < 2:
            return
        polygon = self.regions[channel]
        anchor, bearing = self.observations[channel][-1]
        theta = math.radians(bearing)
        forward = (math.cos(theta), math.sin(theta))
        projections = [p[0]*forward[0]+p[1]*forward[1] for p in polygon]
        lower, upper = min(projections), max(projections)
        count = self.localization_history_slices
        cells = []
        for i in range(count):
            lo, hi = lower+(upper-lower)*i/count, lower+(upper-lower)*(i+1)/count
            cell = clip_halfplane(polygon, forward[0],forward[1],hi)
            cell = clip_halfplane(cell,-forward[0],-forward[1],-lo)
            if cell:
                cells.append(cell)
        for a, _ in self.observations[channel]:
            for i,b_point in enumerate(negatives):
                for c_point in negatives[i+1:]:
                    b,c = b_point,c_point
                    # Negative pair subtends a cone as seen from a known
                    # positive anchor. Its part beyond BC cannot contain the
                    # source whenever both negatives are in reception range.
                    cross = (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
                    if abs(cross) < 1e-5:
                        continue
                    if cross < 0:
                        b,c = c,b
                    dx1,dy1=b[0]-a[0],b[1]-a[1]
                    dx2,dy2=c[0]-a[0],c[1]-a[1]
                    # cross(b-a,s-a)>=0, cross(c-a,s-a)<=0,
                    # and the side of BC opposite the positive anchor.
                    dx3,dy3=c[0]-b[0],c[1]-b[1]
                    forbidden = [(dy1,-dx1,dy1*a[0]-dx1*a[1]),
                                 (-dy2,dx2,-dy2*a[0]+dx2*a[1]),
                                 (dy3,-dx3,dy3*b[0]-dx3*b[1])]
                    # BC has a on its left. Beyond BC is its right.
                    forbidden[2] = tuple(-v for v in forbidden[2])
                    next_cells=[]
                    for cell in cells:
                        if any(min(aa*v[0]+bb*v[1]-cc for v in cell) >= 1e-4 for aa,bb,cc in forbidden):
                            next_cells.append(cell)
                            continue
                        if not all(self._history_point_in_range(p,cell,channel) for p in (b,c)):
                            next_cells.append(cell)
                            continue
                        inside=cell
                        for aa,bb,cc in forbidden:
                            outside=clip_halfplane(inside,-aa,-bb,-cc)
                            if outside:
                                next_cells.append(outside)
                            inside=clip_halfplane(inside,aa,bb,cc)
                            if not inside:
                                break
                    cells=next_cells
                    if not cells:
                        raise RuntimeError('Historical negatives exhausted feasible cells')
                    if len(cells)>128:
                        # Conservative merge caps optional development work.
                        return
        points=[p for cell in cells for p in cell]
        def cross(o,a,b):
            return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
        ordered=sorted(set(points))
        lower_hull=[]
        for p in ordered:
            while len(lower_hull)>1 and cross(lower_hull[-2],lower_hull[-1],p)<=0:
                lower_hull.pop()
            lower_hull.append(p)
        upper_hull=[]
        for p in reversed(ordered):
            while len(upper_hull)>1 and cross(upper_hull[-2],upper_hull[-1],p)<=0:
                upper_hull.pop()
            upper_hull.append(p)
        self.regions[channel]=lower_hull[:-1]+upper_hull[:-1]
        self.stats['history_clips']=self.stats.get('history_clips',0)+1

    def _estimated_point(self, channel, polygon):
        center = polygon_centroid(polygon)
        if not self.localization_ls or len(self.observations[channel]) < 2:
            return center
        # Weighted total least squares of bearing line normals.  This point is
        # only a movement proposal; the bounded-error polygon stays unchanged.
        aa = ab = bb = ac = bc = 0.
        for anchor, bearing in self.observations[channel]:
            theta = math.radians(bearing)
            a, b = -math.sin(theta), math.cos(theta)
            c = a * anchor[0] + b * anchor[1]
            weight = 1 / max(20., distance(anchor, center))**2
            aa += weight * a*a
            ab += weight * a*b
            bb += weight * b*b
            ac += weight * a*c
            bc += weight * b*c
        determinant = aa*bb - ab*ab
        if determinant <= 1e-16:
            return center
        estimate = ((ac*bb-bc*ab)/determinant, (bc*aa-ac*ab)/determinant)
        # Project along center-to-estimate onto every polygon edge if needed.
        # A convex combination with an interior center keeps a valid proposal.
        from problem3.geometry import contains
        if contains(polygon, estimate):
            return estimate
        lo, hi = 0., 1.
        for _ in range(30):
            mid = (lo+hi)/2
            point = (center[0]+mid*(estimate[0]-center[0]), center[1]+mid*(estimate[1]-center[1]))
            if contains(polygon, point):
                lo = mid
            else:
                hi = mid
        return (center[0]+lo*(estimate[0]-center[0]), center[1]+lo*(estimate[1]-center[1]))

    def _near_clear_center(self, polygon, center, position):
        if not self.localization_nearest_clear:
            return center
        if max(distance(position, p) for p in polygon) < self.config.clear_guarantee_radius_m:
            return position
        lo, hi = 0., 1.
        for _ in range(35):
            t = (lo+hi)/2
            q = (center[0]+t*(position[0]-center[0]), center[1]+t*(position[1]-center[1]))
            if max(distance(q, p) for p in polygon) < self.config.clear_guarantee_radius_m:
                lo = t
            else:
                hi = t
        return (center[0]+lo*(position[0]-center[0]), center[1]+lo*(position[1]-center[1]))

    def _localize(self, channel, client):
        if self.strategy != "adaptive":
            return super()._localize(channel, client)
        attempted_clear = False
        attempted_measure = set()
        for _ in range(self.localization_rounds):
            polygon = self.regions[channel]
            center, radius = enclosing_circle(polygon)
            if radius <= self.config.clear_guarantee_radius_m:
                if self._clear(client, self._near_clear_center(polygon, center, client.position), channel):
                    return True
            elif radius <= (self.localization_exploratory_radius or self.config.exploratory_clear_radius_m) and not attempted_clear:
                attempted_clear = True
                if self._clear(client, self._estimated_point(channel, polygon), channel):
                    return True
            anchor, bearing = self.observations[channel][-1]
            theta = math.radians(bearing)
            forward = (math.cos(theta), math.sin(theta))
            sideways = (-forward[1], forward[0])
            longitudinal = [(point[0]-anchor[0])*forward[0] + (point[1]-anchor[1])*forward[1] for point in polygon]
            low, high = min(longitudinal), max(longitudinal)
            step = low + self.localization_quantile*(high-low)
            width = max(self.localization_width_min, min(self.localization_width_max, self.localization_width_fraction * step))
            width = max(width, step*math.tan(math.radians(self.config.bearing_error_deg)) + .01)
            if self.localization_enforce_range:
                # Keep the pair inside the minimum reception distance of all
                # feasible sources so two negatives always provide a cut.
                for _range_step in range(24):
                    midpoint = (anchor[0]+step*forward[0], anchor[1]+step*forward[1])
                    pair = [(midpoint[0]+sign*width*sideways[0], midpoint[1]+sign*width*sideways[1]) for sign in (-1,1)]
                    if max(distance(point,vertex) for point in pair for vertex in polygon) < 999.99:
                        break
                    step = .5*step + .25*(low+high)
                    width = max(width,step*math.tan(math.radians(self.config.bearing_error_deg))+.01)
            midpoint = (anchor[0]+step*forward[0], anchor[1]+step*forward[1])
            probes = [(midpoint[0]+sign*width*sideways[0], midpoint[1]+sign*width*sideways[1]) for sign in (-1,1)]
            probes.sort(key=lambda point: distance(client.position, point))
            all_in_range = all(distance(point, vertex) < 999.999 for point in probes for vertex in polygon)
            negative = 0
            for point in probes:
                key = (round(point[0],7),round(point[1],7))
                if key in attempted_measure:
                    continue
                attempted_measure.add(key)
                result = self._measure(client, point, channel)
                self.stats['paired_probe_actions'] = self.stats.get('paired_probe_actions',0)+1
                if channel in self.cleared:
                    return True
                if result == 'direction':
                    break
                negative += 1
                self.stats['negative_localization_reads'] += 1
            if negative == 2 and all_in_range and step > 0:
                constant = step + anchor[0]*forward[0] + anchor[1]*forward[1]
                updated = clip_halfplane(polygon, forward[0], forward[1], constant)
                if not updated:
                    raise RuntimeError('Paired negative observations contradict feasible region')
                self.regions[channel] = updated
                self.stats['paired_negative_clips'] = self.stats.get('paired_negative_clips',0)+1
        self.stats['optical_fallbacks'] += 1
        points = optical_cover(self.regions[channel], self.config.optical_spacing_m)
        while points:
            index = min(range(len(points)), key=lambda i: distance(client.position, points[i]))
            if self._clear(client, points.pop(index), channel):
                return True
        raise RuntimeError('Optical cover exhausted without clearance')


class SearchPolicy(LocalizationMixin, LegacyPolicy):
    pass


class OptimizedSearchPolicy(LocalizationMixin, LegacyPolicy):
    localization_quantile = .2
    localization_width_fraction = .04
    localization_width_min = 15.
    localization_enforce_range = True
    localization_history = True
    localization_history_slices = 12


class RadiusBoundSearchPolicy(OptimizedSearchPolicy):
    localization_positive_range = True


class PartitionedRadiusSearchPolicy(RadiusBoundSearchPolicy):
    localization_partition_range = True
