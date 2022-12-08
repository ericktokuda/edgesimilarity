#!/usr/bin/env python3
"""Extract features from undirected graph
"""

import argparse
import time, datetime
import os, sys, random
from os.path import join as pjoin
from os.path import isfile
import inspect

import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from myutils import info, create_readme
import igraph
import pandas as pd
from sklearn.preprocessing import StandardScaler
from itertools import combinations

##########################################################
def interiority(dataorig):
    """Calculate the interiority index of the two rows. @vs has 2rows and n-columns, where
    n is the number of features"""
    # info(inspect.stack()[0][3] + '()')
    data = np.abs(dataorig)
    abssum = np.sum(data, axis=1)
    den = np.min(abssum)
    num = np.sum(np.min(data, axis=0))
    return num / den

##########################################################
def jaccard(dataorig, a):
    """Calculate the interiority index of the two rows. @vs has 2rows and n-columns, where
    n is the number of features"""
    data = np.abs(dataorig)
    den = np.sum(np.max(data, axis=0))
    datasign = np.sign(dataorig)
    plus_ = np.abs(datasign[0, :] + datasign[1, :])
    minus_ = np.abs(datasign[0, :] - datasign[1, :])
    splus = np.sum(plus_ * np.min(data, axis=0))
    sminus = np.sum(minus_ * np.min(data, axis=0))
    num = a * splus - (1 - a) * sminus
    return num / den

##########################################################
def coincidence(data, a):
    inter = interiority(data)
    jac = jaccard(data, a)
    return inter * jac

##########################################################
def get_coincidx_graph(dataorig, alpha, standardize, outdir):
    """Get graph of individual elements"""
    info(inspect.stack()[0][3] + '()')
    coincpath = pjoin(outdir, 'coinc.csv')
    impath = pjoin(outdir, 'coinc.png')

    if isfile(coincpath):
        return np.loadtxt(coincpath, delimiter=','), coincpath

    n, m = dataorig.shape
    if standardize:
        data = StandardScaler().fit_transform(dataorig)
    else:
        data = dataorig

    adj = np.zeros((n, n), dtype=float)
    for comb in list(combinations(range(n), 2)):
        data2 = data[list(comb)]
        c = coincidence(data2, alpha)
        adj[comb[0], comb[1]] = adj[comb[1], comb[0]] = c

    fig, ax = plt.subplots()
    im = ax.imshow(adj, cmap='hot', interpolation='nearest')
    fig.colorbar(im)
    plt.savefig(impath)
    np.savetxt(coincpath, adj, delimiter=',')
    return adj, coincpath
##########################################################
def get_reachable_vertices_exact(adj, vs0, h):
    """Get the vertices reachable in *exactly* h steps. This
    implies that, for instance, self may be included in the result."""
    if h == 0: return vs0, adj

    adjh = adj
    for i in range(h-1):
        adjh = np.dot(adjh, adj)

    rows, cols = adjh.nonzero()
    reachable = []
    for v in vs0:
        z = cols[np.where(rows == v)]
        reachable.extend(z)

    return reachable, adjh

##########################################################
def get_neighbourhood(adj, vs0, h, itself=False):
    """Get the entire neighbourhood centered on vs0, including self"""
    if h == 0: return vs0 if itself else []
    neighsprev, _ = get_reachable_vertices_exact(adj, vs0, h - 1)
    neighs, _ =  get_reachable_vertices_exact(adj, vs0, h)
    diff = set(neighsprev).union(set(neighs))
    if itself: return diff
    else: return diff.difference(set(vs0))

##########################################################
def get_ring(adj, vs0, h):
    """Get the hth rings"""
    if h == 0: return []
    neigh1 = get_neighbourhood(adj, vs0, h-1)
    neigh2 = get_neighbourhood(adj, vs0, h)
    return list(set(neigh2).difference(set(neigh1)))

##########################################################
def calculate_hiennodes(neighvs): # OK
    return len(neighvs)

##########################################################
def calculate_hienedges(adj, ringcur):
    return adj[ringcur, :][:, ringcur].sum() / 2

##########################################################
def calculate_hierdegree(adj, ringcur, ringnxt):
    return adj[ringcur, :][:, ringnxt].sum()

##########################################################
def calculate_hierclucoeff(he, hn):
    if hn == 1: return 0
    return 2 * (he / (hn * (hn - 1)))

##########################################################
def calculate_hieconvratio(hd, hnnxt):
    return hd / hnnxt


##########################################################
def graph_from_dfs(dfes, dfvs):
    """Short description """
    info(inspect.stack()[0][3] + '()')
    g = igraph.Graph(n=len(dfvs))
    g.vs['wid'] = dfvs.wid.values
    g.vs['title'] = dfvs.title.values
    g.add_edges(dfes[['srcvid', 'tgtvid']].values)
    g.simplify(multiple=True, loops=True)
    return g

##########################################################
def get_induced_subgraph(snppath, widspath, outdir):
    """Get the subgraph induced by the vertices with @wids wiki ids"""
    info(inspect.stack()[0][3] + '()')

    snpfiltpath = pjoin(outdir, 'snap0_es.tsv')
    widsfiltpath = pjoin(outdir, 'snap0_vs.tsv')

    if isfile(snpfiltpath):
        dfsnpfilt = pd.read_csv(snpfiltpath, sep='\t')
        dfwidsfilt = pd.read_csv(widsfiltpath, sep='\t')
        return dfsnpfilt, dfwidsfilt

    dfsnp = pd.read_csv(snppath, sep='\t')
    dfwids = pd.read_csv(widspath, sep='\t')
    dfwids = dfwids.loc[dfwids.ns == 0] # Filter pages from the main ns

    # Filter snapshot by the reference vertices
    dfsnpfilt = dfsnp.merge(dfwids, how='inner', left_on='src', right_on='id')
    dfsnpfilt = dfsnpfilt.merge(dfwids, how='inner', left_on='tgt', right_on='id')

    # Get titles of the vertices
    uwids = sorted(np.unique(dfsnpfilt[['src', 'tgt']].values.flatten()))
    dfwidsfilt = pd.DataFrame(uwids, columns=['wid']).merge(
        dfwids, how='inner', left_on='wid', right_on='id')
    dfwidsfilt = dfwidsfilt.drop_duplicates(keep='first')
    dfwidsfilt.to_csv(widsfiltpath, sep='\t', index=False,
                    columns=['wid', 'title'],)

    n = len(uwids)
    wid2vid = {wid:vid for vid, wid in enumerate(uwids)}

    # Convert wiki-id to vertex id
    dfsnpfilt = dfsnpfilt[['src', 'tgt']].copy()
    dfsnpfilt['srcvid'] = dfsnpfilt.src.map(wid2vid)
    dfsnpfilt['tgtvid'] = dfsnpfilt.tgt.map(wid2vid)
    dfsnpfilt.to_csv(snpfiltpath, sep='\t', index=False,
                    columns=['src', 'tgt', 'srcvid', 'tgtvid'])
    return dfsnpfilt, dfwidsfilt

##########################################################
def extract_hirarchical_feats(adj, v, h):
    """Extract hierarchical features"""
    ringcur = get_ring(adj, [v], h)
    ringnxt = get_ring(adj, [v], h+1)
    hn = calculate_hiennodes(ringcur)
    he = calculate_hienedges(adj, ringcur)
    hd = calculate_hierdegree(adj, ringcur, ringnxt)
    hc = calculate_hierclucoeff(he, hn)
    cr = calculate_hieconvratio(hd, calculate_hiennodes(ringnxt))
    return [hn, he, hd, hc, cr]

##########################################################
def extract_hierarchical_feats_all(adj,  h):
    labels = 'hn he hd hc cr'.split(' ')
    feats = []
    for v in range(adj.shape[0]):
        feats.append(extract_hirarchical_feats(adj, v, h))
    return feats, labels

##########################################################
def vattributes2edges(g, attribs, aggreg='sum'):
    m = g.ecount()
    for attrib in attribs:
        values = g.vs[attrib]
        for j in range(m):
            src, tgt = g.es[j].source, g.es[j].target
            if aggreg == 'sum':
                g.es[j][attrib] = g.vs[src][attrib] + g.vs[tgt][attrib]
    return g

##########################################################
def plot_motifs(gorig, edges, coincpath, outdir):
    info(inspect.stack()[0][3] + '()')

    outpath = pjoin(outdir, 'coinc.pdf')
    coinc = np.loadtxt(coincpath, delimiter=',', dtype=float)
    coinc = np.power(coinc, 3)
    g1 = igraph.Graph.Weighted_Adjacency(coinc, mode='undirected')
    g1.delete_edges(g1.es.select(weight_lt=.6))

    breakpoint()

    # comm = g1.community_multilevel(weights='weight')
    ncomms = 7
    comm = g1.components(mode='weak')
    szs = comm.sizes()
    largestcommids = np.flip(np.argsort(szs))[:ncomms]
    membs = np.array(comm.membership)
    m = g1.vcount()

    palette = ['#e41a1c','#377eb8','#4daf4a','#984ea3','#ff7f00','#ffff33','#a65628','#f781bf','#999999']
    vcolours = np.array(['#d9d9d9'] * m)



    ##########################################################
    # Making the colormap
    from matplotlib.colors import LinearSegmentedColormap
    cm = LinearSegmentedColormap.from_list(
        'new',
        # palette[:ncomms] + ['#d9d9d9'],
        ['#d9d9d9'] + palette[:ncomms] ,
        N = 8)

    fig, ax = plt.subplots()
    im = ax.imshow(np.random.random((3,3)), interpolation ='nearest',
                    origin ='lower', cmap = cm)
    # ax.set_title("bin: % s" % all_bin)
    fig.colorbar(im, ax=ax)
    plt.savefig('/tmp/colorbar.pdf')

    ##########################################################
    for i in range(ncomms):
        vcolours[np.where(membs == largestcommids[i])[0]] = palette[i]

    outpath = pjoin(outdir, 'coinc.pdf')
    igraph.plot(g1, outpath, edge_width=np.abs(g1.es['weight']), bbox=(1200, 1200),
                vertex_size=5, vertex_color=vcolours.tolist())

    ##########################################################
    g = gorig.copy()
    eids = g.get_eids(edges)
    todel = set(range(g.ecount())).difference(eids)

    g.es['comm'] = -1
    for i in range(ncomms):
        aux = np.array(edges)[np.where(membs == largestcommids[i])[0]]
        g.es[g.get_eids(aux)]['comm'] = i
    aux = np.array(edges)[np.where(membs == largestcommids[0])[0]]
    g.es[g.get_eids(aux)]['comm'] = 0

    g.delete_edges(todel)
    degs = g.degree()
    g.delete_vertices(np.where(np.array(degs) == 0)[0])

    membs = np.array(g.es['comm'])
    m = g.ecount()
    ecolours = np.array(['#d9d9d9'] * m)

    outpath = pjoin(outdir, 'orig.png')
    igraph.plot(g, outpath, bbox=(1200, 1200),
                # vertex_label=g.vs['title'],
                vertex_color='black',
                vertex_size=5,
                edge_color=ecolours.tolist())

    

    outpath = pjoin(outdir, 'orig.pdf')
    igraph.plot(g, outpath, bbox=(1200, 1200),
                # vertex_label=g.vs['title'],
                vertex_color='black',
                vertex_size=5,
                edge_color=ecolours.tolist())
##########################################################
def main(outdir):
    info(inspect.stack()[0][3] + '()')

    random.seed(0); np.random.seed(0)
    n = 200
    p = 0.1
    h = 2

    # Generate the graph
    g = igraph.Graph.Erdos_Renyi(n, p, directed=False, loops=False)
    g = g.connected_components().giant()
    adj = g.get_adjacency_sparse()

    # Extract features
    vfeats, labels = extract_hierarchical_feats_all(adj,  h)
    vfeats = np.array(vfeats)
    for i, l in enumerate(labels):
        g.vs[l] = vfeats[:, i]

    g = vattributes2edges(g, labels, aggreg='sum')
    efeats = np.array([g.es[l] for l in labels]).T
    coinc, coincpath = get_coincidx_graph(efeats, .5, True, outdir)

    edges = [[e.source, e.target] for e in g.es]
    plot_motifs(g, edges, coincpath, outdir)
    
    # If features are from vertices, 'transform' them into edge features
    # Coincidence on each pair of edges
    # Visualize


##########################################################
if __name__ == "__main__":
    info(datetime.date.today())
    t0 = time.time()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir', default='/tmp/out/', help='Output directory')
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    readmepath = create_readme(sys.argv, args.outdir)

    main(args.outdir)

    info('Elapsed time:{:.02f}s'.format(time.time()-t0))
    info('Output generated in {}'.format(args.outdir))
