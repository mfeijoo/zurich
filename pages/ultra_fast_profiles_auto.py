import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import boto3
#from glob import glob
from smart_open import open
from scipy.signal import argrelextrema

st.title('Ultra Fast Profiles Automatic Analysis')

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

df0 = dfz.loc[:,['time', 'ch0z']]
df0.columns = ['time', 'voltage']
df0['ch'] = 'sensor'
df1 = dfz.loc[:, ['time', 'ch1z']]
df1.columns = ['time', 'voltage']
df1['ch'] = 'cerenkov'
dftp = pd.concat([df0, df1])

@st.cache_data
def plotfigch(df, x_string = 'time', y_string = 'voltage'):
    fig = px.scatter(df, x= x_string, y = y_string, color='ch')
    fig.update_trace(marker = dict(size = 2))
    fig.update_xaxes(title = 'time (s)')
    return fig

@st.cache_data
def plotfig(df, x_string = 'time', y_string = 'voltage'):
    fig = px.scatter(df, x= x_string, y = y_string)
    fig.update_traces (marker = dict(size = 2, color = 'blue', opacity = 0.5))
    fig.update_xaxes(title = 'time (s)')
    return fig

#fig1 = plotfigch(dftp)

#st.plotly_chart(fig1)
dfz['chunk'] = dfz.number // int(300000/750)
dfg = dfz.groupby('chunk').agg({'time':np.median, 'ch0z':np.sum, 'ch1z':np.sum})

#Calculate local maximuns
ordernow = st.number_input('select order to find max of profiles', min_value = 1, max_value = 100, value = 8)
maximuns = argrelextrema(dfg.ch0z.to_numpy(), np.greater, order = ordernow)
maximuns_times = dfg.iloc[maximuns[0][2:-2], 0].to_list()

dfg0 = dfg.loc[:,['time', 'ch0z']]
dfg0.columns = ['time', 'signal']
dfg0['ch'] = 'sensor'
dfg1 = dfg.loc[:,['time', 'ch1z']]
dfg1.columns = ['time', 'signal']
dfg1['ch'] = 'cerenkov'
dfgtp = pd.concat([dfg0, dfg1])
fig1b = px.line(dfgtp, x='time', y='signal', color = 'ch', markers = False)
fig1b.update_xaxes(title = 'time (s)')
add_maxtimes_str = st.text_input('Add profile maximum times (separated by commas)', value = '')
if add_maxtimes_str != '':
    add_maxtimes_lst = add_maxtimes_str.split(',')
    add_maxtimes_float = [float(i) for i in add_maxtimes_lst]
    maximun_times_all = maximuns_times + add_maxtimes_float
else:
    maximun_times_all = maximuns_times
maximun_times_all.sort()
for t in maximun_times_all:
    fig1b.add_vline(x = t, line_dash = 'dash', line_color = 'green')
st.plotly_chart(fig1b)


t0 = st.number_input('time before beam on', min_value=0.0, max_value=df.time.round(1).max(), value = 1.00)
t1 = st.number_input('time after beam off', min_value=0.0, max_value=df.time.round(1).max(), value = last_time - 1)
nominal_speed = st.number_input('Nominal Speed (mm/s)', min_value = 0, value = 10)
nominal_fieldsize = st.number_input('Nominal Field Size (mm)', value = 10)
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
numberofpulses = dfz[(dfz.time > t0) & (dfz.time < t1)].pulse.sum()
numberofpulsescoincide = dfz[(dfz.time > t0) & (dfz.time < t1)].pulsecoincide.sum()
numberofsinglepulses = dfz[(dfz.time > t0) & (dfz.time < t1)].singlepulse.sum()
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

#Calculate profiles
espace = nominal_fieldsize * 1.3
toffset = espace / nominal_speed
profilefigs = []
dfzprofiles = []
profiletimes = []
list_of_field_sizes = []
list_of_field_sizes_soft = []
profilespeed = st.number_input('estimated motor speed', min_value = 3.00, max_value = 30.00, value = 7.70)
softmaxprofile = st.slider('soft value to calculate pdd maximum', min_value=0.9, max_value =1.0, value=0.90)
profilesoft = st.slider('Soft value for profile', min_value =0, max_value =1000, value = 500)
for tnow in maximun_times_all:
    t4 = tnow  - toffset
    t5 = tnow  + toffset
    dfzprofile = dfz.loc[(dfz.time > t4) & (dfz.time < t5)]
    #fig6 = plotfig(dfzprofile, x_string = 'time', y_string = 'completedose')
    #st.plotly_chart(fig6)
    dfzprofile['disttraveled'] = dfzprofile.time.diff() * profilespeed
    dfzprofile['pos1'] = dfzprofile.disttraveled.cumsum()
    maxnow = dfzprofile.completedose.max() * softmaxprofile

    centerprofile = dfzprofile.loc[dfzprofile.completedose >= maxnow, 'pos1'].median()
    avmaxdose = dfzprofile.loc[dfzprofile.completedose >= maxnow, 'completedose'].mean()
    dfzprofile['reldose'] = dfzprofile.completedose / avmaxdose * 100
    dfzprofile['pos2'] = dfzprofile.pos1 - centerprofile
    #find better center using FHWM
    newedge1 = dfzprofile.loc[(dfzprofile.pos2 < 0) & (dfzprofile.reldose < 50), 'pos2'].max()
    newedge2 = dfzprofile.loc[(dfzprofile.pos2 > 0) & (dfzprofile.reldose < 50), 'pos2'].min()
    newcenter = (newedge2 - newedge1) / 2
    #move to the new center
    dfzprofile['pos'] = dfzprofile.pos2 - newcenter
    #plot the profile
    fig7 = go.Figure()
    fig7.add_trace(
            go.Scatter(
                x = dfzprofile.pos,
                y = dfzprofile.reldose,
                name = 'pulses',
                mode = 'markers',
                marker = dict(size = 2, color = 'blue', opacity = 0.5),
                )
            )

    #profilemindose1 = st.number_input('Profile dose threshold (0.00xx)', value = 60)
    #profilemindose = profilemindose1 / 10000
    #dfzgp = dfzprofile[dfzprofile.completedose > profilemindose]
    dfzgp = dfzprofile
    dfzgp['dosesoft'] = dfzgp.completedose.rolling(profilesoft, center = True).sum()
    dfzgp['dosepercent'] = dfzgp.dosesoft / dfzgp.dosesoft.max() * 100
    fig7.add_trace(
            go.Scatter(
                x=dfzgp.pos,
                y=dfzgp.dosepercent,
                mode = "lines",
                line = go.scatter.Line(color = 'red'),
                name = 'soft profile',
                showlegend=True)
            )
                
    fig7.add_vline(x = 0, line_color = 'black', line_dash = 'dash')
    # Calculate field size
    edge1 = dfzprofile.loc[(dfzprofile.pos > 0) & (dfzprofile.reldose > 50), 'pos'].max()
    fig7.add_vline(x = edge1, line_color = 'green', line_dash = 'dash')
    edge2 = dfzprofile.loc[(dfzprofile.pos < 0) & (dfzprofile.reldose > 50), 'pos'].min()
    fig7.add_vline(x = edge2, line_color = 'green', line_dash = 'dash')
    fieldsize = edge1 - edge2
    fig7.add_annotation(
            x = -1,
            y = 50,
            text = 'Size: %.2f mm' %fieldsize,
            font = dict(size = 11, color = 'blue'),
            showarrow = False
            )

    list_of_field_sizes.append(fieldsize.round(2))
    #calculate field size soft
    edge1soft = dfzprofile.loc[(dfzprofile.pos > 0) & (dfzprofile.dosepercent > 50), 'pos'].max()
    edge2soft = dfzprofile.loc[(dfzprofile.pos < 0) & (dfzprofile.dosepercent > 50), 'pos'].min()
    fieldsizesoft = edge1soft - edge2soft
    fig7.add_annotation(
            x = -1,
            y = 40,
            text = 'Size-soft: %.2f mm' %fieldsizesoft,
            font = dict(size = 11, color = 'red'),
            showarrow = False
            )

    list_of_field_sizes_soft.append(fieldsizesoft)
    #calculate penumbra
    penumbraright1 = dfzprofile.loc[(dfzprofile.pos > 0) & (dfzprofile.reldose > 80), 'pos'].max()
    penumbraright2 = dfzprofile.loc[(dfzprofile.pos > 0) & (dfzprofile.reldose > 20), 'pos'].max()
    penumbraleft1 = dfzprofile.loc[(dfzprofile.pos < 0) & (dfzprofile.reldose > 80), 'pos'].min()
    penumbraleft2 = dfzprofile.loc[(dfzprofile.pos < 0) & (dfzprofile.reldose > 20), 'pos'].min()
    fig7.add_vrect(x0 = penumbraright1, x1 = penumbraright2, line_width = 0, fillcolor = 'orange', opacity = 0.5)
    fig7.add_vrect(x0 = penumbraleft2, x1 = penumbraleft1, line_width = 0, fillcolor = 'orange', opacity = 0.5)

    penumbraright = penumbraright2 - penumbraright1
    penumbraleft = penumbraleft1 - penumbraleft2

    fig7.add_annotation(
            x = penumbraright2 + 5,
            y = 50,
            text = 'P.: %.2f mm' %penumbraright,
            font = dict(size = 11, color = 'green'),
            showarrow = False)
    fig7.add_annotation(
            x = penumbraleft2 - 5,
            y = 50,
            text = 'P.: %.2f mm' %penumbraleft,
            font = dict(size = 11, color = 'magenta'),
            showarrow = False)


    fig7.update_xaxes(title = 'pos. (mm)')
    fig7.update_yaxes(title = 'relative dose')
    profilefigs.append(fig7)
    dfzprofiles.append(dfzprofile)
    profiletimes.append(tnow)

showprofiledata = st.checkbox('Show Profiles Data')
for tnow, fignow, df in zip(profiletimes, profilefigs, dfzprofiles):
    st.write('time profile: %.2f' %tnow)
    st.plotly_chart(fignow)
    if showprofiledata:
        st.dataframe(df.loc[:,['pos', 'reldose', 'dosesoft', 'dosepercent']])
    
st.write('List of Field Sizes')
dffieldsize = pd.DataFrame({'Field Size pulses':list_of_field_sizes, 'Field Size soft':list_of_field_sizes_soft})
st.dataframe(dffieldsize)
