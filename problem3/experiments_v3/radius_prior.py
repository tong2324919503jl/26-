"""Sensitivity of lookahead quadrature to physically admissible radius priors."""
from problem3.experiments_v3.lookahead import LookaheadPolicy


class RadiusVolumeMixin:
    radius_atom_weight=0.
    radius_sparse_only=False
    def _rollout_nodes(self,polygon,positives,negatives):
        nodes=super()._rollout_nodes(polygon,positives,negatives)
        if self.radius_sparse_only and not getattr(self,'_annular_decision',False):return nodes
        weighted=[]
        for w,g,low,high in nodes:
            mass=(1-self.radius_atom_weight)*(high-low)/500
            if low<=1000.000001<=high+1e-6:mass+=self.radius_atom_weight
            weighted.append((w*mass,g,low,high))
        total=sum(w for w,*_ in weighted)
        return [(w/total,g,low,high) for w,g,low,high in weighted] if total else nodes


class RadiusVolumePolicy(RadiusVolumeMixin,LookaheadPolicy):pass
class SparseRadiusVolumePolicy(RadiusVolumePolicy):radius_sparse_only=True
class MinRadiusMixturePolicy(RadiusVolumePolicy):radius_atom_weight=.5
