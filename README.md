# GBExtractor

Extract your music from GarageBand (GB) project files, natively on iOS.

GB does not have a MIDI export option and this tool has been written to provide interoperability between your musical information stored in a GB project file and other applications on iOS which can make use of that information.

## Features:
* Note on/off supported for all instruments, including all types of smart instrument
* Creates a number of views of your data - full song, per track, per section.
* Time signature and tempo are preserved
* Understands a variety of MIDI meta-data such as MIDI CC and pitch wheel changes.
* GB multi-take sections are supported - use GB to jam short clips of MIDI and then export to a clip launcher such as LK.
* Export drum sections as one track per drum part to allow for multi-stem processing.  Features automatic naming of each stem with the appropriate instrument for ease of use in your sequencer (limited DAW support for this option).
* Extract and compress audio from projects.
* Cut-Up mode to combine all permutations of takes in a track for creative exploration.
* Velocity and duration filter with side-by-side before/after comparison.  Ideal for cleaning up MIDI guitar or drum-kit input.

## Usage instructions

1. Install http://omz-software.com/pythonista/ from the iOS app store.  This is not free and there may be other lower cost/free options but this is what the tool was developed and tested with.  Alternatively, find a desktop machine with Python 3 installed.  The v1.x version of the script was tested to run using Python 3.7 but I have not repeated this testing with v2.x of the tool. The free and powerful app iSH may work but I have not tried this: [How to install Python in iSH](https://www.reddit.com/r/ish/comments/jjq8nc/how_to_install_apk_and_python/)
1. Download the gbextractor.py script from this site, or clone the project on iOS using [Working Copy](https://workingcopyapp.com)
1. (Pythonista) Load the script into Pythonista. **IMPORTANT** You must copy to and run the script from the Pythonista folder, i.e. somewhere under iCloud Drive/Pythonista 3, otherwise you will not have permission to write the MIDI data.
1. Install packages "bitstring" and "MIDIUtil", e.g. "pip install packageName", see [this page](https://github.com/ywangd/stash) for how to do this.
1. Before running the script, ensure that GB does not have the project open otherwise you will not be able to open it via the tool.
1. Run the script.  In Pythonista you will be presented with an iOS file picker which you should use to select your GarageBand project file.  If running the tool outside Pythonista you should provide a single argument to the script which is the GB project directory, e.g. ```python3.7 ~/gbextractor.py ~/MySong.band```
1. With luck, the script will complete with "File processing complete"
1. A directory will be created containing different MIDI representations of the music sections that were found in the GB project.  For Pythonista, this will be in the same iCloud directory as the gbextractor.py script and if run outside of iOS then the directory will be created in the current working directory.

## Features

### MIDI output
There are a number of representations of your musical information written when the tool is run.  Since MIDI data does not take up much storage space then the majority of MIDI representations are written by default.

The hierarchy can be summarised into these main sections:

* `audio` - All the project audio files (optional).
* `sections` - All the sections from every track, including takes.
* `tracks` - Each track from the project as a separate file.
* `song` - The full song with one track per GB track.
* `cutups` - Permutations of each section of takes in each track (optional).

Within the hierarchy you may find the following:
* `stems` - MIDI notes split into tracks for use with external drums.  You can normally ignore this folder if the instrument is not percussive.
* `filtered` - Filter notes by velocity or duration (optional).
* `takes` - GB has a multi-take recording mode and each take from a section can be accessed here.

Here is a more detailed look at the hierarchy that is created:

* `audio` - Contains audio files that were found in the project if the `bExtractAudio` option is enabled.
    * `media` - Audio that was recorded or imported into GB
    * `sampled` - Audio that was sampled into GB
    * `frozen` - Audio that was "frozen" by GB
* `sections` - MIDI from each section.  Sections are output at time position zero so that they can be used as clips in other apps.
    * n folders corresponding to tracks, e.g. `1_MyPiano`
        * `Track-Sxx-SectionName.mid` - Sxx is a unique section number, e.g. `1-S123-TrumpetSection1.mid`.  This is a section from this track.
        * `stems` - folder containing stem representation of sections for this track.  You can normally ignore this folder if the instrument is not percussive.
            * `Track-SStemxxx-SectionName.mid` - This contains a stem representation of the section, e.g. `1-SStem123-DrumMachine.mid`.
            * `takes` - contains stem representation of individual takes for sections that were recorded with multi-take enabled.
                * `Sxxx-SectionName` - folder containing all the takes for instance `Sxxx` of `SectionName`, e.g. `S48-DrumMachine`
                    * `Track-SStemxxx-SectionName-Txx.mid` - This contains a stem representation of a *take* from this section.  `Txx` is the index of the take, e.g. `1-SStem48-DrumMachine-T2`.
        * `filtered` - Contains filtered versions of sections for this track if the `bFilterNotes` option is enabled.
            * `Track-deltas-Sxxx-SectionName-Txx.mid` - This is a file containing three tracks which show the section before the filter, the filtered section, and the delta (i.e. what was filtered).
            * `Track-Sxxx-SectionName-Txx.mid` - Contains the section after being filtered.  This is equivalent to track two of the deltas file.
            * `takes` - contains filtered versions of any takes for this section.
        * `takes` - contains individual takes for sections that were recorded with multi-take enabled.  The hierarchy below this folder is as described earlier.
* `tracks` - Contains each GB track with individual sections rendered to the correct parts of the timeline.
    * n folders corresponding to tracks, e.g. `1_MyPiano`
        * `Track-trackName.mid` - Contains the notes for a track of music from GB.  Sections are added as they appear in GB.  For multi-take sections then the most recent section is chosen when creating the track.  For example, `1-SoloSynth.mid` 
        * `stems` - folder containing stem representation of the track.  You can normally ignore this folder if the instrument is not percussive.  The hierarchy below this folder is as described earlier.
* `song` - Contains a single file named after the project.  This file contains all tracks of music in one file.
* `cutups` - Permutations of each section of takes in each track which are written if the `bEnableCutUp` variable is set.
    * n folders corresponding to tracks, e.g. `1_MyPiano`
        * `Track-CutUp-xxx_a-yyy_b-etc.mid` - A version of the track with one permutation of sections.  There will be n of these files, where n is the product of the total number each takes in each section.  `xxx_a` - `xxx` is the unique section identifier and `a` is the take index.  If, for example, there are three sections containing takes for this track then there will be three of these `xxx_a` parts of the filename, to cover all combinations of multi-take sections.  For example, `1-CutUp-104_1-116_4.mid` - this file represents the track using take 1 of section 104 with take 4 of section 116.

### Audio export
If the `bExtractAudio` option is enabled then the tool will extract the following types of audio:

* Recorded
* Sampled
* Imported
* Frozen

Optionally set `bCompressAudio` to create a zipped version of the audio.

### Filtering
If you use a MIDI guitar interface such as [MIDI Guitar 2](https://www.jamorigin.com/products/midi-guitar-for-ios/) or a MIDI drum-kit then you will be familiar with MIDI "noise" that can be introduced when recording using one of these devices.  Normally this noise manifests itself as very low velocity or duration notes.  To help with this there is a filter option which is enabled using the `bFilterNotes` Boolean.  When this is enabled then the following variables are used to determine whether a note is filtered:

* `velocityMin` - the minimum velocity that a note must be to be kept.
* `velocityMax` - the maximum velocity that a note can be before it is not kept.
* `durationMin` - the minimum duration that a note must be, in milliseconds, in order for it to be kept.

The result of running the filter can be found in the `filtered` directory.  For convenience, a "deltas" file is also created with three tracks:

* A track showing the original notes.
* A track showing the filtered notes.
* A track showing the difference, i.e. what was filtered.

You can use this to fine-tune the filter or manually edit the notes until you are happy.

### Stems
If you prefer to process parts of a drum kit separately, e.g. by adding compression to a kick drum, then you can use the "stems" output which attempts to assign each note to a separate track.

You can modify the `trackLimit` variable if you know how many stems you need.   If `trackLimit` is set too low and there are more notes than stems then they will be added in a round-robin manner and each stem may therefore contain multiple notes.  Splitting notes in this semi-random manner could offer creative options.

Stems are created for all tracks and sections by default but are typically useful for percussive instruments.

#### Note map
When using stems then it can be helpful to have an idea of what instrument each track represents.  If the `bRenameTracks` Boolean is set to `True` then `trackMap` is used to map MIDI notes to an instrument name.  This name is then used to name the track and should help identify the instrument in your sequencer.  You should note that depending on the instrument then the note names may not be correct.  For example, a siren sound in the drum sequencer may be labelled something like a Tom when exported but would make the correct sound if played back in to GB.

NOTE: I have only found a couple of DAW/sequencers that make use of track names - Xequence 2 and MTS Studio.
 
### Cut-Up mode
GB has a great multi-take recording facility for both audio and MIDI input.  This tool will export all of your MIDI takes which you can then sift through at your own leisure.  A further option is "Cut-Up" mode which combines all permutations of MIDI sections as separate tracks.  The idea is that you might discover some great combination of takes.  In practice however the need to audition each track means that it has limited usefulness.

To enable this feature, set the `bEnableCutUp` Boolean to `True`.  For each track in your song the tool will calculate all the possible combinations of takes from each section and will write out that particular combination, plus any static, non-multi-take sections in between.  For example, if you have a track containing sections A, B, C and D and A, C and D are multi-take sections containing two takes each then a file will be written for each combination of the track using every permutation of A, C and D.  In this case there would be 2 x 2 x 2 = 8 combinations of A, C and D (with B being static).

There is a default maximum of 24 combinations of files per track.  This is set to avoid accidentally creating thousands of files.  If you had, for example, a section containing 30 takes and another containing 60 then this would generate 1800 files!  You can modify this limit using the `maxPerms` variable.  Setting it to -1 will disable the limit but you should be cautious about doing this for the reasons mentioned.

## Limitations
The following are known limitations:

### Pitch bends
Pitch bend information is stored as it is found in the GB project file.  This is recorded correctly when the keyboard interface is used to bend the pitch using the pitch wheel.  If however the data was recorded using an on-screen instrument then the pitch information is not scaled to the -8192 +8191 pitch range.  When this exported MIDI data is played back then the pitch bend may be barely perceptible.

There may be scaling information stored with the project but I did not find it.  As a workaround there is a `bOverridePitchBend` Boolean which when set to `True` will use the value of the `pitchBendMultiplier` variable to automatically scale *all* pitch bend values found in that run of the tool.  The default of 24 appears correct for the guitar instrument but may need adjustment for other instruments.

### Automation tracks
The script does not attempt to preserve GB automation tracks.

### On screen controls
Many instruments have buttons which can be depressed or dials which can be turned to change the live sound of the instrument that is playing.  The tool will extract the most common of these (pitch bend, modulation) but most others are ignored.  This means that if you record a piece which requires these interactions then you will lose them on playback.  I have identified a lot of them in the project data but I have not worked out how (or if) it is possible to send them back in to GB.

### Repeated sections
In GB you can repeat a section of MIDI in a track.  The tool does not add these repeats, it will add the section to the track but you will need to use a function like the "duplicate" option in Xequence 2 to manually duplicate sections.

### Modified section lengths
After recording a section, GB allows you to resize it by dragging the start and end of the section to the left or right.  The tool supports the correct rendering of sections that have been dragged from the end of the section but *not* the start.

### MPE support
It has been said that GB records MPE MIDI.  I do not think that the MIDI extracted by this tool includes all of the data required to support MPE.  In particular the MIDIUtil library does not have a way that I have found of recording polyphonic key pressure.

## Playing back MIDI in GB
The easiest way I have found of playing back MIDI into GB after it has been extracted is to use [AudioBus](https://audiob.us) to create a virtual port and then point the MIDI sequencer at that.  If GB is running and the appropriate instrument is open then you should hear the MIDI playing though GB, subject to the restrictions discussed in the Limitations section.

## Testing
I have tested the majority of the GB instruments with this tool and I can get note data from all those tested, subject to the limitations discussed in this document.

The script has not been tested with Mac GB files, although I have no reason to think the format would be different.

Developed and tested on an iPad Air 2020 with iOS 14.4 and latest GB, as of Feb 18th 2020.

## Troubleshooting and further research
If you do hit problems or want to research the file format further then the script has some debug capability.  By default this is turned off but you can enable it by changing the `bDebug` variable to `True`.  This will dump some possibly useful data to the console in Pythonista.  You may also set the `bWriteToFile` variable to `True` in order to write this debug information to a file which will be written to the same working directory as the MIDI files.

Normally, fixing problems will require changing the code to skip unknown or unexpected data.  If you back up your project file and remove all but the track you are interested in then this may improve your chance of success.

If you see a "file missing" type of error then try running the script again as this seems to be a transient Pythonista issue.

## Ideas for future extensions
* Split stems to separate files.
* Create a single file containing all Cut-Ups as one sequence
* Allow more interesting things to happen with takes in Cut-Up mode, e.g. randomly transpose or flip notes horizontal/vertically
* Create a "clip-launch" file which automatically assigns CC or notes to trigger clips so that the end result is as if the file were played on the GB timeline.  The file would contain a track per section that controls when that section is triggered on the timeline.
* Let user choose how to remap GB note values.  For example, remap drum notes as they are written to the MIDI so that they work with a drum kit that expects different note values.  There are already ways of doing this in realtime on iOS, e.g. StreamByter or Mozaic.
* Automatically scale pitch bend based on the instrument.

## Change history
* v2.5 Further enhancements to MIDI extraction including Cut-Up mode, note filters and audio extraction.
* v2.0 Added support for extracting all MIDI
* v1.1 Script can be run outside of Pythonista using Python 3.x (tested with 3.7)
* v1.0 Initial release






