import argparse
import heapq
import logging
import multiprocessing as mp
import random
import segmenting
import sys
from crpslave import CRPSlave
from distributions import MultProduct
from itertools import izip
from vpyp.corpus import Vocabulary

def show_top(model, prefix_vocabulary, suffix_vocabulary):
    top_prefixes = heapq.nlargest(10, izip(model.theta_p.counts, prefix_vocabulary))
    n_prefixes = sum(1 for c in model.theta_p.counts if c > 0)
    logging.info('Top prefixes (10/%d): %s', n_prefixes, ' '.join(prefix for _, prefix in top_prefixes))
    top_suffixes = heapq.nlargest(10, izip(model.theta_s.counts, suffix_vocabulary))
    n_suffixes = sum(1 for c in model.theta_s.counts if c > 0)
    logging.info('Top suffixes (10/%d): %s', n_suffixes, ' '.join(suffix for _, suffix in top_suffixes))

def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('--processors', help='number of slaves to use',
                        type=int, default=4)
    args = parser.parse_args()
    n_processors = args.processors if args.processors else mp.cpu_count()

    word_vocabulary = Vocabulary(start_stop=False)
    corpus = [word_vocabulary[line.decode('utf8').strip()] for line in sys.stdin]
    
    prefix_vocabulary, suffix_vocabulary = segmenting.affixes(word_vocabulary)
    seg_mappings = segmenting.segmentation_mapping(word_vocabulary,
                                                   prefix_vocabulary,
                                                   suffix_vocabulary)

    logging.info('%d tokens / %d types / %d prefixes / %d suffixes',
                 len(corpus), len(word_vocabulary), len(prefix_vocabulary), len(suffix_vocabulary))

    base = MultProduct(len(prefix_vocabulary), 1e-6, len(suffix_vocabulary), 1e-6)
    base.resample()
    processor_indicators = [random.randrange(n_processors) for _ in corpus]

    slaves = []
    for i in xrange(n_processors):
        iq, oq = mp.Queue(), mp.Queue()
        p = CRPSlave(0.5, base, corpus, seg_mappings, i, iq, oq)
        slaves.append((p, iq, oq))
        p.start()
        iq.put(processor_indicators)

    for i in xrange(1000):
        for p, iq, _ in slaves:
            iq.put( (base, processor_indicators) )
        base = MultProduct(len(prefix_vocabulary), 1e-6, len(suffix_vocabulary), 1e-6)
        for p, _, oq in slaves:
            p_counts, s_counts = oq.get()
            base.update(p_counts, s_counts)
        base.resample()
        if i % 10 == 0:
            logging.info('Iteration %d/%d', i+1, 1000)
            show_top(base, prefix_vocabulary, suffix_vocabulary)

    for p, iq, _, in slaves:
        iq.put(None)
        p.join()

if __name__ == '__main__':
    main()