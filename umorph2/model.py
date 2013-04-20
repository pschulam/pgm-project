import random
from vpyp.pyp import CRP
from vpyp.prob import mult_sample

def segmentations(word):
    for k in range(0, len(word)+1):
        yield word[:k], word[k:]

class Multinomial:
    """A multinomial distribution sampled from a prior"""
    def __init__(self, K, prior):
        self.prior = prior
        self.theta = prior.sample([0]*K)

    def prob(self, k):
        return self.theta[k]

    def resample(self, counts):
        self.theta = self.prior.sample(counts)

class Dirichlet:
    """A Dirichlet distribution for sampling multinomials"""
    def __init__(self, alpha):
        self.alpha = alpha

    def sample(self, counts):
        params = [self.alpha + c for c in counts]
        sample = [random.gammavariate(a, 1) for a in params]
        norm = sum(sample)
        return [v/norm for v in sample]

class MultProduct:
    """H(p, s) = theta_p(p) * theta_s(s)"""
    def __init__(self, n_prefixes, alpha_p, n_suffixes, alpha_s):
        self.theta_p = Multinomial(n_prefixes, Dirichlet(alpha_p))
        self.theta_s = Multinomial(n_suffixes, Dirichlet(alpha_s))

    def prob(self, p, s):
        return self.theta_p.prob(p) * self.theta_s.prob(s)

    def resample(self, counts_p, counts_s):
        self.theta_p.resample(counts_p)
        self.theta_s.resample(counts_s)

class SegmentationModel(CRP):
    """SegmentationModel ~ DP(alpha, H)"""
    def __init__(self, alpha, alpha_p, alpha_s, word_vocabulary,
            prefix_vocabulary, suffix_vocabulary):
        self.alpha = alpha
        self.base = MultProduct(len(prefix_vocabulary), alpha_p,
                len(suffix_vocabulary), alpha_s)
        self.word_vocabulary = word_vocabulary
        self.prefix_vocabulary = prefix_vocabulary
        self.suffix_vocabulary = suffix_vocabulary
        super(SegmentationModel, self).__init__()

    def _random_table(self, k):
        """Pick a table with dish k randomly"""
        n = random.randrange(0, self.ncustomers[k])
        tables = self.tables[k]
        for i, c in enumerate(tables):
            if n < c: return i
            n -= c

    def seating_probs(self, k, initialize=False):
        """Joint probabilities of all possible (segmentation, table assignments)"""
        for prefix, suffix in segmentations(self.word_vocabulary[k]):
            p = self.prefix_vocabulary[prefix]
            s = self.suffix_vocabulary[suffix]
            yield (p, s, -1), (1 if initialize else self.alpha * self.base.prob(p, s))
            if not (p, s) in self.tables: continue
            for seat, count in enumerate(self.tables[(p, s)]):
                yield (p, s, seat), (1 if initialize else count)

    def increment(self, k, initialize=False):
        """Sample a segmentation and a table assignment for word k"""
        (p, s, seat) = mult_sample(self.seating_probs(k, initialize))
        self._seat_to((p, s), seat)
        return (p, s)

    def decrement(self, p, s):
        """Decrement the count for a (p, s) segmentation"""
        seat = self._random_table((p, s))
        self._unseat_from((p, s), seat)
