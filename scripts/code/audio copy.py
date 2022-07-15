import pyaudio
import audioop
import os
import numpy as np
import win32pipe
import win32file
import time
import keyboard
import struct
import matplotlib.pyplot as plt
import wave
import win32api
from scipy.fftpack import fft
import sys
import subprocess

cmd = ".\\hidtest.exe"
process = subprocess.Popen(cmd, stdout=subprocess.PIPE, creationflags=0x08000000)

sys.setrecursionlimit(9000000)

# https://github.com/intxcc/pyaudio_portaudio/blob/master/example/echo_python3.py
# https://www.swharden.com/wp/2016-07-19-realtime-audio-visualization-in-python/
# https://stackoverflow.com/questions/35970282/what-are-chunks-samples-and-frames-when-using-pyaudio

np.set_printoptions(suppress=True) # don't use scientific notation
defaultframes = 1024

class Color:
    def __init__(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b
        
    def sanitize(self):
        self.r = min(self.r, 255)
        self.r = max(self.r, 0)
        self.g = min(self.g, 255)
        self.g = max(self.g, 0)
        self.b = min(self.b, 255)
        self.b = max(self.b, 0)
    
    def isZero(self):
        if(self.r == 0 and self.g == 0 and self.b == 0):
            return True
        return False
        
    def zeroOut(self):
        self.setColorValues(0, 0, 0)
        
    def setColor(self, color):
        self.setColorValues(color.r, color.g, color.b)
        
    def setColorValues(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b
        
    def scale(self, scaleValue):
        self.r = int(round(self.r * scaleValue))
        self.g = int(round(self.g * scaleValue))
        self.b = int(round(self.b * scaleValue))
        self.sanitize()
        
    def loopColorBySteps(self, steps):
        colors = [self.r, self.g, self.b]
        maxedCount = 0
        for i in range(0, 3):
            if(colors[i] == 255):
                previous = i - 1
                if(previous == -1):
                    previous = 2
                next = i + 1
                if(next == 3):
                    next = 0
                
                if(colors[previous] > 0):
                    #reduce previous
                    left = steps - colors[previous]
                    if(left <= 0):
                        colors[previous] -= steps
                        
                        self.r = colors[0]
                        self.g = colors[1]
                        self.b = colors[2]
                    else:
                        colors[previous] = 0
                        
                        self.r = colors[0]
                        self.g = colors[1]
                        self.b = colors[2]
                        
                        self.loopColorBySteps(left)
                        
                    break
                    
                elif(colors[next] < 255):
                    #increase next                    
                    left = colors[next] + steps - 255
                    
                    if(left <= 0):
                        colors[next] += steps
                        
                        self.r = colors[0]
                        self.g = colors[1]
                        self.b = colors[2]
                    else:
                        colors[next] = 255
                        
                        self.r = colors[0]
                        self.g = colors[1]
                        self.b = colors[2]
                                            
                        self.loopColorBySteps(left)
                    
                    break

    def printValue(self):
        print(str(self.r) + " " + str(self.g) + " " + str(self.b))

class KeyColor:
    def __init__(self, key, r, g, b):
        self.key = key
        self.color = Color(r, g, b)
        
    def constructStringPacket(self):
        self.color.sanitize()
        return self.key + " " + str(self.color.r) + " " + str(self.color.g) + " " + str(self.color.b) + ";"

def sendUntilNoException(data):
    sent = False
    while(not sent):
        #Ugly but it works
        try:
            pipeHandle = win32file.CreateFile("\\\\.\\pipe\\DuckyController", win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0, None, win32file.OPEN_EXISTING, 0, None)
            win32file.WriteFile(pipeHandle, data)
            win32file.CloseHandle(pipeHandle)
            sent = True
            #print("sent " + data.decode("utf-8"))
        except Exception as e:
            #print(e)
            time.sleep(0.01)

def normalizeArray(arr):
    minVal = min(arr)
    maxVal = max(arr)
    divide = maxVal - minVal
    res = []
    for a in arr:
        normalizedValue = (a - minVal) / divide
        res.append(normalizedValue)
    return res

def binAverageFreqs(freqs, numBins):
    numPerBin = len(freqs) / numBins
    bins = []
    i = 0
    
    while(i < len(freqs)):
        start = int(round(i))
        end = int(round(i + numPerBin))
        if(end > len(freqs)):
            end = len(freqs)
        
        total = 0
        count = 0
        for j in range(start, end):
            total += freqs[j]
            count += 1
        if(count > 0):
            bins.append(total)
            
        i += numPerBin
        
    normalized = normalizeArray(bins)

    return normalized    

class AudioVisualizer:
    def __init__(self):
        self.defineKeyboardGrid()
        self.colorSpeed = 300
        self.lastUpdate = time.time()
        
    def defineKeyboardGrid(self):
        nameGrid = [
            ["Escape", "SectionSign", "Tab", "CapsLock", "LeftShift", "LeftControl"],
            ["", "1", "Q", "A", "<", "LeftWindows"],
            ["F1", "2", "W", "S", "Z", "LeftAlt"],
            ["F2", "3", "E", "D", "X", ""],
            ["F3", "4", "R", "F", "C", ""],
            ["F4", "5", "T", "G", "V", ""],
            ["", "6", "Y", "H", "B", "Space"],
            ["F5", "7", "U", "J", "N", ""],
            ["F6", "8", "I", "K", "M", ""],
            ["F7", "9", "O", "L", ",", ""],
            ["F8", "0", "P", "Semicolon", ".", "RightAlt"],
            ["F9", "-", "[", "'", "FSlash", "RightWindows"],
            ["F10", "=", "]", "''", "", "Function"],
            ["F13", "Backspace", "BSlash", "Enter", "RightShift", "RightControl"], #F12 doesn't fit. It might be a good idea to put together with F11
            ["PrintScreen", "Insert", "Delete", "", "", "LeftArrow"],
            ["ScrollLock", "Home", "End", "", "UpArrow", "DownArrow"],
            ["Pause", "PageUp", "PageDown", "", "", "RightArrow"],
            ["Calc", "NumLock", "N7", "N4", "N1", "N0"],
            ["Mute", "Divide", "N8", "N5", "N2", ""],
            ["VolumeDown", "Multiply", "N9", "N6", "N3", "NDelete"],
            ["VolumeUp", "Subtract", "", "Add", "", "RightEnter"]
        ]
        
        self.keyGrid = []
        self.columnColors = []
        self.columnHeightHistory = []
        columnHeightHistoryLength = 5
        currentColor = Color(255, 0, 0)
        for column in nameGrid:
            keyColumn = []
            for name in column:
                if(name == ""):
                    keyColumn.append(None)
                else:
                    columnColor = Color(0, 0, 0)
                    columnColor.setColor(currentColor)
                    self.columnColors.append(columnColor)
                    keyColumn.append(KeyColor(name, currentColor.r, currentColor.g, currentColor.b))
            self.keyGrid.append(keyColumn)
            currentColor.loopColorBySteps(50)
            self.columnHeightHistory.append([0] * columnHeightHistoryLength)

    def updateColor(self, deltaTime):
        steps = int(round(self.colorSpeed * deltaTime))
        for i in range(0, len(self.keyGrid)):
            columnColor = self.columnColors[i]
            column = self.keyGrid[i]
            columnColor.loopColorBySteps(steps)
            for key in column:
                if(key != None):
                    key.color.setColor(columnColor)
                
    def constructPacket(self):
        packet = b''
        for column in self.keyGrid:
            for key in column:
                if(key != None):
                    packet += key.constructStringPacket().encode()
        return packet
        

    #Already normalized input
    def colorByAudio(self, normalizedAudioBins):
        assert(len(self.keyGrid) == len(normalizedAudioBins))
        
        currentTime = time.time()
        deltaTime = currentTime - self.lastUpdate
        
        #All columns have full color
        self.updateColor(deltaTime)
        
        #Blacken top keys depending on values in audio bins
        columnHeight = len(self.keyGrid[0])
        for i in range(0, len(normalizedAudioBins)):
            audioBin = normalizedAudioBins[i]
            column = self.keyGrid[i]
            heightHistory = self.columnHeightHistory[i]
            
            #Update height history to average the values to prevent it looking completely random
            newHeight = int(round(columnHeight * audioBin))
            for j in range(0, len(heightHistory) - 1):
                heightHistory[j] = heightHistory[j + 1]
            heightHistory[-1] = newHeight
            self.columnHeightHistory[i] = heightHistory
            average = int(round(np.average(heightHistory)))
            
            for j in range(0, average):
                key = column[j]
                if(key != None):
                    key.color.zeroOut()
        
        self.lastUpdate = currentTime



recorded_frames = []
device_info = {}
useloopback = False
recordtime = 5

p = pyaudio.PyAudio()

try:
    default_device_index = p.get_default_input_device_info()
except IOError:
    default_device_index = -1



#6:       Speakers (Realtek High Definiti...   <-- This is my speaker device, so I hardcoded it.
# Uncomment code here to input manually or hardcode the indices to find your audio device.
# This might vary depending on your pc, drivers, etc so you will need to find it.
# In case of multiple devices with the same name you might want to use hardcoded indices.

#Select Device
print ("Available devices:\n")
for i in range(0, p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print (str(info["index"]) + ": \t %s \n \t %s \n" % (info["name"], p.get_host_api_info_by_index(info["hostApi"])["name"]))
    if("Line 1" in info["name"] and "Windows WASAPI" in p.get_host_api_info_by_index(info["hostApi"])["name"]):
        default_device_index = info["index"]

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
device_info = p.get_device_info_by_index(default_device_index)
#device_info = p.get_default_output_device_info()
#try:
    #device_info = p.get_device_info_by_index(device_id)
#except IOError:
    #device_info = p.get_device_info_by_index(default_device_index)
    #print ("Selection not available, using default.")

#Choose between loopback or standard mode

is_input = device_info["maxInputChannels"] > 0
is_wasapi = (p.get_host_api_info_by_index(device_info["hostApi"])["name"]).find("WASAPI") != -1
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

#Open stream
print(device_info["index"])
channelcount = device_info["maxInputChannels"] if (device_info["maxOutputChannels"] < device_info["maxInputChannels"]) else device_info["maxOutputChannels"]
print(channelcount)
print(int(device_info["defaultSampleRate"]))
stream = p.open(format = pyaudio.paInt16,
                channels = channelcount,
                rate = int(device_info["defaultSampleRate"]),
                input = True,
                frames_per_buffer = defaultframes,
                input_device_index = device_info["index"])
                #as_loopback = useloopback)

sendUntilNoException(b'INITIALIZE;')
time.sleep(3) #Wait for startup
#updateRate = 1 / 100
updateRate = 1 / 30
visualizer = AudioVisualizer()

#Exit when escape is pressed
running = True
flag = True
def escapePressed():
    global running
    running = False
def homePressed():
    sendUntilNoException(b'INITIALIZE;')
    time.sleep(3)
    global flag
    flag = True
def endPressed():
    sendUntilNoException(b'TERMINATE;')
    time.sleep(3)
    global flag
    flag = False
keyboard.add_hotkey('end', endPressed)
keyboard.add_hotkey('home', homePressed)

nextUpdate = time.time() + updateRate
mousecontrolcd = time.time()
"""
start=3
flen=3
xlen=int(flen)
for i in range(21):
    print(str(start)+"  "+str(start+xlen))
    flen*=1.3
    start=xlen
    xlen=int(flen)
"""
while(running):
    freqDataToUse = None

    while True:
        x1 = win32api.GetKeyState(0x05)  #stop
        x2 = win32api.GetKeyState(0x06)  #start
        if((x1==-128 or x1==-127)):
            print("end")
            sendUntilNoException(b'TERMINATE;')
            time.sleep(3)
            mousecontrolcd+=time.time()+1
            flag = False
        if((x2==-128 or x2==-127)):
            print("home")
            sendUntilNoException(b'INITIALIZE;')
            time.sleep(3)
            mousecontrolcd=time.time()+1
            flag = True
        if(not flag):
            time.sleep(0.1)
            continue

        #frames = stream.read(defaultframes)
        data = stream.read(defaultframes, exception_on_overflow=False)
        data_int = struct.unpack(str(4 * defaultframes) + 'B', data)
        data_int = np.array(data_int,dtype='b')[::2]
        volume = int(audioop.rms(data,2)/10)
        #print (volume)
        yf = fft(np.array(data_int,dtype='int8'))

        #print(yf)

        yf2 = np.abs(yf[0:int(defaultframes)])*2/(128 * defaultframes)
        #yf2 = np.abs(yf)*2/(128 * defaultframes)
        #print(yf2[750:1000:50])

        #temp = "                                                                                                                                                                                        "
        #print(sum(yf2[10:20])/10*15)
        #Some visualization to help understand the audio stream
        #npData = np.fromstring(stream.read(defaultframes),dtype=np.int16)
        #npData = npData * np.hanning(len(data))
        #sampleSize = pyaudio.get_sample_size(pyaudio.paInt16)
        
        #freqs = []
        #bins = binAverageFreqs(yf2, 21)
        #print(yf2)
        bins = []
        mul=np.array([21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41])/3
        start=0
        flen=5
        xlen=int(flen)
        for i in range(21):
            #bins.append(sum(yf2[start:start+xlen])*sum(yf2[start:start+xlen])/xlen/xlen*300*-1+1)
            #bins.append(sum(yf2[start:start+xlen])*sum(yf2[start:start+xlen])*sum(yf2[start:start+xlen])*4/xlen/xlen*volume*-1+1)
            bins.append(sum(np.power(yf2[start:start+xlen],3))/xlen*10*volume*-1+1)
            start+=xlen
            flen=flen*1.2
            xlen=int(flen)

        #bins = [0.05,0.1,(sum(yf2[10:20])/10*12*-1)+1,0.2,0.25,0.3,0.35,0.4,0.45,0.5,0.55,0.6,0.65,0.7,0.75,0.8,0.85,0.9,0.95,1,1]
        #bins=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
        #print(bins)

        
        if(time.time() >= nextUpdate):
            break
        
    if(len(bins) != 0):
        nextUpdate = time.time() + updateRate
        visualizer.colorByAudio(bins)
        visualizerData = visualizer.constructPacket()
        packet = b'RESET;' + visualizerData + b'PUSH;'
        sendUntilNoException(packet)
            
    time.sleep(updateRate)
        
# Shutdown

stream.stop_stream()
stream.close()

p.terminate()

sendUntilNoException(b'TERMINATE;')


