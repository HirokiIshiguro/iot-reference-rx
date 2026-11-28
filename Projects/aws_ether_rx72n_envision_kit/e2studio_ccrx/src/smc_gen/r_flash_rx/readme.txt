PLEASE REFER TO THE APPLICATION NOTE FOR THIS MODULE FOR MORE INFORMATION

r_flash_rx
=================

Document Number 
---------------
r01an2184ej0531
r01an2184jj0531


Version
-------
v5.31


Overview
--------
A simple Application Program Interface (API) has been created to allow users of
flash based RX700, RX600, RX200 and RX100 Series devices to easily integrate 
reprogramming abilities into their applications using User Mode programming. 
User Mode programming is the term used to describe a Renesas MCU's ability to 
reprogram its own internal flash memory while running in its normal operational 
mode. 


Features
--------
* Data Flash and ROM Erase
* Data Flash and ROM Blank Check
* Data Flash and ROM Write
* Supports background operations (BGO) on ROM and data flash.
* ROM Area Protection support
* ROM Start-Up Program Protection support
* ROM Cache
etc.


Supported MCUs
--------------
* RX110 Group
* RX111 Group
* RX113 Group
* RX130 Group
* RX13T Group
* RX140 Group
* RX14T Group
* RX230 Group
* RX231 Group
* RX23E-A Group
* RX23E-B Group
* RX23T Group
* RX23W Group
* RX24T Group
* RX24U Group
* RX260, RX261 Group
* RX26T Group
* RX64M Group
* RX651, RX65N Group
* RX660 Group
* RX66N Group
* RX66T Group
* RX671 Group
* RX71M Group
* RX72M Group
* RX72N Group
* RX72T Group


Limitations
-----------
* This code is not re-entrant and protects against multiple concurrent function calls.
* During ROM operations neither ROM nor dataflash (DF) can be accessed. 
  If using ROM with BGO, then make sure the code runs from RAM.
* During DF operations, the DF cannot be accessed but ROM can be accessed normally.


Required Packages
-----------------
* r_bsp      V7.70


Toolchain(s) Used
-----------------
* Renesas RXC 3.07.00
* GNU GNURX 14.2.0.202511
* IAR ICCRX 5.20.01


File Structure
--------------
r_flash_rx
|   +-- readme.txt
|   +-- r_flash_rx_if.h
|
+---doc
|   +-- en
|   |   +-- r01an2184ej0531-rx-flash.pdf
|   +-- ja
|       +-- r01an2184jj0531-rx-flash.pdf
|
+---src
    +-- r_flash_rx.c
    +-- r_flash_rx.h
    +-- r_flash_group.c
    +-- r_flash_group.h
    +-- r_flash_fcu.c
    +-- r_flash_fcu.h
    +-- r_flash_nofcu.c
    +-- r_flash_nofcu.h
    +-- r_flash_targets.h
    |
    +-- flash_type_1
        |
        +-- r_flash_type1.c
        +-- r_flash_type1_if.h
    |
    +-- flash_type_3
        |
        +--r_flash_type3.c
        +--r_flash_type3_if.h
    |
    +-- flash_type_4
        |
        +--r_flash_type4.c
        +--r_flash_type4_if.h
    |
    +-- flash_type_5
        |
        +--r_flash_type5.c
        +--r_flash_type5_if.h
    |
    +-- targets
        |
        +--rx110
             +-- r_flash_rx110.h
        |
        +--rx111
             +-- r_flash_rx111.h
        |
        +--rx113
             +-- r_flash_rx113.h
        |
        +--rx130
             +-- r_flash_rx130.h
        |
        +--rx13t
             +-- r_flash_rx13t.h
        |
        +--rx140
             +-- r_flash_rx140.h
        |
        +--rx14t
             +-- r_flash_rx14t.h
        |
        +--rx231
             +-- r_flash_rx231.h
        |
        +--rx23e-a
             +-- r_flash_rx23e-a.h
        |
        +--rx23e-b
             +-- r_flash_rx23e-b.h
        |
        +--rx23t
             +-- r_flash_rx23t.h
        |
        +--rx23w
             +-- r_flash_rx23w.h
        |
        +--rx24t
             +-- r_flash_rx24t.h
        |
        +--rx24u
             +-- r_flash_rx24u.h
        |
        +--rx260
             +-- r_flash_rx260.h
        |
        +--rx261
             +-- r_flash_rx261.h
        |
        +--rx26t
             +-- r_flash_rx26t.h
        |
        +--rx64m
             +-- r_flash_rx64m.h
        |
        +--rx65n
             +-- r_flash_rx65n.h
        |
        +--rx660
             +-- r_flash_rx660.h
        |
        +--rx66n
             +-- r_flash_rx66n.h
        |
        +--rx66t
             +-- r_flash_rx66t.h
        |
        +--rx671
             +-- r_flash_rx671.h
        |
        +--rx71m
             +-- r_flash_rx71m.h
        |    
        +--rx72m
             +-- r_flash_rx72m.h
        |    
        +--rx72n
             +-- r_flash_rx72n.h
        |    
        +--rx72t
             +-- r_flash_rx72t.h

r_config
    r_flash_rx_config.h

