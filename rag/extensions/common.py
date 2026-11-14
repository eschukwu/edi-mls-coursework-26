"""Shared helpers for our RAG extension scripts: data loading, retrieval metrics,
rank-combination methods (RRF, score fusion, top-m protection) and 2-fold parameter selection."""
import json, random, statistics, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # .../rag
sys.path.insert(0, str(ROOT))
from src.data import CourseData                           # supplied
from src.metrics import recall_at_k, mrr_at_k, ndcg_at_k  # supplied

DATA_DIR = ROOT / 'data/rag_corpus'
TRANSCRIPTS = ROOT / '.cache/practice_transcripts.jsonl'
METRICS = ['R@5', 'R@10', 'MRR@10', 'NDCG@10']


# ---------- loading ----------
def load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]

def load_transcripts(path=TRANSCRIPTS):
    return {r['query_id']: r['transcript'] for r in load_jsonl(path)}

def load_rankings(path, depth=None):
    """rankings.jsonl rows {query_id, ranked_ids} -> {query_id: [doc ids]}"""
    return {r['query_id']: r['ranked_ids'][:depth] for r in load_jsonl(path)}


# ---------- metrics ----------
def metrics(ranked, rel):
    return {'R@5': recall_at_k(ranked, rel, 5), 'R@10': recall_at_k(ranked, rel, 10),
            'MRR@10': mrr_at_k(ranked, rel, 10), 'NDCG@10': ndcg_at_k(ranked, rel, 10)}

def mean_of(per_query, qids, names=METRICS):
    return {m: statistics.mean(per_query[q][m] for q in qids) for m in names}

def churn(per_query, baseline, qids):
    """rescued: baseline R@10 = 0 -> > 0; broken: baseline R@10 > 0 -> 0"""
    rescued = sum(baseline[q]['R@10'] == 0 and per_query[q]['R@10'] > 0 for q in qids)
    broken = sum(baseline[q]['R@10'] > 0 and per_query[q]['R@10'] == 0 for q in qids)
    return rescued, broken


# ---------- reordering enc_a's top-N (index i = enc_a rank i) ----------
def _minmax(x):
    r = x.max() - x.min()
    return (x - x.min()) / r if r > 0 else np.zeros_like(x)

def order_rerank(ce):
    return list(np.argsort(-np.asarray(ce), kind='stable'))

def order_fusion(enc, ce, a):
    """a * enc_a score + (1 - a) * reranker score, both min-max scaled per query"""
    s = a * _minmax(np.asarray(enc, float)) + (1 - a) * _minmax(np.asarray(ce, float))
    return list(np.argsort(-s, kind='stable'))

def order_rrf(ce, c):
    """reciprocal rank fusion of enc_a's order and the reranker's order: 1/(c + rank), ranks from 1"""
    n = len(ce)
    ce_rank = np.empty(n); ce_rank[np.argsort(-np.asarray(ce), kind='stable')] = np.arange(n)
    s = 1 / (c + 1 + np.arange(n)) + 1 / (c + 1 + ce_rank)
    return list(np.argsort(-s, kind='stable'))

def order_protect(ce, m):
    """keep enc_a's top m, rerank the rest"""
    return list(range(m)) + sorted(range(m, len(ce)), key=lambda i: -ce[i])

def apply_order(ranked, order):
    """reorder the first len(order) docs of ranked; later docs keep their position"""
    head = [ranked[i] for i in order]
    return head + ranked[len(order):]


# ---------- parameter choice without testing on the same queries ----------
def two_fold_oof(per_param, qids, metric='R@5', seed=0):
    """per_param: {param: {qid: metrics}}. Choose the param on one half, apply to the other half.
    Returns ({qid: metrics} out-of-fold, [param chosen for fold 1, fold 2])."""
    order = sorted(qids); random.Random(seed).shuffle(order)
    h = len(order) // 2
    oof, chosen = {}, []
    for train, test in [(order[:h], order[h:]), (order[h:], order[:h])]:
        best = max(per_param, key=lambda p: mean_of(per_param[p], train)[metric])
        chosen.append(best)
        for q in test:
            oof[q] = per_param[best][q]
    return oof, chosen


# ---------- statistics ----------
def paired_bootstrap(new, base, qids, metric, n_boot=10000, seed=0):
    """Mean per-query difference new - base, 95% bootstrap CI over queries, two-sided bootstrap p."""
    d = np.array([new[q][metric] - base[q][metric] for q in qids])
    idx = np.random.default_rng(seed).integers(0, len(d), size=(n_boot, len(d)))
    bs = d[idx].mean(axis=1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    p = min(1.0, 2 * min((bs <= 0).mean(), (bs >= 0).mean()))
    return float(d.mean()), float(lo), float(hi), float(p)
