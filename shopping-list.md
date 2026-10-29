# Door Lock: Electronics Shopping List

Verification status:
- **Verified** = datasheet found through partfetch.
- **Unverified** = no datasheet found. Check the spec on the seller's page before buying.

Each part has a first choice and a second choice. Use the second choice only if the first is out of stock. Check that the second choice meets the same spec.

## Lock box (outdoor, on the door)

| # | Part | Spec to buy | First choice | Second choice | Status |
|---|---|---|---|---|---|
| 1 | RS-485 transceiver module | **3.3 V supply**, 5 V logic not allowed (ESP32 is 3.3 V) | MAX3485 module (3.3 V) | SP3485 module (3.3 V) | Unverified. The MAX485 is a 5 V part, so do not use it unless you add a level shifter. |
| 2 | Buck converter, 12 V in, 6 V out | **Output 6 V, rated 5 A or more** | Pololu D24V50F6 (6 V, 5 A) | Adjustable XL4016 module, set to 6 V (8 A rated) | Unverified. The LM2596 (TI datasheet found) is rated 3 A, which is too low for the servo's stall current. |
| 3 | Servo | MG996R, about 10 kg·cm | MG996R | DS3218 (20 kg·cm, same size, more torque) | Unverified. Buy one, plus a spare. |
| 4 | Cable gland | PG7, waterproof | PG7 gland | PG9 gland (larger cable size) | Unverified. Check the cable diameter first. |
| 5 | TVS diode, 12 V line | 15 V standoff, SMB package | SMBJ15A | P6KE15A or SMBJ16A | Unverified. Check the standoff voltage on the datasheet. |
| 6 | Fuse holder + fuse | 5 A, on the 12 V line | 5×20 mm panel-mount fuse holder with 5 A glass fuse | Blade-fuse inline holder with 5 A blade fuse | Unverified. |
| 7 | RS-485 termination resistor | 120 Ω, 1/4 W | 120 Ω metal film | Any 120 Ω resistor, 1/4 W or higher | Standard value. |

## Cable run (4 m, lock box to Pi box)

| # | Part | Spec to buy | First choice | Second choice | Status |
|---|---|---|---|---|---|
| 8 | Cable | 4 m. Two twisted pairs: 22 AWG for RS-485 data (A, B), 18 AWG for 12 V and GND. Shielded. | Shielded 4-conductor cable with two twisted pairs (22 AWG + 18 AWG) | Outdoor-rated CAT5e cable (use one pair for A/B, two wires for 12 V/GND) | Unverified. |

## Shared small parts

| # | Part | Spec to buy | First choice | Second choice | Status |
|---|---|---|---|---|---|
| 9 | Terminal blocks | 2-pole and 4-pole, screw type | 5.08 mm screw terminal blocks | Phoenix-style 5.08 mm blocks | Standard. |
| 10 | Ferrules | Crimp ferrules for 18 AWG and 22 AWG | Assorted ferrule kit | Crimp ferrules with a crimping tool | Standard. |

## Already bought

- Pi 4 board
- 12 V power supply (cable run)
- 1000 µF capacitors
- USB-RS485 adapter

## Still needed, not in this list

- ESP32 DevKit (you already have one)
- Pi 4 5 V 3 A USB-C supply
- microSD card for the Pi, 32 GB or more
- Heat-set inserts (M3, M2.5), M3 screws, VHB tape, gasket strip, and PETG or ASA filament for printing

## Notes

- Check the buck converter's output voltage with a multimeter before connecting the servo.
- The fuse and TVS are on the 12 V line at the lock box. The fuse goes first.
- The 120 Ω resistors go at each end of the RS-485 bus only.
- All statuses in this file are unverified except the LM2596 datasheet. I haven't checked stock or prices.
