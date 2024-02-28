import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import boto3
from smart_open import open
#from glob import glob

def R2 (x, y, xmax=False, r2offset=0):
    coeff, cov = np.polyfit(x, y, 1, cov=True)
    stdcoeff = np.sqrt(np.diag(cov))
    polinomio = np.poly1d(coeff)
    yhat = polinomio(x)
    ybar = np.sum(y)/len(y)
    sstot = np.sum((y - ybar)**2)
    ssres = np.sum((y - yhat)**2)
    R2 = 1 - ssres/sstot
    if xmax:
        xline = np.linspace(x.min(), xmax)
    else:
        xline = np.linspace(x.min(), x.max())
    figline = go.Line(
            x = xline,
            y = polinomio(xline),
            line = dict(color = 'green', dash = 'dash')
            )
    return (coeff[0], coeff[1], R2, figline)

st.title('Calculate ACR')

s3 = boto3.client('s3')

response = s3.list_objects_v2(Bucket='bluesoftanalysiszurich')

filenames = [file['Key'] for file in response.get('Contents', [])][1:]

#filenames = glob('zurich*.csv')

dates = []
notes = []

for filename in filenames:
    with open (f's3://bluesoftanalysiszurich/{filename}') as filenow:
    #with open (filename) as filenow:
        datenow = filenow.readline()[11:]
        dates.append(datenow)
        notenow = filenow.readline()[7:]
        notes.append(notenow)

dffiles = pd.DataFrame({'file':filenames, 'date':dates, 'note':notes})
i_list = dffiles.index[dffiles.date.str.contains('000')].tolist()
dffiles.drop(i_list, inplace = True)
dffiles['date'] = pd.to_datetime(dffiles.date)
dffiles.sort_values(by='date', inplace = True)
dffiles.reset_index(inplace = True, drop = True)

filenames = st.multiselect('Select files to calculate ACR', dffiles.file)

@st.cache_data
def read_dataframes(files):
    dfs = []
    for file in files:
        path = f's3://bluesoftanalysiszurich/{file}'
        df = pd.read_csv(path, skiprows = 4)
        #df = pd.read_csv(file, skiprows = 4)
        dfs.append(df)
    return dfs

dfs = read_dataframes(filenames)

cutoff = st.selectbox('cut off', [0.5, 10, 20, 40, 100, 150], index = 3)

OF = st.number_input('Known OF (1 means it will be used the gantry rotation method)', format = '%.3f')

dfis = []
for df in dfs:
    last_time = df.iloc[-1,1]
    zeros = df.loc[(df.time < 1) | (df.time > last_time - 1), 'ch0':].mean()
    dfchz = df.loc[:, 'ch0':] - zeros
    dfchz.columns = ['ch0z', 'ch1z']
    dfz = pd.concat([df, dfchz], axis = 1)

    dfz['sensorcharge'] = dfz.ch0z * 0.03
    dfz['cerenkovcharge'] = dfz.ch1z * 0.03

    dfz['chunk'] = dfz.number // (300000/700)
    group = dfz.groupby('chunk')
    dfg = group.agg({'time':np.median,
                    'ch0z':np.sum,
                    'ch1z':np.sum})
    dfg['time_min'] = group['time'].min()
    dfg['time_max'] = group['time'].max()
    dfg['ch0diff'] = dfg.ch0z.diff()
    starttimes = dfg.loc[dfg.ch0diff > cutoff, 'time_min']
    finishtimes = dfg.loc[dfg.ch0diff < -cutoff, 'time_max']
    stss = [starttimes.iloc[0]] + list(starttimes[starttimes.diff()>2])
    sts = [t - 0.04 for t in stss]
    ftss = [finishtimes.iloc[0]] + list(finishtimes[finishtimes.diff()>2])
    fts = [t + 0.04 for t in ftss]

    #Find pulses
    maxvaluech = dfz.loc[(dfz.time < sts[0] - 1) | (dfz.time > fts[-1] + 1), 'ch0z'].max()
    dfz['pulse'] = dfz.ch0z > maxvaluech * 1.05
    dfz.loc[dfz.pulse, 'pulsenum'] = 1
    dfz.fillna({'pulsenum':0}, inplace = True)
    dfz['pulsecoincide'] = dfz.loc[dfz.pulse, 'number'].diff() == 1
    dfz.fillna({'pulsecoincide':False}, inplace = True)
    dfz['singlepulse'] = dfz.pulse & ~dfz.pulsecoincide

    for (n, (s, f)) in enumerate(zip(sts, fts)):
        dfz.loc[(dfz.time > s) & (dfz.time < f), 'shot'] = n


    dfi = dfz.groupby('shot').agg({'sensorcharge':np.sum,
                                'cerenkovcharge':np.sum,
                                'singlepulse':np.sum})
    dfis.append(dfi)

dfit = pd.concat(dfis)
dfit.reset_index(inplace = True, drop = True)
st.dataframe(dfit)

if OF == 1:
    # Here I have to put all the code to calc ACR based in rotations
    xnow = dfit.cerenkovcharge
    ynow = dfit.sensorcharge
    fig0 = go.Figure()
    go1 = go.Scatter(
            x = xnow,
            y = ynow,
            mode = 'markers'
            )
    fig0.add_traces(go1)
    ACR, ind, R2now, go2 = R2(xnow, ynow)
    fig0.add_traces(go2)
    fig0.add_annotation(
            x = (xnow.max() + xnow.min())/2 + 10,
            y = (ynow.max() + ynow.min())/2,
            text = r'y = %.3f x + %.3f' %(ACR, ind),
            showarrow = False
            )
    fig0.add_annotation(
            x = (xnow.max() + xnow.min())/2 + 10,
            y = (ynow.max() + ynow.min())/2 - 2,
            text = 'R2 = %.3f' %(R2now),
            showarrow = False
            )
    st.plotly_chart(fig0)
    

else:
    index10 = st.multiselect('Select index large field (ex. 10x10)', dfit.index)
    index3 = st.multiselect('Select index small field (ex. 3x3)', dfit.index)


    s10 = dfit.iloc[index10, 0].mean()
    s3 = dfit.iloc[index3, 0].mean()
    c10 = dfit.iloc[index10, 1].mean()
    c3 = dfit.iloc[index3, 1].mean()

    ACR = (s10*OF - s3)/(c10*OF - c3)

st.write("ACR is: %.3f" %ACR)
