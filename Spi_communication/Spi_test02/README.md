##  SPI Wiring: Raspberry Pi Zero W (Master ↔ Slaves)

The system uses one Raspberry Pi Zero W as the **Master**, and five Raspberry Pi Zero Ws as **Slaves**. Each slave is connected to a Raspberry Pi Camera Module v1.3 and communicates with the master via a **wired SPI bus**. The SPI data lines (MOSI, MISO, SCLK) are shared, but each slave has its own **dedicated Chip Select (CS)** line.

###  Wiring Table

| Signal  | Master Pi GPIO | Header Pin | Slaves (Connection Per Pi)                      |
|---------|----------------|------------|--------------------------------------------------|
| **MOSI** | GPIO 10        | Pin 19     | All slaves: MOSI ←→ GPIO 10 (Pin 19)            |
| **MISO** | GPIO 9         | Pin 21     | All slaves: MISO ←→ GPIO 9 (Pin 21)             |
| **SCLK** | GPIO 11        | Pin 23     | All slaves: SCLK ←→ GPIO 11 (Pin 23)            |
| **CS₁**  | GPIO 8 (CE0)   | Pin 24     | Slave ID 1: CS ←→ GPIO 8 (Pin 24)               |
| **CS₂**  | GPIO 7 (CE1)   | Pin 26     | Slave ID 2: CS ←→ GPIO 7 (Pin 26)               |
| **CS₃**  | GPIO 5         | Pin 29     | Slave ID 3: CS ←→ GPIO 5 (Pin 29)               |
| **CS₄**  | GPIO 6         | Pin 31     | Slave ID 4: CS ←→ GPIO 6 (Pin 31)               |
| **CS₅**  | GPIO 13        | Pin 33     | Slave ID 5: CS ←→ GPIO 13 (Pin 33)              |

> ⚠ **Important**: All devices must share a **common Ground (GND)**. Connect GND of the master to GND of each slave.

---

### Notes

- Only one SPI bus (SPI0) is used on the Pi Zero W.
- CE0 and CE1 (GPIO 8 and 7) are hardware-controlled CS lines.
- GPIO 5, 6, and 13 are **software-controlled CS lines** managed manually via code.
- You must manually assert only one CS line at a time during communication.

