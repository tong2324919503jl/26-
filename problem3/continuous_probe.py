"""Three bounded probe-selection structures; hypotheses never stop a search."""
from __future__ import annotations
import math
from problem3.speed_policy import SearchPolicy as ParentPolicy
from problem3.geometry import (distance, enclosing_circle, polygon_centroid,
                               intersect_bearing, clip_halfplane)
from problem3.lookahead import (LookaheadMixin, negative_posterior, band_cover,
                                source_quadrature, sweep_score)


def candidate_points(policy, channel, client, index):
    original = super(LookaheadMixin, policy)._probe_point(channel, client, index)
    polygon = policy.regions[channel]
    anchor, bearing = policy.observations[channel][-1]
    theta = math.radians(bearing)
    forward = math.cos(theta), math.sin(theta)
    side = -forward[1], forward[0]
    projections = [(p[0]-anchor[0])*forward[0]+(p[1]-anchor[1])*forward[1] for p in polygon]
    points = [original, polygon_centroid(polygon)]
    for quantile in policy.rollout_quantiles:
        step = min(projections)+quantile*(max(projections)-min(projections))
        for width in policy.rollout_widths:
            for sign in (-1.,1.):
                points.append((anchor[0]+step*forward[0]+sign*width*side[0],
                               anchor[1]+step*forward[1]+sign*width*side[1]))
    return points, anchor, forward, side, (min(projections),max(projections))


def admissible(point, positives, negatives):
    return (all(distance(point,p)>=2. for p,_ in positives)
            and all(distance(point,p)>=2. for p in negatives))


class ContinuousPolicy(ParentPolicy):
    """Pattern search around the best ordinary probe, retaining the same score.

New proposals avoid sitting directly on the three quadrature atoms: a tiny
movement should not exploit an artificial atom's entire probability mass as a
5 m `near` response. Existing upstream candidates remain available unchanged.
"""
    continuous_scale = 100.
    continuous_min_gain = 3.

    def _probe_point(self, channel, client, probe_index):
        original = super()._probe_point(channel,client,probe_index)
        polygon = self.regions[channel]
        if enclosing_circle(polygon)[1] < self.rollout_min_radius:
            return original
        positives = self.observations[channel]
        negatives = self.negative_history.get(channel,[])
        nodes = self._rollout_nodes(polygon,positives,negatives)
        if not nodes:
            return original
        _, anchor, forward, side, (low,high) = candidate_points(self,channel,client,probe_index)
        cache = {}
        def score(point):
            key = tuple(round(v,7) for v in point)
            if key not in cache:
                cache[key] = self._radio_score(channel,client,point,nodes)
            return cache[key]
        def project(point):
            dx,dy = point[0]-anchor[0],point[1]-anchor[1]
            x = max(low-40.,min(high+40.,dx*forward[0]+dy*forward[1]))
            y = max(-200.,min(200.,dx*side[0]+dy*side[1]))
            return anchor[0]+x*forward[0]+y*side[0],anchor[1]+x*forward[1]+y*side[1]
        best, best_score = original, score(original)
        initial_score = best_score
        for scale in (self.continuous_scale,self.continuous_scale/2,
                      self.continuous_scale/4,self.continuous_scale/8):
            for _ in range(2):
                previous = best
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                    point = project((previous[0]+scale*(dx*forward[0]+dy*side[0]),
                                     previous[1]+scale*(dx*forward[1]+dy*side[1])))
                    if not admissible(point,positives,negatives):
                        continue
                    if any(distance(point,hypothesis)<12. for _,hypothesis,_,_ in nodes):
                        continue
                    value = score(point)
                    if value < best_score-.01:
                        best, best_score = point, value
                if best == previous:
                    break
        self.stats['continuous_score_evaluations'] = self.stats.get('continuous_score_evaluations',0)+len(cache)
        if best_score < initial_score-self.continuous_min_gain:
            self.stats['continuous_probe_changes'] = self.stats.get('continuous_probe_changes',0)+1
            self.stats['continuous_predicted_gain_m'] = self.stats.get('continuous_predicted_gain_m',0)+initial_score-best_score
            return best
        return original


def extreme_hypotheses(polygon, positives, negatives):
    center = polygon_centroid(polygon)
    selected = []
    for k in range(8):
        angle = k*math.tau/8
        direction = math.cos(angle),math.sin(angle)
        vertex = max(polygon,key=lambda p:p[0]*direction[0]+p[1]*direction[1])
        point = (.995*vertex[0]+.005*center[0],.995*vertex[1]+.005*center[1])
        if any(distance(point,previous[0])<1. for previous in selected):
            continue
        low = max([1000.]+[distance(point,p) for p,_ in positives])
        high = min([1500.]+[distance(point,p) for p in negatives])
        if low<=high+1e-6:
            selected.append((point,low,max(low,high)))
    return selected


class RobustRegretPolicy(ParentPolicy):
    """Use worst regret at public feasible-region extremes as a soft penalty."""
    regret_weight = .2

    def _extreme_cost(self,channel,client,point,hypothesis,low,high):
        polygon = self.regions[channel]
        positives = self.observations[channel]
        negatives = self.negative_history.get(channel,[])
        d = distance(point,hypothesis)
        outcomes = []
        if d<=high:
            if d<=5.:
                outcomes.append(25.)
            else:
                angle = math.degrees(math.atan2(hypothesis[1]-point[1],hypothesis[0]-point[0]))
                for noise in (-1.,0.,1.):
                    posterior = intersect_bearing(polygon,point,round((angle+noise)%360,2),self.config.bearing_error_deg)
                    for q in negatives:
                        posterior = clip_halfplane(posterior,2*(q[0]-point[0]),2*(q[1]-point[1]),
                                                   q[0]**2+q[1]**2-point[0]**2-point[1]**2)
                    outcomes.append(self._rollout_finish(point,posterior,hypothesis))
        if d>low:
            absent = negative_posterior(polygon,point,positives)
            outcomes.append(self._rollout_finish(point,absent,hypothesis))
        return distance(client.position,point)+25.+max(outcomes)

    def _probe_point(self,channel,client,probe_index):
        original = super()._probe_point(channel,client,probe_index)
        polygon = self.regions[channel]
        if enclosing_circle(polygon)[1]<self.rollout_min_radius:
            return original
        positives = self.observations[channel]
        negatives = self.negative_history.get(channel,[])
        nodes = self._rollout_nodes(polygon,positives,negatives)
        extremes = extreme_hypotheses(polygon,positives,negatives)
        if not nodes or not extremes:
            return original
        candidates = candidate_points(self,channel,client,probe_index)[0]
        candidates = [p for p in candidates if admissible(p,positives,negatives)]
        if original not in candidates:
            candidates.append(original)
        costs = [[self._extreme_cost(channel,client,p,*hypothesis) for hypothesis in extremes] for p in candidates]
        best_by_hypothesis = [min(row[k] for row in costs) for k in range(len(extremes))]
        scores = [self._radio_score(channel,client,p,nodes)+self.regret_weight*max(
            value-best for value,best in zip(cost,best_by_hypothesis)) for p,cost in zip(candidates,costs)]
        chosen = candidates[min(range(len(candidates)),key=lambda i:scores[i])]
        if distance(chosen,original)>.1:
            self.stats['robust_probe_changes'] = self.stats.get('robust_probe_changes',0)+1
        self.stats['robust_extremes_evaluated'] = self.stats.get('robust_extremes_evaluated',0)+len(extremes)
        return chosen


class OpticalTerminalPolicy(ParentPolicy):
    """Score a radio endpoint's subsequent finite optical service explicitly.

This is a planning terminal model, not a promise that global execution follows
that continuation. The actual controller remains the original adaptive one.
Plan order is chosen from the whole hypothetical posterior, never from the
particular quadrature source used to evaluate its first successful clear.
"""
    terminal_maximum = 8

    def _probe_point(self,channel,client,probe_index):
        self._terminal_cache = {}
        return super()._probe_point(channel,client,probe_index)

    def _rollout_finish(self,point,polygon,hypothesis):
        fallback = super()._rollout_finish(point,polygon,hypothesis)
        if not polygon or enclosing_circle(polygon)[1]<=55.:
            return fallback
        if not hasattr(self,'_terminal_cache'):
            self._terminal_cache = {}
        key = (tuple(point),tuple(polygon))
        if key not in self._terminal_cache:
            plan = band_cover(polygon,maximum=self.terminal_maximum)
            chosen = None
            if len(plan)>1:
                # Area of the complete public posterior, not truth or a
                # per-source plan selected after learning its hypothetical hit.
                nodes = source_quadrature(polygon,[],[],12)
                if nodes:
                    options = [plan,list(reversed(plan))]
                    for i in set((len(plan)//2,(len(plan)-1)//2)):
                        for order in (plan,list(reversed(plan))):
                            options.append([plan[i]]+[p for p in order if p!=plan[i]])
                    chosen = min(options,key=lambda p:sweep_score(point,p,nodes))
            self._terminal_cache[key] = chosen
        chosen = self._terminal_cache[key]
        if chosen is None:
            return fallback
        cost = 0.
        previous = point
        for goal in chosen:
            cost += distance(previous,goal)+15.
            if distance(goal,hypothesis)<=19.99+1e-7:
                self.stats['optical_terminal_predictions'] = self.stats.get('optical_terminal_predictions',0)+1
                return cost+10.
            previous = goal
        return fallback
