"""Backtest intradía de 5 minutos (BTC, ETH) con varios escenarios de comisión.

Requiere data/intradia/*_5m.csv.gz (workflow "Descargar velas intradía").
Uso: python scripts/backtest_intradia.py
Resultado del 22-nov-2026: sin comisiones ~0 a +0,1R por operación; con comisiones
a mercado -0,5 a -0,9R; con órdenes límite -0,1 a -0,4R. No es viable así.
"""
import sys, time, itertools; sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
import numpy as np, pandas as pd, pickle, os
from analizador import indicadores as I, senales as S, backtest as B
def carga(mid):
    df=pd.read_csv(f'data/intradia/{mid}_5m.csv.gz',index_col='fecha'); df.index=pd.to_datetime(df.index,utc=True); return df
cache='/tmp/analizador_x5m.pkl'
if os.path.exists(cache): X=pickle.load(open(cache,'rb'))
else:
    X={}
    for mid in ['btc','eth']:
        t=time.time(); df=carga(mid); x=I.calcular(df)
        # volumen relativo a la misma hora de los últimos 20 días
        hm=df.index.hour*12+df.index.minute//5
        x['vol_media_hora']=df['volume'].groupby(hm).transform(lambda s: s.rolling(20,min_periods=5).mean().shift(1))
        X[mid]=(df,x); print(mid,len(df),df.index[0],round(time.time()-t),'s',flush=True)
    pickle.dump(X,open(cache,'wb'))
def run(N=30, costo=0.0008, tend=200, horas=None, vol_hora=False, pm=3, max_barras=30):
    B.COSTO_POR_LADO['cripto']=costo
    res={}
    for mid,(df,x) in X.items():
        xx=x.copy()
        if vol_hora: xx['vol_media']=xx['vol_media_hora']
        s=S.detectar(df,S.Parametros(rango_barras=N),xx)
        if horas: s=[z for z in s if horas[0]<=z.fecha.hour<horas[1]]
        ops=[o for o in B.simular(df,s,'cripto',B.ReglasBT(puntos_min=pm,filtro_tendencia=tend,max_barras=max_barras)) if o.motivo_salida!='abierta']
        corte=df.index[len(df)//2].strftime('%Y-%m-%d')
        a=[o.r for o in ops if o.fecha_entrada<corte]; b=[o.r for o in ops if o.fecha_entrada>=corte]
        res[mid]=(len(a),np.mean(a) if a else 0,len(b),np.mean(b) if b else 0, np.mean(np.array([o.r for o in ops])>0) if ops else 0)
    return ' | '.join(f"{k}: 1ª mitad {v[0]}/{v[1]:+.2f} 2ª {v[2]}/{v[3]:+.2f} win {v[4]*100:.0f}%" for k,v in res.items())
if __name__=='__main__':
    for N in [30,60,120]:
        for costo,cn in [(0.0008,'mercado'),(0.0003,'límite')]:
            print(f'N={N:3} {cn:8}', run(N=N,costo=costo),flush=True)
    print('--- variantes N=30')
    for kw in [dict(tend=0),dict(horas=(13,21)),dict(vol_hora=True),dict(pm=2),dict(max_barras=60)]:
        for costo,cn in [(0.0008,'mercado'),(0.0003,'límite')]:
            print(kw,cn,run(N=30,costo=costo,**kw),flush=True)
