import os
import numpy as np
import win32pipe
import win32file
import time
import keyboard
import struct
import win32api
from scipy.fftpack import fft
import sys
import subprocess


# https://github.com/intxcc/pyaudio_portaudio/blob/master/example/echo_python3.py
# https://www.swharden.com/wp/2016-07-19-realtime-audio-visualization-in-python/
# https://stackoverflow.com/questions/35970282/what-are-chunks-samples-and-frames-when-using-pyaudio

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
            [
                ["Escape", "SectionSign", "Tab"],
                ["", "1", "Q"],
                ["F1", "2", "W"],
                ["F2", "3", "E"],
                ["F3", "4", "R"],
                ["F4","5",""],
                ["","6","T"],
                ["F5","7","Y"],
                ["F6","8","U"],
                ["F7","9","I"],
                ["F8","0","O"],
                ["F9","-","P"],
                ["F10","=","["],
                ["F11","","]"],
                ["F12","Backspace","BSlash"],
                ["PrintScreen", "Insert", "Delete"],
                ["ScrollLock", "Home", "End"],
                ["Pause", "PageUp", "PageDown"],
                ["Calc", "NumLock", "N7"],
                ["Mute", "Divide", "N8"],
                ["VolumeDown", "Multiply", "N9"],
                ["VolumeUp", "Subtract", ""]
            ],
            [
                ["CapsLock", "LeftShift", "LeftControl"],
                ["A","Z","LeftWindows"],
                ["S","X","LeftAlt"],
                ["D","C",""],
                ["F","V",""],
                ["G","B","Space"],
                ["H","N",""],
                ["J","M",""],
                ["K",",",""],
                ["L",".","RightAlt"],
                ["Semicolon","FSlash","RightWindows"],
                ["'","","Function"],
                ["Enter", "RightShift", "RightControl"],
                ["","","LeftArrow"],
                ["","UpArrow", "DownArrow"],
                ["","","RightArrow"],
                ["N4", "N1",""],
                ["N5","N2","N0"],
                ["N6","N3","NDelete"],
                ["","Add","RightEnter"]

            ]
        ]
        
        
        self.keyGrid = []
        self.columnColors = []
        self.columnHeightHistory = []
        columnHeightHistoryLength = 5
        currentColor = Color(0, 0, 0)
        for a in nameGrid:
            keycol2 = []
            for b in a:
                keycol1 = []
                for c in b:
                    if(c == ""):
                        keycol1.append(None)
                    else:
                        keycol1.append(KeyColor(c, currentColor.r, currentColor.g, currentColor.b))
                keycol2.append(keycol1)
            self.keyGrid.append(keycol2)

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
            for keyarray in column:
                for key in keyarray:
                    if(key != None):
                        packet += key.constructStringPacket().encode()
        return packet
        
    def colorByCD(self, cd):
        cd1 = cd[0]*len(self.keyGrid[0])
        counter1 = 1
        cd1color = Color(255, 0, 0)
        if(cd[0]>=1):
            cd1color = Color(0, 255, 0)
        for keyarray in self.keyGrid[0]:
            for key in keyarray:
                if(key != None):
                    if(counter1<cd1):
                        key.color.setColor(cd1color)
                    else:
                        key.color.zeroOut()
            counter1+=1

        cd2 = cd[1]*len(self.keyGrid[1])
        counter2 = 1
        cd2color = Color(255, 0, 0)
        if(cd[1]>=1):
            cd2color = Color(0, 255, 0)
        for keyarray in self.keyGrid[1]:
            for key in keyarray:
                if(key != None):
                    if(counter2<cd2):
                        key.color.setColor(cd2color)
                    else:
                        key.color.zeroOut()
            counter2+=1


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




def main():
    try:
        
        cmd = ".\\hidtest.exe"
        #process = subprocess.Popen(cmd, stdout=subprocess.PIPE, creationflags=0x08000000)

        sys.setrecursionlimit(9000000)
        np.set_printoptions(suppress=True) # don't use scientific notation

        sendUntilNoException(b'INITIALIZE;')
        time.sleep(3) #Wait for startup
        #updateRate = 1 / 100
        updateRate = 1 / 5
        lastUpdate = time.time()
        visualizer = AudioVisualizer()

        #keyboard.add_hotkey('end', endPressed)
        #keyboard.add_hotkey('home', homePressed)

        nextUpdate = time.time() + updateRate
        mousecontrolcd = time.time()

        cd1 = 60
        cd2 = 90
        cd1last = time.time()-cd1
        cd2last = time.time()-cd2
        while(running):
            x1 = win32api.GetKeyState(0x05)  #stop
            x2 = win32api.GetKeyState(0x06)  #start
            if((x1==-128 or x1==-127)):
                cd2last = time.time()
            if((x2==-128 or x2==-127)):
                cd1last = time.time()
            if((time.time()-lastUpdate)>=updateRate):
                cd1persent = (time.time()-cd1last)/cd1
                cd2persent = (time.time()-cd2last)/cd2
                visualizer.colorByCD([cd1persent,cd2persent])
                visualizerData = visualizer.constructPacket()
                packet = b'RESET;' + visualizerData + b'PUSH;'
                sendUntilNoException(packet)
                lastUpdate = time.time()
            time.sleep(0.01)
    finally:
        #process.kill()
        sendUntilNoException(b'TERMINATE;')
if __name__=='__main__':
    main()