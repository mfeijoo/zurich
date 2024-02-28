import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import boto3
#from glob import glob
from smart_open import open

st.title('Ultra Fast PDD Analysis')

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

listoffiles = [file for file in dffiles.file if 'ultrafast' in file]

filenow = st.selectbox('Select file to analyze:', listoffiles)

@st.cache_data
def read_dataframe(file):
    path = f's3://bluesoftanalysiszurich/{file}'
    df = pd.read_csv(path, skiprows = 4)
    #df = pd.read_csv(file, skiprows = 4)
    return df

df = read_dataframe(filenow)

showdataframe = st.checkbox('Show dataframe')

if showdataframe:
    st.dataframe(df)

#Prepare data frame to first plot

last_time = df.iloc[-1,1]
zeros = df.loc[(df.time < 1) | (df.time > last_time - 1), 'ch0':].mean()
dfzeros = df.loc[:, 'ch0':] - zeros
dfzeros.columns = ['ch0z', 'ch1z']
dfz = pd.concat([df, dfzeros], axis = 1)

@st.cache_data
def plotfigch(df, x_string = 'time', y_string = 'voltage'):
    fig = px.scatter(df, x= x_string, y = y_string, color='ch')
    fig.update_traces (marker = dict(size = 2))
    fig.update_xaxes(title = 'time (s)')
    return fig

@st.cache_data
def plotfig(df, x_string = 'time', y_string = 'voltage'):
    fig = px.scatter(df, x= x_string, y = y_string)
    fig.update_traces (marker = dict(size = 2, color = 'blue', opacity = 0.5))
    fig.update_xaxes(title = 'time (s)')
    return fig
showpulses = st.checkbox('Show Pulses', value = False)
if showpulses:
    dfz0 = dfz.loc[:, ['time', 'ch0z']]
    dfz0.columns = ['time', 'voltage']
    dfz0['ch'] = 'ch0'
    dfz1 = dfz.loc[:, ['time', 'ch1z']]
    dfz1.columns = ['time', 'voltage']
    dfz1['ch'] = 'ch1'
    dfztp = pd.concat([dfz0, dfz1])
    fig1 = plotfigch(dfztp)
    st.plotly_chart(fig1)

group = st.checkbox('group every 300 ms', value = True)
if group:
    dfz['chunk'] = dfz.number // int(300000/750)
    dfg = dfz.groupby('chunk').agg({'time':np.median, 'ch0z':np.sum, 'ch1z':np.sum})
    dfg0 = dfg.loc[:,['time', 'ch0z']]
    dfg0.columns = ['time', 'signal']
    dfg0['ch'] = 'sensor'
    dfg1 = dfg.loc[:,['time', 'ch1z']]
    dfg1.columns = ['time', 'signal']
    dfg1['ch'] = 'cerenkov'
    dfgtp = pd.concat([dfg0, dfg1])
    fig1b = px.line(dfgtp, x='time', y='signal', color = 'ch', markers = False)
    fig1b.update_xaxes(title = 'time (s)')
    st.plotly_chart(fig1b)

t0 = st.number_input('time before beam on', min_value=0.0, max_value=df.time.round(1).max(), value = 1.00)
t1 = st.number_input('time after beam off', min_value=0.0, max_value=df.time.round(1).max(), value = last_time - 1)
t2 = st.number_input('time begining of PDD', min_value=0.0, max_value=df.time.round(1).max())
t3 = st.number_input('time end of PDD', min_value=0.0, max_value=df.time.round(1).max())
depth = st.number_input('PDD depth (mm)', min_value=0, value = 130)
pulsesthreshold = st.slider('Chose threshold for pulses', min_value = 1, max_value = 20, value = 5)
ACR = st.number_input('ACR', value = 0.947)

#calculate zeros
nzeros = df.loc[(df.time < t0) | (df.time > t1), 'ch0':].mean()
dfnzeros = df.loc[:, ['ch0', 'ch1']] - nzeros
dfnzeros.columns = ['ch0z', 'ch1z']
dfz = pd.concat([df, dfnzeros], axis=1)
#prepare to plot zeros
df0z = dfz.loc[:, ['time', 'ch0z']]
df0z.columns = ['time', 'voltage']
df0z['ch'] = 'sensor'
df1z = dfz.loc[:, ['time', 'ch1z']]
df1z.columns = ['time', 'voltage']
df1z['ch'] = 'cerenkov'
dftpz = pd.concat([df0z, df1z])
#plot zeros
fig2 = plotfigch(dftpz)
fig2.add_vline(x=t0, line_dash = 'dash', line_color = 'green', opacity = 0.5)
fig2.add_vline(x=t1, line_dash = 'dash', line_color = 'red', opacity = 0.5)
fig2.add_vrect(x0 = t2, x1 = t3, line_width = 0, fillcolor = 'red', opacity = 0.2)
if showpulses:
    st.plotly_chart(fig2)
#find pulses
maxzeros = dfz.loc[(dfz.time < t0) | (dfz.time > t1), 'ch0z'].max()
dfz['pulse'] = (dfz.ch0z > maxzeros * (1 + pulsesthreshold / 100))
#find coincide pulses
dfz['pulseafter'] = dfz.pulse.shift(-1)
dfz['pulsecoincide'] = dfz.pulse + dfz.pulseafter == 2
dfz['singlepulse'] = dfz.pulse
dfz['pulsecoincideafter'] = dfz.pulsecoincide.shift()
dfz.dropna(inplace = True)
dfz.loc[dfz.pulsecoincideafter, 'singlepulse'] = False
numberofpulses = dfz[(dfz.time > t2) & (dfz.time < t3)].pulse.sum()
numberofpulsescoincide = dfz[(dfz.time > t2) & (dfz.time < t3)].pulsecoincide.sum()
numberofsinglepulses = dfz[(dfz.time > t2) & (dfz.time < t3)].singlepulse.sum()
st.write(f'Number of pulses: {numberofpulses}')
st.write(f'Number of pulses coinciding: {numberofpulsescoincide}')
st.write(f'Number of single pulses: {numberofsinglepulses}')
#find complete dose of pulse and pulseafter
dfz['chargesensor'] = dfz.ch0z * 0.03
dfz['chargecerenkov'] = dfz.ch1z * 0.03
dfz['dose'] = dfz.chargesensor - dfz.chargecerenkov * ACR
dfz['doseafter'] = 0
dfz.loc[dfz.pulsecoincideafter, 'doseafter'] = dfz.dose
dfz['completedose'] = dfz.dose + dfz.doseafter.shift(-1)
dfz.loc[dfz.pulsecoincideafter, 'completedose'] = 0

#Only if photons PDDs
pddphotons = st.checkbox('PDD of Photons')
if pddphotons:
    dfztoplot = dfz[(dfz.time > t2) & (dfz.time < t3)]
    fig3 = plotfig(dfztoplot,  x_string = 'time', y_string = 'completedose')
    st.plotly_chart(fig3)
    mindose1 = st.number_input('PDD dose threshold (0.0xx)', value=20)
    mindose = mindose1 / 1000
    dfzpdd = dfz[((dfz.time > t2) & (dfz.time < t3)) & (dfz.completedose > mindose)]
else:
    dfzpdd = dfz[(dfz.time > t2) & (dfz.time < t3)]
    

#calculate PDD

softmaxpdd = st.slider('soft value to calculate pdd maximum', min_value=0.9, max_value =1.0, value=0.95)
dfzpdd['reldose'] = dfzpdd.completedose / (dfzpdd.completedose.max() * softmaxpdd) * 100
realvel = depth / (t3 - t2)
st.write('Speed measured: %.2f mm/s' %realvel)
dfzpdd['disttraveled'] = dfzpdd.time.diff() * realvel
dfzpdd['pos1'] = dfzpdd.disttraveled.cumsum()
dfzpdd['pos'] = depth - dfzpdd.pos1 
fig4 = go.Figure()
pddpulses = go.Scatter(
        x = dfzpdd.pos,
        y = dfzpdd.reldose,
        mode = 'markers',
        name = 'pulses',
        marker = dict(size = 2, color = 'blue', opacity = 0.5),
        )
fig4.add_trace(pddpulses)
fig4.add_vline(x=0, line_dash='dash', line_color = 'black')
fig4.add_vline(x=1, line_dash='dash', line_color = 'green', opacity = 0.5)
fig4.update_xaxes(title = 'depth (mm)')
fig4.update_yaxes(title = 'PDD')

#Soft PDD
dfzallpdd = dfz[(dfz.time > t2) & (dfz.time < t3)]
numberofsamples = len(dfzallpdd)
samplespermm = numberofsamples / depth
st.write('Number of samples per mm: %s' %int(samplespermm))
numberofpulses = dfzpdd.singlepulse.sum()
pulsespermm = numberofpulses / depth
if pddphotons:
    default_softvalue = 100
else:
    default_softvalue = 500
st.write('Number of pulses per mm: %s' %int(pulsespermm))
softvalue = st.slider('Rolling sum value', min_value = 0, value = default_softvalue, max_value = 1000)
if pddphotons:
    dfzpdd['softdose'] = dfzpdd.completedose.rolling(softvalue, center = True).mean()
else:
    dfzpdd['softdose'] = dfzpdd.completedose.rolling(softvalue, center = True).sum()
    
dfzpdd['dosepercent'] = dfzpdd.softdose / dfzpdd.softdose.max() * 100
#calculate soft dmax
softxdmax = dfzpdd.loc[dfzpdd.dosepercent > 99.95, 'pos'].median()
fig4.add_annotation(
        x = softxdmax,
        y = 100,
        text = 'dmax = %.2fmm' %softxdmax,
        showarrow = True,
        font = dict(color = 'red', size = 10)
        )
pddsoft = go.Scatter(
        x = dfzpdd.pos,
        y = dfzpdd.dosepercent,
        mode = 'lines',
        name = 'PDD soft',
        line = go.scatter.Line(color = 'red')
        )
fig4.add_trace(pddsoft)

st.plotly_chart(fig4)

showpdddata = st.checkbox('Show PDD data')
if showpdddata:
    st.dataframe(dfzpdd.loc[:,['completedose', 'reldose', 'softdose', 'dosepercent', 'pos']])
