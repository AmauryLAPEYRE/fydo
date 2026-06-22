"""
SECTION 3 CORRIGÉE (faille #1 de B).
Avant : bucket cheap = -dd, puis on faisait concourir -dd dedans -> range restriction
        qui déprime l'AUC drawdown (artefact) + re-conflate cheap=tombé.
Maintenant : bucket cheap défini par une VALORISATION indépendante du drawdown
        (earnings yield ~ santé/prix). Le drawdown n'est plus la variable de bucket.
Prédiction de B : le lift rétrécit (peut-être de moitié) ; le signe survit, pas la magnitude.
"""
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

def simulate(N=400,T=140,seed=0,mu_mean=0.05,mu_neg=0.35,sig_h=0.55,h0=6.5,
             c=0.22,noise_f=3.6,noise_p=0.14,noise_v=1.0,H=12):
    rng=np.random.default_rng(seed)
    mu=rng.normal(mu_mean,0.05,N); k=int(mu_neg*N); idx=rng.choice(N,k,replace=False)
    mu[idx]=-np.abs(rng.normal(0.06,0.03,k))
    h=np.full((T+1,N),np.nan); h[0]=h0+rng.normal(0,1.0,N); deftime=np.full(N,T+5)
    mkt=np.cumsum(rng.normal(0.003,0.035,T+1)); eps=np.cumsum(rng.normal(0,noise_p,(T+1,N)),axis=0)
    for t in range(T):
        live=deftime>t; h[t+1]=np.where(live,h[t]+mu+sig_h*rng.normal(size=N),np.nan)
        deftime[live&(h[t+1]<=0)]=t+1
    logp=c*h+mkt[:,None]+eps; price=np.exp(logp)
    runmax=np.fmax.accumulate(np.where(np.isnan(price),-np.inf,price),axis=0); dd=price/runmax-1
    distress=-h+noise_f*rng.normal(size=h.shape)
    # VALORISATION indépendante : earnings yield ~ log(santé) - log(prix) + bruit
    # (cheap = beaucoup de "fondamental" par unité de prix ; distinct du drawdown path-max)
    with np.errstate(divide='ignore',invalid='ignore'):
        value=np.log(np.where(h>0,h,np.nan))-(logp-mkt[:,None])+noise_v*rng.normal(size=h.shape)
    F,Dd,L,Val=[],[],[],[]
    for t in range(T-H):
        for i in np.where(deftime>t)[0]:
            if np.isnan(distress[t,i]) or np.isnan(dd[t,i]) or np.isnan(value[t,i]): continue
            F.append(distress[t,i]); Dd.append(-dd[t,i]); Val.append(value[t,i])
            L.append(1 if deftime[i]<=t+H else 0)
    return map(np.array,(F,Dd,L,Val))

def pooled(seeds=6):
    F,D,L,V=[],[],[],[]
    for s in range(seeds):
        f,d,l,v=simulate(seed=s); F.append(f);D.append(d);L.append(l);V.append(v)
    return np.concatenate(F),np.concatenate(D),np.concatenate(L),np.concatenate(V)

def aucs(F,D,L):
    af=roc_auc_score(L,F); ad=roc_auc_score(L,D)
    X=np.column_stack([(F-F.mean())/F.std(),(D-D.mean())/D.std()])
    ac=roc_auc_score(L,LogisticRegression().fit(X,L).predict_proba(X)[:,1]); return af,ad,ac

F,D,L,V=pooled()
print(f"Corrélation(value, drawdown) = {np.corrcoef(V,D)[0,1]:+.2f}  (proche de 0 = vraiment indépendants ; le drawdown n'est plus le bucket)\n")
print("NON conditionné (univers entier, propre — la section 2 de B, rappel) :")
af,ad,ac=aucs(F,D,L); print(f"  AUC fonda {af:.3f} | drawdown {ad:.3f} | combo {ac:.3f} | lift {ac-ad:+.3f}")
print("\nBucket CHEAP défini par VALO indépendante (corrigé) :")
thr=np.percentile(V,66.7); m=V>=thr
af,ad,ac=aucs(F[m],D[m],L[m])
print(f"  base-rate défaut chez les cheap : {L[m].mean()*100:.1f}%")
print(f"  AUC fonda {af:.3f} | drawdown {ad:.3f} | combo {ac:.3f} | lift {ac-ad:+.3f}")
print("\nRappel — ANCIEN bucket (défini par -dd, biaisé) pour comparer l'ampleur du gonflage :")
thrB=np.percentile(D,66.7); mB=D>=thrB
af2,ad2,ac2=aucs(F[mB],D[mB],L[mB])
print(f"  AUC fonda {af2:.3f} | drawdown {ad2:.3f} | combo {ac2:.3f} | lift {ac2-ad2:+.3f}  <- gonflé par range restriction")
