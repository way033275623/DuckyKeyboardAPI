# paura_lite:
# An ultra-simple command-line audio recorder with real-time
# spectrogram  visualization

import numpy as np
import pyaudio
import struct
import scipy.fftpack as scp
import termplotlib as tpl
import os
import matplotlib.pyplot as plt

# get window's dimensions
#rows, columns = os.popen('stty size', 'r').read().split()
rows = 10
columns = 10

buff_size = 0.002          # window size in seconds
wanted_num_of_bins = 40  # number of frequency bins to display

# initialize soundcard for recording:
fs = 8000
pa = pyaudio.PyAudio()

try:
    default_device_index = pa.get_default_input_device_info()
except IOError:
    default_device_index = -1

print ("Available devices:\n")
for i in range(0, pa.get_device_count()):
    info = pa.get_device_info_by_index(i)
    print (str(info["index"]) + ": \t %s \n \t %s \n" % (info["name"], pa.get_host_api_info_by_index(info["hostApi"])["name"]))
    if("What U Hear" in info["name"] and "Windows WASAPI" in pa.get_host_api_info_by_index(info["hostApi"])["name"]):
        default_device_index = info["index"]
        print("!!!!!!!!!!!!!!")
        print(default_device_index)

    #if default_device_index == -1:
    #    default_device_index = info["index"]

#Handle no devices available
if default_device_index == -1:
    print ("No device available. Quitting.")
    exit()


#Get input or default
#device_id = int(input("Choose device [" + str(default_device_index) + "]: ") or default_device_index)
#print ("")

#Get device info
device_info = pa.get_device_info_by_index(default_device_index)
#device_info = p.get_default_output_device_info()
#try:
    #device_info = p.get_device_info_by_index(device_id)
#except IOError:
    #device_info = p.get_device_info_by_index(default_device_index)
    #print ("Selection not available, using default.")

#Choose between loopback or standard mode

is_input = device_info["maxInputChannels"] > 0
is_wasapi = (pa.get_host_api_info_by_index(device_info["hostApi"])["name"]).find("WASAPI") != -1
if is_input:
    #print ("Selection is input using standard mode.")
    pass
else:
    if is_wasapi:
        useloopback = True
        #print ("Selection is output. Using loopback mode.")
    else:
        print ("Selection is input and does not support loopback mode. Quitting.\n")
        #exit()

#recordtime = int(input("Record time in seconds [" + str(recordtime) + "]: ") or recordtime)
fs = int(device_info["defaultSampleRate"])
#Open stream
print(device_info["index"])
channelcount = device_info["maxInputChannels"] if (device_info["maxOutputChannels"] < device_info["maxInputChannels"]) else device_info["maxOutputChannels"]
print(channelcount)
print(int(device_info["defaultSampleRate"]))
stream = pa.open(format = pyaudio.paInt16,
                channels = channelcount,
                rate = fs,
                input = True,
                frames_per_buffer = int(fs*buff_size),
                input_device_index = device_info["index"])
                #as_loopback = useloopback)



#stream = pa.open(format=pyaudio.paInt16, channels=1, rate=fs,
#                 input=True, frames_per_buffer=int(fs * buff_size))

while 1:  # for each recorded window (until ctr+c) is pressed
    # get current block and convert to list of short ints,
    block = stream.read(int(fs * buff_size))
    format = "%dh" % (len(block) / 2)
    shorts = struct.unpack(format, block)

    # then normalize and convert to numpy array:
    x = np.double(list(shorts)) / (2**15)
    seg_len = len(x)

    # get total energy of the current window and compute a normalization
    # factor (to be used for visualizing the maximum spectrogram value)
    energy = np.mean(x ** 2)
    max_energy = 0.02  # energy for which the bars are set to max
    max_width_from_energy = int((energy / max_energy) * int(columns)) + 1
    if max_width_from_energy > int(columns) - 10:
        max_width_from_energy = int(columns) - 10

    # get the magnitude of the FFT and the corresponding frequencies
    X = np.abs(scp.fft(x))[0:int(seg_len/2)]
    tX = np.abs(scp.fft(x))
    freqs = (np.arange(0, 1 + 1.0/len(X), 1.0 / len(X)) * fs / 2)

    # ... and resample to a fix number of frequency bins (to visualize)
    wanted_step = (int(freqs.shape[0] / wanted_num_of_bins))
    freqs2 = freqs[0::wanted_step].astype('int')
    X2 = np.mean(X.reshape(-1, wanted_step), axis=1)
    X3 = []
    for x in X2:
        X3.append(int(x))
    plt.ion()
    plt.ylim(ymax = 1)
    plt.plot(tX)
    plt.pause(0.0001)
    plt.clf()
