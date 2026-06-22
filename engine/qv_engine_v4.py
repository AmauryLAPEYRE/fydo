"""
MOTEUR QV v4 — les 3 ajouts, testés sur l'EUROPE (out-of-US = test d'edge le plus propre).
  (1) Diversification géographique : le MÊME moteur sur l'Europe -> l'edge capé+gated
      regagne-t-il hors-US ? (si oui = vraie prime, pas curve-fit US)
  (2) Plafonds explicites : cap secteur + cap position -> effet sur le risque/rendement
  (3) Jauge de température : % de noms sous leur 200j -> backtest déploiement du cash
NOTE : prix en devise locale ; la comparaison capé+gated vs EW est neutre en mix-devise
       (mêmes noms) ; le CAGR absolu mélange EUR/GBP/CHF (pas un rendement EUR pur).
"""
import yfinance as yf, pandas as pd, numpy as np
import warnings; warnings.filterwarnings("ignore")

# univers EUROPÉEN : multi-pays (FR/DE/CH/NL/UK/ES/IT/SE), multi-secteurs
UNIV=["ASML.AS","SAP.DE","STM.PA","MC.PA","OR.PA","RMS.PA","AIR.PA","SU.PA","AI.PA",
      "SAN.PA","RI.PA","BN.PA","TTE.PA","NESN.SW","ROG.SW","NOVN.SW","ABBN.SW","SIE.DE",
      "ALV.DE","BAS.DE","MBG.DE","ULVR.L","DGE.L","AZN.L","SHEL.L","RKT.L","GSK.L",
      "ATCO-A.ST","ENEL.MI","IBE.MC","ITX.MC","BBVA.MC"]
FIN_STRUCTURE={"ALV.DE","BBVA.MC"}  # assureur + banque -> non-scorables ROIC/marge

def safe(df,r):
    try: return df.loc[r]
    except Exception: return None
rows=[]
for tk in UNIV:
    try:
        T=yf.Ticker(tk); info=T.info; inc=T.income_stmt; bs=T.balance_sheet
        ebit=safe(inc,"EBIT");rev=safe(inc,"Total Revenue");ni=safe(inc,"Net Income")
        gp=safe(inc,"Gross Profit");tax=safe(inc,"Tax Rate For Calcs")
        ic=safe(bs,"Invested Capital");eq=safe(bs,"Common Stock Equity");debt=safe(bs,"Total Debt")
        if rev is None or ni is None: continue
        n=min(5,len(rev))
        def avg(s,d=np.nan): return d if s is None else pd.to_numeric(s,errors="coerce").iloc[:n].mean()
        tr=avg(tax,0.25); tr=tr if 0<=tr<0.6 else 0.25
        roic=np.nan
        if ebit is not None and ic is not None:
            roic=((pd.to_numeric(ebit,errors="coerce").iloc[:n]*(1-tr))/
                  pd.to_numeric(ic,errors="coerce").iloc[:n].replace(0,np.nan)).mean()
        nm=(avg(ni)/avg(rev)) if avg(rev) else np.nan
        gm=(avg(gp)/avg(rev)) if (gp is not None and avg(rev)) else info.get("grossMargins")
        rv=pd.to_numeric(rev,errors="coerce").iloc[:n].values
        rcagr=(rv[0]/rv[-1])**(1/(n-1))-1 if n>1 and rv[-1]>0 else np.nan
        de=(pd.to_numeric(debt,errors="coerce").iloc[0]/pd.to_numeric(eq,errors="coerce").iloc[0]
            if debt is not None and eq is not None else info.get("debtToEquity"))
        rows.append(dict(tk=tk,sector=info.get("sector","?"),roic_5y_avg=roic,
            net_margin_5y_avg=nm,gross_margin_5y_avg=gm,rev_cagr_5y=rcagr,debt_to_equity=de))
    except Exception: pass
df=pd.DataFrame(rows).set_index("tk")
df["nonscore"]=df.index.isin(FIN_STRUCTURE)
print(f"Europe : {len(df)}/{len(UNIV)} noms récupérés, {df['sector'].nunique()} secteurs, {df['nonscore'].sum()} non-scorables")

# qualité sector-neutral
scor=df[~df["nonscore"]].copy()
def _w(s,lo=.05,hi=.95): return s.clip(s.quantile(lo),s.quantile(hi))
def _z(s):
    sd=s.std(ddof=0); return (s-s.mean())/sd if sd and not np.isnan(sd) else s*0.0
def _snz(d,c): return d.groupby("sector",group_keys=False)[c].apply(lambda g:_z(_w(pd.to_numeric(g,errors="coerce"))))
W={"roic_5y_avg":1.5,"gross_margin_5y_avg":1.0,"net_margin_5y_avg":1.0,"rev_cagr_5y":0.7,"debt_to_equity":-1.0}
acc=pd.Series(0.0,index=scor.index); ws=0
for c,w in W.items():
    if c in scor: acc=acc.add(w*_snz(scor,c).fillna(0),fill_value=0); ws+=abs(w)
scor["quality_z"]=acc/ws
df["quality_pct"]=scor["quality_z"].rank(pct=True)

# prix (devise locale)
px=yf.download(list(df.index),start="2008-01-01",auto_adjust=True,progress=False)["Close"]
basket=[t for t in df.index if t in px and not px[t].dropna().empty]
P=px[basket].resample("ME").last(); R=P.pct_change()
roll=px[basket].rolling(252).max().resample("ME").last()
dd_m=(P/roll-1).clip(upper=0)
ma200=px[basket].rolling(200).mean().resample("ME").last()
below200=(P<ma200)
qpct=df["quality_pct"].reindex(basket).fillna(0)
sectors=df["sector"].reindex(basket)

def pret(w): return (w.shift(1)*R).sum(axis=1).dropna()
def stats(pr):
    e=(1+pr).cumprod();y=len(pr)/12
    return e.iloc[-1]**(1/y)-1,(pr.mean()/pr.std()*np.sqrt(12) if pr.std()>0 else 0),(e/e.cummax()-1).min()

gate=(qpct>=0.4)
base=gate/gate.sum()
cheap=(-dd_m).div((-dd_m).abs().max(axis=1).replace(0,np.nan),axis=0).clip(0,1).fillna(0)
tilt=1.0+(1.5-1.0)*cheap.mul(gate.astype(float),axis=1)
w_cg=(pd.DataFrame(np.tile(base.values,(len(P),1)),index=P.index,columns=basket)*tilt)
w_cg=w_cg.div(w_cg.sum(axis=1),axis=0).fillna(0)
w_ew=pd.DataFrame(1/len(basket),index=P.index,columns=basket)

# ===== TEST 1 : edge cross-univers (Europe) =====
print("\n"+"="*92)
print("(1) DIVERSIFICATION GÉO / TEST D'EDGE — capé+gated vs EW sur l'EUROPE")
print("="*92)
cg,ew=pret(w_cg),pret(w_ew)
for nm,pr in [("Capé+gated (Europe)",cg),("Equal-weight (Europe)",ew)]:
    c,s,d=stats(pr); print(f"  {nm:28} CAGR {c*100:5.1f}%  Sharpe {s:.2f}  MaxDD {d*100:4.0f}%")
c1,s1,_=stats(cg); c0,s0,_=stats(ew)
print(f"  -> ΔSharpe = {s1-s0:+.2f}  | l'edge capé+gated regagne hors-US : {s1>s0}")

# ===== TEST 2 : plafonds explicites =====
print("\n"+"="*92)
print("(2) PLAFONDS EXPLICITES — cap position 8% + cap secteur 30%")
print("="*92)
def apply_caps(wrow,pos=0.08,sec=0.30,it=8):
    w=wrow.copy()
    for _ in range(it):
        w=w.clip(upper=pos); w=w/w.sum()
        ss=w.groupby(sectors).sum(); over=ss[ss>sec]
        if over.empty and (w<=pos+1e-9).all(): break
        for s in over.index:
            m=(sectors==s).values; w[m]*=sec/ss[s]
        w=w/w.sum()
    return w
w_capped=w_cg.apply(lambda r: apply_caps(r),axis=1)
cgc=pret(w_capped)
for nm,pr in [("Capé+gated SANS plafonds",cg),("Capé+gated AVEC plafonds",cgc)]:
    c,s,d=stats(pr); print(f"  {nm:28} CAGR {c*100:5.1f}%  Sharpe {s:.2f}  MaxDD {d*100:4.0f}%")
# concentration actuelle
last_cg=w_cg.iloc[-1]; last_capped=w_capped.iloc[-1]
print(f"  Ligne max : {last_cg.max()*100:.1f}% -> {last_capped.max()*100:.1f}% (plafonnée)")
sec_now=last_capped.groupby(sectors).sum()
print(f"  Secteur max : {last_cg.groupby(sectors).sum().max()*100:.1f}% -> {sec_now.max()*100:.1f}%")

# ===== TEST 3 : jauge de température =====
print("\n"+"="*92)
print("(3) JAUGE DE TEMPÉRATURE — % de noms sous leur 200j -> déploiement du cash")
print("="*92)
pct_below=below200.mean(axis=1)
# stratégie : 30% de cash normalement ; si peur large (>50% sous 200j) -> déploie (100% investi)
invested=pd.Series(0.70,index=P.index)
invested[pct_below>0.50]=1.00
r_temp=(invested.shift(1)*ew).dropna()          # cash rapporte ~0
r_static85=(0.85*ew).dropna()                    # même expo moyenne ~, sans timing
for nm,pr in [("EW 100% investi (réf.)",ew),("Temp-cash (30% cash, déploie sur peur)",r_temp),("Statique 85% (sans timing)",r_static85)]:
    c,s,d=stats(pr); print(f"  {nm:40} CAGR {c*100:5.1f}%  Sharpe {s:.2f}  MaxDD {d*100:4.0f}%")
print(f"  Température AUJOURD'HUI : {pct_below.iloc[-1]*100:.0f}% des noms européens sous leur 200j")

# ===== screen live Europe =====
print("\n"+"="*92)
print("SCREEN LIVE EUROPE — qualités en solde maintenant")
print("="*92)
rsi_now={}
for tk in basket:
    s=px[tk].dropna(); d=s.diff()
    u=d.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();dn=(-d.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    rsi_now[tk]=(100-100/(1+u.iloc[-1]/dn.iloc[-1])) if dn.iloc[-1] else 50
scr=df.copy(); scr["dd"]=dd_m.iloc[-1]; scr["rsi"]=pd.Series(rsi_now)
acc=scr[(scr["quality_pct"]>=0.5)&(scr["dd"]<=-0.15)&(scr["rsi"]<48)].sort_values("dd")
print("ACCUMULER (qualité + soldée) :")
for tk,r in acc.iterrows():
    print(f"  {tk:9} {str(r['sector'])[:16]:16} Q{r['quality_pct']*100:.0f}% DD{r['dd']*100:.0f}% RSI{r['rsi']:.0f}")
if acc.empty: print("  (aucune en zone d'accumulation aujourd'hui)")
