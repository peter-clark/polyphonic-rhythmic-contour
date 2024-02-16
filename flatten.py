import os
import numpy as np
import descriptors as desc
import re

## Finds approriate frequency channel for midi note
def find_LMH(note):
    if(int(note)==0):
        return []
    channel = desc.GM_dict[int(note)][1]
    if(channel=="low"):
        n = 1
    elif(channel=="mid"):
        n = 2
    else:
        n = 3 # "high"
    return n

## Used in flat_from_patt
def get_LMH(pattern):
    pattern_LMH = []
    for step in range(len(pattern)):
        lmh = []
        for note in pattern[step]:
            if pattern[step] != "":
                lmh.append(find_LMH(note))
        pattern_LMH.append(lmh)
    return pattern_LMH

def lmh_counts(pattern):
    pattern_LMH = pattern # LOW MID HIGH
    pattern_LMH_count=[[0 for x in range(len(pattern_LMH))] for y in range(3)]
     # Count multi-hits in same channel on step
    for i in range(len(pattern_LMH)):
        for j in range(len(pattern_LMH[i])):
            pattern_LMH_count[0][i] += 1 if pattern_LMH[i][j]==1 else 0 # LOW
            pattern_LMH_count[1][i] += 1 if pattern_LMH[i][j]==2 else 0 # MID
            pattern_LMH_count[2][i] += 1 if pattern_LMH[i][j]==3 else 0 # HIGH
    return pattern_LMH_count




#-----------------------------------------------------------------------------------------------#
#----------------------------------Flattening Algorithms----------------------------------------#
#-----------------------------------------------------------------------------------------------#

def flat(pattern, density_type, meter, syncopation_type):
    ## density types:
    # 0 := onset density, 1 := weighted. density, 2 := rel. density, 3 := note presence
    ## sync types:
    # 0 := none, 1 := sync, 2 := polysync
    ## meter:
    # 0 := none, 1 := GTTM
    # final normalization done at end of function

    output_pattern = np.array([0.0 for x in range(len(pattern))])
    pattern_LMH = np.array(lmh_counts(pattern), dtype=float) # get # in each channel
    pattern_LMH = np.transpose(pattern_LMH)
    step_values = np.array([0.0, 0.0, 0.0], dtype=float)

    sync_strength = [0,1,0,2, 0,1,0,3, 0,1,0,2, 0,1,0,4]
    meter_strength = [4,0,1,0, 2,0,1,0, 3,0,1,0, 2,0,1,0]
#-----------------------------------------------------------------------------------------------
# [0]
#### Onset Density / Meter / Syncopation
    if density_type == 0: 
        patt_LMH = np.sum(pattern_LMH, axis=1)/np.max(np.sum(pattern_LMH, axis=1))

        if meter == 1: # basic meter
            for note in range(len(pattern)):
                if np.any(pattern_LMH[note][n]>0 for n in pattern_LMH[note]):
                    output_pattern[note] += meter_strength[note]*patt_LMH[note]
        
        if syncopation_type == 1: # mono sync
            for note in range(len(pattern)):
                if sync_strength[note]>sync_strength[(note+1)%len(pattern)]: # if sync
                    if np.any(pattern_LMH[note][x]>0 and pattern_LMH[(note+1)%len(pattern)][x]==0 for x in range(3)): 
                        output_pattern[note] += sync_strength[note]*patt_LMH[note] # add to one sync value if any channel is sync

        
        elif meter==0 and syncopation_type==0: # just onset density
            for note in range(len(pattern)):
                output_pattern[note] += np.sum(patt_LMH, axis=0)
#-----------------------------------------------------------------------------------------------
# [1]
#### Frequency Weighted Onset Density
    if density_type == 1:
        patt_LMH = pattern_LMH
        patt_LMH[:][0] *= 3 # low x3 weight
        patt_LMH[:][1] *= 2 # mid x2 weight
        step_values = np.sum(patt_LMH, axis=0) / np.max(np.sum(patt_LMH, axis=0))
        # now we have value per step

        if meter == 1: # basic meter
            for note in range(len(pattern)):
                for n in range(3):
                    output_pattern[note] += meter_strength[note]*step_values[n]
    
        if syncopation_type == 1: # basic sync
            for note in range(len(pattern)):
                for n in range(len(patt_LMH[note])):
                    if sync_strength[note]>sync_strength[(note+1)%len(pattern)]: # if sync pos
                        if patt_LMH[note][n]>0 and patt_LMH[(note+1)%len(pattern)][n]==0: # if sync note
                            output_pattern[note] += sync_strength[note]*patt_LMH[note][n] # add notexweighted value
        
        elif meter==0 and syncopation_type==0:
            output_pattern += np.sum(patt_LMH, axis=1)

#-------------------------------------------------------------------------------------------
# [2]                            
#### Pattern Relative Onset Density
    if density_type == 2:
        patt_LMH = pattern_LMH
        salience = np.array([0.0, 0.0, 0.0], dtype=float)
        num_notes_channel = np.sum(patt_LMH, axis=0)
        num_notes = np.sum(patt_LMH)
        rel_dens = np.array(num_notes_channel / num_notes, dtype=float)
        salience = 1/rel_dens
        channel_values = salience / np.sum(salience)

        # now we have value per step

        if meter == 1: # basic meter
            for note in range(len(pattern)):
                for n in range(3):
                    output_pattern[note] += meter_strength[note]*(patt_LMH[note][n]*channel_values[n])
    
        if syncopation_type == 1: # basic sync
            for note in range(len(pattern)):
                for n in range(len(patt_LMH[note])):
                    if sync_strength[note]>sync_strength[(note+1)%len(pattern)]: # if sync pos
                        if patt_LMH[note][n]>0 and patt_LMH[(note+1)%len(pattern)][n]==0: # if sync note
                            output_pattern[note] += sync_strength[note]*(patt_LMH[note][n]*channel_values[n]) # add note x sal.weighted value
  
        elif meter==0 and syncopation_type==0:
            for n in range(len(pattern)):
                patt_LMH *= channel_values
            output_pattern += np.sum(patt_LMH[n][:], axis=0)

#-------------------------------------------------------------------------------------------
# [3]                            
#### Note Presence (mono)        
    if density_type == 3:
        mono_patt = np.sum(pattern_LMH, axis=1)
        mono_patt = [1 if i>0 else 0 for i in mono_patt]
        output_pattern = mono_patt
        if meter == 1: # basic meter
            for note in range(len(pattern)):
                if mono_patt[note]==1:
                    output_pattern[note] += meter_strength[note]
    
        if syncopation_type == 1: # basic sync
            for note in range(len(pattern)):
                if sync_strength[note]>sync_strength[(note+1)%len(pattern)]: # if sync pos
                    if mono_patt[note]>0 and mono_patt[(note+1)%len(pattern)]==0: # if sync note
                        output_pattern[note] += sync_strength[note]
        if syncopation_type == 2: # polysync
            #print("TODO: poly sync")
            # TODO
            note=0
        

    output_pattern /= np.max(output_pattern) # norm
    return output_pattern
#-----------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------