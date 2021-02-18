#!/usr/bin/env python3

# GarageBand MIDI extractor gbextractor v2.5.1 18th Feb 2021
# Copyright (C) 2020, 2021 MisplacedDevelopment 
# See LICENSE for license information (Apache 2)

# Comes with the following dependencies:
# bitstring (3.1.7) - Simple construction, analysis and modification of binary data. https://github.com/scott-griffiths/bitstring
# MIDIUtil (1.2.1) - A pure python library for creating multi-track MIDI files. https://github.com/MarkCWirt/MIDIUtil
# https://midiutil.readthedocs.io/en/1.2.1/class.html#classref

#SEONN Edit - Added the tkinter library to allow code to be run from Windows.
#Open the Garageband project and select the "ProjectData" file.

import xml.etree.ElementTree as ET
import os
import base64
import sys
from bitstring import ConstBitStream
import time
import string
from midiutil import MIDIFile
import itertools
import glob
import shutil
if os.name == 'nt':# If the OS is Windows
  import tkinter as tk  # For opening Windows file explorer
  from tkinter import filedialog # For opening Windows file explorer

ROOT_DIR = os.getcwd()

# These offsets are in bits!
TEMPO_OFFSET = 0x550 # 0xAA bytes
TIME_SIGNATURE_OFFSET = 0x7D0 # 0xFA bytes
TIME_SIGNATURE_OFFSET_2 = 0x1DB6
BASE_TIME = 0x9600
PPQN = 960

baseTime = BASE_TIME
trackNameLookup = dict()
trackLookup = dict()

####################################
### User-configurable parameters ###
####################################

## Cut-up mode ##
# Enable this option to dump out every permutation of mutliple takes for each
# track, up to maxPerms permutations.
bEnableCutUp = False
# Configure the maximum number of permutations *per track* in cut-up mode, or -1 for no limit.
# Warning : cut-up mode can quickly produce thousands of files as the number 
# of permutations is the product of all the take counts so be very careful about setting
# this to -1!
maxPerms = 24

## Note filter ##
# If your MIDI came from a source such as a MIDI drum kit or MIDI guitar
# then there may be MIDI artefacts in the output.  These appear as
# very low velocity and/or low duration notes.  Use these parameters
# to filter notes based on their velocity or duration
bFilterNotes = False
# Max and min velocity
velocityMin = 20
velocityMax = 127
# Set the minimum duration in milliseconds that a note must sound to be kept
durationMin = 40

## Audio ##
# Enable this option to extract audio files stored in the project
bExtractAudio = False
# Enable this option to create a zipped version of the audio that is extracted
bCompressAudio = True

## Pitch ##

# Set to True to multiply all pitch bends by pitchBendMultiplier.  Use this with
# instruments such as the playable guitars which do not scale pitch bend values 
# correctly when saved.
bOverridePitchBend = False
pitchBendMultiplier = 24
# TODO: By default all instruments have the pitch bend override applied to them
# If this list is not empty then it is used to target this to specific instruments
# You can use a regular expression here.
pitchBendInstFilter = ["Grand Piano"]

## Track split ##
# If you know that you only have n instruments in your kit then you can set this number
# to limit the number of tracks created.  If more notes are found than tracks then new notes are
# added in a round-robin way, starting again from track zero.  The theoretical max value
# is 128.
trackLimit = 16

# If bRenameTracks set to True then split tracks are given custom names based on the note->name mapping below,
# otherwise the note number is used as part of the track name. 
# TODO: Make this automatic based on the instrument as different instruments have slightly
# different mappings
# TODO: Use a list to target splitting to specific instruments/tracks
bRenameTracks = True
trackMap = {35:'Kick',
            36:'Kick2',
            37:'Sidestick',
            38:'Snare',
            39:'Clap',
            32:'RimShot',
            40:'Rimshot',
            41:'TomFloorLo',
            42:'HiHatClosed',
            43:'TomFloorHi',
            31:'PedalHiHat',
            33:'PedalHiHat',
            44:'PedalHiHat',
            45:'TomLo',
            46:'HiHatOpen',
            47:'TomLoMid',
            48:'TomHiMid',
            49:'Crash',
            50:'TomHi',
            51:'Ride',
            52:'RideChina',
            53:'RideBell',
            54:'Tambourine',
            55:'Splash',
            56:'Cowbell',
            57:'Crash2',
            58:'Vibraslap',
            59:'Ride2',
            60:'BongoHi',
            61:'BongoLo',
            62:'CongaMuteHi',
            63:'CongaOpenHi',
            64:'CongaLo',
            65:'TimbaleHi',
            66:'TimbaleLo',
            67:'AgogoHi',
            68:'AgogoLo',
            69:'Cabasa',
            70:'Maracas',
            71:'WhistleShort',
            72:'WhistleLong',
            73:'GuiroShort',
            74:'GuiroLong',
            75:'Claves',
            76:'WoodBlockHi',
            77:'WoodBlockLo',
            78:'CuicaMute',
            79:'CuicaOpen',
            80:'TriangleMute',
            81:'TriangleOpen'
            }
      
## Debugging ##

# Turn debugging on or off
bDebug = False
# Choose whether to redirect stdout to a log file.  You would normally want to do this
# on iOS
bWriteToFile = False
# If this is set then the whole binary is dumped as hex text at the end of processing
bDumpFile = False

########################################
### END User-configurable parameters ###
########################################


MIDI_EVENT_NOTE = 0x90
MIDI_EVENT_CC   = 0xB0
MIDI_EVENT_CHANNEL_PRESSURE = 0xD0
MIDI_EVENT_PITCH_WHEEL = 0xE0

class MIDISection:
  def __init__(self, label, associatedMidiID, recordNumber, sectionLength, sectionStart):
    self.label = label
    self.associatedMidiID = associatedMidiID
    self.midiEvents = []
    self.recordNumber = recordNumber
    self.sectionLength = sectionLength
    self.sectionStart = sectionStart

class MIDIEvent:
  def __init__(self, type, timeStamp, channel, event):
    self.timeStamp = timeStamp
    self.type = type
    self.event = event
    self.channel = channel
    
class MIDIEventNote:
  def __init__(self, velocity, note):
    self.note = note
    self.velocity = velocity
    self.duration = -1

class MIDIEventCC:
  def __init__(self, ctrlNumber, ctrlValue):
    self.ctrlNumber = ctrlNumber
    self.ctrlValue = ctrlValue
    
class MIDIEventPressure:
  def __init__(self, pressure):
    self.pressure = pressure
    
class MIDIEventPitchWheel:
  def __init__(self, pitchWheelValue):
    self.pitchWheelValue = pitchWheelValue
    
class LastNoteEvent:
  def __init__(self, note, timeStamp):
    self.note = note
    self.timeStamp = timeStamp
    
class TwoPartEvent:
  def __init__(self, time, valueA, valueB):
    self.time = time
    self.valueA = valueA
    self.valueB = valueB
        
class MIDIFilter:
  def __init__(self, velMin, velMax, durMin, bInvert):
    self.velMin = velMin
    self.velMax = velMax
    self.durMin = durMin
    self.bInvert = bInvert # Invert the filter, i.e. include *only* those notes that match

class Record:
  def __init__(self, recordNumber, timeStamp):
    self.recordNumber = recordNumber
    self.timeStamp = timeStamp # Where does the section start on the main timeline?
    self.midiEvents = []
    self.label = None
    self.sectionLength = -1

class Folder:
  def __init__(self, index):
    self.folderContents = []
    self.record = None
    self.folderRecordNumber = None
    self.index = index
    self.trackName = None
  
  # Get the set of track numbers from this folder
  def getTrackSet(self):
    trackSet = set({})
    for folder in self.folderContents:
      trackSet.add(folder.index)
    return trackSet

rootFolder = Folder(0)

class NoteToTrackLookup:
  def __init__(self):
    self.dict = dict()
    self.counter = 0
    self.uniqueCounter = 0
    
  def getTrackCount(self):
    return max(self.uniqueCounter, 1)
    
  # Add all of the note events from a list of events
  def addNotes(self, midiEvents):
    for midiEvent in midiEvents:
      if(midiEvent.type == MIDI_EVENT_NOTE): 
        self.getTrackNumberForNote(midiEvent.event.note)
    
  # Get the track that a note has been assigned to, creating
  # a new assigment if necessary
  def getTrackNumberForNote(self, note):
    trackNumber = self.dict.get(note)
    # If this note has not yet been assigned a track then do so now
    if(trackNumber == None):
      self.dict[note] = trackNumber = self.counter      
      self.counter += 1
      self.uniqueCounter = min(trackLimit, self.uniqueCounter + 1)
      
      if(self.counter >= trackLimit):
        debugPrint("Resetting track counter")
        self.counter = 0
        
      debugPrint("Track number {} for note {}".format(trackNumber, note))
    return trackNumber
        
def millisecondsToTicks(bpm, msDuration):
  return ((bpm * PPQN) / 60000) * msDuration
    
def createDir(path):
  try:
    os.mkdir(path)
  except OSError:
    quitWithError("ERROR: Could not create directory {}".format(path))

def createPath(path):
  try:
    if(not os.path.exists(path)):
      os.makedirs(path)
  except OSError:
    quitWithError("ERROR: Could not create path {}".format(path))

def createAndChDir(path):
  createDir(path)
  os.chdir(path)
  
def copyFiles(src, dest, wildcard):
  if(os.path.exists(src)):
    paths = glob.glob(os.path.join(src, wildcard))
      
    for path in paths:
      if(os.path.isfile(path)):
        # Only create dest if there are files to copy.  If this
        # function is going to process lots of files then this
        # should be refactored
        if(not os.path.exists(dest)):
          createPath(dest)
        debugPrint("Copying {} to {}".format(path, dest))
        shutil.copy(path, dest)

def compressFolder(folderToCompress, archiveName):
  shutil.make_archive(archiveName, 'zip', folderToCompress)
  
def extractAudio(gbRoot):
  # Includes direct recording and audio imported by the user and
  # from Apple Loops
  copyFiles(os.path.join(gbRoot, "Media"), 
            os.path.join(WORKING_DIR, *["audio", "media"]),
            "*")
  copyFiles(os.path.join(gbRoot, *["Media", "Sampler", "Sampler Files"]), 
            os.path.join(WORKING_DIR, *["audio", "sampled"]),
            "*")
  copyFiles(os.path.join(gbRoot, "Freeze Files.nosync"), 
            os.path.join(WORKING_DIR, *["audio", "frozen"]),
            "*")

  audioPath = os.path.join(WORKING_DIR, "audio")
  if(bCompressAudio and os.path.exists(audioPath)):
    compressFolder(audioPath, "audio")

# Return a sorted list of sections for a particular
# track.
def getSectionsForTrack(trackNumber):
  sectionList = []
  for topLevelFolder in rootFolder.folderContents:
    if(topLevelFolder.index == trackNumber):
      sectionList.append(topLevelFolder)
  # Fortunately references to grouped takes do store
  # the timestamp of the start of the section
  sectionList.sort(key=lambda x: x.record.timeStamp)     
  return sectionList
  
# Returns a list of sections, sorted by time stamp, which
# are multi-take sections from the provided track
def getMulitTakeSectionsForTrack(trackNumber):
  sectionList = []
  for topLevelFolder in rootFolder.folderContents:
    if(topLevelFolder.folderContents and topLevelFolder.index == trackNumber):
      sectionList.append(topLevelFolder)
  # Fortunately references to grouped takes do store
  # the timestamp of the start of the section
  sectionList.sort(key=lambda x: x.record.timeStamp)     
  return sectionList
  
def getTrackName(trackNumber):
  for topLevelFolder in rootFolder.folderContents:
    if(topLevelFolder.index == trackNumber):
      return topLevelFolder.trackName
     
  return "" 

# Returns a map of record numbers which are multi-take
# sections and indicate which take should be used in
# each permutation of takes.  This function initialises
# the map to zero.
def getMultiTakeMappings(trackNumber):
  multiTakes = getMulitTakeSectionsForTrack(trackNumber)
  return initMultiTakeChoices(multiTakes)   
  
def dumpSections():
  dumpSectionOrSectionStems(False)
  
def dumpSectionStems():
  dumpSectionOrSectionStems(True)

def writeSection(recordNo, recordLabel, section, bDoStems, path, file, stemPath, stemFile):
  midiEvents = section.record.midiEvents
  
  if(bDoStems):
    noteToTrackLookup = NoteToTrackLookup()
    noteToTrackLookup.addNotes(midiEvents)
    trackCount = noteToTrackLookup.getTrackCount()
  else:
    noteToTrackLookup = None
    trackCount = 1   
  
  perSectionMIDIFileData = allocateMIDIFile(trackCount)        
  dumpSection(perSectionMIDIFileData, midiEvents, 0, 0, 0, noteToTrackLookup, None)
  if(bDoStems):
    writeMIDI(stemPath, stemFile, perSectionMIDIFileData)
  else:
    perSectionMIDIFileData.addTrackName(0, 0, "{}".format(recordLabel))
    writeMIDI(path, file, perSectionMIDIFileData)
   
def dumpSectionOrSectionStems(bDoStems):
  debugPrint("Dumping sections") 
  for track in rootFolder.getTrackSet():        
    for section in getSectionsForTrack(track):
      debugPrint(" Section {} ({}) timestamp {} track {}".format(section.record.recordNumber, section.record.label, section.record.timeStamp, section.trackName))
            
      if(not section.folderContents):
        # This section does not contain multiple takes
        recordLabel = cleanStringForFile(section.record.label)
        recordNo = str(section.record.recordNumber)
        writeSection(recordNo, recordLabel, section, bDoStems,
                     getSectionsPath(track), "{}-{}{}-{}.mid".format(track, "S", recordNo, recordLabel),
                     getSectionsPath(track) + ["stems"], "{}-{}{}-{}.mid".format(track, "SStem", recordNo, recordLabel)) 
      else:
        for sectionToUse in section.folderContents:
          recordNo = str(section.record.recordNumber)
          recordLabel = cleanStringForFile(sectionToUse.record.label)
          sectionIndex = sectionToUse.index
          
          writeSection(recordNo, recordLabel, sectionToUse, bDoStems,
                       getSectionsPath(track) + ["takes", "S{}_{}".format(recordNo, recordLabel)], "{}-{}{}-{}-T{}.mid".format(track, "S", recordNo, recordLabel, sectionIndex),
                       getSectionsPath(track) + ["stems", "takes", "S{}_{}".format(recordNo, recordLabel)], "{}-{}{}-{}-T{}.mid".format(track, "SStem", recordNo, recordLabel, sectionIndex))

def dumpSectionsFiltered():
  debugPrint("Dumping sections with filter applied")  
  for track in rootFolder.getTrackSet():
    sectionList = getSectionsForTrack(track) 
        
    for section in sectionList:
      debugPrint(" Section {} ({}) timestamp {}".format(section.record.recordNumber, section.record.label, section.record.timeStamp))
     
      if(not section.folderContents):
        # This section does not contain multiple takes
        writeSectionFiltered(section, track, getSectionsPath(track) + ["filtered"], str(section.record.recordNumber))             
      else:
        for sectionToUse in section.folderContents:
          writeSectionFiltered(sectionToUse, track, getSectionsPath(track) + ["filtered", "takes", "S{}_{}".format(str(section.record.recordNumber), cleanStringForFile(sectionToUse.record.label))], str(section.record.recordNumber))                      
       
def writeSectionFiltered(section, track, folder, recordNumber):
  # Three tracks - original, filtered, delta
  perSectionMIDIFileData = allocateMIDIFile(3)
  sectionLabel = cleanStringForFile(section.record.label)
  for i in range(0, 3):  
    if(i == 0):
      midiFilter = None
      trackName = "Orig_{}".format(sectionLabel)
    elif(i == 1):
      midiFilter = MIDIFilter(velocityMin, velocityMax, durationAsTicks, False)
      trackName = "Filtered_{}".format(sectionLabel)
      
      # Write the filtered track to a separate file
      perSectionFilteredMIDIFileData = allocateMIDIFile(1)
      dumpSection(perSectionFilteredMIDIFileData, section.record.midiEvents, 0, 0, 0, None, midiFilter)
      perSectionFilteredMIDIFileData.addTrackName(0, 0, "{}".format(sectionLabel))
      writeMIDI(folder, "{}-S{}-{}-T{}.mid".format(track, recordNumber, sectionLabel, section.index), perSectionFilteredMIDIFileData)
    elif(i == 2):
      midiFilter = MIDIFilter(velocityMin, velocityMax, durationAsTicks, True)
      trackName = "Delta_{}".format(sectionLabel)
        
    dumpSection(perSectionMIDIFileData, section.record.midiEvents, 0, i, 0, None, midiFilter)
    perSectionMIDIFileData.addTrackName(i, 0, trackName)
  
  writeMIDI(folder, "{}-deltas-S{}-{}-T{}.mid".format(track, recordNumber, sectionLabel, section.index), perSectionMIDIFileData)
  
def dumpSection(midiFileData, midiEvents, timeStamp, trackToWriteTo, offset, noteToTrackLookup, midiFilter):
  for midiEvent in midiEvents:
    if(noteToTrackLookup and midiEvent.type == MIDI_EVENT_NOTE):
      trackToWriteTo = noteToTrackLookup.getTrackNumberForNote(midiEvent.event.note)
      debugPrint("noteToTrackLookup overrides track number to {}".format(trackToWriteTo))
      midiFileData.addTrackName(trackToWriteTo, 0, str(midiEvent.event.note) + "_" + getNoteName(midiEvent.event.note))
            
    renderMIDIEvent(timeStamp, midiEvent, midiFileData, trackToWriteTo, midiFilter)

# Writes one file per track
def dumpTracks():
  debugPrint("Dumping tracks") 
  for track in rootFolder.getTrackSet():
    multiTakeChoices = getMultiTakeMappings(track)    
    perTrackMIDIFileData = allocateMIDIFile(1)
    perTrackMIDIFileData.addTrackName(0, 0, getFormattedTrackName(track))      
    dumpTrack(track, 0, multiTakeChoices, perTrackMIDIFileData)  
    writeMIDI(getTracksPath(track), "{}-{}.mid".format(track, getCleanTrackName(track)), perTrackMIDIFileData)   

def dumpTrack(track, trackToWriteTo, multiTakeChoices, midiFileData):
  cutUpText = None
  mostRecentSectionEnd = 0
  for section in getSectionsForTrack(track):
    sectionEnd = section.record.timeStamp + section.record.sectionLength
    
    debugPrint(" Section {} ({}) timestamp {}, ends {} trackName is {}".format(section.record.recordNumber, section.record.label, section.record.timeStamp, sectionEnd, section.trackName))
    
    # For some reason a track can have invisible sections that overlap.  MIDIUtil can
    # fail if this is the case as it gets confused with note on/off sequences so ignore
    # any sections which do not follow the last section
    if(mostRecentSectionEnd > 0 and mostRecentSectionEnd > section.record.timeStamp):
      debugPrint("Section overlaps last one so skipping.")
      continue
          
    if(not section.folderContents):
      dumpSection(midiFileData, section.record.midiEvents, section.record.timeStamp, trackToWriteTo, 0, None, None)
    else:
      multiTakeIdx = multiTakeChoices.get(section.record.recordNumber)
      debugPrint("Found multi take at {} {}".format(section.record.recordNumber, multiTakeIdx))
      formattedCombo = "{}_{}".format(section.record.recordNumber, multiTakeIdx)
      if(not cutUpText):
        cutUpText = formattedCombo
      else:
        cutUpText = "{}-{}".format(cutUpText, formattedCombo)
      
      sectionToUse = section.folderContents[multiTakeIdx]
      dumpSection(midiFileData, sectionToUse.record.midiEvents, section.record.timeStamp, trackToWriteTo, 0, None, None)
    debugPrint("Most recent section ended {} + {} = {}".format(str(section.record.timeStamp), str(section.record.sectionLength), str(sectionEnd)))    
    mostRecentSectionEnd = sectionEnd
  
  return cutUpText

def dumpTrackStems():
  debugPrint("Dumping track stems")
  for track in rootFolder.getTrackSet():
    debugPrint("Dumping track {}:".format(track))        
    noteToTrackLookup = NoteToTrackLookup()    
    sectionList = getSectionsForTrack(track)
        
    for section in sectionList:        
      if(not section.folderContents):
        noteToTrackLookup.addNotes(section.record.midiEvents)
      else:
        # Use the most recent take    
        sectionToUse = section.folderContents[0]
        noteToTrackLookup.addNotes(sectionToUse.record.midiEvents)
           
    trackCount = noteToTrackLookup.getTrackCount()
    debugPrint("Derived track count is {}".format(trackCount))
    
    perTrackMIDIFileData = allocateMIDIFile(trackCount)
    mostRecentSectionEnd = 0
    for section in sectionList:
      sectionTimestamp = section.record.timeStamp
      sectionRecordNo = section.record.recordNumber
      sectionEnd = sectionTimestamp + section.record.sectionLength
      
      if(mostRecentSectionEnd > 0 and mostRecentSectionEnd > sectionTimestamp):
        debugPrint("WARN: Section overlaps last one so skipping.")
        continue
        
      debugPrint(" Section {} ({}) timestamp {}".format(sectionRecordNo, section.record.label, sectionTimestamp))
      
      if(not section.folderContents):
        dumpSection(perTrackMIDIFileData, section.record.midiEvents, sectionTimestamp, 0, 0, noteToTrackLookup, None)
      else:
        # Use the most recent take  
        sectionToUse = section.folderContents[0]
        dumpSection(perTrackMIDIFileData, sectionToUse.record.midiEvents, sectionTimestamp, 0, 0, noteToTrackLookup, None)
     
      debugPrint("Most recent section ended {} + {} = {}".format(str(sectionTimestamp), str(section.record.sectionLength), str(sectionEnd))) 
      mostRecentSectionEnd = sectionEnd
    
    writeMIDI(getTracksPath(track) + ["stems"], "{}-{}-{}.mid".format(track, "TStem", getCleanTrackName(track)), perTrackMIDIFileData)    
   
bCutItUp = False

def initMultiTakeChoices(multiTakes):
  multiTakeChoices = dict()
  for multiTake in multiTakes:
    multiTakeChoices[multiTake.record.recordNumber] = 0
  return multiTakeChoices

def getCleanTrackName(track):
  return cleanStringForFile(getTrackName(track))

def getFormattedTrackName(track):
  return "{}".format(getCleanTrackName(track))

def getTracksPath(track):
  return ["tracks", "{}_{}".format(str(track), getCleanTrackName(track))]
  
def getSectionsPath(track):
  return ["sections", "{}_{}".format(str(track), getCleanTrackName(track))]

def getCutUpsPath(track):
  return ["cutups", "{}_{}".format(str(track), getCleanTrackName(track))]
  
def writeMIDI(path, filename, midiFileData):
  # 'with open' means Python will automatically close the file
  createPath(os.path.join(WORKING_DIR, *path))
  with open(os.path.join(WORKING_DIR, *path, filename), "wb") as output_file:
    print("Writing MIDI to {}".format(filename))
    midiFileData.writeFile(output_file)

# Writes one file per combination of takes in the track
def dumpCutUps():
  debugPrint("Dumping cut-ups of each track")
  for track in rootFolder.getTrackSet():
    multiTakes = getMulitTakeSectionsForTrack(track)
    takeSizes = []
    cutUpText = None
    permutations = 1
    
    debugPrint("{} multi-takes in use for track {}".format(len(multiTakes), str(track)))
    
    if(len(multiTakes) <= 1):
      continue
    
    # Create a list describing how big each set of takes is
    for take in multiTakes:
      permutations *= len(take.folderContents)
      takeSizes.append(len(take.folderContents))
    
    debugPrint("{} permutations of takes".format(permutations))
    values = itertools.product(*[range(0, i) for i in takeSizes])

    multiTakeChoices = dict()
    permCount = 0
    for value in values:
      if(maxPerms != -1 and permCount >= maxPerms):
        debugPrint("maxPerms hit for this track, breaking from perm loop")
        break
      
      takeCount = 0
      perTrackMIDIFileData = allocateMIDIFile(1)
      
      for element in value:
        multiTakeChoices[multiTakes[takeCount].record.recordNumber] = element
        takeCount += 1
      cutUpText = dumpTrack(track, 0, multiTakeChoices, perTrackMIDIFileData)
      perTrackMIDIFileData.addTrackName(0, 0, "{}".format(cutUpText))
      writeMIDI(getCutUpsPath(track),"{}-CutUp-{}.mid".format(str(track), cutUpText), perTrackMIDIFileData)
      permCount += 1
      
def dumpSong():
  debugPrint("Dumping whole song")
  trackSet = rootFolder.getTrackSet()
  perSongMIDIFileData = allocateMIDIFile(len(trackSet))
  trackCounter = 0
  for track in trackSet:
    multiTakeChoices = getMultiTakeMappings(track)   
    perSongMIDIFileData.addTrackName(trackCounter, 0, getFormattedTrackName(track))
    dumpTrack(track, trackCounter, multiTakeChoices, perSongMIDIFileData)
    trackCounter += 1
  writeMIDI(["full"], "{}.mid".format(projectName), perSongMIDIFileData)

def allocateMIDIFile(numTracks):
  debugPrint("Allocating MIDI file with {} tracks".format(numTracks))
  midiFileData = MIDIFile(numTracks=numTracks, ticks_per_quarternote=960, eventtime_is_ticks=True, file_format=1)
  midiFileData.addTimeSignature(0, 0, numerator, denominator, clocks_per_tick = 24, notes_per_quarter=8)
  midiFileData.addTempo(0, 0, songTempo)
  midiFileData.addTrackName(0, 0, "Track_0")
  return midiFileData

def renderMIDIEvent(startOffset, midiEvent, midiFileData, trackNumber, midiFilter):
  if(startOffset > 0):  
    timeStamp = midiEvent.timeStamp - baseTime + (startOffset - 0x8700)
  else:
    timeStamp = midiEvent.timeStamp - baseTime

  if(midiEvent.type == MIDI_EVENT_NOTE):
    midiEventNote = midiEvent.event
    
    bAddIt = True
    if(midiFilter):
      if(midiEventNote.duration < midiFilter.durMin):
        debugPrint("Note {} at {} duration {} < {}".format(midiEventNote.note, timeStamp, midiEventNote.duration, midiFilter.durMin))
        bAddIt = False
      if(midiEventNote.velocity < velocityMin or midiEventNote.velocity > velocityMax):
        debugPrint("Note {} at {} velocity {} not in range {} -> {}".format(midiEventNote.note, timeStamp, midiEventNote.velocity, midiFilter.velMin, midiFilter.velMax))
        bAddIt = False
        
      if(midiFilter.bInvert):
        bAddIt = not bAddIt
      
    if(bAddIt):
      midiFileData.addNote(trackNumber, midiEvent.channel, midiEventNote.note, timeStamp, midiEventNote.duration, midiEventNote.velocity)
  elif(midiEvent.type == MIDI_EVENT_CC):
    midiEventCC = midiEvent.event        
    midiFileData.addControllerEvent(trackNumber, midiEvent.channel, timeStamp, midiEventCC.ctrlValue, midiEventCC.ctrlNumber)
  elif(midiEvent.type == MIDI_EVENT_PITCH_WHEEL):
    midiEventPitchWheel = midiEvent.event
    midiFileData.addPitchWheelEvent(trackNumber, midiEvent.channel, timeStamp, midiEventPitchWheel.pitchWheelValue)
  elif(midiEvent.type == MIDI_EVENT_CHANNEL_PRESSURE):
    midiEventPressure = midiEvent.event
    # This method does not appear to be documented but is in the MIDIUtil unit tests and the
    # changelog says it was added in 1.2.1
    midiFileData.addChannelPressure(trackNumber, midiEvent.channel, timeStamp, midiEventPressure.pressure)

def associateFolder(folder, midiSection):
  # If we have not resolved the track name for this folder then do
  # this now
  if(folder.trackName == None):
    ref = trackLookup.get(folder.folderRecordNumber)
    trackName = trackNameLookup.get(ref)
    folder.trackName = trackName
  
  if(folder.record.recordNumber == midiSection.recordNumber):
    debugPrint("Matched folder record {} with section record {} folderRecordNumber {}".format(folder.record.recordNumber, midiSection.recordNumber, folder.folderRecordNumber))    
    folder.record.midiEvents = midiSection.midiEvents
    folder.record.sectionLength = midiSection.sectionLength    
    debugPrint("found {} events and label {}".format(len(midiSection.midiEvents), midiSection.label))
    folder.record.label = midiSection.label
    return 1
  return 0

def associateMIDIEvents(recordHash):
  for key, midiSection in recordHash.items():
    if(not midiSection.midiEvents): continue
    matchCount = 0
    for topLevelFolder in rootFolder.folderContents:
      matchCount += associateFolder(topLevelFolder, midiSection)
      for subFolder in topLevelFolder.folderContents:
        matchCount += associateFolder(subFolder, midiSection)
        
    if(matchCount != 1):
      debugPrint("WARN: Found unexpected number of matching records ({}) for {}".format(matchCount, midiSection.recordNumber))
  
def quitWithError(errorString):
  print(errorString)
  if bIsPythonista:
    console.hud_alert(errorString, 'error', 2)
  sys.exit(1)

def getNoteName(note):
  noteName = None    
  
  if(bRenameTracks):
    noteName = trackMap.get(note)
        
  if(noteName == None):
    noteName = str(note)
  
  return noteName
    
def createKey(partA, partB):    
  return "{}:{}".format(str(partA), str(partB))
  
def debugPrint(stringToPrint):
  if(bDebug): print(stringToPrint)

def dumphex(dataLength, s):
  originalPosition = s.pos
  byteCounter = 0
  hexDump = ""
  for lineOffset in range(0, dataLength, 16):
    hexString = ""
    asciiString = ""
    
    bytesToRead = min(16, dataLength - lineOffset)
    
    for byte in s.readlist("{}*uint:8".format(bytesToRead)):      
      if(byte in canBePrinted):
        asciiString += chr(byte)
      else:
        asciiString += "."
        
      hexString += "{:02X} ".format(byte)
      
      byteCounter += 1
      if (byteCounter == dataLength):
        break        
    hexDump += "0x{:08X} | {:48}| {:16} |\n".format(lineOffset, hexString, asciiString)
  s.pos = originalPosition
  print(hexDump)

# Removes some characters from a string to make it more suitable for use as a filename
# Also limits the string to 24 characters
def cleanStringForFile(stringToClean):
  cleanedString = ""
  if(stringToClean):
    cleanedString = "".join(thisChar for thisChar in stringToClean if (thisChar.isalnum() or thisChar in "._-"))
    cleanedString = cleanedString[:24]
  return cleanedString

def processOffsetList(s):
  for thisOffset in sorted_offset_list:
    s.pos = thisOffset

    if bDebug:
      debugPrint("Byte offset {}".format(thisOffset))
      dumphex(64, s)
    
    identity, recordType, recordSubType, recordNumber, recordMidiID, dataLength = s.readlist("bytes:4, uintle:16, uintle:32, uintle:32, uintle:32, 2*pad:32, pad:16, uintle:32, pad:32")
    
    # We are now at the start of the data so save this position for later...
    dataStart = s.pos
    
    if bDebug:
      debugPrint("Data length is: {} Type is: {}/{} Record no: {} MIDI ID: {} ".format(dataLength, identity, recordType, recordNumber, recordMidiID))
      if(recordType == 1 or recordType == 2 or recordType == 4 or recordType == 5): dumphex(dataLength, s)
  
    # Test for a MIDI block header
    blockType = s.read("bytes:2")
    s.read("bytes:1")
  
    debugPrint("BlockType is {}".format(blockType.hex()))

    if(identity == b'qSxT'):
      s.pos = dataStart
      sectionLength = s.read("uintle:32")
      debugPrint("Section length {}".format(sectionLength))
      if(sectionLength < 98):
        quitWithError("ERROR: section length invalid {}".format(sectionLength))
      s.read("bytes:94")
      nameStart = s.pos
      i = 0
      for i in range(0, sectionLength - 98):
        thisChar = s.read("uintle:8")
        if(thisChar == 0):
          break  
      debugPrint("Found track section name length {}".format(i))
      s.pos = nameStart
      if(i > 0):
        trackName = s.read("bytes:{}".format(str(i))).decode("utf-8")
        debugPrint("trackName is {}".format(trackName))
        trackNameLookup[recordNumber] = trackName
      else:
        debugPrint("No track name")
      continue
      
    # Is this a section header?
    if(recordType == 2):
      associatedMidiID, sectionNameLength = s.readlist("pad:40, uintle:32, pad:32, uintle:16")
      if(sectionNameLength == 0):
        continue
        
      # Create a key from the record + associated midi ID
      hashKey = createKey(str(recordNumber), str(associatedMidiID))
      origSectionName = s.read("bytes:{}".format(str(sectionNameLength))).decode("utf-8")
      
      # Strip out filename unfriendly characters
      sectionName = "".join(thisChar for thisChar in origSectionName if (thisChar.isalnum() or thisChar in "._- "))      
      
      debugPrint("Section name is {} (orig {}), hash key is {}".format(sectionName, origSectionName, hashKey))
      # Nothing to guide us here
      sectionLength = None
      sectionStart = 0
      for i in range(0, 100):
        thisByte = s.read("uintle:8")
        if(thisByte == 0x20):
          if bDebug: dumphex(45, s)
          s.read("bytes:39")
          sectionLength = s.read("uintle:24")
          s.read("bytes:161")
          sectionStart = s.read("uintle:24")
          break
          
      if(sectionLength == None):
        quitWithError("ERROR: Did not find section length")
      
      debugPrint("Section length is {} {} start is {} ({})".format(sectionLength, hex(sectionLength), sectionStart, hex(sectionStart)))  
      
      existingRecord = recordHash.get(hashKey)
      # Validation - The key should be unique
      if(existingRecord != None):
        quitWithError("ERROR: Found second record for key {}".format(hashKey))
  
      midiSection = MIDISection(sectionName, associatedMidiID, recordNumber, sectionLength, sectionStart)
      recordHash[hashKey] = midiSection
    elif(recordType == 1): # MIDI data block
      hashKey = createKey(str(recordNumber), str(recordMidiID))    
      debugPrint("Hash key is {}".format(hashKey))    
      # Have we seen a section header with this MIDI ID?
      midiSection = recordHash.get(hashKey)
      if(midiSection != None):
        debugPrint("Found MIDI data for section {} blockType {}".format(midiSection.label, blockType.hex()))
        midiEvents = None
        
        if(blockType.hex() == "2000" or blockType.hex() == "2400"):
          debugPrint("Found Folder")
          if(midiSection.label != "Automation"):
            processFolder(s, midiSection, dataStart, dataLength)
          else:
            debugPrint("TODO: Automation folders.  Ignoring for now.")
        else:
          midiEvents = processMIDI(s, midiSection, baseTime, recordNumber, recordMidiID, dataStart, dataLength)     
        
        midiSection.midiEvents = midiEvents
    elif(midiSection != None and midiSection.label == "Root Folder" and recordType == 4 and identity == b'karT'):
      s.pos = dataStart
      s.read("bytes:4")
      trackNameBlock = s.read("uintle:32")
      trackId = s.read("uintle:32")
      if(not trackId in trackLookup.keys() and trackNameBlock != 0):
        trackLookup[trackId] = trackNameBlock
        debugPrint("set key {} to {}".format(trackId, trackNameBlock))
      debugPrint("trackNameBlock: {} ({}) trackId: {} ({})".format(trackNameBlock, hex(trackNameBlock), trackId, hex(trackId)))
      
def processFolder(s, midiSection, dataStart, dataLength):
  s.pos = dataStart
  folder = None
  if(midiSection.label == "Root Folder"):
    folder = rootFolder
    folder.record = Record(midiSection.recordNumber, 0)
  else:
    # Find this section, it must be in the root folder
    for thisFolder in rootFolder.folderContents:
      if(thisFolder.record.recordNumber == midiSection.recordNumber):
        folder = thisFolder
      
  # This must be a reference to an existing section    
  if(folder == None):
    debugPrint("Found folder by reference")
    folder = rootFolder

  while True:
    # Read in the next command byte
    midiCmd = s.read('uintle:8')
    debugPrint('Command is {} ({})'.format(midiCmd, hex(midiCmd)))
    
    if (midiCmd == 0xF1):
      debugPrint("Found end of buffer")
      break
  
    if(midiCmd == 0x20):
      # 0x00000050 | 20 00 00 00 40 44 03 00 00 00 00 00 00 05 00 80 | ....@D.......... |
      # 0x00000060 | 64 00 00 00 01 00 00 89 00 00 00 00 FF FF FF 3F | d..............? |
      # 0x00000070 | 1C 00 00 00 00 00 00 88 00 00 00 00 00 00 00 00 | ................ |
      
      s.read("bytes:3")
      timeStamp = s.read('uintle:32')
      s.read("bytes:8")
      folderRecordNumber = s.read('uintle:32')
      index = s.read('uintle:16') # might be 24 but that would be a lot of takes!
      debugPrint("Index is {}".format(index))
      s.read("bytes:10")
      recordNumber = s.read('uintle:32')
      debugPrint("Record number is {}".format(recordNumber))
      s.read("bytes:44")
      
      newFolder = Folder(index)
      newRecord = Record(recordNumber, timeStamp)
      newFolder.record = newRecord
      newFolder.folderRecordNumber = folderRecordNumber
      folder.folderContents.append(newFolder)
    elif (midiCmd & 0xF0 == 0x50): # Possibly some onscreen dial setup?
      debugPrint("Found 0x5x, skipping")
      s.read("bytes:15")
    elif (midiCmd == 0x00):
      debugPrint("Null block")
      s.read("bytes:63")
    elif (midiCmd == 0x24): # Audio section, skip for now
      debugPrint("Found 0x24 audio section, skipping")
      s.read("bytes:79")
    else: # Unknown section, skip for now
      debugPrint("Unknown command {}".format(midiCmd, hex(midiCmd)))
      s.read("bytes:79")
    
    # Check we have not exceeded the length of the data in this block
    bufferUsed = s.pos - dataStart
    totalBufferSize = (dataLength * 8)
    debugPrint("Buffer used so far: {} out of: {}".format(bufferUsed, totalBufferSize))
    
    if(bufferUsed > totalBufferSize):
      quitWithError("ERROR: Went past end of buffer.")
      
    if(bufferUsed == totalBufferSize):
      debugPrint("Used full buffer")
      break  
  
def getRecord(recordNumber):
  for topLevelFolder in rootFolder.folderContents:
    if(topLevelFolder.record.recordNumber == recordNumber):
      return topLevelFolder.record
         
      for subFolder in topLevelFolder.folderContents:
        if(subFolder.record.recordNumber == recordNumber):
          return subFolder.record
      
  return None

def readTwoPartEvent(bitStream):
  bitStream.read("bytes:3")
  eventTime = bitStream.read("uintle:32")
  bitStream.read("bytes:3")
  eventValueA = bitStream.read("uintle:8")
  eventValueB = bitStream.read("uintle:8")
  debugPrint("eventValueA {}({}) eventValueB {}({})".format(eventValueA, hex(eventValueA), eventValueB, hex(eventValueB)))
  bitStream.read("bytes:3")  
  return TwoPartEvent(eventTime, eventValueA, eventValueB)

def processMIDI(s, midiSection, baseTime, recordNumber, recordMidiID, dataStart, dataLength):
  eventList = []
  lastNoteEvent = None 
  s.pos = dataStart
  
  sectionEnd = baseTime + midiSection.sectionLength
  
  while True:
    # Read in the next command byte
    midiCmd = s.read('uintle:8')
    debugPrint('Command is {} ({})'.format(midiCmd, hex(midiCmd)))
    
    midiChl = midiCmd & 0x0F
    
    if(midiCmd >= 0x90 and midiCmd <= 0x9F): # Note on/off event
      # 0x00000000 | 90 00 00 00 00 96 00 00 00 00 00 7D 24 00 00 00 | ...........}$...
      # 0x00000010 | 80 00 00 00 00 00 00 89 00 00 00 00 F0 00 00 00 | ................
      s.read("bytes:3")
      noteStart = s.read("uintle:32")
      s.read("bytes:3")      
      midiEventNote = MIDIEventNote(*s.readlist('uintle:8, uintle:8'))
      s.read("bytes:3")
      s.read("bytes:7")
      
      midiCmd = s.read('uintle:8')
      if(midiCmd >= 0x80 and midiCmd <= 0x8F): # Note Off event then set note duration event
        # 0x00000580 | 40 00 00 00 00 00 00 89 00 00 00 00 F0 00 00 00 | @...............
        # 0x00000590 | 00 00 00 00 00 00 00 A7 00 00 00 00 00 00 00 00 | ................
        # 0x000005A0 | 90 00 00 00 53 BD 00 00 00 00 00 73 24 00 00 00 | ....S......s$...
  
        extendedBytes = s.read("uintle:32")
        # Duration spans at least 3, probably 4 bytes.  We'll go for 4 for now!
        midiEventNote.duration = s.read("uintle:32")
        
        if(baseTime is None):
          baseTime = noteStart
           
        bAddNote = True
        
        sectionEnd = baseTime + midiSection.sectionLength
        noteEnd = noteStart + midiEventNote.duration
        
        debugPrint(":Event time is {} logical section start is {} ({}) section length is {} basetime {} datastart {} dataLength {}".format(noteStart, midiSection.sectionStart, midiSection.sectionStart + baseTime, midiSection.sectionLength, baseTime, dataStart, dataLength))
        debugPrint(":event is {} in to the section.  It goes from {} to {} and the end of the section is {}".format(noteStart-baseTime, noteStart, noteEnd, sectionEnd))
        
        # Try and work around duplicate note bug https://github.com/MarkCWirt/MIDIUtil/issues/24
        if(lastNoteEvent is not None):
          if(lastNoteEvent.note == midiEventNote.note and
             lastNoteEvent.timeStamp == noteStart):
             bAddNote = False
        
        if(noteStart >= sectionEnd):
          debugPrint("Note starts at or past logical end of the section so ignoring it")
          bAddNote = False        	      
        elif(noteEnd > sectionEnd):
          midiEventNote.duration = sectionEnd - noteStart
          debugPrint("Duration corrected to {}".format(midiEventNote.duration))
        
        if(bAddNote):                    
          eventList.append(MIDIEvent(MIDI_EVENT_NOTE, noteStart, midiChl, midiEventNote))
          lastNoteEvent = LastNoteEvent(midiEventNote.note, noteStart)
                      
        if(extendedBytes > 0):
          debugPrint('Found extended bytes {} '.format(hex(extendedBytes)))
          
      else: # Did not find expected 0x8x before note duration data
        quitWithError('ERROR: Unknown command {} ({})'.format(midiCmd, hex(midiCmd)))
    elif ((midiCmd >= 0x00 and midiCmd <= 0x0A) or midiCmd == 0xFF): # internal commands/screen elements?
      # 00 00 00 00 00 00 01 B5 00 00 00 00 00 00 00 00. button on? 01 on 02 off
      s.read('bytes:6')
      midiCmd = s.read('uintle:8')
      if (midiCmd != 0xA8 and midiCmd != 0xA7 and midiCmd != 0xB5):
        debugPrint('WARN: Unknown command {} ({})'.format(midiCmd, hex(midiCmd)))            
      s.read('bytes:8')
    elif (midiCmd >= 0x20 and midiCmd <= 0x2F): # cc bank change
      # 20 3D 01 00 00 00 00 A8 00 00 00 00 A5 83 00 00
      s.read("bytes:15")
    elif (midiCmd == 0x40): # cc sustain ?
      # 40 2F 01 00 00 00 00 A8 00 00 00 00 A2 83 00 00
      s.read("bytes:15")
    elif (midiCmd == 0x50): # cc general purpose controller, synth knobs 0x00-0x0b pads CA-CD
      # 50 40 00 00 00 96 00 00 10 58 39 0E 00 01 00 01 # knob top left synth 00 
      # 50 40 00 00 00 96 00 00 45 B6 D3 0C 01 01 00 01 # knob bottom left 01
      # 50 40 00 00 00 96 00 00 00 00 00 7F 02 01 00 01 # knob top right 02
      # 50 40 00 00 00 96 00 00 00 00 00 00 07 01 00 01 # knob bottom right 07
      
      thisEvent = readTwoPartEvent(s)
    
      # It feels like program change, e.g. patch change in synth is implemented like this but GB does not respond
      # so disabling this for now.
      if(False and thisEvent.valueB & 0xC0 == 0xC0):
        ctrlChl = thisEvent.valueB & 0x0F
        debugPrint("Adding program change")
    elif (midiCmd >= 0x60 and midiCmd <= 0x6F): # Do not know what this is. Seen with Grand Piano, possibly where smart piano is being touched?
      # 60 9B 01 00 00 00 00 A8 00 00 00 00 A5 83 00 00
      # Special case the start of a 48 byte block
      if(dataLength == 48):
        s.read("bytes:31")
      else: 
        s.read("bytes:15")
    elif (midiCmd >= 0x70 and midiCmd <= 0x7F): # can be triggered by manually adding and moving percussion with smart drums while recording
      # 70 00 00 00 00 96 00 00 00 00 00 01 36 00 00 00
      # 09 00 02 06 00 00 00 A8 00 00 00 00 21 00 09 00            
      s.read("bytes:31")
    elif (midiCmd >= 0x80 and midiCmd <= 0x8F): # Do not know what this is. Seen with synth, not a note-off though as it uses the same bytes each time.
      # 80 AE 01 00 00 00 00 A8 00 00 00 00 A5 83 00 00
      s.read("bytes:15")
    elif (midiCmd >= 0xA0 and midiCmd <= 0xAF): # polyphonic key pressure unsupported in MIDIUtil API :(
      # A0 11 01 00 00 00 00 A8 00 00 00 00 A5 83 00 00
      debugPrint("Polyphonic key pressure (unsupported) {}({})".format(midiCmd, hex(midiCmd)))
      s.read("bytes:15")
    elif (midiCmd >= 0xB0 and midiCmd <= 0xBF): # MIDI CC
      # B0 40 00 00 5D 9D 00 00 00 00 00 00 40 00 00 01 cc sustain off 00 40 ch 0 40 is cc val
      # B0 40 00 00 5D 9D 00 00 00 00 00 7F 40 00 00 01 cc sus on 7F 40 ch 0
      # 0 (to 63) is off. 127 (to 64) is on.
      # B0 40 00 00 40 9A 00 00 00 00 00 00 01 00 00 01 cc mod wheel zero
      
      thisEvent = readTwoPartEvent(s)
      if(thisEvent.time > sectionEnd):
        debugPrint("CC event starts ({}) past logical end of the section ({})".format(thisEvent.time, sectionEnd))
      else:
        eventList.append(MIDIEvent(MIDI_EVENT_CC, thisEvent.time, midiChl, MIDIEventCC(thisEvent.valueA, thisEvent.valueB)))
    elif (midiCmd >= 0xC0 and midiCmd <= 0xCF): # Should be program change but don't think it is 
      # C0 03 01 00 00 00 00 A8 00 00 00 00 A5 83 00 00
      s.read("bytes:15")
    elif (midiCmd >= 0xD0 and midiCmd <= 0xDF): # channel pressure
      # D3 40 00 00 81 A1 00 00 00 00 00 00 00 00 00 01 channel pressure 0
      # D5 40 00 00 C4 BA 00 00 00 00 00 1F 1F 00 00 01 channel pressure 1F
      
      thisEvent = readTwoPartEvent(s)

      if(thisEvent.time > sectionEnd):
        debugPrint("Pressure event starts ({}) past logical end of the section ({})".format(thisEvent.time, sectionEnd))
      else:  
        eventList.append(MIDIEvent(MIDI_EVENT_CHANNEL_PRESSURE, thisEvent.time, midiChl, MIDIEventPressure(thisEvent.valueA)))      
    elif (midiCmd >= 0xE0 and midiCmd <= 0xEF): # pitch bend
      # E8 40 00 00 19 A0 00 00 00 00 00 40 17 00 00 01 pitch bend ch 8 val 40 17
      # E4 40 00 00 41 9A 00 00 00 00 00 40 00 00 00 01 pitch bend 0
      
      thisEvent = readTwoPartEvent(s)
      
      pb = 0
      pb = (pb << 7) + (thisEvent.valueA & 0x7F)
      pb = (pb << 7) + (thisEvent.valueB & 0x7F)
      pitchWheelValue = -8192 + pb
  
      if(bOverridePitchBend):
        pitchWheelValue *= pitchBendMultiplier
        # Correct any overshoot
        if(pitchWheelValue < -8192): pitchWheelValue = -8192
        if(pitchWheelValue > 8191): pitchWheelValue = 8191
        debugPrint("Adjusted pitchWheelValue is: {}({})".format(pitchWheelValue, hex(pitchWheelValue)))
  
      if(thisEvent.time > sectionEnd):
        debugPrint("PitchWheel event starts past logical end of the section")
      else:
        eventList.append(MIDIEvent(MIDI_EVENT_PITCH_WHEEL, thisEvent.time, midiChl, MIDIEventPitchWheel(pitchWheelValue)))
    elif (midiCmd == 0xF1):
      debugPrint("Found end of buffer")
      break
    elif ((midiCmd >= 0x30 and midiCmd <= 0x3F) or
           midiCmd == 0x11 or 
           midiCmd == 0x12):
      # These tend to be at the start of blocks we are not interested in
      debugPrint("Unknown bytes: {}".format(hex(midiCmd)))
      break
    else:
      # Not seen this command byte before so dump some context for debugging
      # purposes then exit
      s.pos -= (96 * 8)
      dumphex(100, s)
      quitWithError("Unrecognised command: {}".format(midiCmd))
      break # Unreachable
  
    # Check we have not exceeded the length of the data in this block
    bufferUsed = s.pos - dataStart
    totalBufferSize = (dataLength * 8)
    debugPrint("Buffer used so far: {} out of: {}".format(bufferUsed, totalBufferSize))
    
    if(bufferUsed > totalBufferSize):
      quitWithError("ERROR: Went past end of buffer.")
      
    if(bufferUsed == totalBufferSize):
      debugPrint("Used full buffer")
      break
  return eventList

trackCounter = 0
trackDict = dict()
recordHash = dict()

try:
  import dialogs
  import console
  bIsPythonista = True
  debugPrint("Running inside of Pythonista")
except:
  bIsPythonista = False
  debugPrint("Running outside of Pythonista")

if bIsPythonista: 
  # Show iOS file picker to select GB file
  fp = dialogs.pick_document(types=["public.item"])
elif os.name == 'nt':# If the OS is Windows
  root=tk.Tk()
  root.withdraw()
  fp = filedialog.askopenfilename().replace('/projectData','') # Select the Project Data file for Windows as it opens up the folder
  debugPrint(fp)
else:
  if(len(sys.argv) == 2):
    fp = sys.argv[1]
  else:
    quitWithError("ERROR: Expects a single argument which is the path to the GB project.band directory")

if (fp != None):
  projectName = os.path.splitext(os.path.basename(fp))[0]
  pathToGBFile = os.path.join(fp, "projectData")
else:
  quitWithError("ERROR: No file selected.")

WORKING_DIR = os.path.join(ROOT_DIR, "{}_{}".format(time.strftime("%Y%m%d-%H%M%S"), projectName))

canBePrinted = bytes(string.ascii_letters + string.digits + string.punctuation, 'ascii')

createAndChDir(WORKING_DIR)

# Should we redirect stdout to a log file?
if bWriteToFile:
  origStdout = sys.stdout
  newStdout = open("GB_Extract_Log.txt", 'w')
  sys.stdout = newStdout
  
if os.path.exists(pathToGBFile):
  parseDataFile = ET.parse(pathToGBFile)
  xmlRoot = parseDataFile.getroot()
else:
  quitWithError("ERROR: File does not exist: {}".format(pathToGBFile))

# Decode the base64 data in the projectData file
nsData = xmlRoot.find(".//*[key='NS.data']/data")
encodedText = nsData.text
try:
  decodedData = base64.b64decode(encodedText)
  with open("decoded.bin","wb") as binOut:
    binOut.write(decodedData)
except Exception as ex:
  print(str(ex))
  quitWithError("ERROR: Failed to decode data")

# Open the decoded binary file for parsing
s = ConstBitStream(filename='decoded.bin')
s.pos = 0

if bDebug: dumphex(0x800, s)

# Pull out the tempo, offset is number of BITS
s.pos = TEMPO_OFFSET
preciseBPM = s.read('uintle:24')
songTempo = preciseBPM/10000
debugPrint("Tempo BPM is {} ({})".format(songTempo, hex(preciseBPM)))

# Pull out the time signature 
s.pos = TIME_SIGNATURE_OFFSET
numerator = s.read('uintle:8')
denominator = s.read('uintle:8')
debugPrint("Time signature is {}/{}".format(numerator, 2**denominator))

durationAsTicks = millisecondsToTicks(songTempo, durationMin)

# Generate an ordered list of offsets pointing to bits of the 
# binary data that we are interested in
offset_list = list(s.findall('0x71537645', bytealigned = True)) #qSvE
offset_list.extend(list(s.findall('0x7165534D', bytealigned = True))) #qeSM
offset_list.extend(list(s.findall('0x71537854', bytealigned = True))) #qSxT

offset_list.extend(list(s.findall('0x6B617254', bytealigned = True)))
offset_list.extend(list(s.findall('0x74536e49', bytealigned = True)))
offset_list.extend(list(s.findall('0x74537854', bytealigned = True)))
offset_list.extend(list(s.findall('0x69766e45', bytealigned = True)))
sorted_offset_list = sorted(offset_list)

processOffsetList(s)

associateMIDIEvents(recordHash)

debugPrint("trackLookup items:")
for key, lookup in trackLookup.items():
  debugPrint("key {} lookup {}".format(key, lookup))

debugPrint("trackNameLookup items:")
for key, lookup in trackNameLookup.items():
  debugPrint("key {} lookup {}".format(key, lookup))

debugPrint("Root folder:")
for thisFolder in rootFolder.folderContents:
  debugPrint("  Top level folder: idx {} record number {} folder id {} trackName {}".format(thisFolder.index, thisFolder.record.recordNumber, thisFolder.folderRecordNumber, thisFolder.trackName))
  for subFolder in thisFolder.folderContents:
    debugPrint("   Sub Folder: idx {} record number {} folder id {} trackName {}".format(subFolder.index, subFolder.record.recordNumber, subFolder.folderRecordNumber, subFolder.trackName))

if(bExtractAudio):
  extractAudio(fp)

dumpTracks()
dumpSong()
dumpTrackStems()

if(bEnableCutUp):
  dumpCutUps()

dumpSectionStems()
dumpSections()

if(bFilterNotes):
  dumpSectionsFiltered()

if(bDumpFile):
  s.pos = 0
  fileSize = os.path.getsize('decoded.bin')
  debugPrint("fileSize is {}".format(fileSize))
  dumphex(fileSize, s)

if bWriteToFile:
  newStdout.close()
  sys.stdout = origStdout

if bIsPythonista:
  console.hud_alert("File processing complete", 'success', 1)
else:
  print("File processing complete")
