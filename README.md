# Manestrone
Apogee Quartet Control Panel for linux written in python

Heavily based on take_control of stefanocoding, I have written a python program to control
Apogee Quartet, an old but excellent USB Audio Interface.

Unfortunately, I could not manage to control internal mixer enough, but for inputs, outpus
and routing, I am satisfied what I have done.

If you want to use this program, you will need to add a rules file in /etc/udev/rules.d/
which contains following rule.

SUBSYSTEM=="usb", ATTRS{idVendor}=="0c60", ATTRS{idProduct}=="0014", GROUP="plugdev", TAG+="uaccess"

python, wxpython and pyusb are needed for this program to operate. Hope this is helpful for you.
