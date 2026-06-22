"""
Défi de B — version CORRIGÉE.
Bug 1 : on mesure l'edge SUR L'EW dans chaque univers (pas le Sharpe absolu), sinon le
        retrait des morts domine. inflation = edge_survivants − edge_complet.
Bug 2 : sélection top-tercile calculée UNIQUEMENT sur les noms éligibles∩univers.
Le tilt avait +0.25→+0.39 d'inflation d'edge. Le gate ordinal, décomposé par facteur ?
"""
import numpy as np

def run(N=400, T=180, seeds=120, mr=0.05, sigma=0.09, drift=0.006,
        base_h=0.0012, fh=0.012, ddh=0.010, noise=0.5, sel=0.30):
    rules=['Value (cheap)','Quality (low-frag)','Q+V','Q+V+écran']
    infl={k:[] for k in rules}; edgeF={k:[] for k in rules}
    dv_val=[]; dv_valscr=[]; dv_qv=[]; fp=[]
    for sd in range(seeds):
        rng=np.random.default_rng(sd)
        f=rng.uniform(0,1,N)
        logp=np.zeros((T+1,N)); alive=np.ones(N,bool); trend=np.zeros(N)
        for t in range(T):
            r=drift-mr*(logp[t]-trend)-0.004*f+sigma*rng.normal(size=N)
            logp[t+1]=logp[t]+r; trend=trend+drift
            price=np.exp(logp[t+1]); rmax=np.exp(np.maximum.accumulate(logp[:t+2],axis=0)).max(axis=0)
            dd=price/rmax-1
            die=(rng.random(N)<base_h+fh*f+ddh*np.clip(-dd,0,None))&alive
            logp[t+1,die]=-np.inf; alive&=~die
        price=np.exp(logp)
        with np.errstate(divide='ignore',invalid='ignore'):
            ret=np.where(price[:-1]>0,price[1:]/price[:-1]-1,0.0)
        ret=np.nan_to_num(ret,nan=0.0,posinf=0.0,neginf=-1.0)
        elig=price[:-1]>0; surv=price[-1]>0
        rmax_t=np.maximum.accumulate(np.where(price>0,price,np.nan),axis=0)
        cheap=np.nan_to_num(-(np.where(price>0,price/rmax_t-1,np.nan))[:-1],nan=0.0)
        q=-f+noise*rng.normal(size=N); distress=f+noise*rng.normal(size=N)
        def zc(x): m=x.mean(axis=1,keepdims=True);s=x.std(axis=1,keepdims=True);return np.divide(x-m,s,out=np.zeros_like(x),where=s>0)
        qz=np.tile((q-q.mean())/q.std(),(T,1)); vz=zc(cheap); qvz=qz+vz
        screen=(distress<np.percentile(distress,70))
        def top(score,univ):
            out=np.zeros((T,N),bool); mask=elig & univ[None,:]
            for t in range(T):
                v=mask[t]
                if v.sum()<3: continue
                thr=np.percentile(score[t][v],100*(1-sel)); out[t]=v & (score[t]>=thr)
            return out
        def sharpe(mask):
            s=mask.sum(axis=1,keepdims=True); w=np.divide(mask,s,out=np.zeros_like(mask,float),where=s>0)
            pr=(w*ret).sum(axis=1); return pr.mean()/pr.std()*np.sqrt(12) if pr.std()>0 else 0.0
        full=np.ones(N,bool)
        scores={'Value (cheap)':cheap,'Quality (low-frag)':qz,'Q+V':qvz,'Q+V+écran':qvz}
        for univ,store in [(full,'F'),(surv,'S')]:
            ew=sharpe(elig & univ[None,:])
            for k in rules:
                sv = screen&univ if k=='Q+V+écran' else univ
                e=sharpe(top(scores[k],sv))-ew
                if store=='F': edgeF[k].append(e); infl[k].append(-e)  # tmp: store -edgeF
                else: infl[k][-1]+=e                                   # inflation = edgeS - edgeF
        # bouclier : taux de faillite des noms tenus (univers complet)
        died=price[-1]==0
        def drate(mask): h=mask.any(axis=0); return (h&died).sum()/max(h.sum(),1)
        dv_val.append(drate(top(cheap,full)))
        dv_valscr.append(drate(top(cheap,screen)))
        dv_qv.append(drate(top(qvz,full)))
        healthy=price[-1]>0
        fp.append(((distress>=np.percentile(distress,70))&healthy).sum()/max(healthy.sum(),1))
    return rules,edgeF,infl,np.array(dv_val),np.array(dv_valscr),np.array(dv_qv),np.array(fp)

rules,edgeF,infl,dvv,dvs,dvq,fp=run()
print("DÉFI DE B — edge SUR L'EW, et son inflation de survivance, par facteur")
print("(le TILT de drawdown avait +0.25 à +0.39 d'inflation d'edge)\n")
print(f"{'Sélection':22}{'Edge/EW (complet)':>18}{'Inflation survivance':>22}")
for k in rules:
    print(f"{k:22}{np.mean(edgeF[k]):>+18.2f}{np.mean(infl[k]):>+22.3f}")
print("\nBOUCLIER détresse — taux de faillite des noms tenus :")
print(f"  Value seul (cheap)            : {dvv.mean()*100:.1f}%")
print(f"  Value + écran détresse        : {dvs.mean()*100:.1f}%   (réduction {(1-dvs.mean()/max(dvv.mean(),1e-9))*100:.0f}%)")
print(f"  Q+V (qualité dans la sélection): {dvq.mean()*100:.1f}%")
print(f"  Faux positifs (sains exclus)  : {fp.mean()*100:.0f}%")
