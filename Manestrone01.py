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

import usb.core
import usb.util
import wx
import threading

programName = "Manestrone"
debug = False # just for GUI visual checking (no apogee device needed)
disable_mixer = True # as most elements cannot be controlled...
borderValue = 10
inputWindowSize = (770,280)
outputWindowSize = (770,330)
mixerWindowSize = (1140,540)
mainWindowSize = (450,160)
updateInterval = 0.2 # interval for periodic information update of the device

def get_dev_value(self, device, request, wValue = 0, wIndex = 0):
    return device.ctrl_transfer(0xc0, self.apogeeinfo[request], wValue, wIndex, 1)[0]

def set_dev_value(self, device, request, wValue = 0, wIndex = 0, msg = None):
    device.ctrl_transfer(0x40, self.apogeeinfo[request], wValue, wIndex, [msg])

class stripPanel(wx.Panel):

    def __init__(self, parent, apogeeinfo = None, dev = None, mixerindex = None, channel = None, title = None, grandpa = None):
        wx.Panel.__init__(self, parent, id = wx.Window.NewControlId())

        self.grandpa = grandpa
        self.apogeeinfo = apogeeinfo
        self.dev = dev
        self.mixerindex = mixerindex
        self.index = channel
        self.title = title # "Software Return" or "Output"

        self.source = 0
        self.level = 0
        self.pan = 0
        self.solo = 0
        self.mute = 0

        box = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(box)

        if (self.title == None):
            self.title = "Input " + str(channel + 1)
        self.Title =  wx.StaticText(self, label=self.title, style = wx.ALIGN_CENTRE)

        self.LevelTitle =  wx.StaticText(self, label="Level", style = wx.ALIGN_CENTRE)
        self.Level = wx.SpinCtrl(self, wx.Window.NewControlId())
        self.Level.SetRange(apogeeinfo["mixerLevel_Min"], apogeeinfo["mixerLevel_Max"]) # Level(-48 - +6) <=> self.level(0-64)

        if (self.title == "Software Return"):
            self.secondTitle =  wx.StaticText(self, label="Source", style = wx.ALIGN_CENTRE)
        else:
            if (self.title == "Output"):
                self.secondTitle =  wx.StaticText(self, label="", style = wx.ALIGN_CENTRE)
            else:
                self.secondTitle =  wx.StaticText(self, label="Pan", style = wx.ALIGN_CENTRE) # Inputs

        self.Source = wx.Choice(self, wx.Window.NewControlId(),choices=apogeeinfo["mixerSoftRtnChoice"])
        self.Pan = wx.SpinCtrl(self, wx.Window.NewControlId())
        self.Pan.SetRange(apogeeinfo["mixerPan_Min"], apogeeinfo["mixerPan_Max"]) # Pan(-64 - +64) <=> self.pan(0-128)
        self.Solo = wx.ToggleButton(self, wx.Window.NewControlId(), label='Solo')
        self.Mute = wx.ToggleButton(self, wx.Window.NewControlId(), label='Mute')

        # adding parts to the "box" (vertical boxsizer)
        lst = [self.Title,
               None,
               self.LevelTitle,
               self.Level,
               None,
               self.secondTitle,
               self.Source,
               self.Pan,
               self.Solo,
               self.Mute]

        for each in lst:
            if each == None:
                box.AddSpacer(borderValue)
            else:
                box.Add(each, flag=wx.EXPAND)

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

    def get_mixer_info(self): # for "info", see "ApogeeDevices".
        dev = self.dev

        if (debug):
            self.source = 0
            self.level = 0
            self.pan = 0
            self.solo = 0
            self.mute = 0
        else:
            self.source = get_dev_value(dev, "mixerSoftRtn_Request", 0, self.mixerindex)
            self.level = get_dev_value(dev, "mixerLevel_Request", self.mixerindex, self.index)
            self.pan = get_dev_value(dev, "mixerPan_Request", self.mixerindex, self.index)
            self.solo = get_dev_value(dev, "mixerSolo_Request", self.mixerindex, self.index)
            self.mute = get_dev_value(dev, "mixerMute_Request", self.mixerindex, self.index)

        if (self.title == "Software Return"):
            self.Pan.Hide()
            self.Layout()
        else:
            if (self.title == "Output"):
                self.Source.Hide()
                self.Pan.Hide()
                self.Solo.Hide()
                self.Mute.Hide()
                self.Layout()
            else:
                self.Source.Hide()
                self.Layout()

    def update(self):
        self.get_mixer_info()
        self.Source.SetSelection(self.source)
        self.Level.SetValue(self.level + self.apogeeinfo["mixerLevel_Min"])#  - 48)
        if (self.title != "Output"):
            self.Pan.SetValue(self.pan + self.apogeeinfo["mixerPan_Min"]) # -64
            self.Solo.SetValue(self.solo)
            self.Mute.SetValue(self.mute)


    def on_source_changed(self, event):
        set_dev_value(self.dev, "mixerSoftRtn_Request", 0, self.mixerindex,  event.GetSelection())
        self.grandpa.update()

    def on_mixer_level_changed(self, event):
        set_dev_value(self.dev, "mixerLevel_Request", self.mixerindex, self.index, event.GetPosition() - self.apogeeinfo["mixerLevel_Min"]) # + 48
        self.grandpa.update()

    def on_mixer_pan_changed(self, event):
        set_dev_value(self.dev, "mixerPan_Request", self.mixerindex, self.index, event.GetPosition() - self.apogeeinfo["mixerPan_Min"]) # + 64
        self.grandpa.update()

    def on_solo_toggled(self, event):
        set_dev_value(self.dev, "mixerSolo_Request", self.mixerindex, self.index, event.GetInt())
        self.grandpa.update()

    def on_mute_toggled(self, event):
        set_dev_value(self.dev, "mixerMute_Request", self.mixerindex, self.index, event.GetInt())
        self.grandpa.update()


class mixerWindow(wx.Frame):

    def __init__(self, parent, apogeeinfo = None, dev = None, num = None):
        wx.Frame.__init__(self, parent, size = mixerWindowSize)

        self.parent = parent
        self.SetTitle(apogeeinfo["ProductName"] + ": Mixer" )
        vbox = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(vbox)
            
        self.splist = [] # list of mixer strip panels
        mixerindex = 0
        while (mixerindex < num):

            mtitle =  wx.StaticText(self, label="Mixer " + str(mixerindex), style = wx.ALIGN_CENTRE)
            mp = wx.Panel(self) # a mixer panel

            hbox = wx.BoxSizer(wx.HORIZONTAL)
            mp.SetSizer(hbox)

            vbox.AddSpacer(borderValue)
            vbox.Add(mtitle, flag=wx.EXPAND |  wx.TOP | wx.LEFT | wx.RIGHT, border=borderValue)
            vbox.Add(mp, flag=wx.EXPAND)

            softRtnPanel = stripPanel(mp, apogeeinfo, dev, mixerindex,                   # soft return panel follows
                                      channel = apogeeinfo["mixerChannel_Other"][0][1],
                                      title = apogeeinfo["mixerChannel_Other"][0][0], grandpa = self) # software return source
            self.splist.append(softRtnPanel)
            hbox.Add(softRtnPanel, flag=wx.EXPAND |  wx.BOTTOM | wx.LEFT | wx.RIGHT, border=borderValue)

            channel = 0
            while (channel < apogeeinfo["mixerChannel_Num"]):                  # strips are produced per channel
                sp = stripPanel(mp, apogeeinfo, dev, mixerindex, channel, grandpa = self) # a strip(panel)
                hbox.Add(sp, flag=wx.EXPAND |  wx.BOTTOM | wx.LEFT | wx.RIGHT, border=borderValue)
                self.splist.append(sp)                                           # sp added to splist
                channel  = channel + 1

            masterPanel = stripPanel(mp, apogeeinfo, dev, mixerindex,
                                     channel = apogeeinfo["mixerChannel_Other"][1][1],
                                     title = apogeeinfo["mixerChannel_Other"][1][0], grandpa = self) # output
            self.splist.append(masterPanel)
            hbox.Add(masterPanel, flag=wx.EXPAND |  wx.BOTTOM  | wx.LEFT | wx.RIGHT, border=borderValue)

            mp.Layout()
            mixerindex = mixerindex + 1

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.Layout()
        #self.Show()

    def update(self):
        for each in self.splist:
            each.update()

    def OnClose(self, event):
        self.Hide()

class inputPanel(wx.Panel):

    def __init__(self, parent, apogeeinfo = None, dev = None, deviceindex = None):
        wx.Panel.__init__(self, parent, id = wx.Window.NewControlId())

        self.parent = parent
        self.apogeeinfo = apogeeinfo
        self.dev = dev
        self.index = deviceindex

        self.itype = None
        self.softlimit = None
        self.phantom = None
        self.miclevel = None
        self.instlevel = None
        self.group = None

        box = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(box)

        self.Title =  wx.StaticText(self, label="Input " + str(deviceindex + 1), style = wx.ALIGN_CENTRE)
        self.Type = wx.Choice(self, wx.Window.NewControlId(),choices=apogeeinfo["inputType"])

        self.MicLevel = wx.SpinCtrl(self, wx.Window.NewControlId())
        self.MicLevel.SetRange(apogeeinfo["micLevel_Min"], apogeeinfo["micLevel_Max"]) 

        self.InstLevel = wx.SpinCtrl(self, wx.Window.NewControlId())
        self.InstLevel.SetRange(apogeeinfo["instLevel_Min"], apogeeinfo["instLevel_Max"]) 

        self.SoftLimit = wx.ToggleButton(self, wx.Window.NewControlId(), label='Soft Limit')
        self.Phase = wx.ToggleButton(self, wx.Window.NewControlId(), label='Phase')
        self.Phantom = wx.ToggleButton(self, wx.Window.NewControlId(), label='48V')
        self.Group = wx.Choice(self, wx.Window.NewControlId(),choices=apogeeinfo["inputGroupChoice"])

        # adding parts to the "box" (vertical boxsizer)

        lst = [self.Title,
               self.Type,
               self.MicLevel,
               self.InstLevel,
               self.SoftLimit,
               self.Phase,
               self.Phantom,
               self.Group]

        for each in lst:
            if each == None:
                box.AddSpacer(borderValue)
            else:
                box.Add(each, flag=wx.EXPAND)

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
        dev = self.dev

        if (debug):
            self.itype = 0
            self.softlimit = 0
            self.phantom = 0
            self.miclevel = 0
            self.instlevel = 0
            self.group = 0
        else:
            self.itype = get_dev_value(dev, "inputType_Request", 0, self.index)
            self.softlimit = get_dev_value(dev, "softLimit_Request", 0, self.index)
            self.phantom = get_dev_value(dev, "phantom_Request", 0, self.index)
            self.miclevel = get_dev_value(dev, "micLevel_Request", 0, self.index)
            self.instlevel = get_dev_value(dev, "instLevel_Request", 0, self.index)
            self.group = get_dev_value(dev, "inputGroup_Request", 0, self.index)

    def update(self):
        self.get_input_info()
        self.MicLevel.SetValue(self.miclevel)
        self.InstLevel.SetValue(self.instlevel)
        self.Type.SetSelection(self.itype)
        self.SoftLimit.SetValue(self.softlimit)
        self.Group.SetSelection(self.group)

        if self.apogeeinfo["inputType"][self.itype] == "Microphone":
            self.MicLevel.Show()
            self.InstLevel.Hide()
            self.Layout()
            self.Phantom.Enable()
            self.Phantom.SetValue(self.phantom)
        else:
            self.MicLevel.Hide()
            self.InstLevel.Show()
            if (self.apogeeinfo["inputType"][self.itype] == "Instrument"):
                self.InstLevel.Enable()
            else: # Line
                self.InstLevel.Disable()
            self.Phantom.Disable()
        
    def on_input_level_changed(self, event):
        set_dev_value(self.dev, "instLevel_Request", 0, self.index, event.GetPosition())
        set_dev_value(self.dev, "micLevel_Request", 0, self.index, event.GetPosition())
        self.parent.update()

    def on_input_type_changed(self, event):
        set_dev_value(self.dev, "inputType_Request", 0, self.index, event.GetSelection())

        self.get_input_info()
        if self.apogeeinfo["inputType"][self.itype] != "Microphone":
            self.Phantom.Disable()
        else:
            self.Phantom.Enable()
            self.Phantom.SetValue(self.phantom)

        self.parent.update()

    def on_softlimit_toggled(self, event):
        set_dev_value(self.dev, "softLimit_Request", 0, self.index, event.GetInt())
        self.parent.update()

    def on_phase_toggled(self, event):
        set_dev_value(self.dev, "phase_Request", 0, self.index, event.GetInt())
        self.parent.update()

    def on_phantom_toggled(self, event):
        set_dev_value(self.dev, "phantom_Request", 0, self.index, event.GetInt())
        self.parent.update()

    def on_input_group_changed(self, event):
        set_dev_value(self.dev, "inputGroup_Request", 0, self.index, event.GetSelection())
        self.parent.update()



class inputWindow(wx.Frame):

    def __init__(self, parent, apogeeinfo = None, dev = None):
        wx.Frame.__init__(self, parent, size = inputWindowSize)

        self.parent = parent
        self.SetTitle(apogeeinfo["ProductName"] + ": Inputs")
        box = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(box)
        self.panel = []

        deviceindex = 0
        while (deviceindex < apogeeinfo["InputNum"]):
            p = inputPanel(self, apogeeinfo, dev, deviceindex)
            box.Add(p, flag=wx.EXPAND |  wx.BOTTOM | wx.TOP | wx.LEFT | wx.RIGHT, border=borderValue)
            self.panel.append(p)
            deviceindex = deviceindex + 1

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.Layout()
        #self.Show()

    def update(self):
        for each in self.panel:
            each.update()
    
    def OnClose(self, event):
        self.Hide()


class speakerPanel(wx.Panel): # used for both speaker and headphone

    def __init__(self, parent, apogeeinfo = None, dev = None, index = None):
        wx.Panel.__init__(self, parent, id = wx.Window.NewControlId())

        self.parent = parent
        self.apogeeinfo = apogeeinfo
        self.dev = dev
        self.index = index
        if (self.index == apogeeinfo["output_Speaker_Index"]):
            self.Speaker = True
        else:
            if self.index == apogeeinfo["output_Headphone_Index"]:
                self.Speaker = False
            else:
                print("speakerPanel: index should indicate either speaker or headphone! index = " + str(self.index))
                exit(1)

        self.source = None # in case of Speaker, this indicate line pair which sends audio to speakers
        self.level = None
        self.mute = None
        self.dim = None
        self.mono = None
        self.config = None # speaker configuration
        
        box = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(box)

        if self.Speaker == True:
            title = "Speaker"
            source_title = "Choice"
            source_choice = "output_LineNameChoice"
        else:
            title = "Headphone"
            source_title = "Source"
            source_choice = "outputSourceChoice"
            
        self.Title =  wx.StaticText(self, label=title, style = wx.ALIGN_CENTRE)
        self.SourceTitle =  wx.StaticText(self, label=source_title, style = wx.ALIGN_CENTRE)
        self.Source = wx.Choice(self, wx.Window.NewControlId(),choices=apogeeinfo[source_choice])

        self.Level = wx.SpinCtrl(self, wx.Window.NewControlId())
        self.Level.SetRange(apogeeinfo["outputLevel_Min"], apogeeinfo["outputLevel_Max"]) 

        self.Mute = wx.ToggleButton(self, wx.Window.NewControlId(), label = "Mute")
        self.Dim = wx.ToggleButton(self, wx.Window.NewControlId(), label = "Dim")
        self.Mono = wx.ToggleButton(self, wx.Window.NewControlId(), label = "Mono")

        # adding parts to the "box" (vertical boxsizer)
        lst = [self.Title,
               None,
               self.SourceTitle,
               self.Source,
               self.Level,
               self.Mute,
               self.Dim,
               self.Mono]

        if self.Speaker == True:
            self.ConfigTitle =  wx.StaticText(self, label="Configuration", style = wx.ALIGN_CENTRE)
            self.Config = wx.Choice(self, wx.Window.NewControlId(),choices=apogeeinfo["outputConfigChoice"])
            lst.append(None)
            lst.append(self.ConfigTitle)
            lst.append(self.Config)

        for each in lst:
            if each == None:
                box.AddSpacer(borderValue)
            else:
                box.Add(each, flag=wx.EXPAND)

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
        dev = self.dev

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
            self.level = -(get_dev_value(dev, "outputLevel_Request", 0, self.index))
            self.mute = get_dev_value(dev, "outputMute_Request", 0, self.index)
            self.dim =  get_dev_value(dev, "outputDim_Request",  0, self.index)
            self.mono = get_dev_value(dev , "outputMono_Request", 0, self.index)

            if self.Speaker == True:
                self.source = get_dev_value(dev, "output_Line_Request", 0, self.index)
                self.config = get_dev_value(dev, "outputConfig_Request", 0, self.index)
            else:
                self.source = get_dev_value(dev, "outputSource_Request", 0, self.apogeeinfo["outputSource_Dest"][self.index])

            
    def update(self):
        self.get_info()

        self.Level.SetValue(self.level)
        if self.Speaker == True:
            self.Source.SetSelection(self.apogeeinfo["output_SpChoiceToIndex"][self.source])
            self.Config.SetSelection(self.config)
        else:
            self.Source.SetSelection(self.source)
        self.Mute.SetValue(self.mute)
        self.Dim.SetValue(self.dim)
        self.Mono.SetValue(self.mono)
        
    def on_output_level_changed(self, event):
        set_dev_value(self.dev, "outputLevel_Request", 0, self.index, self.apogeeinfo["outputLevel_Max"] - event.GetPosition())
        self.parent.update()

    def on_output_source_changed(self, event):
        if self.Speaker == True:
            set_dev_value(self.dev, "output_Line_Request", 0, 0, self.apogeeinfo["output_SpSelectIndex"][event.GetSelection()])
        else:
            set_dev_value(self.dev, "outputSource_Request", 0, self.apogeeinfo["outputSource_Dest"][self.index], event.GetSelection())

        self.parent.update()

    def on_mute_toggled(self, event):
        set_dev_value(self.dev, "outputMute_Request", 0, self.index, event.GetInt())
        self.parent.update()

    def on_dim_toggled(self, event):
        set_dev_value(self.dev, "outputDim_Request", 0, self.index, event.GetInt())
        self.parent.update()

    def on_mono_toggled(self, event):
        set_dev_value(self.dev, "outputMono_Request", 0, self.index, event.GetInt())
        self.parent.update()

    def on_output_config_changed(self, event):
        set_dev_value(self.dev, "outputConfig_Request", 0, 0, event.GetSelection())
        self.parent.update()



class linePanel(wx.Panel):

    def __init__(self, parent, apogeeinfo = None, dev = None, deviceindex = None):
        wx.Panel.__init__(self, parent, id = wx.Window.NewControlId())

        self.parent = parent
        self.apogeeinfo = apogeeinfo
        self.dev = dev
        self.index = deviceindex

        self.source = None
        self.lineLevel = None
        self.lineIndex = apogeeinfo["outputSource_Dest"][self.index] * 2 # [0, (not used), 4, 2]
        
        box = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(box)
        
        destTitle = apogeeinfo["line_Name"][self.index]

        self.Title =  wx.StaticText(self, label=destTitle, style = wx.ALIGN_CENTRE)
        self.SourceTitle =  wx.StaticText(self, label="Source", style = wx.ALIGN_CENTRE)
        self.Source = wx.Choice(self, wx.Window.NewControlId(),choices=apogeeinfo["outputSourceChoice"])
        self.LineLevel = wx.Choice(self, wx.Window.NewControlId(),choices=apogeeinfo["outputLineLevelChoice"])

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
        dev = self.dev

        if (debug):
            self.source = 0
            self.linelevel = 0
        else:
            self.source = get_dev_value(dev, "outputSource_Request", 0, self.apogeeinfo["outputSource_Dest"][self.index])
            self.linelevel =  get_dev_value(dev, "outputLineLevel_Request", 0, self.lineIndex)#  for Line [0, (not used), 4, 2]
            self.linelevel2 = get_dev_value(dev, "outputLineLevel_Request", 0, self.lineIndex + 1)#  for Line [1, (not used), 5, 3]
            if (self.linelevel != self.linelevel2):
                print ("line level of Line " + str(self.lineIndex) + ": " + str(self.linelevel) + " and " + str(self.lineIndex + 1) + ": " + str(self.linelevel2) + " differs!")

    def update(self):
        self.get_output_info()
        self.Source.SetSelection(self.source)
        self.LineLevel.SetSelection(self.linelevel)

    def on_output_source_changed(self, event):
        set_dev_value(self.dev, "outputSource_Request", 0, self.apogeeinfo["outputSource_Dest"][self.index], event.GetSelection())
        self.parent.update()

    def on_line_level_changed(self, event):
        set_dev_value(self.dev, "outputLineLevel_Request", 0, self.lineIndex,     event.GetSelection())
        set_dev_value(self.dev, "outputLineLevel_Request", 0, self.lineIndex + 1, event.GetSelection())
        self.parent.update()

class outputWindow(wx.Frame):

    def __init__(self, parent, apogeeinfo = None, dev = None):
        wx.Frame.__init__(self, parent, size = outputWindowSize)
        self.apogeeinfo = apogeeinfo
        self.SetTitle(apogeeinfo["ProductName"] + ": Outputs")
        box = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(box)
        self.panel = []

        sp = speakerPanel(self, apogeeinfo, dev, index = apogeeinfo["output_Speaker_Index"])
        self.panel.append(sp)

        hp = speakerPanel(self, apogeeinfo, dev, index = apogeeinfo["output_Headphone_Index"])
        self.panel.append(hp)

        box.Add(sp, flag=wx.EXPAND |  wx.BOTTOM | wx.TOP | wx.LEFT | wx.RIGHT, border=borderValue)
        box.Add(hp, flag=wx.EXPAND |  wx.BOTTOM | wx.TOP | wx.LEFT | wx.RIGHT, border=borderValue)

        for index in apogeeinfo["output_Line_Index"] :# [0, 3, 2]
            p = linePanel(self, apogeeinfo, dev, deviceindex = index)
            box.Add(p, flag=wx.EXPAND |  wx.BOTTOM | wx.TOP | wx.LEFT | wx.RIGHT, border=borderValue)
            self.panel.append(p)

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.Layout()
        #self.Show()

    def update(self):
        for each in self.panel:
            each.update()

        self.Layout()
        #self.Show()
        
    def OnClose(self, event):
        self.Hide()
            
class mainWindow(wx.Frame):

    def __init__(self, parent, title):
        wx.Frame.__init__(self, parent, title=title, size = mainWindowSize)

        # vendor ID, product ID, product name, number of input, output.
        Quartet = {}
        Quartet["VendorID"] = 0x0c60
        Quartet["ProductID"] = 0x0014
        Quartet["ProductName"] = "Apogee Quartet"
        Quartet["InputNum"] = 4

        Quartet["inputType"] = ["Line  +4dB", "Line -10dB", "Microphone", "Instrument"]
        Quartet["softLimit_Request"] = 17
        Quartet["phase_Request"] = 19
        Quartet["phantom_Request"] = 21
        Quartet["inputType_Request"] = 22
        Quartet["micLevel_Request"] = 52
        Quartet["micLevel_Min"] = 0 
        Quartet["micLevel_Max"] = 75
        Quartet["instLevel_Request"] = 62
        Quartet["instLevel_Min"] = 0 
        Quartet["instLevel_Max"] = 65
        Quartet["inputGroup_Request"] = 68
        Quartet["inputGroupChoice"] = ["Group OFF", "Group 1", "Group2 "]

        Quartet["outputSourceChoice"] = ["Output 1/2", "Output 3/4", "Output 5/6", "Output 7/8", "Mixer    1",  "Mixer    2"] 
        Quartet["outputLineLevelChoice"] = ["+ 4dBV", "-10dBV"]
        Quartet["outputLevel_Min"] = -64
        Quartet["outputLevel_Max"] =   0
        Quartet["outputSource_Request"] = 83
        Quartet["outputLevel_Request"] = 51
        Quartet["outputMute_Request"] = 53
        Quartet["outputDim_Request"] = 64
        Quartet["outputMono_Request"] = 70
        Quartet["outputConfig_Request"] = 69
        Quartet["outputConfigChoice"] = ["Line", "Stereo", "2 Speaker Sets", "3 Speaker Sets", "5.1"]
        Quartet["outputLineLevel_Request"] = 182
        Quartet["output_Line_Request"] = 71
        Quartet["output_Speaker_Index"] = 0
        Quartet["output_Headphone_Index"] = 1
        Quartet["output_LineNameChoice"] = ["Line 1/2", "Line 3/4", "Line 5/6"] 
        Quartet["output_Line_Index"] = [0, 3, 2]
        Quartet["output_SpSelectIndex"] = [1, 2, 4]
        Quartet["output_SpChoiceToIndex"] = {1:0, 2:1, 4:2}
        Quartet["line_Name"] = ["Line 1/2", "Headphone", "Line 5/6", "Line 3/4"]
        Quartet["outputSource_Dest"] = [0 ,3, 2, 1] # line1/2:index0,  headphone:index3, line 5/6:index2, line3/4:index1

        Quartet["mixer_Num"] =  2 # wValue = 0, 1
        Quartet["mixerChannel_Num"] =  4 # actually it is 12, but I do not use ADAT input, so 4 is enough. (index 0-11) 
        Quartet["mixerChannel_Other"] =  [["Software Return", 12], ["Output",14]]

        Quartet["mixerSoftRtn_Request"] =  54 # software return source
        Quartet["mixerLevel_Request"] =  76
        Quartet["mixerPan_Request"] =  77
        Quartet["mixerSolo_Request"] =  78
        Quartet["mixerMute_Request"] =  79
        Quartet["mixerSoftRtnChoice"] =  ["Playback 1/2", "Playback 3/4",  "Playback 5/6",  "Playback 7/8"]
        Quartet["mixerLevel_Min"] =  -48
        Quartet["mixerLevel_Max"] =  6
        Quartet["mixerPan_Min"] =  -64
        Quartet["mixerPan_Max"] =  64

        self.ApogeeDevices = [Quartet]

        if (debug):
            ApogeeInfo = self.ApogeeDevices[0]
            self.dev = None
        else:
            find_result = self.find_device()
            if find_result is None:
                print("No Apogee device found!")
                exit(1)

            self.dev = find_result[0]
            ApogeeInfo =  find_result[1]

        print(ApogeeInfo["ProductName"] + " found!")

        self.SetTitle(ApogeeInfo["ProductName"] + " Control Panel")
        self.inputSection = inputWindow(self, apogeeinfo = ApogeeInfo, dev = self.dev)
        self.outputSection = outputWindow(self, apogeeinfo = ApogeeInfo, dev = self.dev)

        #mixer does not work.... mostly readonly
        self.mixerSection =mixerWindow(self, apogeeinfo = ApogeeInfo, dev = self.dev, num = ApogeeInfo["mixer_Num"])

        #  setting up GUI in the mainFrame
        vbox = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(vbox)

        ShowHidePanel = wx.Panel(self)
        ShowHideBox = wx.BoxSizer(wx.HORIZONTAL)
        ShowHidePanel.SetSizer(ShowHideBox)
        #ShowHidePanel.SetBackgroundColour("lightblue")

        ShowHidePanelTitle = wx.StaticText(ShowHidePanel, label = "Show/Hide: ")

        inputBtn = wx.Button(ShowHidePanel, wx.Window.NewControlId(), label = "Input")
        outputBtn = wx.Button(ShowHidePanel, wx.Window.NewControlId(), label = "Output")
        mixerBtn = wx.Button(ShowHidePanel, wx.Window.NewControlId(), label = "Mixer")
        #updateBtn = wx.Button(self, wx.Window.NewControlId(), label = "Update")
        exitBtn   = wx.Button(self, wx.Window.NewControlId(), label = "Exit")

        ShowHideBox.Add(ShowHidePanelTitle, 0, flag= wx.ALL, border=borderValue)
        ShowHideBox.Add(inputBtn, 0, flag= wx.ALL, border=borderValue)
        ShowHideBox.Add(outputBtn, 0, flag= wx.ALL, border=borderValue)
        ShowHideBox.Add(mixerBtn, 0, flag= wx.ALL, border=borderValue)

        #vbox.Add(updateBtn, 0, flag= wx.ALL, border=borderValue)
        vbox.Add(exitBtn, 0, flag= wx.ALL, border=borderValue)
        vbox.Add(ShowHidePanel, 0, flag= wx.ALL, border=borderValue)

        self.Bind(wx.EVT_BUTTON, self.OnInputBtn, inputBtn)
        self.Bind(wx.EVT_BUTTON, self.OnOutputBtn, outputBtn)
        self.Bind(wx.EVT_BUTTON, self.OnMixerBtn, mixerBtn)
        #self.Bind(wx.EVT_BUTTON, self.OnUpdateBtn, updateBtn)
        self.Bind(wx.EVT_BUTTON, self.OnExitBtn, exitBtn)

        self.Layout()
        self.inputSection.Show()
        self.outputSection.Show()
        self.mixerSection.Show()
        self.Show()

        # periodically update, using threading.
        # "Close" button sends an event to terminate the looping thread.

        self.event = threading.Event()
        thread = threading.Thread(target = self.periodic_update)
        thread.start()
        
    def periodic_update(self):
        while not self.event.wait(timeout = updateInterval):
            self.Update()

    def find_device(self):
        dev = None
        for apogeeinfo in self.ApogeeDevices:
            dev = usb.core.find(idVendor = apogeeinfo["VendorID"], idProduct = apogeeinfo["ProductID"])
        if (dev != None):
            return [dev, apogeeinfo]

        return None

    def OnInputBtn(self, e):
        if (self.inputSection.Show(True) == False):
            self.inputSection.Show(False)
        
    def OnOutputBtn(self, e):
        if (self.outputSection.Show(True) == False):
            self.outputSection.Show(False)
        
    def OnMixerBtn(self, e):
        if (self.mixerSection.Show(True) == False):
            self.mixerSection.Show(False)
        
    def OnUpdateBtn(self, e):
        self.Update()

    def Update(self):
        self.inputSection.update()
        self.outputSection.update()
        self.mixerSection.update()

    def OnExitBtn(self, e):
        # do not forget to close the update loop (thread)
        self.event.set()
        self.Close(True)


app = wx.App(False)
frame = mainWindow(None, programName)
app.MainLoop()

