#!/usr/bin/env python
from __future__ import print_function
import sys
import getopt
import re
import matplotlib.font_manager as fm
from matplotlib.backends.backend_pdf import PdfPages
import pylab as plt
import numpy as np
from matplotlib.path import Path
import matplotlib.patches as patches
from collections import OrderedDict
import os
import math
import random
import argparse

## Parsing arguments
parser = argparse.ArgumentParser(description='Draw multi-level bands')
parser.add_argument('filename',metavar='FILENAME')
parser.add_argument('-o','--output',dest="outfile",metavar='OUTFILE',help='Write data to OUTFILE')
parser.add_argument('--far',metavar='COLOR',help='Set COLOR of <FAR> regions',default=None)
parser.add_argument('--mid',metavar='COLOR',help='Set COLOR of <MID> regions',default='yellow')
parser.add_argument('--near',metavar='COLOR',help='Set COLOR of <NEAR> regions',default='red')
parser.add_argument('--recovery',metavar='COLOR',help='Set COLOR of <RECOVERY> regions',default='green')
parser.add_argument('--xticks',type=int,default=10,help='Number of ticks in x-axis') 
parser.add_argument('--yticks',type=int,default=10,help='Number of ticks in y-axis') 
parser.add_argument('--to360',help='Set degrees to the range [0,360]',action='store_true')
args = parser.parse_args()

try:
    infile = open(args.filename,'r')
except IOError:
    parser.error("File "+args.filename+" not found")
print("Reading %s" % args.filename)
###

outfile = args.outfile
xticks = args.xticks
yticks = args.yticks
far_color = args.far
mid_color = args.mid
near_color = args.near
rec_color = args.recovery

###

def to_180(L):
    LL = []
    for l in L:
        if l[1]<= 180:
            LL.append(l)
        elif l[0]< 180:
            LL.append([l[0], 180.0, l[2]])
            LL.append([-180.0, l[1]-360.0, l[2]])
        else:
            LL.append([l[0]-360.0, l[1]-360.0, l[2]])
    return LL

def figmaker(bounds,tick, bandl, trajl, dimension, pdffile, scene):
    plt.rc('grid', linestyle="-", color='0.7')
    fig, ax = plt.subplots()
    plt.grid()
    plt.yticks(np.arange(bounds[0],bounds[1],tick))
    time_ticks = (xtime[-1]-xtime[0])/xticks
    plt.xticks(np.arange(xtime[0],xtime[-1],time_ticks))
        
    for tmband in bandl:
        tm = tmband[0]
        for bnd in tmband[1]:
            if bnd[2] > 0:
                plt.plot([tm,tm],[bnd[0], bnd[1]],color=bands_color(bnd[2]),linestyle=bands_styles[bnd[2]],linewidth=2,label=bands_types[bnd[2]],alpha=1)
   
    if len(trajl) > 0:
        plt.plot(xtime,trajl,color=traj_color,marker=traj_style,linewidth=0.5,label=ownship, markersize = 3)

    level = 1
    while level <= most_severe_alert_level:
        x_level = []
        y_level = []
        t = 0
        while t < min(len(xtime),len(trajl)):
            try:
                alert = alert_levels_per_time[xtime[t]]
                if alert == level:
                    x_level.append(xtime[t])
                    y_level.append(trajl[t])
            except KeyError:
                None
            t += 1
        if len(x_level) > 0:
            plt.plot(x_level,y_level,color=alert_color(level),linestyle='None',marker='o',label='Alert('+str(level)+')',markersize = 2*level+1)
        level += 1
           
    plt.ylim([bounds[0], bounds[1]])
    plt.xlim([xtime[0],xtime[-1]])
    handles,labels = ax.get_legend_handles_labels()
    by_label = OrderedDict(zip(labels,handles))
    ax.legend(by_label.values(),by_label.keys(),loc='best') #'upper right')
    ax.set_title(scene+" ("+dimension[0]+")")
    ax.set_xlabel('Time [s]')
    ax.set_ylabel(dimension[0]+' Maneuver '+dimension[1])
    #ax.autoscale(enable=True,axis='both',tight=None)
    pdffile.savefig(transparent=True)
    plt.clf()

# Return a color for guidance bands
def bands_color(code):
    color = bands_colors[code]
    if color == None:
        return 'white'
    return color

# Return a color for alerting that is compatible with the color of guidance bands
def alert_color(alert):
    color = bands_colors[alert]
    i=alert
    while i < 4 and color == None:
        i += 1
    if i==4:
        color = 'red'
    return color

##
ownship = ''
scenario = ''
traj_color = 'blue'
traj_style = '+'
bands_colors = [None, far_color, mid_color, near_color, rec_color ]
bands_styles = ['-', '-', '-', '-', '--']
bands_types  = ["NONE", "FAR", "MID", "NEAR", "RECOVERY"]
trkband = []
vsband = []
altband = []
gsband =[]
xtime = []
ytrk = []
yvs = []
yalt = []
ygs = []
gs_units = 'knot'
vs_units = 'fpm'
alt_units = 'ft'
alerting_times = {}
most_severe_alert_level =0

for line in infile:
    linestr = line.strip()
    if linestr != "" and not re.match('#',linestr):
        lstln = [y.strip() for y in linestr.split(":")]
        if lstln[0] == "Ownship":
            ownship = lstln[1]
        elif lstln[0] == "Scenario":
            scenario = lstln[1]
        elif lstln[0] == "MinMaxGs":
            gs_bounds = list(map(float, re.findall(r'[+-]?[0-9.]+',lstln[1])))
            gs_units = lstln[2]
        elif lstln[0] == "MinMaxVs":
            vs_bounds = list(map(float, re.findall(r'[+-]?[0-9.]+',lstln[1])))
            vs_units = lstln[2]
        elif lstln[0] == "MinMaxAlt":
            alt_bounds = list(map(float, re.findall(r'[+-]?[0-9.]+',lstln[1])))
            alt_units = lstln[2]
        elif lstln[0] == "TrkBands":
            values = list(map(float, re.findall(r'[+-]?[0-9.]+',lstln[2])))
            if len(values) > 0:
                x = float(lstln[1])
                nn = int((len(values))/3)
                if args.to360:
                    trkband.append( [x, [ [values[3*i], values[3*i+1], int(values[3*i+2])] for i in range(int(nn))]])
                else:
                    trkband.append( [x, to_180([ [values[3*i], values[3*i+1], int(values[3*i+2])] for i in range(int(nn))])])
        elif lstln[0] == "VsBands":
            values = list(map(float, re.findall(r'[+-]?[0-9.]+',lstln[2])))
            if len(values) > 0:
                vslb = values[0]
                vsub  = values[-2]
                x = float(lstln[1])
                nn = int((len(values))/3)
                vsband.append([x, [ [values[3*i], values[3*i+1], int(values[3*i+2])] for i in range(int(nn))]])
        elif lstln[0] == "AltBands":
            values = list(map(float, re.findall(r'[+-]?[0-9.]+',lstln[2])))
            if len(values) >0:
                altlb = values[0]
                altub  = values[-2]
                x = float(lstln[1])
                nn = int((len(values))/3)
                altband.append([x,[ [values[3*i], values[3*i+1], int(values[3*i+2])] for i in range(int(nn))]])
        elif lstln[0] == "GsBands":
            values = list(map(float, re.findall(r'[+-]?[0-9.]+',lstln[2])))
            if len(values) > 0:
                gslb = values[0]
                gsub  = values[-2]
                x = float(lstln[1])
                nn = int((len(values))/3)
                gsband.append([x, [ [values[3*i], values[3*i+1], int(values[3*i+2])] for i in range(int(nn))]])
        elif lstln[0] == "Times":
            xtime = list(map(float, re.findall(r'[+-]?[0-9.]+',lstln[1])))
        elif lstln[0] == "OwnTrk":
            ytrk = list(map(float, re.findall(r'[+-]?[0-9.]+',lstln[1])))
        elif lstln[0] == "OwnVs":
            yvs = list(map(float, re.findall(r'[+-]?[0-9.]+',lstln[1])))
        elif lstln[0] == "OwnGs":
            ygs = list(map(float, re.findall(r'[+-]?[0-9.]+',lstln[1])))
        elif lstln[0] == "OwnAlt":
            yalt = list(map(float, re.findall(r'[+-]?[0-9.]+',lstln[1])))
        elif lstln[0] == "MostSevereAlertLevel":
            most_severe_alert_level = int(lstln[1])
        elif lstln[0] == "AlertingTimes":
            alerting_times[lstln[1]] = list(map(float, re.findall(r'[+-]?[0-9.]+',lstln[2])))
infile.close()

if outfile == None:
    outfile = scenario+".pdf"

print("Writing "+outfile)

alert_levels_per_time = {}

for key in alerting_times:
    i=0
    times = alerting_times[key]
    while i < len(times)-1:
        try:
            alert_levels_per_time[times[i]] = max(int(alert_levels_per_time[times[i]]),times[i+1])
        except:
            alert_levels_per_time[times[i]] = int(times[i+1])
        i += 2

with PdfPages(outfile) as pdf:
    if len(trkband)>0:
        tick_trk = 360/yticks
        degs = [-180,180]
        if args.to360:
            degs = [0,360]
        figmaker(degs, tick_trk, trkband, ytrk, ['Track', '[deg]'], pdf, scenario)
    if len(vsband)>0:
        tick_vs = (vs_bounds[1]-vs_bounds[0])/yticks;
        figmaker(vs_bounds, tick_vs, vsband, yvs, ['Vertical Speed','['+vs_units+']'], pdf, scenario)
    if len(gsband)>0:
        tick_gs = (gs_bounds[1]-gs_bounds[0])/yticks;
        figmaker(gs_bounds, tick_gs, gsband, ygs, ['Ground Speed','['+gs_units+']'], pdf, scenario)
    if len(altband)>0:
        tick_alt = (alt_bounds[1]-alt_bounds[0])/yticks;
        figmaker(alt_bounds, tick_alt, altband, yalt, ['Altitude','['+alt_units+']'], pdf, scenario)
