import streamlit as st
import numpy as np
import pandas as pd

st.title('Small Field Dosimetry Size and Center')
aplus = st.number_input('A+ (mm)', min_value = -300.00, max_value = 300.00, value = 0.00)
aminus = st.number_input('A- (mm)', min_value = -300.00, max_value = 300.00, value = 0.00)
cplus = st.number_input('C+ (mm)', min_value = -300.00, max_value = 300.00, value = 0.00)
cminus = st.number_input('C- (mm)', min_value = -300.00, max_value = 300.00, value = 0.00)
centera = (aplus + aminus)/2
st.write('Center in A is: %.2f mm' %centera)
centerc = (cplus + cminus)/2
st.write('Center in C is: %.2f mm' %centerc)
fieldsizea = aplus - aminus
st.write('Field Size in A is: %.2f mm' %fieldsizea)
fieldsizec = cplus - cminus
st.write('Field Size in C is: %.2f mm' %fieldsizec)
sclinsquare = np.sqrt(fieldsizea * fieldsizec)
st.write('Sclin square is: %.2f mm' %sclinsquare)
sclincircle = np.sqrt(np.pi)*(fieldsizea + fieldsizec)/4
st.write('Sclin circle is: %.2f mm' %sclincircle)

mybutton = st.button('Add to table')

if 'data' not in st.session_state:
    data = pd.DataFrame({'A+':[], 'A-':[], 'C+':[], 'C-':[]})
    st.session_state.data = data

st.session_state.data['Center_A'] = (st.session_state.data['A+'] + st.session_state.data['A-'])/2
st.session_state.data['Center_C'] = (st.session_state.data['C+'] + st.session_state.data['C-'])/2
st.session_state.data['Size_A'] = (st.session_state.data['A+'] - st.session_state.data['A-'])
st.session_state.data['Size_C'] = (st.session_state.data['C+'] - st.session_state.data['C-'])
st.session_state.data['Sclinsquare'] = np.sqrt(st.session_state.data['Size_A'] * st.session_state.data['Size_C'])
st.session_state.data['Sclincircle'] = np.sqrt(np.pi)*(st.session_state.data['Size_A'] + st.session_state.data['Size_C'])/4
        
st.dataframe(st.session_state.data)

if mybutton:
    row = pd.DataFrame({'A+':[aplus], 'A-':[aminus], 'C+':[cplus], 'C-':[cminus]})
    st.session_state.data = pd.concat([st.session_state.data, row])

deletebutton = st.button('Delete table')

if deletebutton:
    data = pd.DataFrame({'A+':[], 'A-':[], 'C+':[], 'C-':[]})
    st.session_state.data = data
    

