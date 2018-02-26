#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2016, Perceptive Automation, LLC. All rights reserved.
# http://www.indigodomo.com

import indigo
import time
from ghpu import GitHubPluginUpdater

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

################################################################################
kHvacModeEnumToStrMap = {
    indigo.kHvacMode.Cool               : u"high only",
    indigo.kHvacMode.Heat               : u"low only",
    indigo.kHvacMode.HeatCool           : u"auto high/low",
    indigo.kHvacMode.Off                : u"off",
    indigo.kHvacMode.ProgramHeat        : u"program low",
    indigo.kHvacMode.ProgramCool        : u"program high",
    indigo.kHvacMode.ProgramHeatCool    : u"program auto"
}
def _lookupUiStrFromHvacMode(hvacMode):
    return kHvacModeEnumToStrMap.get(hvacMode, u"unknown")

k_updateCheckHours = 24

################################################################################
class Plugin(indigo.PluginBase):

    #-------------------------------------------------------------------------------
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        self.updater = GitHubPluginUpdater(self)

    #-------------------------------------------------------------------------------
    # Start, Stop and Config changes
    #-------------------------------------------------------------------------------
    def startup(self):
        self.nextCheck = self.pluginPrefs.get('nextUpdateCheck',0)
        self.debug = self.pluginPrefs.get("showDebugInfo",False)
        self.logger.debug("startup")
        if self.debug:
            self.logger.debug("Debug logging enabled")
        self.deviceDict = dict()

        indigo.devices.subscribeToChanges()
        indigo.variables.subscribeToChanges()

    #-------------------------------------------------------------------------------
    def shutdown(self):
        self.logger.debug("shutdown")
        self.pluginPrefs['nextUpdateCheck'] = self.nextCheck
        self.pluginPrefs["showDebugInfo"] = self.debug

    #-------------------------------------------------------------------------------
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.logger.debug("closedPrefsConfigUi")
        if not userCancelled:
            self.debug = valuesDict.get("showDebugInfo",False)
            if self.debug:
                self.logger.debug("Debug logging enabled")

    #-------------------------------------------------------------------------------
    def runConcurrentThread(self):
        try:
            while True:
                if time.time() > self.nextCheck:
                    self.checkForUpdates()
                self.sleep(600)
        except self.StopThread:
            pass

    #-------------------------------------------------------------------------------
    # Device Methods
    #-------------------------------------------------------------------------------
    def deviceStartComm(self, dev):
        self.logger.debug("deviceStartComm: {}".format(dev.name))
        if dev.configured:
            if dev.deviceTypeId == 'DeviceUnistat':
                self.deviceDict[dev.id] = DeviceUnistat(dev, self.logger)
            elif dev.deviceTypeId == 'ActionGroupUnistat':
                self.deviceDict[dev.id] = ActionGroupUnistat(dev, self.logger)

    #-------------------------------------------------------------------------------
    def deviceStopComm(self, dev):
        self.logger.debug("deviceStopComm: {}".format(dev.name))
        if dev.id in self.deviceDict:
            del self.deviceDict[dev.id]

    #-------------------------------------------------------------------------------
    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        errorsDict = indigo.Dict()

        # validate input
        if valuesDict.get('inputType','dev') == 'dev':
            if not valuesDict.get('inputDevice',0):
                errorsDict['inputDevice'] = "Required"
            else:
                if not valuesDict.get('inputState',''):
                    errorsDict['inputState'] = "Required"
                else:
                    testStateValue = indigo.devices[int(valuesDict['inputDevice'])].states[valuesDict['inputState']]
                    try: num = float(testStateValue)
                    except: errorsDict['inputState'] = "Must be a numerical state"

        elif valuesDict.get('inputType','dev') == 'var':
            if not valuesDict.get('inputVariable',0):
                errorsDict['inputVariable'] = "Required"
            else:
                testStateValue = indigo.variables[int(valuesDict['inputVariable'])].value
                try: num = float(testStateValue)
                except: errorsDict['inputVariable'] = "Must have a numerical value"

        try:
            if float(valuesDict['deadband']) < 0.0:
                raise
        except:
            errorsDict['deadband'] = "Must be a number 0 or greater"

        try:
            if int(valuesDict['inputDecimals']) < 0:
                raise
        except:
            errorsDict['inputDecimals'] = "Must be an integer 0 or greater"

        # validate device unistat
        if typeId == 'DeviceUnistat':
            try:
                if int(valuesDict['dimmerControlLevel']) <= 0:
                    raise
            except:
                errorsDict['dimmerControlLevel'] = "Must be a positive integer"


        if len(errorsDict) > 0:
            self.logger.debug('validate device config error: \n{}'.format(errorsDict))
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)

    #-------------------------------------------------------------------------------
    # Device Config callbacks
    #-------------------------------------------------------------------------------
    def getInputDeviceList(self, filter='', valuesDict=dict(), typeId='', targetId=0):
        devList = list()
        for dev in indigo.devices.iter():
            if not dev.id == targetId:
                devList.append((dev.id, dev.name))
        return devList

    #-------------------------------------------------------------------------------
    def getDeviceStateList(self, filter=None, valuesDict=dict(), typeId='', targetId=0):
        stateList = list()
        devId = zint(valuesDict.get(filter,0))
        if devId:
            for state in indigo.devices[devId].states:
                stateList.append((state,state))
        return stateList

    #-------------------------------------------------------------------------------
    def getActionGroups(self, filter=None, valuesDict=dict(), typeId='', targetId=0):
        actionList = list()
        for action in indigo.actionGroups.iter():
            actionList.append((action.id, action.name))
        actionList.append((0,'-- None --'))
        return actionList

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
            self.logger.debug('"{}" {} action not available'.format(dev.name, unicode(action.thermostatAction)))

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
            self.logger.debug('"{}" {} action not available'.format(dev.name, unicode(action.thermostatAction)))


    #-------------------------------------------------------------------------------
    # Menu Methods
    #-------------------------------------------------------------------------------
    def checkForUpdates(self):
        try:
            self.updater.checkForUpdate()
        except Exception as e:
            msg = 'Check for update error.  Next attempt in {} hours.'.format(k_updateCheckHours)
            if self.debug:
                self.logger.exception(msg)
            else:
                self.logger.error(msg)
                self.logger.debug(e)
        self.nextCheck = time.time() + k_updateCheckHours*60*60

    #-------------------------------------------------------------------------------
    def updatePlugin(self):
        self.updater.update()

    #-------------------------------------------------------------------------------
    def forceUpdate(self):
        self.updater.update(currentVersion='0.0.0')

    #-------------------------------------------------------------------------------
    def toggleDebug(self):
        if self.debug:
            self.logger.debug("Debug logging disabled")
            self.debug = False
        else:
            self.debug = True
            self.logger.debug("Debug logging enabled")

    #-------------------------------------------------------------------------------
    # subscribed changes
    #-------------------------------------------------------------------------------
    def deviceUpdated(self, oldDev, newDev):
        if newDev.pluginId == self.pluginId:
            # device belongs to plugin
            indigo.PluginBase.deviceUpdated(self, oldDev, newDev)
            if newDev.id in self.deviceDict:
                self.deviceDict[newDev.id].selfUpdated(newDev)
        else:
            for devId, unistatDevice in self.deviceDict.items():
                unistatDevice.deviceUpdated(oldDev, newDev)

    #-------------------------------------------------------------------------------
    def variableUpdated(self, oldVar, newVar):
        for devId, unistatDevice in self.deviceDict.items():
            unistatDevice.variableUpdated(oldVar, newVar)

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
        instance.replacePluginPropsOnServer(self.props)

        if self.props.get('inputType','dev') == 'dev':
            self.inputDevice = int(self.props['inputDevice'])
            self.inputState = self.props['inputState']
            self.inputVariable = None
        else:
            self.inputDevice = None
            self.inputState = None
            self.inputVariable = int(self.props['inputVariable'])

        self.halfband = float(self.props.get('deadband', 0.0))/2.0
        self.units = self.props.get('inputUnits','')
        self.decimals = int(self.props.get('inputDecimals', 1))

        self.requestTemperature()

    #-------------------------------------------------------------------------------
    def requestTemperature(self):
        if self.props.get('inputType','dev') == 'dev':
            self.temperatureInput = indigo.devices[self.inputDevice].states[self.inputState]
        else:
            self.temperatureInput = indigo.variables[self.inputVariable].value

    #-------------------------------------------------------------------------------
    def selfUpdated(self, newDev):
        self.dev = newDev
        self.evaluateEquipmentState()

    #-------------------------------------------------------------------------------
    def deviceUpdated(self, oldDev, newDev):
        if newDev.id == self.inputDevice:
            self.temperatureInput = newDev.states[self.inputState]

    #-------------------------------------------------------------------------------
    def variableUpdated(self, oldVar, newVar):
        if newVar.id == self.inputVariable:
            self.temperatureInput = newVar.value

    #-------------------------------------------------------------------------------
    def evaluateEquipmentState(self):
        self.logger.debug('"{}" evaluateEquipmentState [temp:{} cool:{} heat:{} mode:{}]'.format(
                self.name, self.temperatureInput, self.setpointCool, self.setpointHeat, self.hvacOperationMode))
        if self.hvacCoolerEnabled:
            if self.temperatureInput > self.setpointCool + self.halfband:
                self.hvacCoolerIsOn = True
            elif self.temperatureInput < self.setpointCool - self.halfband:
                self.hvacCoolerIsOn = False
        else:
            self.hvacCoolerIsOn = False

        if self.hvacHeaterEnabled:
            if self.temperatureInput < self.setpointHeat - self.halfband:
                self.hvacHeaterIsOn = True
            elif self.temperatureInput > self.setpointHeat + self.halfband:
                self.hvacHeaterIsOn = False
        else:
            self.hvacHeaterIsOn = False

    #-------------------------------------------------------------------------------
    # properties
    #-------------------------------------------------------------------------------
    def _temperatureInputGet(self):
        return self.dev.states['temperatureInput1']
    def _temperatureInputSet(self, temp):
        try:
            self.dev.updateStateOnServer('temperatureInput1', float(temp), uiValue=u'{:.{}f}{}'.format(float(temp),self.decimals,self.units))
        except ValueError:
            self.logger.error('"{}" received invalid input "{}" ({})'.format(self.name, temp, type(temp)))
    temperatureInput = property(_temperatureInputGet,_temperatureInputSet)

    #-------------------------------------------------------------------------------
    def _hvacOperationModeGet(self):
        return self.dev.states['hvacOperationMode']
    def _hvacOperationModeSet(self, mode):
        if mode != self.hvacOperationMode:
            self.dev.updateStateOnServer('hvacOperationMode', mode, uiValue=_lookupUiStrFromHvacMode(mode))
            self.logger.info('"{}" set mode to {}'.format(self.name, _lookupUiStrFromHvacMode(mode)))
    hvacOperationMode = property(_hvacOperationModeGet,_hvacOperationModeSet)

    #-------------------------------------------------------------------------------
    def _setpointCoolGet(self):
        if self.props['SupportsCoolSetpoint']:
            return self.dev.states['setpointCool']
        else:
            return 0.0
    def _setpointCoolSet(self, setpoint):
        if setpoint != self.setpointCool:
            self.dev.updateStateOnServer('setpointCool', setpoint, uiValue=u'{:.{}f}{}'.format(float(setpoint),self.decimals,self.units))
            self.logger.info('"{}" set high setpoint to {}'.format(self.name, setpoint))
    setpointCool = property(_setpointCoolGet,_setpointCoolSet)

    #-------------------------------------------------------------------------------
    def _setpointHeatGet(self):
        if self.props['SupportsHeatSetpoint']:
            return self.dev.states['setpointHeat']
        else:
            return 0.0
    def _setpointHeatSet(self, setpoint):
        if setpoint != self.setpointHeat:
            self.dev.updateStateOnServer('setpointHeat', setpoint, uiValue=u'{:.{}f}{}'.format(float(setpoint),self.decimals,self.units))
            self.logger.info('"{}" set low setpoint to {}'.format(self.name, setpoint))
    setpointHeat = property(_setpointHeatGet,_setpointHeatSet)

    #-------------------------------------------------------------------------------
    def _hvacCoolerIsOnGet(self):
        return self.dev.states['hvacCoolerIsOn']
    def _hvacCoolerIsOnSet(self, onState):
        if onState != self.hvacCoolerIsOn:
            self.dev.updateStateOnServer('hvacCoolerIsOn', onState)
            self.logger.info('"{}" set high equipment to {}'.format(self.name, ['off','on'][onState]))
            self.setCoolerEquipmentState(onState)
    hvacCoolerIsOn = property(_hvacCoolerIsOnGet,_hvacCoolerIsOnSet)

    #-------------------------------------------------------------------------------
    def _hvacHeaterIsOnGet(self):
        return self.dev.states['hvacHeaterIsOn']
    def _hvacHeaterIsOnSet(self, onState):
        if onState != self.hvacHeaterIsOn:
            self.dev.updateStateOnServer('hvacHeaterIsOn', onState)
            self.logger.info('"{}" set low equipment to {}'.format(self.name, ['off','on'][onState]))
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
        self.speedControlLevel = int(self.props.get('speedControlLevel', 3))
        self.dimmerControlLevel = int(self.props.get('dimmerControlLevel', 100))

        self.coolDevices = list()
        for devId in self.props.get('coolDevices',[]):
            self.coolDevices.append(indigo.devices[int(devId)])

        self.heatDevices = list()
        for devId in self.props.get('heatDevices',[]):
            self.heatDevices.append(indigo.devices[int(devId)])


    #-------------------------------------------------------------------------------
    def setCoolerEquipmentState(self, onState):
        self._setEquipmentState(self.coolDevices, onState)

    #-------------------------------------------------------------------------------
    def setHeaterEquipmentState(self, onState):
        self._setEquipmentState(self.heatDevices, onState)

    #-------------------------------------------------------------------------------
    def _setEquipmentState(self, deviceList, onState):
        if self.reverseMode: onState = not onState

        if onState:
            speedlevel = self.speedControlLevel
            dimmerlevel = self.dimmerControlLevel
            relayfunction = indigo.device.turnOn
        else:
            speedlevel = 0
            dimmerlevel = 0
            relayfunction = indigo.device.turnOff

        for device in deviceList:
            if isinstance(device, indigo.SpeedControlDevice):
                indigo.speedcontrol.setSpeedLevel(device, speedlevel)
            elif isinstance(device, indigo.DimmerDevice):
                indigo.dimmer.setBrightness(device, dimmerlevel)
            else:
                relayfunction(device)

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
            indigo.actionGroup.execute(actionId)

################################################################################
# Utilities
################################################################################
def zint(value):
    try: return int(value)
    except: return 0
