"""Cuatro ideas intradía en 5m (BTC, ETH, 1 año): falsa ruptura del rango asiático, tendencia 1H/4H + retroceso,
ruptura del rango de apertura de NY y reversión a la VWAP. Resultado 22-nov-2026: todas negativas con comisiones de Bitget."""
import sys; sys.path.insert(0,'/home/user/analizador-de-mercados')
import numpy as np, pandas as pd
from analizador.indicadores import atr as A, rsi as RS
def carga(mid):
    df=pd.read_csv(f'/home/user/analizador-de-mercados/data/intradia/{mid}_5m.csv.gz',index_col='fecha'); df.index=pd.to_datetime(df.index,utc=True); return df
TAKER=0.0006+0.0002; MAKER=0.0002
def sim(df, ent, entrada_limite=False):
    """ent: lista (t_senal, d, stop, objetivo, t_fin). Entra a mercado en open[t+1]. Sale en stop (taker), objetivo (maker) o t_fin (taker). Una a la vez."""
    o,h,l,c=(df[x].to_numpy() for x in ('open','high','low','close')); n=len(df)
    out=[]; libre=0
    for t,d,stop,obj,tf in ent:
        if t+1>=n or t<libre: continue
        e=o[t+1]; R=(e-stop)*d
        if R<=0 or (obj-e)*d<=0: continue
        ce=MAKER if entrada_limite else TAKER
        res=None
        for i in range(t+1,min(tf,n-1)+1):
            if (l[i]<=stop if d>0 else h[i]>=stop): x=stop if not ((o[i]<stop) if d>0 else (o[i]>stop)) else o[i]; res=((x-e)*d, TAKER, x); break
            if (h[i]>=obj if d>0 else l[i]<=obj): res=((obj-e)*d, MAKER, obj); break
        else:
            i=min(tf,n-1); res=((c[i]-e)*d, TAKER, c[i])
        bruto=res[0]/R; neto=bruto-(ce*e+res[1]*res[2])/R
        out.append((df.index[t],bruto,neto,R/e*100,i-t)); libre=i+1
    return pd.DataFrame(out,columns=['fecha','bruto','neto','stop_pct','velas'])
def informe(nombre, por_mercado):
    for mid,r in por_mercado.items():
        if r.empty: print(f'{nombre:40} {mid}: 0 ops'); continue
        corte=r.fecha.iloc[0]+(r.fecha.iloc[-1]-r.fecha.iloc[0])/2
        a=r[r.fecha<corte].neto.mean(); b=r[r.fecha>=corte].neto.mean()
        print(f'{nombre:40} {mid}: n={len(r):4} gana={(r.neto>0).mean()*100:3.0f}% bruto={r.bruto.mean():+.2f} neto={r.neto.mean():+.2f} (mitades {a:+.2f}/{b:+.2f}) stop {r.stop_pct.median():.2f}% dur {r.velas.median()*5/60:.1f}h',flush=True)

D={m:carga(m) for m in ('btc','eth')}
def prep(df):
    x=df.copy(); x['atr']=A(df); x['rsi']=RS(df['close'])
    x['dia']=x.index.floor('D'); x['hora']=x.index.hour+x.index.minute/60
    h1=df['close'].resample('1h',label='right',closed='left').last().dropna()
    e50=h1.ewm(span=50,adjust=False).mean()
    x['tend1h']=np.sign(h1-e50).where(e50.diff(3)*np.sign(h1-e50)>0,0).reindex(x.index,method='ffill').fillna(0)
    h4=df['close'].resample('4h',label='right',closed='left').last().dropna()
    x['tend4h']=np.sign(h4-h4.rolling(50).mean()).reindex(x.index,method='ffill').fillna(0)
    return x
X={m:prep(df) for m,df in D.items()}

# ---------- A) Falsa ruptura del rango asiático ----------
def asia(x, objetivo='opuesto', ini=8, fin=20, perf_max=0.5, filtro=None):
    h,l,c=x.high.to_numpy(),x.low.to_numpy(),x.close.to_numpy(); hr=x.hora.to_numpy(); a=x.atr.to_numpy()
    ent=[]
    for dia,g in x.groupby('dia'):
        pos=x.index.get_indexer(g.index); asi=pos[g.hora.to_numpy()<8]
        if len(asi)<90: continue
        H,L=h[asi].max(),l[asi].min(); W=H-L
        hechos=set(); ext={1:None,-1:None}
        for t in pos[(g.hora.to_numpy()>=ini)&(g.hora.to_numpy()<fin)]:
            for d in (1,-1):
                if d in hechos: continue
                if d==1 and l[t]<L: ext[1]=min(ext[1] or l[t],l[t])
                if d==-1 and h[t]>H: ext[-1]=max(ext[-1] or h[t],h[t])
                e=ext[d]
                if e is None: continue
                if abs(e-(L if d==1 else H))>perf_max*W: hechos.add(d); continue
                if (c[t]>L if d==1 else c[t]<H):
                    if filtro is not None and x[filtro].iat[t]==-d: hechos.add(d); continue
                    stop=e-0.1*a[t]*d
                    obj={'opuesto':H if d==1 else L,'medio':(H+L)/2}[objetivo]
                    ent.append((t,d,stop,obj,pos[-1])); hechos.add(d)
    return sorted(ent)
for objv in ('opuesto','medio'):
    informe(f'A asia falsa ruptura obj {objv}',{m:sim(D[m],asia(X[m],objv)) for m in D})
informe('A asia obj opuesto + filtro 4h',{m:sim(D[m],asia(X[m],'opuesto',filtro='tend4h')) for m in D})
informe('A asia opuesto solo 13-20 UTC (NY)',{m:sim(D[m],asia(X[m],'opuesto',ini=13)) for m in D})

# ---------- B) Tendencia 1H + retroceso en 5m ----------
def retroceso(x, rr=3.0, stop_min=0.4, filtro='tend1h'):
    o,h,l,c=(x[k].to_numpy() for k in ('open','high','low','close')); a=x.atr.to_numpy()
    e20=x.close.ewm(span=20,adjust=False).mean().to_numpy(); tnd=x[filtro].to_numpy(); n=len(x)
    ent=[]
    for t in range(30,n-1):
        d=tnd[t]
        if d==0: continue
        toco = l[t-1]<=e20[t-1] if d>0 else h[t-1]>=e20[t-1]
        sale = c[t]>e20[t] and c[t]>h[t-1] if d>0 else c[t]<e20[t] and c[t]<l[t-1]
        if not (toco and sale): continue
        sw = l[t-12:t+1].min()-0.1*a[t] if d>0 else h[t-12:t+1].max()+0.1*a[t]
        e=c[t]; R=(e-sw)*d
        if R/e*100<stop_min: sw=e-d*e*stop_min/100; R=e*stop_min/100
        ent.append((t,int(d),sw,e+d*rr*R,t+288))
    return ent
for rr,sm in ((2,0.3),(3,0.4),(4,0.6)):
    informe(f'B tend 1h + retroceso EMA20 {rr}R stop>={sm}%',{m:sim(D[m],retroceso(X[m],rr,sm)) for m in D})
informe('B tend 4h + retroceso 3R stop>=0.5%',{m:sim(D[m],retroceso(X[m],3,0.5,'tend4h')) for m in D})

# ---------- C) Ruptura del rango de apertura de NY (13:30-14:00 UTC) ----------
def orb(x, rr=2.0, stop='opuesto', filtro=None):
    h,l,c=x.high.to_numpy(),x.low.to_numpy(),x.close.to_numpy()
    ent=[]
    for dia,g in x.groupby('dia'):
        pos=x.index.get_indexer(g.index); hr=g.hora.to_numpy()
        rg=pos[(hr>=13.5)&(hr<14)]
        if len(rg)<6: continue
        H,L=h[rg].max(),l[rg].min()
        for t in pos[(hr>=14)&(hr<17)]:
            d=1 if c[t]>H else -1 if c[t]<L else 0
            if d==0: continue
            if filtro is not None and x[filtro].iat[t]==-d: break
            st={'opuesto':L if d==1 else H,'medio':(H+L)/2}[stop]
            R=(c[t]-st)*d; ent.append((t,d,st,c[t]+d*rr*R,pos[hr<20][-1])); break
    return ent
for rr,st in ((1.5,'medio'),(2,'opuesto'),(3,'medio')):
    informe(f'C ORB NY {rr}R stop {st}',{m:sim(D[m],orb(X[m],rr,st)) for m in D})
informe('C ORB NY 2R stop medio + filtro 4h',{m:sim(D[m],orb(X[m],2,'medio','tend4h')) for m in D})

# ---------- D) Reversión a la VWAP diaria ----------
def vwap_rev(x, k=3.0, rmax=25):
    tp=(x.high+x.low+x.close)/3; pv=(tp*x.volume).groupby(x.dia).cumsum(); vv=x.volume.groupby(x.dia).cumsum()
    vw=(pv/vv).to_numpy(); c=x.close.to_numpy(); a=x.atr.to_numpy(); r=x.rsi.to_numpy(); hr=x.hora.to_numpy()
    fin=pd.Series(np.arange(len(x)),index=x.index).groupby(x.dia).transform('max').to_numpy()
    ent=[]
    for t in range(30,len(x)-1):
        if hr[t]<2 or hr[t]>21: continue
        dist=c[t]-vw[t]
        if dist<-k*a[t] and r[t]<rmax: d=1
        elif dist>k*a[t] and r[t]>100-rmax: d=-1
        else: continue
        ent.append((t,d,c[t]-d*abs(dist),vw[t],fin[t]))
    return ent
for k,rm in ((3,25),(4,20),(5,20)):
    informe(f'D VWAP reversión {k} ATR RSI {rm}',{m:sim(D[m],vwap_rev(X[m],k,rm)) for m in D})
