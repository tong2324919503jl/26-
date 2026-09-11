"""Risk measured on paired improvements, canceling shared episode difficulty."""
import math
from problem4.experiments_v3.belief_sampling import SpreadConditionalPolicy


class PairedRolloutPolicy(SpreadConditionalPolicy):
    def _rank_scores(self,rows):
        scores=[]
        for row in rows:
            differences=[new-old for new,old in zip(row,rows[0])]
            mean=sum(differences)/len(differences)
            risk=math.sqrt(sum((d-mean)**2 for d in differences)/len(differences))
            scores.append(mean+self.rollout_risk*risk)
        return scores
