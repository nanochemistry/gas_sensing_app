# Gas Sensing Setup 2026.1

## Hardware
### USB ports
#### Windows

#### MacOS
    ls /dev/cu.usb*
- provides listing of all connected devices
- map all devides in config.yaml

#### Linux

### Sample heater

### Gas composition controller
Mass Flow Controllers (MFCs) are used to controll the 4 independent gas flows.

| ID    | Range /sccm | Usage         |
| ----- | ----------- | ------------- |
| MFC 1 | 1000        | Syn. air, dry (reference gas)|
| MFC 2 | 1000        | Syn. air, wet (reference gas)|
| MFC 3 | 200         | Analyte gas 1 |
| MFC 4 | 200         | Analyte gas 2 |

- by combining the different gas flows different analyte gas concentrations can be realized
- maintain a constant gas flow throughout the experiment. Variations can cause temperature fluctuations
- 

### Sample Illumination
A simple shutter is used to enable or block the illumination of the sample.

### Electrical resistance

## Software
### files & folders

#### data
storeage folder for measurement data

#### drivers
folder for all device drivers

#### recipes
folder for all recipe files for automated experiment

#### manual.md
documentation; this file

#### main.py
main program file

#### config.yaml
system configuration file
- USB Ports
- Gas information
- Folder paths
  - data
  - recipes