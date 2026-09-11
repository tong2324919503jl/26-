"""Deferred channel batches with an independent certificate for each channel.

Only high posterior probability of the16-source cap permits deferral. Every
remaining unknown channel must eventually observe every one of the21 original
stations. Discovery of16 channels stops discovery, but only16 actual clears
permits early completion. No missing measurement is recorded as performed.
"""
from __future__ import annotations
import math
from problem4.experiments_v3.coverage_ring_policy import Ring12CoverPolicy
from problem4.experiments_v3.routing_shared import SharedBaselineMixin


def count_posterior(known,fractions):
    """P(N|known channels, per-unknown-channel negative visibility masses)."""
    elementary=[1.]+[0.]*len(fractions)
    for count,value in enumerate(fractions,1):
        for m in range(count,0,-1):elementary[m]+=value*elementary[m-1]
    weights={n:elementary[n-known]/math.comb(20,n) for n in range(max(10,known),17)}
    total=sum(weights.values())
    return {n:w/total for n,w in weights.items()} if total else {}


class ChannelSplitMixin:
    channel_split_enabled=True
    channel_min_known=14
    channel_min_maximum_probability=.75
    channel_batch_fraction=.5
    channel_future_ratio=.8
    channel_stop_at_16=True

    def _unknown_channels(self):
        known=set(self.regions)|self.cleared
        return [ch for ch in range(1,21) if ch not in known]

    def _refresh_channel_prior(self):
        masks=[self._channel_masks[ch] for ch in self._unknown_channels()]
        common=(1<<len(self.samples))-1
        for mask in masks:common&=mask
        self.scanned_mask=common

    def _select_channels(self,point):
        needed=[ch for ch in self._unknown_channels() if point not in self._channel_points[ch]]
        if (not self.channel_split_enabled or self._channel_compensating or not self.coverage_visited
                or not self._shared_pending or len(set(self.regions)|self.cleared)<self.channel_min_known
                or len(needed)<2):return set(needed)
        unknown=self._unknown_channels();known=20-len(unknown);total=len(self.samples)
        fractions=[1-self._channel_masks[ch].bit_count()/total for ch in unknown]
        posterior=count_posterior(known,fractions)
        if posterior.get(16,0.)<self.channel_min_maximum_probability:return set(needed)
        here=self._mask(point);future=[self._mask(p) for p in self._shared_pending]
        scores={};selected=[]
        for ch in needed:
            old=self._channel_masks[ch]
            local=(here&~old).bit_count()
            best=max((mask&~old).bit_count() for mask in future)
            # Comparing sites for a single channel cancels its existence mass.
            # The independent approximation below only breaks channel ties.
            unseen=1-old.bit_count()/total
            scores[ch]=(.65*local/total)/(.35+.65*unseen)
            if local>=self.channel_future_ratio*best:selected.append(ch)
        minimum=max(1,math.ceil(len(needed)*self.channel_batch_fraction))
        ranked=sorted(needed,key=lambda ch:(scores[ch],ch==getattr(self,'_channel_current',None)),reverse=True)
        for ch in ranked:
            if len(selected)>=minimum:break
            if ch not in selected:selected.append(ch)
        if len(selected)<len(needed):
            self.stats['channel_partial_stations']=self.stats.get('channel_partial_stations',0)+1
        return set(selected)

    def _measure(self,client,point,ch):
        if (getattr(self,'_channel_scanning',False) and ch not in self.regions and ch not in self.cleared):
            if self.channel_stop_at_16 and len(set(self.regions)|self.cleared)==16:
                self.stats['channel_stop16_skips']=self.stats.get('channel_stop16_skips',0)+1
                return 'no_signal'
            if tuple(point) in self._channel_points[ch] or ch not in self._channel_selected:
                self.stats['channel_deferred_reads']=self.stats.get('channel_deferred_reads',0)+1
                return 'no_signal'
        result=super()._measure(client,point,ch)
        if hasattr(self,'_channel_points'):
            self._channel_points[ch].add(tuple(point))
            if ch not in self.regions and ch not in self.cleared:
                self._channel_masks[ch]|=self._mask(point)
        return result

    def _scan(self,client,point):
        old=set(self.regions);self._channel_current=client.current_channel
        self._channel_selected=self._select_channels(point);self._channel_scanning=True
        try:
            # Run the ordinary physical sweep before the shared baseline, so
            # the latter sees the actual common negative prior after deferrals.
            super(SharedBaselineMixin,self)._scan(client,point)
        finally:self._channel_scanning=False
        self._refresh_channel_prior()
        if self.shared_initial_only and len(self.coverage_visited)>1:return
        if len(self.cleared)==16:return
        if self.shared_neighbor_first:self._update_neighbors(client)
        if self.shared_outer_only and math.hypot(*client.position)<1800:return
        for _ in range(self.shared_rounds):
            if not self._shared_step(client,old):break

    def _channel_certificate(self):
        return all(set(self._channel_fixed)<=self._channel_points[ch] for ch in self._unknown_channels())

    def _missing_points(self):
        unknown=self._unknown_channels()
        return [p for p in self._channel_fixed if any(p not in self._channel_points[ch] for ch in unknown)]

    def _result(self,reason,coverage_complete):
        result=super()._result(reason,self._channel_certificate())
        result['channel_coverage_counts']={str(ch):sum(p in self._channel_points[ch] for p in self._channel_fixed) for ch in self._unknown_channels()}
        result['channel_completion_basis']='maximum16_actual_clears' if len(self.cleared)==16 else 'individual_channel_fixed_cover'
        return result

    def run(self,client):
        pending=self.coverage_points();self._channel_fixed=tuple(pending)
        self._channel_points={ch:set() for ch in range(1,21)}
        self._channel_masks={ch:0 for ch in range(1,21)}
        self._channel_compensating=False
        while True:
            client.check_budget()
            if len(self.cleared)==16:return self._result('maximum_source_count_cleared',False)
            if self._channel_compensating:
                needed=set(self._missing_points());pending[:]=[p for p in pending if p in needed]
            if not pending and len(set(self.regions)|self.cleared)<16:
                missing=self._missing_points()
                if missing:
                    pending.extend(missing);self._channel_compensating=True
                    self.stats['channel_compensation_stations']=self.stats.get('channel_compensation_stations',0)+len(missing)
            if not pending and not any(ch not in self.cleared for ch in self.regions):
                if not self._channel_certificate():raise RuntimeError('Independent channel coverage is incomplete')
                return self._result('individual_channel_coverage_and_all_detected_cleared',True)
            self._refresh_channel_prior()
            _,kind,identifier=self._route_goal(client,pending)
            if kind=='scan':self._scan(client,pending.pop(identifier))
            else:self._localize(identifier,client)
            self._update_neighbors(client)


def get_class(name):
    tokens=set(name.split('_'))
    attrs=dict(shared_min_channels=1,shared_radius_m=50.,shared_fresh_only=True)
    if 'base' in tokens:attrs.update(channel_split_enabled=False,channel_stop_at_16=False)
    if 'loose' in tokens:attrs['channel_min_maximum_probability']=.5
    if 'any' in tokens:attrs.update(channel_min_maximum_probability=0.,channel_min_known=10)
    if 'focus15' in tokens:attrs.update(channel_min_maximum_probability=.5,channel_min_known=15)
    if 'aggressive' in tokens:attrs.update(channel_min_maximum_probability=.5,channel_future_ratio=1.1)
    return type(name,(ChannelSplitMixin,SharedBaselineMixin,Ring12CoverPolicy),attrs)
