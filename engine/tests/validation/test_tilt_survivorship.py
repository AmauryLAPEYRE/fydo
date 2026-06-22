"""
TEST MINIMAL — l'edge du tilt contrarien survit-il sans survivance ?
Mécanisme (la critique de B) : le tilt surpondère la profondeur du drawdown.
Sur un panier de survivants, tout drawdown profond a récupéré PAR DÉFINITION.
Modèle : mean-reversion (les creux rebondissent partiellement) + faillites dont la
proba MONTE avec le drawdown (les détresses meurent plus). On compare le tilt vs EW :
  - sur l'univers COMPLET (les morts encaissent leur -100%)
  - sur le sous-ensemble SURVIVANT (sélectionné ex-post = biais de survivance)
Si ΔSharpe(tilt-EW) est bien plus haut sur les survivants -> l'edge du tilt EST gonflé.
"""
import numpy as np

def run(n=300, T=200, seeds=120, kappa=0.07, sigma=0.10, drift=0.006,
        death_base=0.0015, death_slope=0.015):
    full_d, surv_d = [], []
    for sd in range(seeds):
        rng = np.random.default_rng(sd)
        logp = np.zeros((T+1, n))
        alive = np.ones(n, bool)
        trend = np.zeros(n)
        for t in range(T):
            dev = logp[t] - trend                      # écart au trend
            r = drift - kappa*dev + sigma*rng.normal(size=n)   # mean-reverting
            logp[t+1] = logp[t] + r
            trend = trend + drift
            price = np.exp(logp[t+1])
            runmax = np.exp(np.maximum.accumulate(logp[:t+2], axis=0)).max(axis=0)
            dd = price/runmax - 1
            p_death = death_base + death_slope*np.clip(-dd, 0, None)
            die = (rng.random(n) < p_death) & alive
            logp[t+1, die] = -np.inf                    # prix -> 0 (mort)
            alive &= ~die
        price = np.exp(logp)                            # (T+1, n), 0 si mort
        # rendements simples mensuels
        with np.errstate(divide='ignore', invalid='ignore'):
            ret = np.where(price[:-1] > 0, price[1:]/price[:-1] - 1, 0.0)
        ret = np.nan_to_num(ret, nan=0.0, posinf=0.0, neginf=-1.0)
        # drawdown observé à chaque t (pour pondérer, pas de look-ahead)
        rmax = np.maximum.accumulate(np.where(price > 0, price, np.nan), axis=0)
        dd_obs = np.where(price > 0, price/rmax - 1, np.nan)[:-1]   # (T, n)
        eligible = price[:-1] > 0                        # vivant à t-1 = investissable

        def sharpe(weights):
            w = weights * eligible
            s = w.sum(axis=1, keepdims=True); w = np.divide(w, s, out=np.zeros_like(w), where=s>0)
            pr = (w * ret).sum(axis=1)
            return pr.mean()/pr.std()*np.sqrt(12) if pr.std() > 0 else 0.0

        tilt = np.nan_to_num(-dd_obs, nan=0.0)           # ∝ profondeur du drawdown
        ew = np.ones((T, n))
        full_d.append(sharpe(tilt) - sharpe(ew))

        # --- sous-ensemble SURVIVANT (vivant à la fin) ---
        surv = price[-1] > 0
        retS = ret[:, surv]; ddS = dd_obs[:, surv]; eligS = eligible[:, surv]
        def sharpeS(weights):
            w = weights * eligS
            s = w.sum(axis=1, keepdims=True); w = np.divide(w, s, out=np.zeros_like(w), where=s>0)
            pr = (w * retS).sum(axis=1)
            return pr.mean()/pr.std()*np.sqrt(12) if pr.std() > 0 else 0.0
        tiltS = np.nan_to_num(-ddS, nan=0.0); ewS = np.ones_like(retS)
        surv_d.append(sharpeS(tiltS) - sharpeS(ewS))
    return np.array(full_d), np.array(surv_d)

f, s = run()
print("ΔSharpe (tilt − equal-weight) :")
print(f"  Univers COMPLET (avec les morts)        : {f.mean():+.3f}   [{np.percentile(f,5):+.2f} .. {np.percentile(f,95):+.2f}]")
print(f"  Sous-ensemble SURVIVANT (biais ex-post) : {s.mean():+.3f}   [{np.percentile(s,5):+.2f} .. {np.percentile(s,95):+.2f}]")
print(f"  -> inflation de l'edge du tilt par la survivance : {s.mean()-f.mean():+.3f} de Sharpe")
print(f"  -> l'edge du tilt sur l'univers complet est-il positif ? {f.mean()>0.02}")
