#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2016, Perceptive Automation, LLC. All rights reserved.
# http://www.indigodomo.com

import indigo #noqa
import time

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

################################################################################
# Globals

################################################################################
class Plugin(indigo.PluginBase):

    #-------------------------------------------------------------------------------
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

    #-------------------------------------------------------------------------------
    # Start, Stop and Config changes
    #-------------------------------------------------------------------------------
    def startup(self):
        self.debug = self.pluginPrefs.get("showDebugInfo",False)
        self.logger.debug(u"startup")
        if self.debug:
            self.logger.debug(u"Debug logging enabled")
        self.deviceDict = dict()

        indigo.devices.subscribeToChanges()
        indigo.variables.subscribeToChanges()

    #-------------------------------------------------------------------------------
    def shutdown(self):
        self.logger.debug(u"shutdown")
        self.pluginPrefs['showDebugInfo'] = self.debug

    #-------------------------------------------------------------------------------
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.logger.debug(u"closedPrefsConfigUi")
        if not userCancelled:
            self.debug = valuesDict.get('showDebugInfo',False)
            if self.debug:
                self.logger.debug(u"Debug logging enabled")

    #-------------------------------------------------------------------------------
    # Device Methods
    #-------------------------------------------------------------------------------
    def deviceStartComm(self, dev):
        self.logger.debug(u"deviceStartComm: {}".format(dev.name))
        if dev.configured:
            if dev.deviceTypeId == 'DeviceUnistat':
                self.deviceDict[dev.id] = DeviceUnistat(dev, self.logger)
            elif dev.deviceTypeId == 'ActionGroupUnistat':
                self.deviceDict[dev.id] = ActionGroupUnistat(dev, self.logger)

    #-------------------------------------------------------------------------------
    def deviceStopComm(self, dev):
        self.logger.debug(u"deviceStopComm: {}".format(dev.name))
        if dev.id in self.deviceDict:
            del self.deviceDict[dev.id]

    #-------------------------------------------------------------------------------
    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        errorsDict = indigo.Dict()

        # validate input
        if valuesDict.get('inputType','dev') == 'dev':
            if valuesDict.get('inputDevice',0):
                if valuesDict.get('inputState',''):
                    testStateValue = indigo.devices[int(valuesDict['inputDevice'])].states[valuesDict['inputState']]
                    if not validateTextFieldNumber(testStateValue, numType=float, zero=True, negative=True):
                        errorsDict['inputState'] = "Must be a numerical state"
                else:
                    errorsDict['inputState'] = "Required"
            else:
                errorsDict['inputDevice'] = "Required"

        elif valuesDict.get('inputType','dev') == 'var':
            if valuesDict.get('inputVariable',0):
                testStateValue = indigo.variables[int(valuesDict['inputVariable'])].value
                if not validateTextFieldNumber(testStateValue, numType=float, zero=True, negative=True):
                    errorsDict['inputVariable'] = "Must have a numerical value"
            else:
                errorsDict['inputVariable'] = "Required"

        if not validateTextFieldNumber(valuesDict['deadband'], numType=float, zero=True, negative=False):
            errorsDict['deadband'] = "Must be a number 0 or greater"

        if not validateTextFieldNumber(valuesDict['inputDecimals'], numType=int, zero=True, negative=False):
            errorsDict['inputDecimals'] = "Must be an integer 0 or greater"

        # validate device unistat
        if typeId == 'DeviceUnistat':
            if not validateTextFieldNumber(valuesDict['dimmerControlLevel'], numType=int, zero=False, negative=False):
                errorsDict['dimmerControlLevel'] = "Must be a positive integer"


        if len(errorsDict) > 0:
            self.logger.debug(u"validate device config error: \n{}".format(errorsDict))
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)

    #-------------------------------------------------------------------------------
    # Device Config callbacks
    #-------------------------------------------------------------------------------
    def getInputDeviceList(self, filter='', valuesDict=dict(), typeId='', targetId=0):
        return [(dev.id, dev.name) for dev in indigo.devices.iter() if (dev.id != targetId)]

    #-------------------------------------------------------------------------------
    def getDeviceStateList(self, filter=None, valuesDict=dict(), typeId='', targetId=0):
        devId = zint(valuesDict.get(filter,0))
        return [(state, state) for state in indigo.devices[devId].states] if devId else []

    #-------------------------------------------------------------------------------
    def getActionGroups(self, filter=None, valuesDict=dict(), typeId='', targetId=0):
        return [(action.id, action.name) for action in indigo.actionGroups.iter()] + [(0,'-- None --')]

    #-------------------------------------------------------------------------------
    def loadStates(self, valuesDict=None, typeId='', targetId=0):
        pass

    #-------------------------------------------------------------------------------
    # Thermostat Action callback
    #-------------------------------------------------------------------------------
    def actionControlThermostat(self, action, dev):
        unistatDevice = self.deviceDict[dev.id]

        ###### SET HVAC MODE ######
        if action.thermostatAction == indigo.kThermostatAction.SetHvacMode:
            unistatDevice.hvacOperationMode = action.actionMode

        ###### SET COOL SETPOINT ######
        elif action.thermostatAction == indigo.kThermostatAction.SetCoolSetpoint:
            unistatDevice.setpointCool = action.actionValue

        ###### SET HEAT SETPOINT ######
        elif action.thermostatAction == indigo.kThermostatAction.SetHeatSetpoint:
            unistatDevice.setpointHeat = action.actionValue

        ###### DECREASE/INCREASE COOL SETPOINT ######
        elif action.thermostatAction == indigo.kThermostatAction.DecreaseCoolSetpoint:
            unistatDevice.setpointCool = unistatDevice.setpointCool - action.actionValue

        elif action.thermostatAction == indigo.kThermostatAction.IncreaseCoolSetpoint:
            unistatDevice.setpointCool = unistatDevice.setpointCool + action.actionValue

        ###### DECREASE/INCREASE HEAT SETPOINT ######
        elif action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint:
            unistatDevice.setpointHeat = unistatDevice.setpointHeat - action.actionValue

        elif action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint:
            unistatDevice.setpointHeat = unistatDevice.setpointHeat + action.actionValue

        ###### REQUEST STATE UPDATES ######
        elif action.thermostatAction == indigo.kThermostatAction.RequestTemperatures:
            unistatDevice.requestTemperature()

        ###### OTHER ACTIONS ######
        else:
            self.logger.debug(f'"{dev.name}" {action.thermostatAction} action not available')

    #-------------------------------------------------------------------------------
    # General Action callback
    #-------------------------------------------------------------------------------
    def actionControlUniversal(self, action, dev):
        unistatDevice = self.deviceDict[dev.id]

        ###### STATUS REQUEST ######
        if action.deviceAction == indigo.kUniversalAction.RequestStatus:
            unistatDevice.requestTemperature()

        ###### OTHER ACTIONS ######
        else:
            self.logger.debug(f'"{dev.name}" {action.deviceAction} action not available')


    #-------------------------------------------------------------------------------
    # Menu Methods
    #-------------------------------------------------------------------------------
    def toggleDebug(self):
        if self.debug:
            self.logger.debug(u"Debug logging disabled")
            self.debug = False
        else:
            self.debug = True
            self.logger.debug(u"Debug logging enabled")

    #-------------------------------------------------------------------------------
    # subscribed changes
    #-------------------------------------------------------------------------------
    def deviceUpdated(self, oldDev, newDev):
        if newDev.pluginId == self.pluginId:
            # device belongs to plugin
            indigo.PluginBase.deviceUpdated(self, oldDev, newDev)
            if newDev.id in self.deviceDict:
                self.deviceDict[newDev.id].selfDeviceUpdated(newDev)
        else:
            for devId, unistatDevice in self.deviceDict.items():
                unistatDevice.inputDeviceUpdated(newDev)

    #-------------------------------------------------------------------------------
    def variableUpdated(self, oldVar, newVar):
        for devId, unistatDevice in self.deviceDict.items():
            unistatDevice.inputVariableUpdated(newVar)

###############################################################################
# Classes
###############################################################################
class UnistatBase(object):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, logger):
        self.logger = logger

        self.dev = instance

        self.props = instance.pluginProps
        self.props['SupportsHvacOperationMode'] = True
        self.props['SupportsHvacFanMode'] = False
        self.props['ShowCoolHeatEquipmentStateUI'] = True
        self.props['NumTemperatureInputs'] = 1
        self.props['NumHumidityInputs'] = 0
        if self.props != instance.pluginProps:
            instance.replacePluginPropsOnServer(self.props)

        if self.props.get('inputType','dev') == 'dev':
            self.inputDeviceId = int(self.props['inputDevice'])
            self.inputStateKey = self.props['inputState']
            self.inputVariableId = None
        elif self.props.get('inputType','dev') == 'var':
            self.inputDeviceId = None
            self.inputStateKey = None
            self.inputVariableId = int(self.props['inputVariable'])
        else:
            self.logger.error(f'"{self.name}" input init failed')
            raise

        self.halfband = float(self.props.get('deadband', 1.0))/2.0
        self.units = self.props.get('inputUnits','')
        self.decimals = int(self.props.get('inputDecimals', 1))

        self.modeNameMap = {
            indigo.kHvacMode.Off        : self.props.get('modeNameOff',  'Off' ),
            indigo.kHvacMode.Heat       : self.props.get('modeNameHeat', 'Heat'),
            indigo.kHvacMode.Cool       : self.props.get('modeNameCool', 'Cool'),
            indigo.kHvacMode.HeatCool   : self.props.get('modeNameAuto', 'Auto'),
            }

        self.requestTemperature()

    #-------------------------------------------------------------------------------
    def requestTemperature(self):
        if self.inputDeviceId:
            try:
                self.temperatureInput = indigo.devices[self.inputDeviceId].states[self.inputStateKey]
            except KeyError:
                self.logger.error(f'Input device {self.inputDeviceId} does not exist.  Reconfigure "{self.name}".')
        elif self.inputVariableId:
            try:
                self.temperatureInput = indigo.variables[self.inputVariableId].value
            except KeyError:
                self.logger.error(f'Input variable {self.inputVariableId} does not exist.  Reconfigure "{self.name}".')

    #-------------------------------------------------------------------------------
    def selfDeviceUpdated(self, newDev):
        self.dev = newDev
        self.logger.debug(f'"{self.name}" evaluate equipment state [in:{self.temperatureInput} hi:{self.setpointCool}, lo:{self.setpointHeat}, hb:{self.halfband}]')

        # evaluate cool equipment state
        if self.hvacCoolerEnabled:
            if self.temperatureInput > self.setpointCool + self.halfband:
                self.hvacCoolerIsOn = True
            elif self.temperatureInput <= self.setpointCool - self.halfband:
                self.hvacCoolerIsOn = False
        else:
            self.hvacCoolerIsOn = False

        # evaluate heat equipment state
        if self.hvacHeaterEnabled:
            if self.temperatureInput < self.setpointHeat - self.halfband:
                self.hvacHeaterIsOn = True
            elif self.temperatureInput >= self.setpointHeat + self.halfband:
                self.hvacHeaterIsOn = False
        else:
            self.hvacHeaterIsOn = False

    #-------------------------------------------------------------------------------
    def inputDeviceUpdated(self, newDev):
        if newDev.id == self.inputDeviceId:
            self.temperatureInput = newDev.states[self.inputStateKey]

    #-------------------------------------------------------------------------------
    def inputVariableUpdated(self, newVar):
        if newVar.id == self.inputVariableId:
            self.temperatureInput = newVar.value

    #-------------------------------------------------------------------------------
    def getModeName(self, mode=None):
        if mode is None: mode = self.hvacOperationMode
        return self.modeNameMap.get(mode, 'Unknown')

    #-------------------------------------------------------------------------------
    # properties
    #-------------------------------------------------------------------------------
    def _temperatureInputGet(self):
        return self.dev.states['temperatureInput1']
    def _temperatureInputSet(self, temp):
        if temp != self.temperatureInput:
            try:
                self.dev.updateStateOnServer('temperatureInput1', float(temp), uiValue=f'{float(temp):.{self.decimals}f}{self.units}')
                self.logger.debug(f'"{self.name}" received input {float(temp):.{self.decimals}f}{self.units}')
            except ValueError:
                self.logger.error(f'"{self.name}" received invalid input "{temp}" ({type(temp)})')
    temperatureInput = property(_temperatureInputGet,_temperatureInputSet)

    #-------------------------------------------------------------------------------
    def _hvacOperationModeGet(self):
        return self.dev.states['hvacOperationMode']
    def _hvacOperationModeSet(self, mode):
        if mode in range(4):
            if mode != self.hvacOperationMode:
                self.dev.updateStateOnServer('hvacOperationMode', mode, uiValue=self.getModeName(mode))
                self.logger.info(f'"{self.name}" mode now {self.getModeName(mode)}')
        else:
            self.logger.error(f'"{self.name}" program mode not supported')
    hvacOperationMode = property(_hvacOperationModeGet,_hvacOperationModeSet)

    #-------------------------------------------------------------------------------
    def _setpointCoolGet(self):
        if self.props['SupportsCoolSetpoint']:
            return self.dev.states['setpointCool']
        else:
            return 0.0
    def _setpointCoolSet(self, setpoint):
        if self.props['SupportsCoolSetpoint']:
            if setpoint != self.setpointCool:
                self.dev.updateStateOnServer('setpointCool', setpoint, uiValue=f'{float(setpoint):.{self.decimals}f}{self.units}')
                self.logger.info(f'"{self.name}" {self.getModeName(indigo.kHvacMode.Cool)} setpoint now {setpoint}{self.units}')
        else:
            self.logger.error(f'"{self.name}" {self.getModeName(indigo.kHvacMode.Cool)} setpoint not supported')
    setpointCool = property(_setpointCoolGet,_setpointCoolSet)

    #-------------------------------------------------------------------------------
    def _setpointHeatGet(self):
        if self.props['SupportsHeatSetpoint']:
            return self.dev.states['setpointHeat']
        else:
            return 0.0
    def _setpointHeatSet(self, setpoint):
        if self.props['SupportsHeatSetpoint']:
            if setpoint != self.setpointHeat:
                self.dev.updateStateOnServer('setpointHeat', setpoint, uiValue=f'{float(setpoint):.{self.decimals}f}{self.units}')
                self.logger.info(f'"{self.name}" {self.getModeName(indigo.kHvacMode.Heat)} setpoint now {setpoint}{self.units}')
        else:
            self.logger.error(f'"{self.name}" {self.getModeName(indigo.kHvacMode.Heat)} setpoint not supported')
    setpointHeat = property(_setpointHeatGet,_setpointHeatSet)

    #-------------------------------------------------------------------------------
    def _hvacCoolerIsOnGet(self):
        return self.dev.states['hvacCoolerIsOn']
    def _hvacCoolerIsOnSet(self, onState):
        if onState != self.hvacCoolerIsOn:
            self.dev.updateStateOnServer('hvacCoolerIsOn', onState)
            self.logger.info(f'"{self.name}" {self.getModeName(indigo.kHvacMode.Cool)} equipment now {["off","on"][onState]}')
            self.setCoolerEquipmentState(onState)
    hvacCoolerIsOn = property(_hvacCoolerIsOnGet,_hvacCoolerIsOnSet)

    #-------------------------------------------------------------------------------
    def _hvacHeaterIsOnGet(self):
        return self.dev.states['hvacHeaterIsOn']
    def _hvacHeaterIsOnSet(self, onState):
        if onState != self.hvacHeaterIsOn:
            self.dev.updateStateOnServer('hvacHeaterIsOn', onState)
            self.logger.info(f'"{self.name}" {self.getModeName(indigo.kHvacMode.Cool)} equipment now {["off","on"][onState]}')
            self.setHeaterEquipmentState(onState)
    hvacHeaterIsOn = property(_hvacHeaterIsOnGet,_hvacHeaterIsOnSet)

    #-------------------------------------------------------------------------------
    @property
    def hvacCoolerEnabled(self):
        return (self.props['SupportsCoolSetpoint'] and
               (self.dev.states['hvacOperationModeIsCool'] or self.dev.states['hvacOperationModeIsAuto'])
               )

    #-------------------------------------------------------------------------------
    @property
    def hvacHeaterEnabled(self):
        return (self.props['SupportsHeatSetpoint'] and
               (self.dev.states['hvacOperationModeIsHeat'] or self.dev.states['hvacOperationModeIsAuto'])
               )

    #-------------------------------------------------------------------------------
    @property
    def name(self):
        return self.dev.name

    #-------------------------------------------------------------------------------
    # abstract methods
    #-------------------------------------------------------------------------------
    def setCoolerEquipmentState(self, onState):
        raise NotImplementedError

    #-------------------------------------------------------------------------------
    def setHeaterEquipmentState(self, onState):
        raise NotImplementedError

###############################################################################
class DeviceUnistat(UnistatBase):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, logger):
        super(DeviceUnistat, self).__init__(instance, logger)

        self.reverseMode = self.props.get('deviceControlMode','normal') != 'normal'

        self.coolDeviceIdList = [zint(devId) for devId in self.props.get('coolDevices',[])]
        self.heatDeviceIdList = [zint(devId) for devId in self.props.get('heatDevices',[])]

        self.speedControlIndex    = [0, int(self.props.get('speedControlIndex', 3))]
        self.dimmerControlLevel   = [0, int(self.props.get('dimmerControlLevel', 100))]
        self.relayControlFunction = [indigo.device.turnOff, indigo.device.turnOn]

    #-------------------------------------------------------------------------------
    def setCoolerEquipmentState(self, onState):
        self._setEquipmentState(self.coolDeviceIdList, onState)

    #-------------------------------------------------------------------------------
    def setHeaterEquipmentState(self, onState):
        self._setEquipmentState(self.heatDeviceIdList, onState)

    #-------------------------------------------------------------------------------
    def _setEquipmentState(self, deviceIdList, onState):
        if self.reverseMode: onState = not onState

        for deviceId in deviceIdList:
            try:
                device = indigo.devices[deviceId]
                if isinstance(device, indigo.SpeedControlDevice):
                    indigo.speedcontrol.setSpeedIndex(device, self.speedControlIndex[onState])
                elif isinstance(device, indigo.DimmerDevice):
                    indigo.dimmer.setBrightness(device, self.dimmerControlLevel[onState])
                else:
                    self.relayControlFunction[onState](device)
            except KeyError:
                self.logger.error(f'Device {deviceId} does not exist.  Reconfigure "{self.name}".')

###############################################################################
class ActionGroupUnistat(UnistatBase):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, logger):
        super(ActionGroupUnistat, self).__init__(instance, logger)

        self.coolerOn  = zint(self.props.get('coolerOnActionGroup',0))
        self.coolerOff = zint(self.props.get('coolerOffActionGroup',0))
        self.heaterOn  = zint(self.props.get('heaterOnActionGroup',0))
        self.heaterOff = zint(self.props.get('heaterOffActionGroup',0))

    #-------------------------------------------------------------------------------
    def setCoolerEquipmentState(self, onState):
        if onState:
            self._executeAction(self.coolerOn)
        else:
            self._executeAction(self.coolerOff)

    #-------------------------------------------------------------------------------
    def setHeaterEquipmentState(self, onState):
        if onState:
            self._executeAction(self.heaterOn)
        else:
            self._executeAction(self.heaterOff)

    #-------------------------------------------------------------------------------
    def _executeAction(self, actionId):
        if actionId:
            try:
                indigo.actionGroup.execute(actionId)
            except KeyError:
                self.logger.error(f'Action Group {actionId} does not exist.  Reconfigure device "{self.name}".')


################################################################################
# Utilities
################################################################################
def zint(value):
    try: return int(value)
    except: return 0

def validateTextFieldNumber(rawInput, numType=float, zero=True, negative=True):
    try:
        num = numType(rawInput)
        if not zero:
            if num == 0: raise
        if not negative:
            if num < 0: raise
        return True
    except:
        return False
