#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Manestrone.py
#
# Copyright (C) 2021  SUZUDO Yasushi  <yasushi_suzudo@yahoo.co.jp>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# change from 02 to 03: now low latency mixer works.
# also program cleaned up and efficiency increased by eliminating
# unnecessary update of display. 2021/06/27

import usb.core
import usb.util
import wx
import threading
import math

programName = "Manestrone"
debug = False        # just for GUI visual checking (no apogee device needed)
disable_mixer = False # as most elements cannot be controlled...
borderValue = 10
inputWindowSize = (1140,390)
mixerWindowSize = (1140,390)
mainWindowSize = (1140,390)
outputWindowSize = (1140,390)
updateInterval = 0.2 # interval for periodic information update of the device

#
# global variable
#
# vendor ID, product ID, product name, number of input, output.

Quartet = {}                           # dict of device(Quartet) info 
Quartet["VendorID"] = 0x0c60
Quartet["ProductID"] = 0x0014
Quartet["ProductName"] = "Apogee Quartet"

Quartet["InputNum"] = 4
Quartet["softLimit_Request"]  = 17
Quartet["phase_Request"]      = 19
Quartet["phantom_Request"]    = 21
Quartet["inputType_Request"]  = 22
Quartet["micLevel_Request"]   = 52
Quartet["instLevel_Request"]  = 62
Quartet["inputGroup_Request"] = 68
Quartet["inputType"]        = ["Line  +4dB", "Line -10dB", "Microphone", "Instrument"]
Quartet["micLevel_Range"]   = {"Min":0, "Max":75}
Quartet["instLevel_Range"]  = {"Min":0, "Max":65}
Quartet["inputGroupChoice"] = ["Group OFF", "Group 1", "Group2 "]

Quartet["outputLevel_Request"]     =  51
Quartet["outputMute_Request"]      =  53
Quartet["outputDim_Request"]       =  64
Quartet["outputConfig_Request"]    =  69
Quartet["outputMono_Request"]      =  70
Quartet["output_Line_Request"]     =  71
Quartet["outputSource_Request"]    =  83
Quartet["outputLineLevel_Request"] = 182
Quartet["output_Speaker_Index"]   = 0
Quartet["output_Headphone_Index"] = 1
Quartet["outputConfigChoice"]    = ["Line", "Stereo", "2 Speaker Sets", "3 Speaker Sets", "5.1"]
Quartet["output_LineNameChoice"] = ["Line 1/2", "Line 3/4", "Line 5/6"] 
Quartet["line_Name"]             = ["Line 1/2", "Headphone", "Line 5/6", "Line 3/4"]
Quartet["output_Line_Index"]     = [0, 3, 2]
Quartet["output_SpSelectIndex"]  = [1, 2, 4]
Quartet["output_SpChoiceToIndex"] = {1:0, 2:1, 4:2}
Quartet["outputSource_Dest"]     = [0 ,3, 2, 1] # line1/2:index0, headphone:index3,
                                                # line 5/6:index2, line3/4:index1
Quartet["outputSourceChoice"]    = ["Output 1/2",
                                    "Output 3/4",
                                    "Output 5/6",
                                    "Output 7/8",
                                    "Mixer    1",
                                    "Mixer    2"] 
Quartet["outputLineLevelChoice"] = ["+ 4dBV", "-10dBV"]
Quartet["outputLevel_Range"]     = {"Min":-64, "Max":0}

Quartet["mixer_Num"] =  2        # wValue = 0, 1
Quartet["mixerChannel_Num"] =  12 # number of input channels. actually quartet has 12(index 0-11,
                                  # (4 analog, 8 digital)
Quartet["mixerChannel_SWR"] =  12 # software return channel
Quartet["mixerChannel_Master"] =  13  # master output channel
Quartet["mixerHWset_Request"]   = 16
Quartet["mixerSoftRtn_Request"] = 54 # software return source
Quartet["mixerLevel_Request"]   = 76
Quartet["mixerPan_Request"]     = 77
Quartet["mixerSolo_Request"]    = 78
Quartet["mixerMute_Request"]    = 79
Quartet["mixerSoftRtnChoice"] = ["Playback 1/2", "Playback 3/4",  "Playback 5/6",  "Playback 7/8"]
Quartet["mixerLevel_Range"]   = {"Min":-48, "Max":6}
Quartet["mixerPan_Range"]     = {"Min":-64, "Max":64}

ApogeeDevices = [Quartet]     # list of supported devices (currently only Quartet)

dev = None                    # hardware device found
Apogeeinfo = None             # dict of info for identified device

def get_dev_value(request, wValue = 0, wIndex = 0):
    return dev.ctrl_transfer(0xc0, Apogeeinfo[request], wValue, wIndex, 1)[0]

def set_dev_value(request, wValue = 0, wIndex =0, msg = None):
        dev.ctrl_transfer(0x40, Apogeeinfo[request], wValue, wIndex,  [msg])

class stripPanel(wx.Panel):

    def __init__(self, parent, mixerindex = None, channel = None):
        wx.Panel.__init__(self, parent, id = wx.Window.NewControlId())

        self.parent = parent
        self.mixerindex = mixerindex
        self.index = channel
        self.source = 0
        self.level = 0
        self.pan = 0
        self.solo = 0
        self.mute = 0

        box = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(box)

        if (self.index == Apogeeinfo["mixerChannel_SWR"]):
            title = "Software Return"
            subtitle = "Source"
        elif (self.index == Apogeeinfo["mixerChannel_Master"]):
            title = "Output"
            subtitle = ""
        else:
            title = "Input " + str(channel + 1)
            subtitle = "Pan"

        self.Title =  wx.StaticText(self, label=title, style = wx.ALIGN_CENTRE)
        self.secondTitle =  wx.StaticText(self, label=subtitle, style = wx.ALIGN_CENTRE)

        self.LevelTitle =  wx.StaticText(self, label="Level", style = wx.ALIGN_CENTRE)
        self.Level = wx.SpinCtrl(self, wx.Window.NewControlId())
        self.Level.SetRange(Apogeeinfo["mixerLevel_Range"]["Min"],
                            Apogeeinfo["mixerLevel_Range"]["Max"]) #  Level(-48 - +6) <=> self.level(0-54)


        self.Source = wx.Choice(self, wx.Window.NewControlId(),
                                choices=Apogeeinfo["mixerSoftRtnChoice"])
        self.Pan = wx.SpinCtrl(self, wx.Window.NewControlId())
        self.Pan.SetRange(Apogeeinfo["mixerPan_Range"]["Min"],
                          Apogeeinfo["mixerPan_Range"]["Max"]) # Pan(-64 - +64) <=> self.pan(0-128)
        self.Solo = wx.ToggleButton(self, wx.Window.NewControlId(), label='Solo')
        self.Mute = wx.ToggleButton(self, wx.Window.NewControlId(), label='Mute')

        box.AddSpacer(borderValue)
        box.Add(self.Title, flag=wx.EXPAND)
        box.AddSpacer(borderValue)
        box.Add(self.LevelTitle, flag=wx.EXPAND)
        box.Add(self.Level, flag=wx.EXPAND)
        box.AddSpacer(borderValue)
        box.Add(self.secondTitle, flag=wx.EXPAND)
        box.Add(self.Source, flag=wx.EXPAND)
        box.Add(self.Pan, flag=wx.EXPAND)
        box.Add(self.Solo, flag=wx.EXPAND)
        box.Add(self.Mute, flag=wx.EXPAND)

        if (debug == False):
            self.Level.Bind(wx.EVT_SPINCTRL, self.on_mixer_level_changed)
            self.Source.Bind(wx.EVT_CHOICE, self.on_source_changed)
            self.Pan.Bind(wx.EVT_SPINCTRL, self.on_mixer_pan_changed)
            self.Solo.Bind(wx.EVT_TOGGLEBUTTON, self.on_solo_toggled)
            self.Mute.Bind(wx.EVT_TOGGLEBUTTON, self.on_mute_toggled)

        if (disable_mixer == True):
            self.Level.Disable()
            self.Pan.Disable()
            self.Solo.Disable()
            self.Mute.Disable()

        self.update()

    def get_mixer_info(self): # this function gathers mixer setting stored in hardware.
                              # for "info", see "ApogeeDevices".

        if (debug):
            self.level = 0
            self.source = 0
            self.pan = 0
            self.solo = 0
            self.mute = 0
        else:
            self.level = get_dev_value("mixerLevel_Request", self.mixerindex,
                                    self.index) + Apogeeinfo["mixerLevel_Range"]["Min"]  #  - 48

            if (self.index == Apogeeinfo["mixerChannel_SWR"]):
                self.source = get_dev_value("mixerSoftRtn_Request", 0, self.mixerindex)
            else:
                self.source = 0

            if (self.index < Apogeeinfo["mixerChannel_Num"]):
                self.pan = get_dev_value("mixerPan_Request", self.mixerindex,
                                         self.index) + Apogeeinfo["mixerPan_Range"]["Min"]      #  - 64
            else:
                self.pan = 0

            if (self.index != Apogeeinfo["mixerChannel_Master"]):
                self.solo = get_dev_value("mixerSolo_Request", self.mixerindex, self.index)
                self.mute = get_dev_value("mixerMute_Request", self.mixerindex, self.index)
            else:
                self.solo = 0
                self.mute = 0

        if (self.index == Apogeeinfo["mixerChannel_SWR"]):
            self.Pan.Hide()
        else:
            self.Source.Hide()
            if (self.index == Apogeeinfo["mixerChannel_Master"]):
                self.Pan.Hide()
                self.Solo.Hide()
                self.Mute.Hide()

        self.Layout()

    def update(self):   # this function update display of software, but does not affect hardware.
        self.get_mixer_info()
        self.Source.SetSelection(self.source)
        self.Level.SetValue(self.level)
        if (self.index != Apogeeinfo["mixerChannel_Master"]):
            self.Pan.SetValue(self.pan)
            self.Solo.SetValue(self.solo)
            self.Mute.SetValue(self.mute)

    def on_source_changed(self, event):
        set_dev_value("mixerSoftRtn_Request", 0, self.mixerindex,  event.GetSelection())

    def on_mixer_level_changed(self, event):
        self.level = event.GetPosition()
        set_dev_value("mixerLevel_Request", self.mixerindex, self.index,
                      self.level - Apogeeinfo["mixerLevel_Range"]["Min"]) # + 48
        # in case of mixer, set_dev_value change setting info stored in the hardware,
        # but does not affect hardware behavior.
        # so following is needed.
        self.parent.setmixer()

    def on_mixer_pan_changed(self, event):
        self.pan = event.GetPosition()
        set_dev_value("mixerPan_Request", self.mixerindex, self.index,
                      self.pan  - Apogeeinfo["mixerPan_Range"]["Min"]) # + 64
                      
        self.parent.setmixer()

    def on_solo_toggled(self, event):
        self.solo = event.GetInt()
        set_dev_value("mixerSolo_Request", self.mixerindex, self.index, self.solo)
        self.parent.setmixer()

    def on_mute_toggled(self, event):
        self.mute = event.GetInt()
        set_dev_value("mixerMute_Request", self.mixerindex, self.index, self.mute)
        self.parent.setmixer()

    def sp_info(self):
        self.get_mixer_info()
        if self.index == Apogeeinfo["mixerChannel_SWR"]: # software return source
            return {"Level":self.level, "Pan":None, "Mute":self.mute, "Solo":self.solo}
        else:
            return {"Level":self.level, "Pan":self.pan, "Mute":self.mute, "Solo":self.solo}

    # def input_info(self):
    #     self.get_mixer_info()
    #     return {"Level":self.level, "Pan":self.pan, "Mute":self.mute, "Solo":self.solo}

    # def swr_info(self):
    #     self.get_mixer_info()
    #     return {"Level":self.level, "Pan":None, "Mute":self.mute, "Solo":self.solo}

    def master_level(self):
        self.get_mixer_info()
        return self.level


class mixerPanel(wx.Panel):

    def __init__(self, parent, index = 0):
        wx.Panel.__init__(self, parent)

        self.parent = parent
        self.index = index
        self.spList = {} # list of input strip panels
        self.spInfo = {} # info of input & software return strip settings. each element is:
                         # {"Level":(-48 - +6),
                         #  "Pan":(-64 - + 64, None for SWR),
                         #  "Mute":(bool)
                         #  "Solo":(bool)}
        self.outLevel = None # info of mixer master output setting. (-48 - +6)
        self.mixerHWinfo = {} # each element corresponds to each input/swr.
                              # each element is, basically:
                              # {"mute":(bool) if true, below values are ignored.
                              # "left" :(int) = int(8192(=0x2000) * exp(10^0.05, input dB+master dB) * cos(mixerPan(=0-128)/128 * PI()/2))
                              # "right":(int) = int(8192(=0x2000) * log10(input dB + master dB) * sin(mixerPan(=0-128)/128 * PI()/2))
        self.step = math.pow(10,(1/200)) # 1.01157945 # 
        self.db =   math.pow(10,(1/20))  # 1.1220185   # 
        self.panRange = Apogeeinfo["mixerPan_Range"]["Max"] - Apogeeinfo["mixerPan_Range"]["Min"] # 64 - -64 = 128

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(hbox)

        self.masterPanel = stripPanel(self, index,
                                 channel = Apogeeinfo["mixerChannel_Master"]) # master output

        self.softRtnPanel = stripPanel(self, index, 
                                  channel = Apogeeinfo["mixerChannel_SWR"]) # software return source

        hbox.Add(self.masterPanel, flag=wx.EXPAND | wx.BOTTOM | wx.LEFT | wx.RIGHT,
                 border=borderValue)

        hbox.Add(self.softRtnPanel, flag=wx.EXPAND | wx.BOTTOM | wx.LEFT | wx.RIGHT,
                 border=borderValue)
        self.spList[Apogeeinfo["mixerChannel_SWR"]] = self.softRtnPanel

        for channel in range(0, Apogeeinfo["mixerChannel_Num"]):    # strips are produced per channel
            sp = stripPanel(self, index, channel)            # a strip(panel)
            hbox.Add(sp, flag=wx.EXPAND |  wx.BOTTOM | wx.LEFT | wx.RIGHT, border=borderValue)
            self.spList[channel] = sp                                   # sp added to splist

        # as I do not use digital inputs...
        for i in range(Apogeeinfo["InputNum"], Apogeeinfo["mixerChannel_Num"]):
            self.spList[i].Hide()
        self.Layout()

    def toggle_dInput(self):
        for i in range(Apogeeinfo["InputNum"], Apogeeinfo["mixerChannel_Num"]):
            if (self.spList[i].Show(True) == False):
                self.spList[i].Show(False)
        self.Layout()


    def update(self):
        for each in self.spList:
            each.update()
        #self.softRtnPanel.update()
        self.masterPanel.update()

    def setmixer(self):
        soloFlag = False
        iList = []

        for i in range(0, Apogeeinfo["mixerChannel_Num"]):
            iList.append(i)

        iList.append(Apogeeinfo["mixerChannel_SWR"])

        for i in iList:
            self.spInfo[i] = self.spList[i].sp_info()
            if self.spInfo[i]["Solo"] == True:
                soloFlag = True
            self.mixerHWinfo[i] = {}

        # setting mute flags
        # if outLevel == -48, mute every channel.
        self.outLevel = self.masterPanel.master_level()
        if self.outLevel == -48: # mute all the channels
            for i in iList:
                self.mixerHWinfo[i]["mute"] = True
        else:
            for i in iList:
                self.mixerHWinfo[i]["mute"] = False

            # if some channels have solo flags, mute non-solo channels
            if soloFlag == True:
                for i in iList:
                    if self.spInfo[i]["Solo"] == False:
                        self.mixerHWinfo[i]["mute"] = True

            # if the channel has mute flag or its level = -48, mute it even it has solo flag.
            for i in iList:
                if self.spInfo[i]["Mute"] == True or self.spInfo[i]["Level"] == -48:
                    self.mixerHWinfo[i]["mute"] = True

        # now mute flags are setup. calculation starts.
        # first for input channels.
        oLevel = {}
        msg = {"left":[], "right":[]}
        for i in range(0, Apogeeinfo["mixerChannel_Num"]):
            if self.mixerHWinfo[i]["mute"] == True:
                oLevel["left"] =  0
                oLevel["right"] =  0
            else:
                # otherwise: inputlevel * outlevel * pan (cos/sin), then make it stepwise of 10^(1/200)
                thruLevel = 0x2000 * math.pow(self.db, (self.spInfo[i]["Level"] + self.outLevel))
                theta = ((self.spInfo[i]["Pan"] - Apogeeinfo["mixerPan_Range"]["Min"])/self.panRange) * math.pi/2

                oLevel["left"]  =  thruLevel * math.cos (theta)
                oLevel["right"] =  thruLevel * math.sin (theta)
                
            for each in ["left", "right"]:
                if oLevel[each] < 100:
                    self.mixerHWinfo[i][each] = int(oLevel[each])
                else:
                    self.mixerHWinfo[i][each] = int(0x2000 * math.pow(self.step, round(math.log(oLevel[each]/0x2000, self.step))))

                # preparing message to be sent to HW
                upperByte = self.mixerHWinfo[i][each] >> 8
                lowerByte = self.mixerHWinfo[i][each] - (upperByte << 8)
                msg[each].append(upperByte)
                msg[each].append(lowerByte)

        # calculation fo swr channel. in output message, it is treated as two channels,
        # one for left, the other is for right, so it should be handled separately.
        if self.mixerHWinfo[Apogeeinfo["mixerChannel_SWR"]]["mute"] == True:
            thruLevel = 0
        else:
            # fortunately swr has no pan, so it is much simpler
            thruLevel =  int(0x2000 * math.pow(self.db, self.spInfo[Apogeeinfo["mixerChannel_SWR"]]["Level"] + self.outLevel))

        upperByte = thruLevel >> 8
        lowerByte = thruLevel - (upperByte << 8)
        msg["left"].append(upperByte)
        msg["left"].append(lowerByte)
        msg["left"].append(int(0))
        msg["left"].append(int(0))

        msg["right"].append(int(0))
        msg["right"].append(int(0))
        msg["right"].append(upperByte)
        msg["right"].append(lowerByte)

        resL = dev.ctrl_transfer(0x40, Apogeeinfo["mixerHWset_Request"], 0, self.index * 2,     msg["left"])
        resR = dev.ctrl_transfer(0x40, Apogeeinfo["mixerHWset_Request"], 0, self.index * 2 + 1, msg["right"])

class mixerWindow(wx.Frame):

    def __init__(self, parent, mainbody):
        wx.Frame.__init__(self, parent, size = mixerWindowSize)

        self.parent = parent
        self.mainbody = mainbody
        self.SetTitle(Apogeeinfo["ProductName"] + ": Mixer" )
        vbox = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(vbox)
            
        mixerindex = 0
        self.mplist = [] # list of mixer panels
        for mixerindex in range(0, Apogeeinfo["mixer_Num"]):

            mtitle =  wx.StaticText(self, label="Mixer " + str(mixerindex + 1),
                                    style = wx.ALIGN_CENTRE)
            mp = mixerPanel(self, mixerindex) # a mixer panel
            self.mplist.append(mp)                                   # mp added to mplist

            vbox.AddSpacer(borderValue)
            vbox.Add(mtitle, flag=wx.EXPAND |  wx.TOP | wx.LEFT | wx.RIGHT, border=borderValue)
            vbox.Add(mp, flag=wx.EXPAND)

            mp.Layout()

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # menu part

        menuBar = wx.MenuBar()

        fileMenu = wx.Menu()

        menuAbout = fileMenu.Append(wx.ID_ABOUT, "&About"," Information about this program")
        fileMenu.AppendSeparator()
        menuExit = fileMenu.Append(wx.ID_EXIT,"&Exit"," Terminate this program")
        
        viewMenu = wx.Menu()

        #menuOutput = viewMenu.Append(wx.ID_ANY, "Toggle window/tab: &Outputs \tCTRL-O","")
        menuInput = viewMenu.Append(wx.ID_ANY, "Toggle window/tab: &Inputs \tCTRL-I","")
        menuMixer = viewMenu.Append(wx.ID_ANY, "Toggle window/tab: &Mixer \tCTRL-M","")
        menuDMixer = viewMenu.Append(wx.ID_ANY, "Toggle &Digital Input display in Mixer \tCTRL-D","")

        menuBar.Append(fileMenu, "&File")
        menuBar.Append(viewMenu, "&View")
        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)
        self.Bind(wx.EVT_MENU, self.OnAbout, menuAbout)
        #self.Bind(wx.EVT_MENU, self.OnMenuOut, menuOutput)
        self.Bind(wx.EVT_MENU, self.OnMenuIn, menuInput)
        self.Bind(wx.EVT_MENU, self.OnMenuMix, menuMixer)
        self.Bind(wx.EVT_MENU, self.OnMenuDMix, menuDMixer)

        self.Layout()

    def OnAbout(self, e):
        dlg = wx.MessageBox("Apogee Devices Control Panel\n\n"
                            "built on WxPython and PyUSB\n\n"
                            "Thanks to take_control by stefanocoding", programName)

    def OnMenuIn(self, e):
        if (self.mainbody.inputSection.Show(True) == False):
            self.mainbody.inputSection.Show(False)
            self.mainbody.inputP.Show(True)
        else:
            self.mainbody.inputP.Show(False)
        
    def OnMenuOut(self, e):
        if (self.mainbody.outputSection.Show(True) == False):
            self.mainbody.outputSection.Show(False)
            self.mainbody.outputP.Show(True)
        else:
            self.mainbody.outputP.Show(False)
        
    def OnMenuMix(self, e):
        if (self.mainbody.mixerSection.Show(True) == False):
            self.mainbody.mixerSection.Show(False)
            for each in self.mainbody.mplist:
                each.Show(True)
        else:
            for each in self.mainbody.mplist:
                each.Show(False)
        
    def OnMenuDMix(self, e):
        for each in self.mplist:
            each.toggle_dInput()
        
    def OnExit(self, e):
        # do not forget to close the update loop (thread)
        self.mainbody.event.set()
        self.mainbody.Close(True)
        exit(0)

    def update(self):
        for each in self.mplist:
            each.update()

    def OnClose(self, event):
        self.OnMenuMix(event)
        #self.Hide()

class inputPanel(wx.Panel):

    def __init__(self, parent, deviceindex = None):
        wx.Panel.__init__(self, parent, id = wx.Window.NewControlId())

        self.parent = parent
        self.index = deviceindex

        self.itype = None
        self.softlimit = None
        self.phantom = None
        self.miclevel = None
        self.instlevel = None
        self.group = None

        box = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(box)

        self.Title =  wx.StaticText(self, label="Input " + str(deviceindex + 1),
                                    style = wx.ALIGN_CENTRE)
        self.Type = wx.Choice(self, wx.Window.NewControlId(),choices=Apogeeinfo["inputType"])

        self.MicLevel = wx.SpinCtrl(self, wx.Window.NewControlId())
        self.MicLevel.SetRange(Apogeeinfo["micLevel_Range"]["Min"], Apogeeinfo["micLevel_Range"]["Max"]) 

        self.InstLevel = wx.SpinCtrl(self, wx.Window.NewControlId())
        self.InstLevel.SetRange(Apogeeinfo["instLevel_Range"]["Min"], Apogeeinfo["instLevel_Range"]["Max"]) 

        self.SoftLimit = wx.ToggleButton(self, wx.Window.NewControlId(), label='Soft Limit')
        self.Phase = wx.ToggleButton(self, wx.Window.NewControlId(), label='Phase')
        self.Phantom = wx.ToggleButton(self, wx.Window.NewControlId(), label='48V')
        self.Group = wx.Choice(self, wx.Window.NewControlId(),choices=Apogeeinfo["inputGroupChoice"])

        box.Add(self.Title, flag=wx.EXPAND)
        box.Add(self.Type, flag=wx.EXPAND)
        box.Add(self.MicLevel, flag=wx.EXPAND)
        box.Add(self.InstLevel, flag=wx.EXPAND)
        box.Add(self.SoftLimit, flag=wx.EXPAND)
        box.Add(self.Phase, flag=wx.EXPAND)
        box.Add(self.Phantom, flag=wx.EXPAND)
        box.Add(self.Group, flag=wx.EXPAND)

        if (debug == False):
            self.Type.Bind(wx.EVT_CHOICE, self.on_input_type_changed)
            self.MicLevel.Bind(wx.EVT_SPINCTRL, self.on_input_level_changed)
            self.InstLevel.Bind(wx.EVT_SPINCTRL, self.on_input_level_changed)
            self.SoftLimit.Bind(wx.EVT_TOGGLEBUTTON, self.on_softlimit_toggled)
            self.Phase.Bind(wx.EVT_TOGGLEBUTTON, self.on_phase_toggled)
            self.Phantom.Bind(wx.EVT_TOGGLEBUTTON, self.on_phantom_toggled)
            self.Group.Bind(wx.EVT_CHOICE, self.on_input_group_changed)

        self.update()

    def get_input_info(self): # for "info", see "ApogeeDevices".

        if (debug):
            self.itype = 0
            self.softlimit = 0
            self.phantom = 0
            self.miclevel = 0
            self.instlevel = 0
            self.group = 0
        else:
            self.itype = get_dev_value("inputType_Request", 0, self.index)
            self.softlimit = get_dev_value("softLimit_Request", 0, self.index)
            self.phantom = get_dev_value("phantom_Request", 0, self.index)
            self.miclevel = get_dev_value("micLevel_Request", 0, self.index)
            self.instlevel = get_dev_value("instLevel_Request", 0, self.index)
            self.group = get_dev_value("inputGroup_Request", 0, self.index)

    def update(self):
        self.get_input_info()
        self.Type.SetSelection(self.itype)

        if Apogeeinfo["inputType"][self.itype] == "Microphone":
            self.MicLevel.Show()
            self.InstLevel.Hide()
            self.Layout()
            self.MicLevel.Enable()
            self.InstLevel.Disable()
            self.MicLevel.SetValue(self.miclevel)
            self.Phantom.Enable()
            self.Phantom.SetValue(self.phantom)
        else:
            self.MicLevel.Hide()
            self.InstLevel.Show()
            self.Layout()
            self.MicLevel.Disable()
            if (Apogeeinfo["inputType"][self.itype] == "Instrument"):
                self.InstLevel.Enable()
                self.InstLevel.SetValue(self.instlevel)
            else:
                self.InstLevel.Disable()
            self.Phantom.Disable()
        
        #self.MicLevel.SetValue(self.miclevel)
        self.SoftLimit.SetValue(self.softlimit)
        self.Group.SetSelection(self.group)


    def on_input_level_changed(self, event):
        set_dev_value("instLevel_Request", 0, self.index, event.GetPosition())
        set_dev_value("micLevel_Request", 0, self.index, event.GetPosition())

    def on_input_type_changed(self, event):
        set_dev_value("inputType_Request", 0, self.index, event.GetSelection())

        self.update()

    def on_softlimit_toggled(self, event):
        set_dev_value("softLimit_Request", 0, self.index, event.GetInt())

    def on_phase_toggled(self, event):
        set_dev_value("phase_Request", 0, self.index, event.GetInt())

    def on_phantom_toggled(self, event):
        set_dev_value("phantom_Request", 0, self.index, event.GetInt())

    def on_input_group_changed(self, event):
        set_dev_value("inputGroup_Request", 0, self.index, event.GetSelection())



class inputsPanel(wx.Panel):

    def __init__(self, parent):
        wx.Panel.__init__(self, parent)

        self.parent = parent
        box = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(box)
        self.panel = []

        for deviceindex in range(0, Apogeeinfo["InputNum"]):
            p = inputPanel(self, deviceindex)
            box.Add(p, flag=wx.EXPAND |  wx.BOTTOM | wx.TOP | wx.LEFT | wx.RIGHT, border=borderValue)
            self.panel.append(p)

        self.Layout()

    def update(self):
        for each in self.panel:
            each.update()
    
class inputWindow(wx.Frame):

    def __init__(self, parent, mainbody):
        wx.Frame.__init__(self, parent, size = inputWindowSize)

        self.parent = parent
        self.mainbody = mainbody
        self.SetTitle(Apogeeinfo["ProductName"] + ": Inputs")
        box = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(box)

        self.panel = inputsPanel(self)
        box.Add(self.panel, flag=wx.EXPAND |  wx.BOTTOM | wx.TOP | wx.LEFT | wx.RIGHT,
                border=borderValue)

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # menu part

        menuBar = wx.MenuBar()

        fileMenu = wx.Menu()

        menuAbout = fileMenu.Append(wx.ID_ABOUT, "&About"," Information about this program")
        fileMenu.AppendSeparator()
        menuExit = fileMenu.Append(wx.ID_EXIT,"&Exit"," Terminate this program")
        
        viewMenu = wx.Menu()

        #menuOutput = viewMenu.Append(wx.ID_ANY, "Toggle window/tab: &Outputs \tCTRL-O","")
        menuInput = viewMenu.Append(wx.ID_ANY, "Toggle window/tab: &Inputs \tCTRL-I","")
        menuMixer = viewMenu.Append(wx.ID_ANY, "Toggle window/tab: &Mixer \tCTRL-M","")

        menuBar.Append(fileMenu, "&File")
        menuBar.Append(viewMenu, "&View")
        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)
        self.Bind(wx.EVT_MENU, self.OnAbout, menuAbout)
        #self.Bind(wx.EVT_MENU, self.OnMenuOut, menuOutput)
        self.Bind(wx.EVT_MENU, self.OnMenuIn, menuInput)
        self.Bind(wx.EVT_MENU, self.OnMenuMix, menuMixer)

        self.Layout()

    def OnAbout(self, e):
        dlg = wx.MessageBox("Apogee Devices Control Panel\n\n"
                            "built on WxPython and PyUSB\n\n"
                            "Thanks to take_control by stefanocoding", programName)

    def OnMenuIn(self, e):
        if (self.mainbody.inputSection.Show(True) == False):
            self.mainbody.inputSection.Show(False)
            self.mainbody.inputP.Show(True)
        else:
            self.mainbody.inputP.Show(False)
        
    def OnMenuOut(self, e):
        if (self.mainbody.outputSection.Show(True) == False):
            self.mainbody.outputSection.Show(False)
            self.mainbody.outputP.Show(True)
        else:
            self.mainbody.outputP.Show(False)
        
    def OnMenuMix(self, e):
        if (self.mainbody.mixerSection.Show(True) == False):
            self.mainbody.mixerSection.Show(False)
            for each in self.mainbody.mplist:
                each.Show(True)
        else:
            for each in self.mainbody.mplist:
                each.Show(False)
        
    def OnExit(self, e):
        # do not forget to close the update loop (thread)
        self.mainbody.event.set()
        self.mainbody.Close(True)
        exit(0)

    def update(self):
        self.panel.update()
    
    def OnClose(self, event):
        self.OnMenuIn(event)
        #self.Hide()


class speakerPanel(wx.Panel): # used for both speaker and headphone

    def __init__(self, parent, speaker = True):
        wx.Panel.__init__(self, parent, id = wx.Window.NewControlId())

        self.parent = parent
        if speaker == True:
            self.index = Apogeeinfo["output_Speaker_Index"]
            title = "Speaker"
            source_title = "Choice"
            source_choice = "output_LineNameChoice"
        else:
            self.index = Apogeeinfo["output_Headphone_Index"]
            title = "Headphone"
            source_title = "Source"
            source_choice = "outputSourceChoice"

        self.Speaker = speaker
        self.source = None # in case of Speaker, this indicate line pair which sends audio to speakers
        self.level = None
        self.mute = None
        self.dim = None
        self.mono = None
        self.config = None # speaker configuration
        
        box = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(box)

        self.Title =  wx.StaticText(self, label=title, style = wx.ALIGN_CENTRE)
        self.SourceTitle =  wx.StaticText(self, label=source_title, style = wx.ALIGN_CENTRE)
        self.Source = wx.Choice(self, wx.Window.NewControlId(),choices=Apogeeinfo[source_choice])

        self.Level = wx.SpinCtrl(self, wx.Window.NewControlId())
        self.Level.SetRange(Apogeeinfo["outputLevel_Range"]["Min"], Apogeeinfo["outputLevel_Range"]["Max"]) 

        self.Mute = wx.ToggleButton(self, wx.Window.NewControlId(), label = "Mute")
        self.Dim = wx.ToggleButton(self, wx.Window.NewControlId(), label = "Dim")
        self.Mono = wx.ToggleButton(self, wx.Window.NewControlId(), label = "Mono")

        box.Add(self.Title, flag=wx.EXPAND)
        box.AddSpacer(borderValue)
        box.Add(self.SourceTitle, flag=wx.EXPAND)
        box.Add(self.Source, flag=wx.EXPAND)
        box.Add(self.Level, flag=wx.EXPAND)
        box.Add(self.Mute, flag=wx.EXPAND)
        box.Add(self.Dim, flag=wx.EXPAND)
        box.Add(self.Mono, flag=wx.EXPAND)

        if self.Speaker == True:

            self.ConfigTitle = wx.StaticText(self, label="Configuration", style = wx.ALIGN_CENTRE)
            self.Config = wx.Choice(self, wx.Window.NewControlId(),
                                    choices=Apogeeinfo["outputConfigChoice"])
            box.AddSpacer(borderValue)
            box.Add(self.ConfigTitle, flag=wx.EXPAND)
            box.Add(self.Config, flag=wx.EXPAND)

        if (debug == False):
            self.Source.Bind(wx.EVT_CHOICE, self.on_output_source_changed)
            self.Level.Bind(wx.EVT_SPINCTRL, self.on_output_level_changed)
            self.Mute.Bind(wx.EVT_TOGGLEBUTTON, self.on_mute_toggled)
            self.Dim.Bind(wx.EVT_TOGGLEBUTTON, self.on_dim_toggled)
            self.Mono.Bind(wx.EVT_TOGGLEBUTTON, self.on_mono_toggled)
            if self.Speaker == True:
                self.Config.Bind(wx.EVT_CHOICE, self.on_output_config_changed)

        self.update()

    def get_info(self): # for "info", see "ApogeeDevices".

        if (debug):
            self.level = 0
            self.mute = 0
            self.dim =  0
            self.mono = 0
            if self.Speaker == True:
                self.source = 1
                self.config = 0
            else:
                self.source = 0
        else:
            self.level = -(get_dev_value("outputLevel_Request", 0, self.index))
            self.mute = get_dev_value("outputMute_Request", 0, self.index)
            self.dim =  get_dev_value("outputDim_Request",  0, self.index)
            self.mono = get_dev_value("outputMono_Request", 0, self.index)

            if self.Speaker == True:
                self.source = get_dev_value("output_Line_Request", 0, self.index)
                self.config = get_dev_value("outputConfig_Request", 0, self.index)
            else:
                self.source = get_dev_value("outputSource_Request", 0,
                                            Apogeeinfo["outputSource_Dest"][self.index])

            
    def update(self):
        self.get_info()

        self.Level.SetValue(self.level)
        if self.Speaker == True:
            self.Source.SetSelection(Apogeeinfo["output_SpChoiceToIndex"][self.source])
            self.Config.SetSelection(self.config)
        else:
            self.Source.SetSelection(self.source)
        self.Mute.SetValue(self.mute)
        self.Dim.SetValue(self.dim)
        self.Mono.SetValue(self.mono)
        
    def on_output_level_changed(self, event):
        set_dev_value("outputLevel_Request", 0, self.index,
                      Apogeeinfo["outputLevel_Range"]["Max"] - event.GetPosition())

    def on_output_source_changed(self, event):
        if self.Speaker == True:
            set_dev_value("output_Line_Request",
                          0,
                          0,
                          Apogeeinfo["output_SpSelectIndex"][event.GetSelection()])
        else:
            set_dev_value("outputSource_Request",
                          0,
                          Apogeeinfo["outputSource_Dest"][self.index],
                          event.GetSelection())

    def on_mute_toggled(self, event):
        set_dev_value("outputMute_Request", 0, self.index, event.GetInt())

    def on_dim_toggled(self, event):
        set_dev_value("outputDim_Request", 0, self.index, event.GetInt())

    def on_mono_toggled(self, event):
        set_dev_value("outputMono_Request", 0, self.index, event.GetInt())

    def on_output_config_changed(self, event):
        set_dev_value("outputConfig_Request", 0, 0, event.GetSelection())


class linePanel(wx.Panel):

    def __init__(self, parent, deviceindex = None):
        wx.Panel.__init__(self, parent, id = wx.Window.NewControlId())

        self.parent = parent
        self.index = deviceindex

        self.source = None
        self.lineLevel = None
        self.lineIndex = Apogeeinfo["outputSource_Dest"][self.index] * 2 # [0, (not used), 4, 2]
        
        box = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(box)
        
        destTitle = Apogeeinfo["line_Name"][self.index]

        self.Title =  wx.StaticText(self, label=destTitle, style = wx.ALIGN_CENTRE)
        self.SourceTitle =  wx.StaticText(self, label="Source", style = wx.ALIGN_CENTRE)
        self.Source = wx.Choice(self, wx.Window.NewControlId(),
                                choices=Apogeeinfo["outputSourceChoice"])
        self.LineLevel = wx.Choice(self, wx.Window.NewControlId(),
                                   choices=Apogeeinfo["outputLineLevelChoice"])

        box.Add(self.Title, flag=wx.EXPAND)
        box.AddSpacer(borderValue)
        box.Add(self.SourceTitle, flag=wx.EXPAND)
        box.Add(self.Source, flag=wx.EXPAND)
        box.Add(self.LineLevel, flag=wx.EXPAND)

        if (debug == False):
            self.Source.Bind(wx.EVT_CHOICE, self.on_output_source_changed)
            self.LineLevel.Bind(wx.EVT_CHOICE, self.on_line_level_changed)

        self.update()

    def get_output_info(self): # for "info", see "ApogeeDevices".

        if (debug):
            self.source = 0
            self.linelevel = 0
        else:
            self.source = get_dev_value("outputSource_Request", 0,
                                        Apogeeinfo["outputSource_Dest"][self.index])
            self.linelevel  = get_dev_value("outputLineLevel_Request", 0,
                                            self.lineIndex)     #  for Line [0, (not used), 4, 2]
            self.linelevel2 = get_dev_value("outputLineLevel_Request", 0,
                                            self.lineIndex + 1) #  for Line [1, (not used), 5, 3]
            if (self.linelevel != self.linelevel2):
                print ("line level of Line " + str(self.lineIndex) + ": "
                       + str(self.linelevel) + " and " + str(self.lineIndex + 1)
                       + ": " + str(self.linelevel2) + " differs!")

    def update(self):
        self.get_output_info()
        self.Source.SetSelection(self.source)
        self.LineLevel.SetSelection(self.linelevel)

    def on_output_source_changed(self, event):
        set_dev_value("outputSource_Request", 0, Apogeeinfo["outputSource_Dest"][self.index],
                      event.GetSelection())

    def on_line_level_changed(self, event):
        set_dev_value("outputLineLevel_Request", 0, self.lineIndex,     event.GetSelection())
        set_dev_value("outputLineLevel_Request", 0, self.lineIndex + 1, event.GetSelection())

class outputPanel(wx.Panel):

    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        box = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(box)
        self.panel = []

        sp = speakerPanel(self, speaker = True)
        self.panel.append(sp)

        hp = speakerPanel(self, speaker = False) # headphone
        self.panel.append(hp)

        box.Add(sp, flag=wx.EXPAND |  wx.BOTTOM | wx.TOP | wx.LEFT | wx.RIGHT, border=borderValue)
        box.Add(hp, flag=wx.EXPAND |  wx.BOTTOM | wx.TOP | wx.LEFT | wx.RIGHT, border=borderValue)

        for index in Apogeeinfo["output_Line_Index"] :# [0, 3, 2]
            p = linePanel(self, deviceindex = index)
            box.Add(p, flag=wx.EXPAND |  wx.BOTTOM | wx.TOP | wx.LEFT | wx.RIGHT, border=borderValue)
            self.panel.append(p)

        #self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.Layout()
        #self.Show()

    def update(self):
        for each in self.panel:
            each.update()

        self.Layout()
            

class outputWindow(wx.Frame):

    def __init__(self, parent, mainbody):
        self.mainbody = mainbody
        wx.Frame.__init__(self, parent, size = outputWindowSize)
        self.SetTitle(Apogeeinfo["ProductName"] + ": Outputs")
        box = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(box)

        self.panel = outputPanel(self)

        box.Add(self.panel, flag=wx.EXPAND |  wx.BOTTOM | wx.TOP | wx.LEFT | wx.RIGHT,
                border=borderValue)

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # menu part

        menuBar = wx.MenuBar()

        fileMenu = wx.Menu()

        menuAbout = fileMenu.Append(wx.ID_ABOUT, "&About"," Information about this program")
        fileMenu.AppendSeparator()
        menuExit = fileMenu.Append(wx.ID_EXIT,"&Exit"," Terminate this program")
        
        viewMenu = wx.Menu()

        #menuOutput = viewMenu.Append(wx.ID_ANY, "Toggle window/tab: &Outputs \tCTRL-O","")
        menuInput = viewMenu.Append(wx.ID_ANY, "Toggle window/tab: &Inputs \tCTRL-I","")
        menuMixer = viewMenu.Append(wx.ID_ANY, "Toggle window/tab: &Mixer \tCTRL-M","")

        menuBar.Append(fileMenu, "&File")
        menuBar.Append(viewMenu, "&View")
        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)
        self.Bind(wx.EVT_MENU, self.OnAbout, menuAbout)
        #self.Bind(wx.EVT_MENU, self.OnMenuOut, menuOutput)
        self.Bind(wx.EVT_MENU, self.OnMenuIn, menuInput)
        self.Bind(wx.EVT_MENU, self.OnMenuMix, menuMixer)

        self.Layout()
        #self.Show()

    def OnAbout(self, e):
        dlg = wx.MessageBox("Apogee Devices Control Panel\n\n"
                            "built on WxPython and PyUSB\n\n"
                            "Thanks to take_control by stefanocoding", programName)

    def OnMenuIn(self, e):
        if (self.mainbody.inputSection.Show(True) == False):
            self.mainbody.inputSection.Show(False)
            self.mainbody.inputP.Show(True)
        else:
            self.mainbody.inputP.Show(False)
        
    def OnMenuOut(self, e):
        if (self.mainbody.outputSection.Show(True) == False):
            self.mainbody.outputSection.Show(False)
            self.mainbody.outputP.Show(True)
        else:
            self.mainbody.outputP.Show(False)
        
    def OnMenuMix(self, e):
        if (self.mainbody.mixerSection.Show(True) == False):
            self.mainbody.mixerSection.Show(False)
            for each in self.mainbody.mplist:
                each.Show(True)
        else:
            for each in self.mainbody.mplist:
                each.Show(False)
        
    def OnExit(self, e):
        # do not forget to close the update loop (thread)
        self.mainbody.event.set()
        self.mainbody.Close(True)
        exit(0)

    def update(self):
        self.panel.update()

        self.Layout()
        #self.Show()
        
    def OnClose(self, event):
        self.OnMenuOut(event)
        #self.Hide()
            

class mainWindow(wx.Frame):

    def __init__(self, parent, title):
        global dev
        global Apogeeinfo
        wx.Frame.__init__(self, parent, title=title, size = mainWindowSize)

        if (debug):
            Apogeeinfo = ApogeeDevices[0]
            dev = None
        else:
            find_result = self.find_device()
            if find_result is None:
                print("No Apogee device found!")
                exit(1)

            dev = find_result[0]
            Apogeeinfo =  find_result[1]

        print(Apogeeinfo["ProductName"] + " found!")

        self.SetTitle(Apogeeinfo["ProductName"] + " Control Panel")

        self.notebook = wx.Notebook(self)
        #self.mainPanel = wx.Panel(self.notebook)
        self.outputP = outputPanel(self.notebook)
        self.inputP = inputsPanel(self.notebook)

        pageIndex = 0
        #self.notebook.InsertPage(pageIndex, self.mainPanel, "Main")
        #pageIndex = pageIndex + 1
        self.notebook.InsertPage(pageIndex, self.outputP, "Outputs")
        pageIndex = pageIndex + 1
        self.notebook.InsertPage(pageIndex, self.inputP, "Inputs")
        pageIndex = pageIndex + 1
        
        self.mplist = [] # list of mixer panels
        for mixerindex in range(0, Apogeeinfo["mixer_Num"]):
            mp = mixerPanel(self.notebook, mixerindex) # a mixer panel
            self.mplist.append(mp)                     # mp added to mplist
            self.notebook.InsertPage(pageIndex, mp, "Mixer " + str(mixerindex + 1))
            pageIndex = pageIndex + 1

        self.inputSection = inputWindow(self, self)
        self.outputSection = outputWindow(self, self)
        self.mixerSection =mixerWindow(self, self)

        # menu part

        menuBar = wx.MenuBar()

        fileMenu = wx.Menu()

        menuAbout = fileMenu.Append(wx.ID_ABOUT, "&About"," Information about this program")
        fileMenu.AppendSeparator()
        menuExit = fileMenu.Append(wx.ID_EXIT,"&Exit"," Terminate this program")
        
        viewMenu = wx.Menu()

        #menuOutput = viewMenu.Append(wx.ID_ANY, "Toggle window/tab: &Outputs \tCTRL-O","")
        menuInput = viewMenu.Append(wx.ID_ANY, "Toggle window/tab: &Inputs \tCTRL-I","")
        menuMixer = viewMenu.Append(wx.ID_ANY, "Toggle window/tab: &Mixer \tCTRL-M","")
        menuDMixer = viewMenu.Append(wx.ID_ANY, "Toggle &Digital Input display in Mixer \tCTRL-D","")

        menuBar.Append(fileMenu, "&File")
        menuBar.Append(viewMenu, "&View")
        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)
        self.Bind(wx.EVT_MENU, self.OnAbout, menuAbout)
        #self.Bind(wx.EVT_MENU, self.OnMenuOut, menuOutput)
        self.Bind(wx.EVT_MENU, self.OnMenuIn, menuInput)
        self.Bind(wx.EVT_MENU, self.OnMenuMix, menuMixer)
        self.Bind(wx.EVT_MENU, self.OnMenuDMix, menuDMixer)

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.Layout()
        #self.inputSection.Show()
        #self.outputSection.Show()
        #self.mixerSection.Show()
        self.Show()

        # periodically update, using threading.
        # "Close" button sends an event to terminate the looping thread.

        self.event = threading.Event()
        thread = threading.Thread(target = self.periodic_update)
        thread.start()
        
    def periodic_update(self):
        while not self.event.wait(timeout = updateInterval):
            if (debug == False):
                self.update()

    def find_device(self):
        dev = None
        for apogeeinfo in ApogeeDevices:
            dev = usb.core.find(idVendor = apogeeinfo["VendorID"],
                                idProduct = apogeeinfo["ProductID"])
        if (dev != None):
            return [dev, apogeeinfo]

        return None

    def OnAbout(self, e):
        dlg = wx.MessageBox("Apogee Devices Control Panel\n\n"
                            "built on WxPython and PyUSB\n\n"
                            "Thanks to take_control by stefanocoding", programName)

    def OnMenuIn(self, e):
        if (self.inputSection.Show(True) == False):
            self.inputSection.Show(False)
            self.inputP.Show(True)
        else:
            self.inputP.Show(False)
        
    def OnMenuOut(self, e):
        if (self.outputSection.Show(True) == False):
            self.outputSection.Show(False)
            self.outputP.Show(True)
        else:
            self.outputP.Show(False)
        
    def OnMenuDMix(self, e):
        for each in self.mplist:
            each.toggle_dInput()

    def OnMenuMix(self, e):
        if (self.mixerSection.Show(True) == False):
            self.mixerSection.Show(False)
            for each in self.mplist:
                each.Show(True)
        else:
            for each in self.mplist:
                each.Show(False)
        

    def update(self):
        self.inputSection.update()
        self.outputSection.update()
        #self.mixerSection.update() # mixer setting cannot be changed by HW - maybe no need to update
        self.inputP.update()
        self.outputP.update()
        #for each in self.mplist:
        #    each.update()

    def OnClose(self, e):
        # do not forget to close the update loop (thread)
        self.event.set()
        e.Skip()
        
    def OnExit(self, e):
        # do not forget to close the update loop (thread)
        self.event.set()
        self.Close(True)
        exit(0)

app = wx.App(False)
frame = mainWindow(None, programName)
app.MainLoop()

