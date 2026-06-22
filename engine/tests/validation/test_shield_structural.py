"""
TEST DU BOUCLIER — version structurelle (design de B).
Santé latente h (Merton-like) pilote le DÉFAUT. Fondamentaux ET prix = deux proxys
bruités de h. Question falsifiable : le score de détresse (bilan) ajoute-t-il un AUC
INCRÉMENTAL sur le drawdown (prix) pour prédire le défaut à horizon H ?
- Conditionné sur les VIVANTS à t (le bon dénominateur).
- Calibré : bruit fonda réglé pour AUC mono-variable ≈ Altman documenté (~0.85).
- Aussi conditionné sur le bucket CHEAP (le seul contexte de décision honnête).
Si AUC_fonda ne bat pas AUC_dd même calibré -> bouclier redondant, on le retire.
"""
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

def simulate(N=400, T=140, seed=0, mu_mean=0.05, mu_neg=0.35, sig_h=0.55, h0=6.5,
             c=0.22, noise_f=2.0, noise_p=0.12, H=12):
    rng=np.random.default_rng(seed)
    mu=rng.normal(mu_mean,0.05,N)
    k=int(mu_neg*N); idx=rng.choice(N,k,replace=False)
    mu[idx]=-np.abs(rng.normal(0.06,0.03,k))                 # décliners structurels -> futurs morts
    h=np.full((T+1,N),np.nan); h[0]=h0+rng.normal(0,1.0,N)
    deftime=np.full(N,T+5)                                   # mois de défaut (T+5 = jamais)
    mkt=np.cumsum(rng.normal(0.003,0.035,T+1))
    eps=np.cumsum(rng.normal(0,noise_p,(T+1,N)),axis=0)      # bruit prix idiosyncratique (marche)
    for t in range(T):
        live=deftime>t
        h[t+1]=np.where(live,h[t]+mu+sig_h*rng.normal(size=N),np.nan)
        newdef=live&(h[t+1]<=0)
        deftime[newdef]=t+1
    logp=c*h+mkt[:,None]+eps; price=np.exp(logp)
    runmax=np.fmax.accumulate(np.where(np.isnan(price),-np.inf,price),axis=0)
    dd=price/runmax-1
    distress=-h+noise_f*rng.normal(size=h.shape)             # bilan : proxy bruité de -santé
    F,D,L,V=[],[],[],[]                                      # fonda, drawdown, label, valeur(cheap)
    for t in range(T-H):
        live=np.where(deftime>t)[0]
        for i in live:
            if np.isnan(distress[t,i]) or np.isnan(dd[t,i]): continue
            F.append(distress[t,i]); D.append(-dd[t,i])      # -dd : plus profond = plus "à risque" (croissant)
            V.append(-dd[t,i])                               # cheap = drawdown profond
            L.append(1 if deftime[i]<=t+H else 0)
    return np.array(F),np.array(D),np.array(L),np.array(V)

def pooled(noise_f,noise_p,seeds=6,H=12):
    F,D,L,V=[],[],[],[]
    for s in range(seeds):
        f,d,l,v=simulate(seed=s,noise_f=noise_f,noise_p=noise_p,H=H)
        F.append(f);D.append(d);L.append(l);V.append(v)
    return np.concatenate(F),np.concatenate(D),np.concatenate(L),np.concatenate(V)

def aucs(F,D,L):
    af=roc_auc_score(L,F); ad=roc_auc_score(L,D)
    X=np.column_stack([(F-F.mean())/F.std(),(D-D.mean())/D.std()])
    lr=LogisticRegression().fit(X,L); ac=roc_auc_score(L,lr.predict_proba(X)[:,1])
    return af,ad,ac

# --- 1. calibrer noise_f pour AUC_fonda ≈ 0.85 (Altman documenté) ---
print("Calibration du bruit fonda -> cible AUC ≈ 0.85 (Altman 1 an) :")
best=None
for nf in [1.2,1.8,2.4,3.0,3.6]:
    F,D,L,V=pooled(nf,0.12,seeds=4)
    af=roc_auc_score(L,F)
    print(f"  noise_f={nf:.1f} -> AUC_fonda={af:.3f}  (base-rate défaut {L.mean()*100:.1f}%)")
    if best is None or abs(af-0.85)<abs(best[1]-0.85): best=(nf,af)
NF=best[0]; print(f"  -> retenu noise_f={NF:.1f} (AUC_fonda≈{best[1]:.3f})\n")

# --- 2. la question centrale : lift incrémental du bilan sur le prix, balayage du bruit prix ---
print("Lift incrémental du BILAN sur le PRIX (drawdown) pour prédire le défaut (H=12m) :")
print(f"{'bruit prix':>11}{'AUC fonda':>11}{'AUC drawdown':>14}{'AUC combo':>11}{'lift combo−dd':>15}")
for npz in [0.06,0.12,0.20,0.35]:
    F,D,L,V=pooled(NF,npz,seeds=6)
    af,ad,ac=aucs(F,D,L)
    print(f"{npz:>11.2f}{af:>11.3f}{ad:>14.3f}{ac:>11.3f}{ac-ad:>+15.3f}")

# --- 3. le test opérationnel honnête : DANS le bucket cheap uniquement ---
print("\nDANS le bucket CHEAP (value_z ≥ tercile haut) — le seul contexte de décision :")
F,D,L,V=pooled(NF,0.12,seeds=6)
thr=np.percentile(V,66.7); m=V>=thr
af,ad,ac=aucs(F[m],D[m],L[m])
print(f"  base-rate défaut chez les cheap : {L[m].mean()*100:.1f}%  (vs {L.mean()*100:.1f}% univers)")
print(f"  AUC fonda {af:.3f} | AUC drawdown {ad:.3f} | combo {ac:.3f} | lift {ac-ad:+.3f}")
# au seuil opérationnel : hazard ratio FAIL vs PASS, recall, FPR
tau=np.percentile(F[m],70); fail=F[m]>=tau
pf=L[m][fail].mean(); pp=L[m][~fail].mean()
print(f"  Au seuil (30% pires) : hazard ratio P(défaut|FAIL)/P(défaut|PASS) = {pf/max(pp,1e-9):.1f}×  (Altman réel ~5-20×)")
print(f"  Recall (faillites flaggées) {L[m][fail].sum()/max(L[m].sum(),1)*100:.0f}%  |  FPR (sains exclus) {(fail&(L[m]==0)).sum()/max((L[m]==0).sum(),1)*100:.0f}%")
