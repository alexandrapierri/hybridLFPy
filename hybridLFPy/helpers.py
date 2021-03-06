'''
Documentation:

This is a script containing general helper functions which can be applied
to specialized cases.
'''

import numpy as np
import os
import stat
import shutil
import glob
import copy
import scipy.signal as ss
import h5py
from mpi4py import MPI


###################################
# Initialization of MPI stuff     #
###################################
COMM = MPI.COMM_WORLD
SIZE = COMM.Get_size()
RANK = COMM.Get_rank()



#######################################
### DATA I/O                        ###
#######################################


def read_gdf(fname):
    '''
    Fast line-by-line gdf-file reader
    
    Parameters:
        ::
        
            fname : str, 
                path to gdf-file
    
    Returns:
        ::
        
            np.array([gid, val0, val1, **]), dtype=object)
    '''
    gdf_file = open(fname, 'r')
    gdf = []
    for l in gdf_file:
        data = l.split()
        gdf += [data]

    gdf = np.array(gdf, dtype=object)
    if gdf.size > 0:
        gdf[:, 0] = gdf[:, 0].astype(int)
        gdf[:, 1:] = gdf[:, 1:].astype(float)
    return np.array(gdf)


def write_gdf(gdf,fname):
    '''
    Fast line-by-line gdf-file write function
    
    Parameters:
        ::
        
            gdf : np.array, 
                column 0 is gids, columns 1: are values
            fname : 'str', 
                path to gdf-file
    
    '''
    gdf_file = open(fname,'w')
    for line in gdf:
        for i in np.arange(len(line)):
            gdf_file.write(str(line[i]) + '\t')
        gdf_file.write('\n')
    return None


def load_h5_data(path= '', data_type='LFP', y=None, electrode=None, warmup=0., scaling=1.):
    '''
    Function loading results from hdf5 file
    
    Parameters:
        ::
        
            path : str,
                path to hdf5-file
            data_type : str,
                signal type, yypes: 'CSD' , 'LFP', 'CSDsum', 'LFPsum'
            y : None or str,
                name of population
            electrode : None or int
                TODO: update, electrode is NOT USED
            warmup : float,
                lower cutoff of time series to remove possible transients
            scaling : float,
                scaling factor for population size that determines the amount of loaded single-cell signals
                
    Returns:
        ::
            
            if y is None:
                np.array([electrode id, compound signal])
            else:
                np.array([cell id, electrode, single-cell signal])
    
    
    '''
    assert y is not None or electrode is not None
    if y is not None:
        f = h5py.File(os.path.join(path, '%s_%ss.h5' %(y,data_type)))
        data = f['data'].value[:,:, warmup:]
        if scaling != 1.:
            np.random.shuffle(data)
            num_cells = int(len(data)*scaling)
            data = data[:num_cells,:, warmup:]

    else:
        f = h5py.File(os.path.join(path, '%ssum.h5' %data_type))
        data = f['data'].value[:, warmup:]

    return data


def dump_dict_of_nested_lists_to_h5(fname, data):
    '''
    Take nested list structure and dump it in hdf5 file

    Parameters:
        ::
            
            fname : str, 
                filename
            data: dict(list(array)), 
                dict of nested lists with variable len arrays

    '''
    #open file
    print 'writing to file: %s' % fname
    f = h5py.File(fname)
    #iterate over values
    for i, ivalue in data.items():
        igrp = f.create_group(str(i))
        for j, jvalue in enumerate(ivalue):
            jgrp = igrp.create_group(str(j))
            for k, kvalue in enumerate(jvalue):
                if kvalue.size > 0:
                    dset = jgrp.create_dataset(str(k), data=kvalue,
                                               compression='gzip')
                else:
                    dset = jgrp.create_dataset(str(k), data=kvalue,
                                               maxshape=(None, ),
                                               compression='gzip')
    #close file
    f.close()


def load_dict_of_nested_lists_from_h5(fname, toplevelkeys=None):
    '''
    load nested list structure from hdf5 file

    Parameters:
        ::
        
            fname: str, 
                filename
            toplevelkeys: None or iterable, 
                load a two(default) or three-layered structure

    Returns:
        ::
        
            data: dict(list(array)), nested lists with array data of variable length
    
    '''
    
    #container:
    data = {}

    #open file object
    f = h5py.File(fname, 'r')

    #iterate over partial dataset
    if toplevelkeys != None:
        for i in toplevelkeys:
            ivalue = f[str(i)]
            data[i] = []
            for j, jvalue in enumerate(ivalue.values()):
                data[int(i)].append([])
                for k, kvalue in enumerate(jvalue.values()):
                    data[i][j].append(kvalue.value)
    else:
        for i, ivalue in f.items():
            i = int(i)
            data[i] = []
            for j, jvalue in enumerate(ivalue.values()):
                data[i].append([])
                for k, kvalue in enumerate(jvalue.values()):
                    data[i][j].append(kvalue.value)

    #close dataset
    f.close()

    return data


def setup_file_dest(params, clearDestination=True):
    '''
    Function to set up the file catalog structure for simulation output
    
    Parameters:
        ::
            
            params : object, 
                e.g., cellsim16popsParams.multicompartment_params()
            clear_dest : bool, 
                savefolder will be cleared if already existing
    '''
    if COMM.Get_rank() == 0:
        if not os.path.isdir(params.savefolder):
            os.mkdir(params.savefolder)
        else:
            if clearDestination:
                print 'removing folder tree %s' % params.savefolder
                try:
                    os.system('find %s -delete' % params.savefolder)
                except:
                    shutil.rmtree(params.savefolder)
                os.mkdir(params.savefolder)
        
        if not os.path.isdir(params.sim_scripts_path):
            print 'creating %s' % params.sim_scripts_path
            os.mkdir(params.sim_scripts_path)
        
        if not os.path.isdir(params.cells_path):
            print 'creating %s' % params.cells_path
            os.mkdir(params.cells_path)
        
        if not os.path.isdir(params.figures_path):
            print 'creating %s' % params.figures_path
            os.mkdir(params.figures_path)
        if not os.path.isdir(params.populations_path):
            print 'creating %s' % params.populations_path
            os.mkdir(params.populations_path)
        
        try:
            if not os.path.isdir(params.raw_nest_output_path):
                print 'creating %s' % params.raw_nest_output_path
                os.mkdir(params.raw_nest_output_path)
        except:
            pass
        
        if not os.path.isdir(params.spike_output_path):
            print 'creating %s' % params.spike_output_path
            os.mkdir(params.spike_output_path)
    
        for f in ['cellsim16popsParams.py',
                  'cellsim16pops.py',
                  'example_brunel.py',
                  'brunel_alpha_nest.py',
                  'binzegger_connectivity_table.json', 
                  'nest_simulation.py',
                  'microcircuit.sli']:
            if os.path.isfile(f):
                if not os.path.exists(os.path.join(params.sim_scripts_path, f)):
                    shutil.copy(f, os.path.join(params.sim_scripts_path, f))
                    os.chmod(os.path.join(params.sim_scripts_path, f),
                             stat.S_IREAD)
       
    COMM.Barrier()
    

#######################################
### GENERAL                         ###
#######################################


def calculate_fft(data, tbin):
    '''
    Function to calculate the Fourier transform of data
    
    Parameters:
        ::
        
            data : np.array,
                1D or 2D array containing time series
            tbin : float,
                bin size of time series (in ms)
    
    Returns:
        ::
        
            freqs : np.array,
                frequency axis of signal in Fourier space           
            fft : np.array,
                signal in Fourier space
    '''
    if len(np.shape(data)) > 1:
        n = len(data[0])
        return np.fft.fftfreq(n, tbin * 1e-3), np.fft.fft(data, axis=1)
    else:
        n = len(data)
        return np.fft.fftfreq(n, tbin * 1e-3), np.fft.fft(data)


#######################################
### DATA MANIPULATION               ###
#######################################

def centralize(data, time=False, units=False):
    '''
    Function to subtract the mean across time and/or across units from data
    
    Parameters:
        ::
        
            data : np.array,
                1D or 2D array containing time series, 1st index: unit, 2nd index: time
            time : bool,
                True: subtract mean across time
            units : bool,
                True: subtract mean across units
            
    Returns:
        ::
        
            res : np.array,
                1D or 0D array of centralized signal
    '''
    assert(time is not False or units is not False)
    res = copy.copy(data)
    if time is True:
        res = np.array([x - np.mean(x) for x in res])
    if units is True:
        res = np.array(res - np.mean(res, axis=0))
    return res


def normalize(data):
    '''
    Function to normalize data to have mean 0 and unity standard deviation
    (also called z-transform)
    
    Parameters:
        ::
        
            data : np.array, 
    '''
    data = data.astype(float)
    data -= data.mean()
    return data / data.std()


#######################################
### FILTER                          ###
#######################################

def movav(y, Dx, dx):
    '''
    Moving average rectangular window filter:
    calculate average of signal y by using sliding rectangular
    window of size Dx using binsize dx
    
    Parameters:
        ::
        
            y : np.array,
                signal
            Dx : float,
                window length of filter
            dx : float,
                bin size of signal sampling
                
    Returns:
        ::
        
            yf : np.array,
                 filtered signal
    '''
    if Dx <= dx:
        return y
    else:
        ly = len(y)
        r = np.zeros(ly)
        n = np.int(np.round((Dx / dx)))
        r[0:np.int(n / 2.)] = 1.0 / n
        r[-np.int(n / 2.)::] = 1.0 / n
        R = np.fft.fft(r)
        Y = np.fft.fft(y)
        yf = np.fft.ifft(Y * R)
        return yf


def decimate(x, q=10, n=4, k=0.8, axis=-1, filterfun=ss.cheby1):
    '''
    scipy.signal.decimate like downsampling using filtfilt instead of lfilter,
    and filter coeffs from butterworth or chebyshev type 1.

    Parameters:
        ::
            
            x : np.ndarray, 
                array to be downsampled along last axis
            q : int, 
                downsampling factor
            n : int, 
                butterworth filter order
            k : float,
                aliasing filter critical frequency will be set as Wn=k/q
              
    Returns:
        ::
        
            y : np.ndarray,
                array of downsampled signal         
              
    '''
    if not isinstance(q, int):
        raise TypeError("q must be an integer")

    if n is None:
        n = 1

    if filterfun == ss.butter:
        b, a = filterfun(n, k / q)
    elif filterfun == ss.cheby1:
        b, a = filterfun(n, 0.05, k / q)
    else:
        raise Exception, 'only ss.butter or ss.cheby1 supported'

    try:
        y = ss.filtfilt(b, a, x)
    except: # multidim array can only be processed at once for scipy version largen than 0.9.0
        y = []
        for data in x:
            y.append(ss.filtfilt(b,a,data))
        y = np.array(y)

    try:
        return y[:, ::q]
    except:
        return y[::q]


#######################################
### CORRELATION ANALYSIS            ###
#######################################


def mean(data, units=False, time=False):
    '''
    Function to compute mean of data

    Parameters:
        ::   

            data: numpy.ndarray, 
                1st axis unit, 2nd axis time
            units: bool, 
                average over units
            time: bool, 
                average over time

    Returns:
        ::
    
            if units=False and time=False: 
                error
            if units=True: 
                1 dim numpy.ndarray; time series
            if time=True: 
                1 dim numpy.ndarray; series of unit means across time
            if units=True and time=True: 
                float; unit and time mean

    Examples:
        ::
            
            >>> mean(np.array([[1,2,3],[4,5,6]]),units=True)
            Out[1]: np.array([2.5,3.5,4.5])

            >>> mean(np.array([[1,2,3],[4,5,6]]),time=True)
            Out[1]: np.array([2.,5.])

            >>> mean(np.array([[1,2,3],[4,5,6]]),units=True,time=True)
            Out[1]: 3.5

    '''

    assert(units is not False or time is not False)
    if units is True and time is False:
        return np.mean(data, axis=0)
    elif units is False and time is True:
        return np.mean(data, axis=1)
    elif units is True and time is True:
        return np.mean(data)


def compound_mean(data):
    '''
    Compute the mean of the compound/sum signal.
    Data is first summed across units and averaged across time.

    Parameters:
        ::   

            data: numpy.ndarray,
                1st axis unit, 2nd axis time

    Returns:
        ::
        
            float,
                time-averaged compound/sum signal

    Examples:
        ::
            
            >>> compound_mean(np.array([[1,2,3],[4,5,6]]))
            Out[1]: 7.0

    '''

    return np.mean(np.sum(data, axis=0))


def variance(data, units=False, time=False):
    '''
    Compute the variance of data across time, units or both.

    Parameters:
        ::
            
            data: numpy.ndarray, 
                1st axis unit, 2nd axis time
            units: bool, 
                variance across units
            time: bool, 
                average over time

    Returns:
        ::
        
            if units=False and time=False: 
                error,
            if units=True: 
                1 dim numpy.ndarray; time series,       
            if time=True:  
                1 dim numpy.ndarray; series of single unit variances across time,
            if units=True and time=True: 
                float; mean of single unit variances across time

    Examples:
        ::
            
            >>> variance(np.array([[1,2,3],[4,5,6]]),units=True)
            Out[1]: np.array([ 2.25,  2.25,  2.25])
            >>> variance(np.array([[1,2,3],[4,5,6]]),time=True)
            Out[1]: np.array([ 0.66666667,  0.66666667])
            >>> variance(np.array([[1,2,3],[4,5,6]]),units=True,time=True)
            Out[1]: 0.66666666666666663

    '''

    assert(units is not False or time is not False)
    if units is True and time is False:
        return np.var(data, axis=0)
    elif units is False and time is True:
        return np.var(data, axis=1)
    elif units is True and time is True:
        return np.mean(np.var(data, axis=1))


def compound_variance(data):
    '''
    Compute the variance of the compound/sum signal.
    data is first summed across units, then the variance across time is calculated.
    
    Parameters:
        ::
            
            data: numpy.ndarray, 
                1st axis unit, 2nd axis time
  
    Returns:
        ::
            
            float; variance across time of compound/sum signal

    Examples:
        ::
        
            >>> compound_variance(np.array([[1,2,3],[4,5,6]]))
            Out[1]: 2.6666666666666665

    '''

    return np.var(np.sum(data, axis=0))


def powerspec(data, tbin, Df=None, units=False, pointProcess=False):
    '''
    Calculate (smoothed) power spectra of all timeseries in data.
    If units=True, power spectra are averaged across units.
    Note that averaging is done on power spectra rather than data.

    If pointProcess=True, power spectra are normalized by the length T of the time series.
 
    Parameters:
        ::
       
            data: numpy.ndarray, 
                1st axis unit, 2nd axis time
            tbin: float, 
                binsize in ms
            Df: float/None, 
                window width of sliding rectangular filter (smoothing), None -> no smoothing
            units: bool, 
                average power spectrum
            pointProcess: bool, 
                if set to True, powerspectrum is normalized to signal length T

    Returns:
        ::
          
            (freq, POW): tuple
            freq: numpy.ndarray, 
                frequencies
            POW: 
                if units=False: 
                    2 dim numpy.ndarray; 1st axis unit, 2nd axis frequency
                if units=True:  
                    1 dim numpy.ndarray; frequency series

    Examples:
        ::
            
            >>> powerspec(np.array([analog_sig1,analog_sig2]),tbin, Df=Df)
            Out[1]: (freq,POW)
            >>> POW.shape
            Out[2]: (2,len(analog_sig1))

            >>> powerspec(np.array([analog_sig1,analog_sig2]),tbin, Df=Df, units=True)
            Out[1]: (freq,POW)
            >>> POW.shape
            Out[2]: (len(analog_sig1),)

    '''

    freq, DATA = calculate_fft(data, tbin)
    df = freq[1] - freq[0]
    T = tbin * len(freq)
    POW = np.abs(DATA) ** 2
    if Df is not None:
        POW = [movav(x, Df, df) for x in POW]
        cut = int(Df / df)
        freq = freq[cut:]
        POW = np.array([x[cut:] for x in POW])
        POW = np.abs(POW)
    assert(len(freq) == len(POW[0]))
    if units is True:
        POW = mean(POW, units=units)
        assert(len(freq) == len(POW))
    if pointProcess:
        POW *= 1. / T * 1e3  # normalization, power independent of T
    return freq, POW


def compound_powerspec(data, tbin, Df=None, pointProcess=False):
    '''
    Calculate the power spectrum of the compound/sum signal.
    data is first summed across units, then the power spectrum is calculated.

    If pointProcess=True, power spectra are normalized by the length T of the time series.

    
    Parameters:
        ::
       
            data: numpy.ndarray, 
                1st axis unit, 2nd axis time
            tbin: float, 
                binsize in ms
            Df: float/None, 
                window width of sliding rectangular filter (smoothing), None -> no smoothing
            units: bool, 
                average power spectrum
            pointProcess: bool, 
                if set to True, powerspectrum is normalized to signal length T
                
                

    Returns:
        ::
          
            (freq, POW): tuple
            freq: numpy.ndarray, 
                frequencies
            POW: 
                1 dim numpy.ndarray; frequency series


    Examples:
        ::
        
            >>> compound_powerspec(np.array([analog_sig1,analog_sig2]),tbin, Df=Df)
            Out[1]: (freq,POW)
            >>> POW.shape
            Out[2]: (len(analog_sig1),)

    '''

    return powerspec([np.sum(data, axis=0)], tbin, Df=Df, units=True, pointProcess=pointProcess)


def crossspec(data, tbin, Df=None, units=False, pointProcess=False):
    '''
    Calculate (smoothed) cross spectra of data.
    If units=True, cross spectra are averaged across units.
    Note that averaging is done on cross spectra rather than data.

    Cross spectra are normalized by the length T of the time series -> no scaling with T.

    If pointProcess=True, power spectra are normalized by the length T of the time series.
     
    Parameters:
        ::
       
            data: numpy.ndarray, 
                1st axis unit, 2nd axis time
            tbin: float, 
                binsize in ms
            Df: float/None, 
                window width of sliding rectangular filter (smoothing), None -> no smoothing
            units: bool, 
                average cross spectrum
            pointProcess: bool, 
                if set to True, crossspectrum is normalized to signal length T
                
    
    Returns:
        ::
        
            (freq, CRO): tuple
            freq: numpy.ndarray,
                frequencies
            CRO: 
                if units=True:  
                    1 dim numpy.ndarray; frequency series
                if units=False: 
                    3 dim numpy.ndarray; 1st axis first unit, 2nd axis second unit, 3rd axis frequency

    Examples:
        ::
        
            >>> crossspec(np.array([analog_sig1,analog_sig2]),tbin, Df=Df)
            Out[1]: (freq,CRO)
            >>> CRO.shape
            Out[2]: (2,2,len(analog_sig1))

            >>> crossspec(np.array([analog_sig1,analog_sig2]),tbin, Df=Df, units=True)
            Out[1]: (freq,CRO)
            >>> CRO.shape
            Out[2]: (len(analog_sig1),)

    '''

    N = len(data)
    if units is True:
        # smoothing and normalization take place in powerspec
        # and compound_powerspec
        freq, POW = powerspec(data, tbin, Df=Df, units=True)
        freq_com, CPOW = compound_powerspec(data, tbin, Df=Df)
        assert(len(freq) == len(freq_com))
        assert(np.min(freq) == np.min(freq_com))
        assert(np.max(freq) == np.max(freq_com))
        CRO = 1. / (1. * N * (N - 1.)) * (CPOW - 1. * N * POW)
        assert(len(freq) == len(CRO))
    else:
        freq, DATA = calculate_fft(data, tbin)
        T = tbin * len(freq)
        df = freq[1] - freq[0]
        if Df is not None:
            cut = int(Df / df)
            freq = freq[cut:]
        CRO = np.zeros((N, N, len(freq)), dtype=complex)
        for i in xrange(N):
            for j in xrange(i + 1):
                tempij = DATA[i] * DATA[j].conj()
                if Df is not None:
                    tempij = movav(tempij, Df, df)[cut:]
                CRO[i, j] = tempij
                CRO[j, i] = CRO[i, j].conj()
        assert(len(freq) == len(CRO[0, 0]))
        if pointProcess:
            CRO *= 1. / T * 1e3  # normalization
    return freq, CRO


def compound_crossspec(a_data, tbin, Df=None, pointProcess=False):
    '''
    Calculate cross spectra of compound signals.
    a_data is a list of datasets (a_data = [data1,data2,...]).
    For each dataset in a_data, the compound signal is calculated
    and the crossspectra between these compound signals is computed.
    
    If pointProcess=True, power spectra are normalized by the length T of the time series.
     
    Parameters:
        ::
       
            a_data: list of numpy.ndarrays; 
                array: 1st axis unit, 2nd axis time     
            tbin: float, 
                binsize in ms
            Df: float/None, 
                window width of sliding rectangular filter (smoothing), None -> no smoothing
            pointProcess: bool, 
                if set to True, crossspectrum is normalized to signal length T
                
    
    Returns:
        ::
        
            (freq, CRO): tuple
            freq: numpy.ndarray,
                frequencies
            CRO: 
                3 dim numpy.ndarray; 1st axis first compound signal, 2nd axis second compound signal, 3rd axis frequency

    Examples:
        ::
        
            >>> compound_crossspec([np.array([analog_sig1,analog_sig2]),np.array([analog_sig3,analog_sig4])],tbin, Df=Df)
            Out[1]: (freq,CRO)
            >>> CRO.shape
            Out[2]: (2,2,len(analog_sig1))


    '''

    a_mdata = []
    for data in a_data:
        a_mdata.append(np.sum(data, axis=0))  # calculate compound signals
    return crossspec(np.array(a_mdata), tbin, Df, units=False, pointProcess=pointProcess)


def autocorrfunc(freq, power):
    '''
    Calculate autocorrelation function(s) for given power spectrum/spectra.

    Parameters:
        ::
        
            freq: 1 dim numpy.ndarray; 
                frequencies
            power: 2 dim numpy.ndarray; 
                power spectra, 1st axis units, 2nd axis frequencies

    Returns:
        ::
        
            (time,autof): tuple
            time: 1 dim numpy.ndarray; 
                times
            autof: 2 dim numpy.ndarray; 
                autocorrelation functions, 1st axis units, 2nd axis times


    '''
    tbin = 1. / (2. * np.max(freq)) * 1e3  # tbin in ms
    time = np.arange(-len(freq) / 2. + 1, len(freq) / 2. + 1) * tbin
    # T = max(time)
    multidata = False
    if len(np.shape(power)) > 1:
        multidata = True
    if multidata:
        N = len(power)
        autof = np.zeros((N, len(freq)))
        for i in xrange(N):
            raw_autof = np.real(np.fft.ifft(power[i]))
            mid = int(len(raw_autof) / 2.)
            autof[i] = np.hstack([raw_autof[mid + 1:], raw_autof[:mid + 1]])
        assert(len(time) == len(autof[0]))
    else:
        raw_autof = np.real(np.fft.ifft(power))
        mid = int(len(raw_autof) / 2.)
        autof = np.hstack([raw_autof[mid + 1:], raw_autof[:mid + 1]])
        assert(len(time) == len(autof))
    # autof *= T*1e-3 # normalization is done in powerspec()
    return time, autof


def crosscorrfunc(freq, cross):
    '''
    Calculate crosscorrelation function(s) for given cross spectra.

    Parameters:
        ::
        
            freq: 1 dim numpy.ndarray,
                frequencies
            cross: 3 dim numpy.ndarray, 
                cross spectra, 1st axis units, 2nd axis units, 3rd axis frequencies

    Returns:
        ::
        
            (time,crossf): tuple
            time: 1 dim numpy.ndarray, 
                times
            crossf: 3 dim numpy.ndarray, 
                crosscorrelation functions, 1st axis first unit, 2nd axis second unit, 3rd axis times


    '''

    tbin = 1. / (2. * np.max(freq)) * 1e3  # tbin in ms
    time = np.arange(-len(freq) / 2. + 1, len(freq) / 2. + 1) * tbin
    # T = max(time)
    multidata = False
    # check whether cross contains many cross spectra
    if len(np.shape(cross)) > 1:
        multidata = True
    if multidata:
        N = len(cross)
        crossf = np.zeros((N, N, len(freq)))
        for i in xrange(N):
            for j in range(N):
                raw_crossf = np.real(np.fft.ifft(cross[i, j]))
                mid = int(len(raw_crossf) / 2.)
                crossf[i, j] = np.hstack(
                    [raw_crossf[mid + 1:], raw_crossf[:mid + 1]])
        assert(len(time) == len(crossf[0, 0]))
    else:
        raw_crossf = np.real(np.fft.ifft(cross))
        mid = int(len(raw_crossf) / 2.)
        crossf = np.hstack([raw_crossf[mid + 1:], raw_crossf[:mid + 1]])
        assert(len(time) == len(crossf))
    # crossf *= T*1e-3 # normalization happens in cross spectrum
    return time, crossf


def corrcoef(time, crossf, integration_window=0.):
    '''
    Calculate the correlation coefficient for given auto- and crosscorrelation functions.
    Standard settings yield the zero lag correlation coefficient.
    Setting integration_window > 0 yields the correlation coefficient of integrated auto- and crosscorrelation functions.
    The correlation coefficient between a zero signal with any other signal is defined as 0.

    Parameters:
        ::
        
            time: 1 dim numpy.ndarray, 
                times corresponding to signal
            crossf: 3 dim numpy.ndarray, 
                crosscorrelation functions, 1st axis first unit, 2nd axis second unit, 3rd axis times
            integration_window: float
                size of the integration window

    Returns:
        ::
        
            cc: 2 dim numpy.ndarray,
                correlation coefficient between two units


    '''

    N = len(crossf)
    cc = np.zeros(np.shape(crossf)[:-1])
    tbin = abs(time[1] - time[0])
    lim = int(integration_window / tbin)
    if len(time)%2 == 0:
        mid = len(time)/2-1
    else:
        mid = np.floor(len(time)/2.)
    for i in xrange(N):
        ai = np.sum(crossf[i, i][mid - lim:mid + lim + 1])
        offset_autoi = np.mean(crossf[i,i][:mid-1])
        for j in xrange(N):
            cij = np.sum(crossf[i, j][mid - lim:mid + lim + 1])
            offset_cross = np.mean(crossf[i,j][:mid-1])
            aj = np.sum(crossf[j, j][mid - lim:mid + lim + 1])
            offset_autoj = np.mean(crossf[j,j][:mid-1])
            if ai > 0. and aj > 0.:
                cc[i, j] = (cij-offset_cross) / np.sqrt((ai-offset_autoi) * (aj-offset_autoj))
            else:
                cc[i, j] = 0.
    return cc


def coherence(freq, power, cross):
    '''
    Calculate frequency resolved coherence for given power- and crossspectra.

    Parameters:
        ::

            freq: 1 dim numpy.ndarray, 
                frequencies
            power: 2 dim numpy.ndarray, 
                power spectra, 1st axis units, 2nd axis frequencies
            cross: 3 dim numpy.ndarray, 
                cross spectra, 1st axis units, 2nd axis units, 3rd axis frequencies

    Returns:
        ::
            
            (freq,coh): tuple
            freq: 1 dim numpy.ndarray, 
                frequencies
            coh: 3 dim numpy.ndarray, 
                coherences, 1st axis units, 2nd axis units, 3rd axis frequencies


    '''

    N = len(power)
    coh = np.zeros(np.shape(cross))
    for i in xrange(N):
        for j in xrange(N):
            coh[i, j] = cross[i, j] / np.sqrt(power[i] * power[j])
    assert(len(freq) == len(coh[0, 0]))
    return freq, coh


def cv(data, units=False):
    '''
    Calculate coefficient of variation for data. Mean and standard deviation are computed across time.


    Parameters:
        ::

            data: numpy.ndarray, 
                1st axis unit, 2nd axis time
            units: bool, 
                average CV

    Returns:
        ::
        
            if units=False: 
                  numpy.ndarray; series of unit CVs
            if units=True: 
                  float; mean CV across units

    Examples:
            
            >>> cv(np.array([[1,2,3,4,5,6],[11,2,3,3,4,5]]))
            Out[1]: np.array([ 0.48795004,  0.63887656])

            >>> cv(np.array([[1,2,3,4,5,6],[11,2,3,3,4,5]]),units=True)
            Out[1]: 0.56341330073710316

    '''

    mu = mean(data, time=True)
    var = variance(data, time=True)
    cv = np.sqrt(var) / mu
    if units is True:
        return np.mean(cv)
    else:
        return cv


def fano(data, units=False):
    '''
    Calculate fano factor for data. Mean and variance are computed across time.


    Parameters:
        ::
            
            data: numpy.ndarray, 
                1st axis unit, 2nd axis time
            units: bool, 
                average FF

    Returns:
        ::
         
            if units=False: 
                numpy.ndarray; series of unit FFs
            if units=True: 
                float; mean FF across units

    Examples:
        ::
            
            >>> fano(np.array([[1,2,3,4,5,6],[11,2,3,3,4,5]]))
            Out[1]: np.array([0.83333333, 1.9047619])

            >>> fano(np.array([[1,2,3,4,5,6],[11,2,3,3,4,5]]),units=True)
            Out[1]: 1.3690476190476191

    '''

    mu = mean(data, time=True)
    var = variance(data, time=True)
    ff = var / mu
    if units is True:
        return np.mean(ff)
    else:
        return ff


    

