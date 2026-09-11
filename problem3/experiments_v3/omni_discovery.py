"""P3-only discovery costs, with correctly omnidirectional latent samples.

These finite samples determine action scores only. Neither source candidates
nor continuous coverage certificates are ever pruned by this probability model.
"""
from __future__ import annotations
import math
from problem3.geometry import distance,polygon_centroid
from problem4.routing import route_length
from problem3.experiments_v3.lookahead import LookaheadPolicy


OMNI_SAMPLES=[((x,y),radius,None)
              for x in range(-1800,1801,300) for y in range(-1800,1801,300)
              if math.hypot(x,y)<=1800 for radius in (1000,1250,1500)]


def expected_remaining_sources(discovered,unseen_fraction):
    """Posterior mean N-K for an initially uniform total N in 10..16.

    Conditional on N, exactly K discovered sources has binomial likelihood
    C(N,K) (1-u)^K u^(N-K). The common factor (1-u)^K cancels. All actual
    scanner observations enter through K and the union's unseen mass u.
    """
    if discovered>=16:return 0.
    unseen_fraction=max(0.,min(1.,unseen_fraction))
    counts=range(max(10,discovered),17)
    if unseen_fraction==0.:return float(max(10,discovered)-discovered)
    logarithms=[(n,math.log(math.comb(n,discovered))+(n-discovered)*math.log(unseen_fraction)) for n in counts]
    top=max(v for _,v in logarithms)
    weights=[(n,math.exp(v-top)) for n,v in logarithms]
    return sum((n-discovered)*w for n,w in weights)/sum(w for _,w in weights)


class OmniDiscoveryMixin:
    # A distinct cache is required: inherited P4 mask positions refer to a
    # different sample layout even when a scanner coordinate is identical.
    samples=OMNI_SAMPLES
    mask_cache={}
    escape_info_weight=1.


class OmniDiscoveryPolicy(OmniDiscoveryMixin,LookaheadPolicy):pass
class OmniZeroPolicy(OmniDiscoveryPolicy):escape_info_weight=0.
class OmniStrongPolicy(OmniDiscoveryPolicy):escape_info_weight=3.


class CountPosteriorMixin:
    def _route_goal(self,client,pending):
        weight=self.escape_info_weight
        # Keep the existing route construction, rotations and warm start, then
        # replace only its independent-channel discovery cost with the count
        # posterior. Restoring this option also preserves subsequent calls.
        self.escape_info_weight=0.
        try:original=super()._route_goal(client,pending)
        finally:self.escape_info_weight=weight
        known=set(self.regions)|self.cleared
        if not weight or len(pending)<2 or len(known)==16:return original
        total=len(self.samples);unseen=total-self.scanned_mask.bit_count()
        if not unseen:return original
        goals=[(p,'scan',i) for i,p in enumerate(pending)]+[(polygon_centroid(p),'clear',ch) for ch,p in self.regions.items() if ch not in self.cleared]
        mapping={self._goal_key(goal):i for i,goal in enumerate(goals)}
        route=[mapping[key] for key in self._route_keys if key in mapping]
        points=[g[0] for g in goals]+[client.position]
        matrix=[[distance(a,b) for b in points] for a in points]
        masks={i:self._mask(p) for i,p in enumerate(pending)}
        unknown=20-len(known)
        expected=expected_remaining_sources(len(known),unseen/total)
        self.stats['expected_undiscovered_sources']=expected
        def score(order):
            cost=route_length(order,matrix)/5;covered=self.scanned_mask
            for index in order:
                _,kind,ident=goals[index]
                if kind=='scan':
                    newly_covered=covered.bit_count()-self.scanned_mask.bit_count()
                    expected_unknown=unknown-expected*newly_covered/unseen
                    cost+=weight*6*max(0.,expected_unknown)
                    covered|=masks[ident]
            return cost
        best=score(route)
        for _ in range(20):
            changed=False
            for i in range(len(route)-1):
                for j in range(i+1,len(route)):
                    candidate=route[:i]+list(reversed(route[i:j+1]))+route[j+1:]
                    cost=score(candidate)
                    if cost<best-.01:route=candidate;best=cost;changed=True;break
                if changed:break
            if not changed:break
        self._route_keys=[self._goal_key(goals[i]) for i in route]
        return goals[route[0]]


class OmniCountPolicy(CountPosteriorMixin,OmniDiscoveryPolicy):pass
class OmniCountStrongPolicy(OmniCountPolicy):escape_info_weight=3.


from problem4.experiments_v3.discovery_insertion import DiscoveryInsertionMixin

class OmniInsertionPolicy(DiscoveryInsertionMixin,OmniZeroPolicy):pass
class OmniInsertionOnlyPolicy(OmniInsertionPolicy):discovery_latency_weight=0.
class OmniLatencyOnlyPolicy(OmniInsertionPolicy):discovery_insertion_weight=0.


def verify_discovery_model():
    """Compare against a different enumeration over the 20 channel labels."""
    checked=0;worst=0.
    for known in range(17):
        for unseen in (.01,.1,.4,.8,.99):
            # P(exactly these K labels are sources | N), independently of
            # the binomial formula used in expected_remaining_sources.
            weights=[(n,math.comb(20-known,n-known)/math.comb(20,n)*unseen**(n-known))
                     for n in range(max(10,known),17)]
            reference=sum((n-known)*w for n,w in weights)/sum(w for _,w in weights)
            error=abs(reference-expected_remaining_sources(known,unseen))
            assert error<1e-10
            worst=max(worst,error);checked+=1
    assert expected_remaining_sources(0,1.)==13.
    assert expected_remaining_sources(16,.4)==0.
    assert expected_remaining_sources(12,0.)==0.
    policy=OmniDiscoveryPolicy();point=(113.7,-801.2)
    mask=sum((1<<i) for i,(source,radius,orientation) in enumerate(policy.samples)
             if distance(source,point)<=radius and orientation is None)
    assert policy._mask(point)==mask
    from problem4.routing import RoutingMixin
    assert policy.mask_cache is not RoutingMixin.mask_cache
    return {'posterior_checks':checked,'max_error':worst,'omni_samples':len(policy.samples),'cache_isolation':True}


if __name__=='__main__':
    from problem3.experiments_v3.benchmark import run,generate_suite,ROOT
    import sys,json
    if len(sys.argv)>1 and sys.argv[1]=='--check':
        print(verify_discovery_model());raise SystemExit(0)
    n=int(sys.argv[1]) if len(sys.argv)>1 else 96
    requested=sys.argv[2:]
    classes=(OmniZeroPolicy,OmniDiscoveryPolicy,OmniStrongPolicy,OmniCountPolicy,OmniCountStrongPolicy,OmniInsertionPolicy,OmniInsertionOnlyPolicy,OmniLatencyOnlyPolicy)
    if requested:classes=tuple(cls for cls in classes if cls.__name__ in requested)
    cases=generate_suite(3,'development_v2',n);results={}
    for cls in classes:
        r=run(cls,cases);results[cls.__name__]=r
        print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
        suffix=('_'+('_'.join(requested))) if requested else ''
        (ROOT/f'problem3/results/p3_omni_discovery_v3_development{n}{suffix}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
