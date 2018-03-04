# Unistat
This plugin co-opts Indigo thermostat devices as general purpose threshold-response devices.  

Any numerical device state or variable value can be used as input (analogous to temperature), and devices can be switched on/off or action groups executed in response to the input value crossing a high threshold (analogous to cooling) and or low threshold (analogous to heating).

This doesn't do anything that can't be accomplished in Indigo with a combination of triggers and variables, so why bother?  A couple reasons come to mind:
1. It's nice to have all the logic encapsulated in one device vs keeping track of multiple triggers, variables, etc.
2. This is even more true if you want to periodically change thresholds (setpoints) or operation mode based on time of day or house state (e.g. home/away).
3. I already had a system for periodically adjusting my real thermostat like this, so it was convenient to extend that to other sorts of 'stats'.

Example uses†:
* Thermostat
* Humidistat
* Lumistat
* Heliostat
* Anemostat
* Pluviostat
* Acoustistat
* Hydromistat
* Salinistat
* Ampistat
* Chromostat

†Some of these names might be completely fabricated
