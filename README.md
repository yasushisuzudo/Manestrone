# Manestrone
Apogee Quartet Control Panel for linux written in python

Heavily based on take_control of stefanocoding, I have written a python program to control
Apogee Quartet, an old but excellent USB Audio Interface.

As of "03", mixer works.

If you want to use this program as a non-root user, you will need to add a rules file in /etc/udev/rules.d/
which contains following rule.

SUBSYSTEM=="usb", ATTRS{idVendor}=="0c60", ATTRS{idProduct}=="0014", GROUP="plugdev", TAG+="uaccess"

python, wxpython and pyusb are needed for this program to operate. Hope this is helpful for you.
