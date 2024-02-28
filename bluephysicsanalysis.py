import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import boto3
from smart_open import open
#from glob import glob

st.title('Blue Physics Analysis')

s3 = boto3.client('s3')

response = s3.list_objects_v2(Bucket = 'bluesoftanalysiszurich')

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
st.write('List of Files')
st.dataframe(dffiles)

filenow = st.selectbox('Select File to Analyze', dffiles.file)

#Take a quick look at the raw data
@st.cache_data
def read_dataframe(file):
    path = f's3://bluesoftanalysiszurich/{file}'
    df = pd.read_csv(path, skiprows = 4)
    #df = pd.read_csv(file, skiprows = 4)
    return df

dforig = read_dataframe(filenow)
df = dforig.loc[:, ['number', 'time', 'temp', 'ch0', 'ch1']]
st.dataframe(df)

last_time = df.iloc[-1,1]
zeros = df.loc[(df.time < 1) | (df.time > last_time -1), 'ch0':].mean()
dfzeros = df.loc[:, 'ch0':] - zeros
dfzeros.columns = ['ch0z', 'ch1z']
dfz = pd.concat([df, dfzeros], axis = 1)

showpulses = st.checkbox('Show Pulses', value = False)
if showpulses:
    dfz0 = dfz.loc[:, ['time', 'ch0z']]
    dfz0.columns = ['time', 'signal']
    dfz0['ch'] = 'ch0z'
    dfz1 = dfz.loc[:, ['time', 'ch1z']]
    dfz1.columns = ['time', 'signal']
    dfz1['ch'] = 'ch1z'
    dfztp = pd.concat([dfz0, dfz1])
    fig1 = px.scatter(dfztp, x='time', y='signal', color = 'ch')
    fig1.update_traces(marker=dict(size=2))
    fig1.update_xaxes(title = 'time (s)')
    fig1.update_yaxes(title = 'Voltage (V)')
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
    fig2 = px.line(dfgtp, x='time', y='signal', color = 'ch', markers = False)
    fig2.update_xaxes(title = 'time (s)')
    st.plotly_chart(fig2)
