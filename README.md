# Gas Sensing App
The Gas Sensing App is a GUI to control the gas sensing experiment at the Chair of Inorganic and Materials Chemistry at the University of Cologne, Germany (https://nanochemistry.uni-koeln.de)

This GUI was created using Google Gemini 3.5 Flash.

## Hardware components
### Mass flow controllers (MFC)
Aera MFC controllers

Mass Flow Controllers (MFCs) are used to control 4 independent gas flows.

| MFC    | max. Flow rate /sccm | Usage         |
| ----- | ----------- | ------------- |
|  1 | 1000        | Syn. air, dry (reference gas)|
|  2 | 1000        | Syn. air, wet (reference gas)|
|  3 | 200         | Analyte gas 1 |
|  4 | 200         | Analyte gas 2 |

- By varying relative reference gas flows (dry/wet) target humidity can be realized.
- By varying relative gas flows (analyte/reference) target analyte gas concentrations can be realized depending on the initial gas cylinder base concentrations.
- A constant gas flow (e.g. 200 sccm) throughout the experiment should be maintained to ensure stable conditions.
- Minimal gas flow is ~10% of maximal MFC range. 

### Source Measure Unit (SMU)
Keithley 2400
- 2- and 4-wire measurements
- Resistance measurement
- Current-Voltage curves 

### Multimeter
Keithley 2800
- 2- and 4-wire measurements
- Resistance measurement up to 16 channels in sequence

### Shutter
A simple shutter is used to enable or block the illumination of the sample.

## Software manual

### Start GUI
Start the GUI by typing the followig commands, which can also be combined in a bat/bash file:

```console
cd gas-sensing-app/
conda activate gas-sensing-env
sensing-app
```

### Update App
To update the program, pull the most recent files from the git repository usig the following commands:

```console
cd gas-sensing-app/
conda activate gas-sensing-env
git pull
```
### Automatic operation


### Manual operation



## Installation
### Python environment
Install miniconda: https://www.anaconda.com/docs/getting-started/miniconda/main
### GIT
Install git in your base python environment
```console
conda install -c anaconda git
```
### Download program files
Download the most recent program version from the git repository
```console
cd ~/Documents
git clone https://github.com/nanochemistry/gas-sensing-app.git
cd gas-sensing-app
```
### Add folders in gas-sensing-app
- add folder **data** for measurement data 
- add folder **logs**
- add folder **recipes**

### Create and activate the Python environment
```console
conda env create -f environment.yml
conda activate gas-sensing-env
```
### Register packages
```console
pip install -e .
```
### Identify hardware adresses
The script **find_ports.py** lists all available hardware adresses to be added in **config.yaml**
```console
cd gas-sensing-app/tools/
python find_ports.py
```
### Create configuration file
Rename **config.template.yaml** to **config.yaml** and add the hardware addresses obtained from **find_ports.py**.


## App file structure
```block
gas-sensing-app/
├── bundle.py
├── config.template.yaml
├── config.yaml
├── data
├── dummy_recipe.yaml
├── environment.yml
├── logs
├── main.py
├── pyproject.toml
├── README.md
├── recipes
├── repo_dump.txt
├── src
│   ├── gas_sensing_app
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── assets
│   │   │   ├── icon.svg
│   │   │   └── sensor_icon.png
│   │   ├── core
│   │   │   ├── __init__.py
│   │   │   ├── logger.py
│   │   │   └── worker.py
│   │   ├── gui
│   │   │   ├── __init__py
│   │   │   └── dashboard.py
│   │   └── hardware
│   │       ├── __init__.py
│   │       ├── aera_mfc.py
│   │       ├── keithley_2400.py
│   │       ├── mock_drivers.py
│   │       └── shutter.py
├── tests
└── tools
    └── find_ports.py
```

### gas-sensing-app/
| File    | Function | 
| ----- | ----------- | 
| bundle.py | Creates a plain text file **repo_dump.txt** including all relevant files and folders to be used in LLMs for further assistance, extention and updates.        | 
|  config.template.yaml | template for  **config.yaml**      | 
|  config.yaml | Main configuration file          | 
| data | Folder, where all measurement data is stored in csv format; path and file prefix can be changes in config.yaml  | 
| dummy_recipe.yaml | Template for a reciepe file for automated measurements  | 
| environment.yml | Configuration for setting up the Miniconda Python environment | 
| logs | Folder, where all log files are stored; creation of log files can be toggled in **config.yaml** | 
| main.py | script to start the main program using "python main.py" | 
| pyproject.toml | configuration file or library handling | 
| README.md | This file | 
| recipes | Folder to store the recipe files | 
| repo_dump.txt | Plain text file created by **bundle.py**  | 
| tests |   | 
| tools | folder for support programs  | 


### gas-sensing-app/src/gas_sensing_app
| File    | Function | 
| ----- | ----------- | 
| \_\_init\_\_.py | Main app folder  | 
| \_\_main\_\_.py | Main app folder  | 
| assets | Folder for program images  | 
| core | Folder for main scripts  | 
| gui | Folder for GUI scripts  | 
| hardware | Folder for hardware drivers  |

### assets
| File    | Function | 
| ----- | ----------- | 
| icon.svg | Editable program icon in svg format |
| sensor_icon.png | Program icon in png format referenced in code | 

### core
| File    | Function | 
| ----- | ----------- | 
| \_\_init\_\_.py| This file |
| logger.py | Script to write data and log files | 
| worker.py | Main script | 
 
 ### gui
 | File    | Function | 
| ----- | ----------- | 
| \_\_init\_\_.py|  |
| dashboard.py | Script to render GUI | 

 ### hardware
 | File    | Function | 
| ----- | ----------- | 
| \_\_init\_\_.py|  |
| aera_mfc.py | Driver for the MFCs | 
| keithley_2400.py | Driver for Keithley 2400 SMU| 
| mock_drivers.py | Mock drivers to simulate hardware for testing; usage can be toggled in **config.yaml** | 
| shutter.py | Driver for the shutter control | 